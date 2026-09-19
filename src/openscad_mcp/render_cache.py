"""Dependency-aware render cache used by the OpenSCAD runtime."""

import base64
import contextlib
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from .diagnostics import Diagnostics
from .utils.config import get_config

logger = logging.getLogger(__name__)


def _hash_field(hasher: "hashlib._Hash", value: Any) -> None:
    """Feed one length-prefixed value into a hash without field ambiguity."""
    data = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True).encode()
    hasher.update(len(data).to_bytes(8, "big"))
    hasher.update(data)


def _compute_render_cache_key(
    scad_content: str | None = None,
    scad_file: str | None = None,
    camera_position: list[float] | None = None,
    camera_target: list[float] | None = None,
    camera_up: list[float] | None = None,
    image_size: list[int] | None = None,
    color_scheme: str = "Cornfield",
    variables: dict[str, Any] | None = None,
    auto_center: bool = False,
    include_paths: list[str] | None = None,
    binary_identity: str | None = None,
) -> str:
    """Compute a render key from source, camera, quality, and runtime inputs."""
    hasher = hashlib.sha256()
    if scad_content:
        _hash_field(hasher, scad_content.encode("utf-8"))
    elif scad_file:
        try:
            _hash_field(hasher, Path(scad_file).read_bytes())
        except OSError:
            _hash_field(hasher, scad_file.encode("utf-8"))
    else:
        _hash_field(hasher, b"")

    for value in (
        camera_position,
        camera_target,
        camera_up,
        image_size,
        color_scheme,
        variables or {},
        bool(auto_center),
        include_paths or [],
        binary_identity or "",
    ):
        _hash_field(hasher, value)
    return hasher.hexdigest()


def _manifest_path(cache_key: str) -> Path:
    return get_config().cache.directory / f"{cache_key}.json"


def _file_fingerprint(path: Path, with_hash: bool = True) -> dict[str, Any] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    entry: dict[str, Any] = {
        "path": str(path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
    if with_hash:
        try:
            entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return None
    return entry


def _build_cache_manifest(
    deps: list[str],
    scad_dir: Path,
    missing_includes: list[str],
    diagnostics: Diagnostics,
    exclude: list[Path] | None = None,
) -> dict[str, Any]:
    """Record dependency fingerprints and render diagnostics for one entry."""
    excluded = {path.resolve() for path in (exclude or [])}
    entries: list[dict[str, Any]] = []
    for dependency in deps:
        path = Path(dependency)
        if not path.is_absolute():
            path = scad_dir / path
        try:
            if path.resolve() in excluded:
                continue
        except OSError:
            continue
        fingerprint = _file_fingerprint(path)
        if fingerprint is not None:
            entries.append(fingerprint)
    return {
        "version": 1,
        "dependencies": entries,
        "unresolved_includes": missing_includes,
        "scad_dir": str(scad_dir),
        "diagnostics": diagnostics.to_dict(include_records=True),
        "statistics": diagnostics.statistics,
    }


def _manifest_is_current(
    manifest: dict[str, Any],
    include_paths: list[str] | None,
    library_paths: list[Path] | None = None,
) -> bool:
    """Return whether dependencies and previously missing includes are unchanged."""
    for entry in manifest.get("dependencies", []):
        fresh = _file_fingerprint(Path(entry["path"]), with_hash=True)
        if fresh is None or fresh.get("sha256") != entry.get("sha256"):
            return False

    search_dirs = [Path(manifest.get("scad_dir", "."))]
    search_dirs.extend(Path(path) for path in (include_paths or []))
    search_dirs.extend(library_paths or [])
    for name in manifest.get("unresolved_includes", []):
        if any((directory / name).exists() for directory in search_dirs):
            return False
    return True


def _check_cache(
    cache_key: str,
    include_paths: list[str] | None = None,
    library_paths: list[Path] | None = None,
) -> tuple[str, dict[str, Any]] | None:
    """Return a validated base64 image and manifest, or ``None`` on a miss."""
    config = get_config()
    if not config.cache.enabled:
        return None

    cache_file = config.cache.directory / f"{cache_key}.png"
    manifest_file = _manifest_path(cache_key)
    if not cache_file.exists():
        return None

    age_hours = (time.time() - cache_file.stat().st_mtime) / 3600.0
    if age_hours > config.cache.ttl_hours:
        _remove_cache_entry(cache_key)
        return None
    if not manifest_file.exists():
        _remove_cache_entry(cache_key)
        return None
    try:
        manifest = json.loads(manifest_file.read_text())
    except (OSError, ValueError):
        _remove_cache_entry(cache_key)
        return None
    if not _manifest_is_current(manifest, include_paths, library_paths):
        _remove_cache_entry(cache_key)
        return None
    try:
        return base64.b64encode(cache_file.read_bytes()).decode("utf-8"), manifest
    except OSError:
        return None


def _remove_cache_entry(cache_key: str) -> None:
    config = get_config()
    for suffix in (".png", ".json"):
        with contextlib.suppress(OSError):
            (config.cache.directory / f"{cache_key}{suffix}").unlink()


def _save_to_cache(
    cache_key: str, image_data: bytes, manifest: dict[str, Any] | None = None
) -> None:
    """Save raw PNG bytes and their dependency manifest."""
    config = get_config()
    if not config.cache.enabled:
        return
    config.cache.ensure_cache_directory()
    cache_file = config.cache.directory / f"{cache_key}.png"
    try:
        _manifest_path(cache_key).write_text(
            json.dumps(manifest or {"version": 1, "dependencies": []})
        )
        cache_file.write_bytes(image_data)
    except OSError as exc:
        logger.warning("Failed to write render cache entry: %s", exc)
        _remove_cache_entry(cache_key)
        return
    _evict_cache_if_needed()


def _evict_cache_if_needed() -> None:
    """Evict complete render and part-cache entries oldest first."""
    config = get_config()
    if not config.cache.enabled:
        return
    cache_dir = config.cache.directory
    if not cache_dir.exists():
        return

    max_bytes = config.cache.max_size_mb * 1024 * 1024
    entries: dict[tuple[Path, str], list[tuple[Path, int]]] = {}
    newest: dict[tuple[Path, str], float] = {}
    total_size = 0
    candidates = list(cache_dir.glob("*.png")) + list(cache_dir.glob("*.json"))
    parts_dir = cache_dir / "parts"
    if parts_dir.is_dir():
        candidates += [
            path for path in parts_dir.iterdir() if path.suffix in (".stl", ".json", ".csg")
        ]

    for path in candidates:
        try:
            stat = path.stat()
        except OSError:
            continue
        key = (path.parent, path.stem)
        entries.setdefault(key, []).append((path, stat.st_size))
        newest[key] = max(newest.get(key, 0.0), stat.st_mtime)
        total_size += stat.st_size

    if total_size <= max_bytes:
        return
    for key in sorted(entries, key=lambda entry: newest[entry]):
        if total_size <= max_bytes:
            break
        for file_path, file_size in entries[key]:
            try:
                file_path.unlink()
                total_size -= file_size
            except OSError:
                continue
