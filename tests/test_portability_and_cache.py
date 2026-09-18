"""Regression coverage for portable text IO and cache freshness."""

import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from openscad_mcp import server
from openscad_mcp.diagnostics import Diagnostics
from openscad_mcp.utils.config import Config


def test_empty_yaml_uses_defaults(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("# defaults\n", encoding="utf-8")
    assert Config.from_yaml(str(path)).rendering.max_concurrent == 5


@pytest.mark.parametrize("text", ["[]", "42", "true", "a string"])
def test_non_mapping_yaml_has_actionable_error(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        Config.from_yaml(str(path))


def test_utf8_bom_yaml_and_roundtrip(tmp_path):
    path = tmp_path / "config.yaml"
    name = "Gehäuse 日本語"
    path.write_text(f'server:\n  name: "{name}"\n', encoding="utf-8-sig")
    config = Config.from_yaml(str(path))
    assert config.server.name == name
    config.to_yaml(str(path))
    assert Config.from_yaml(str(path)).server.name == name


async def test_model_crud_and_wrapper_preserve_unicode(configured_env):
    text = '// Gehäuse 日本語\necho("Größe 日本語"); cube(1);\n'
    model = server._tool_fn(server.model)
    created = await model(action="create", name="unicode", content=text)
    assert created["success"]
    path = Path(created["path"])
    assert path.read_bytes().decode("utf-8").replace("\r\n", "\n") == text
    loaded = await model(action="get", name="unicode")
    assert loaded["content"] == text
    from openscad_mcp.wrappers import build_wrapper

    with server._ModelSource(None, str(path), "test") as source:
        assert source.text == text
        wrapper = source.wrapper_file(build_wrapper(source.text))
        assert "Größe 日本語" in wrapper.read_bytes().decode("utf-8")


def test_measure_key_changes_when_stat_is_preserved(configured_env):
    root, _ = configured_env
    model = root / "main.scad"
    dep = root / "params.scad"
    dep.write_text("W=10;", encoding="utf-8")
    model.write_text("include <params.scad>\ncube(W);", encoding="utf-8")

    def key():
        with server._ModelSource(None, str(model), "test") as source:
            return server._measure_cache_key(source, {}, None)

    first = key()
    stat = dep.stat()
    dep.write_text("W=99;", encoding="utf-8")
    os.utime(dep, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    second = key()
    assert second != first
    stat = model.stat()
    model.write_text("include <params.scad>\ncube(2);", encoding="utf-8")
    os.utime(model, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert key() != second


def test_disabled_measure_cache_recomputes(configured_env, monkeypatch):
    analyze = Mock(return_value=(object(), Diagnostics(returncode=0), None))
    monkeypatch.setattr(server, "_analyze_mesh_export", analyze)
    with server._ModelSource("cube(1);", None, "test") as source:
        server._measure_source(source, {}, None)
        server._measure_source(source, {}, None)
    assert analyze.call_count == 2
    assert not server._measure_cache


@pytest.mark.parametrize("disk_cache_exists", [False, True])
async def test_clear_cache_also_clears_memory(configured_env, disk_cache_exists):
    _, config = configured_env
    if disk_cache_exists:
        config.cache.directory.mkdir()
        (config.cache.directory / "old.png").write_bytes(b"old")
    server._measure_cache["test"] = (object(), Diagnostics(returncode=0))
    server._mesh_cache["test"] = (0, object())
    result = await server._tool_fn(server.clear_cache)()
    assert result["success"]
    assert result["cleared_files"] == int(disk_cache_exists)
    assert not server._measure_cache
    assert not server._mesh_cache
