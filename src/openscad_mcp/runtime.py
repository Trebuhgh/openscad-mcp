"""OpenSCAD executable discovery and version-dependent capabilities."""

import logging
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .diagnostics import parse_openscad_output
from .utils.config import get_config

logger = logging.getLogger(__name__)

OPENSCAD_NAMES = ["openscad-nightly", "openscad", "OpenSCAD", "openscad.exe"]

OPENSCAD_COMMON_PATHS = [
    "/usr/bin/openscad-nightly",
    "/usr/local/bin/openscad-nightly",
    "/snap/bin/openscad-nightly",
    "/usr/bin/openscad",
    "/usr/local/bin/openscad",
    "/snap/bin/openscad",
    "/var/lib/flatpak/exports/bin/org.openscad.OpenSCAD",
    "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD",
    "/Applications/OpenSCAD-nightly.app/Contents/MacOS/OpenSCAD",
    "C:\\Program Files\\OpenSCAD\\openscad.exe",
    "C:\\Program Files\\OpenSCAD (Nightly)\\openscad.exe",
    "C:\\Program Files (x86)\\OpenSCAD\\openscad.exe",
]

_VERSION_RE = re.compile(r"OpenSCAD version (\S+)")
_openscad_cache: dict[str, str | None] = {}
_capability_cache: dict[str, dict[str, Any]] = {}
_memory_limit_checked: dict[str, bool] = {}


def reset_openscad_cache() -> None:
    """Forget discovered binaries and capability records."""
    _openscad_cache.clear()
    _capability_cache.clear()


def probe_version(path: str) -> str | None:
    """Return the version printed by ``openscad --version``, if executable."""
    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=15,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        return None
    output = f"{result.stdout or ''}\n{result.stderr or ''}"
    match = _VERSION_RE.search(output)
    if match:
        return match.group(1)
    stripped = output.strip()
    return stripped.splitlines()[0] if stripped else None


def version_tuple(version: str | None) -> tuple[int, ...]:
    """Convert an OpenSCAD version string into a sortable integer tuple."""
    if not version:
        return (0,)
    parts: list[int] = []
    for piece in re.split(r"[.\-]", version):
        match = re.match(r"\d+", piece)
        if not match:
            break
        parts.append(int(match.group(0)))
    return tuple(parts) if parts else (0,)


def find_openscad() -> str | None:
    """Locate the newest usable configured, PATH, or fixed-path executable."""
    configured = get_config().openscad_path or ""
    if configured in _openscad_cache:
        return _openscad_cache[configured]

    found: str | None = None
    if configured and Path(configured).exists():
        found = configured
    else:
        probed = [(name, probe_version(name)) for name in OPENSCAD_NAMES]
        probed.extend(
            (path, probe_version(path)) for path in OPENSCAD_COMMON_PATHS if Path(path).exists()
        )
        best: tuple[tuple[int, ...], int, str] | None = None
        for index, (candidate, version) in enumerate(probed):
            if version is None:
                continue
            _capability_cache.setdefault(candidate, {})["version"] = version
            key = (version_tuple(version), -index, candidate)
            if best is None or key[:2] > best[:2]:
                best = key
        if best is not None:
            found = best[2]
        else:
            existing = [candidate for candidate, _ in probed if candidate.startswith(("/", "C:"))]
            found = existing[0] if existing else None

    _openscad_cache[configured] = found
    return found


def get_openscad_capabilities(path: str | None = None) -> dict[str, Any]:
    """Return a memoized version and feature profile for an OpenSCAD binary."""
    if path is None:
        path = find_openscad()
    if not path:
        return {"installed": False}
    cached = _capability_cache.get(path)
    if cached and cached.get("probed"):
        return cached

    version = (cached or {}).get("version") or probe_version(path)
    parsed_version = version_tuple(version)
    is_snapshot = bool(version) and (len(parsed_version) >= 3 or "git" in (version or ""))
    record: dict[str, Any] = {
        "installed": True,
        "path": str(path),
        "version": version,
        "version_tuple": list(parsed_version),
        "is_snapshot": is_snapshot,
        "has_manifold_backend": parsed_version >= (2024, 9),
        "has_summary_json": parsed_version >= (2022,),
        "has_egl_headless": parsed_version >= (2023, 9),
        "amf_export": parsed_version < (2026,),
        "probed": True,
    }
    _capability_cache[path] = record
    return record


def library_search_paths() -> list[Path]:
    """Return standard OpenSCAD library directories plus ``OPENSCADPATH``."""
    search_paths: list[Path] = []
    system = platform.system()
    home = Path.home()
    if system == "Linux":
        search_paths.extend(
            [
                home / ".local" / "share" / "OpenSCAD" / "libraries",
                Path("/usr/share/openscad/libraries"),
                Path("/usr/share/openscad-nightly/libraries"),
                Path("/usr/local/share/openscad/libraries"),
            ]
        )
    elif system == "Darwin":
        search_paths.extend(
            [
                home / "Documents" / "OpenSCAD" / "libraries",
                home / "Library" / "Application Support" / "OpenSCAD" / "libraries",
            ]
        )
    elif system == "Windows":
        search_paths.append(home / "Documents" / "OpenSCAD" / "libraries")

    openscad_path = os.environ.get("OPENSCADPATH")
    if openscad_path:
        for value in openscad_path.split(os.pathsep):
            if value.strip():
                path = Path(value.strip())
                if path not in search_paths:
                    search_paths.append(path)
    return search_paths


def wrap_with_memory_limit(cmd: list[str]) -> list[str]:
    """Prefix a POSIX command with an address-space limit when configured."""
    limit_mb = get_config().security.max_memory_mb
    if limit_mb <= 0 or os.name != "posix":
        return cmd
    shell = shutil.which("sh")
    if not shell:
        return cmd

    limit_kb = int(limit_mb) * 1024
    key = str(limit_kb)
    if key not in _memory_limit_checked:
        try:
            probe = subprocess.run(
                [shell, "-c", f"ulimit -v {limit_kb}"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            _memory_limit_checked[key] = probe.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            _memory_limit_checked[key] = False
        if not _memory_limit_checked[key]:
            logger.warning(
                "Could not apply memory limit of %d MB to OpenSCAD subprocesses "
                "(ulimit -v unsupported here); running without a ceiling",
                limit_mb,
            )
    if not _memory_limit_checked[key]:
        return cmd
    return [
        shell,
        "-c",
        f'ulimit -v {limit_kb} 2>/dev/null; exec "$@"',
        "openscad-mcp",
        *cmd,
    ]


def openscad_env(include_paths: list[str] | None = None) -> dict[str, str] | None:
    """Build a subprocess environment containing caller include paths."""
    if not include_paths:
        return None
    env = os.environ.copy()
    paths = [str(path) for path in include_paths]
    existing = env.get("OPENSCADPATH", "")
    if existing:
        paths.append(existing)
    env["OPENSCADPATH"] = os.pathsep.join(paths)
    return env


def run_openscad(
    cmd: list[str],
    include_paths: list[str] | None = None,
    label: str = "rendering",
) -> subprocess.CompletedProcess:
    """Run OpenSCAD with configured timeout, memory, and include-path limits."""
    config = get_config()
    full_cmd = wrap_with_memory_limit(cmd)
    try:
        return subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=config.rendering.timeout_seconds,
            env=openscad_env(include_paths),
            stdin=subprocess.DEVNULL,
            start_new_session=(os.name == "posix"),
        )
    except subprocess.TimeoutExpired as exc:
        raw_partial = exc.stderr
        if isinstance(raw_partial, bytes):
            partial = raw_partial.decode("utf-8", errors="replace")
        elif isinstance(raw_partial, str):
            partial = raw_partial
        else:
            partial = ""
        tail = ""
        if partial:
            diagnostics = parse_openscad_output(partial, None)
            lines = diagnostics.errors + diagnostics.warnings
            if not lines:
                lines = [line for line in partial.splitlines() if line.strip()][-5:]
            if lines:
                tail = " Output before timeout: " + " | ".join(lines[-5:])
        raise RuntimeError(
            f"OpenSCAD {label} timed out after {config.rendering.timeout_seconds} seconds.{tail}"
        ) from exc


def format_variables(variables: dict[str, Any] | None) -> list[str]:
    """Turn a variables mapping into OpenSCAD ``-D name=value`` arguments."""
    args: list[str] = []
    if not variables:
        return args
    for key, value in variables.items():
        if isinstance(value, str):
            rendered = f'"{value}"'
        elif isinstance(value, bool):
            rendered = "true" if value else "false"
        else:
            rendered = str(value)
        args.extend(["-D", f"{key}={rendered}"])
    return args
