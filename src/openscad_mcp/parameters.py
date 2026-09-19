"""Flexible parameter normalization for MCP tool inputs.

MCP clients do not always encode list, mapping, camera, and image-size values
the same way. These helpers keep that compatibility logic independent from the
tool orchestration in :mod:`openscad_mcp.server`.
"""

import json
from typing import Any


def parse_camera_param(
    param: str | list[float] | dict[str, float] | None, default: list[float]
) -> list[float]:
    """Parse a camera vector from a list, mapping, JSON string, or ``None``."""
    if param is None:
        return default
    if isinstance(param, list):
        if len(param) == 3:
            return [float(value) for value in param]
        raise ValueError(f"Expected 3 values for camera parameter, got {len(param)}")
    if isinstance(param, dict):
        if all(key in param for key in ("x", "y", "z")):
            return [float(param["x"]), float(param["y"]), float(param["z"])]
        raise ValueError(f"Dict must have x, y, z keys, got {param.keys()}")
    if isinstance(param, str):
        try:
            parsed = json.loads(param.strip())
            if isinstance(parsed, list) and len(parsed) == 3:
                return [float(value) for value in parsed]
            if isinstance(parsed, dict) and all(key in parsed for key in ("x", "y", "z")):
                return [float(parsed["x"]), float(parsed["y"]), float(parsed["z"])]
            raise ValueError("Parsed value must be a list of 3 numbers or dict with x,y,z keys")
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Cannot parse '{param}' as camera parameter: {exc}") from exc
    raise ValueError(f"Unexpected type for camera parameter: {type(param)}")


def parse_list_param(param: str | list[Any] | None, default: list[Any]) -> list[Any]:
    """Parse a list from a native list, JSON/CSV string, or ``None``."""
    if param is None:
        return default
    if isinstance(param, list):
        return param
    if not isinstance(param, str):
        raise ValueError(f"Cannot parse list from type {type(param)}")

    value = param.strip()
    if not value:
        return default
    if value.startswith("["):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
            raise ValueError(f"JSON parsed to {type(parsed)}, expected list")
        except json.JSONDecodeError:
            pass
    if "," in value:
        return [item.strip() for item in value.split(",") if item.strip()]
    return [value]


def parse_dict_param(param: str | dict[str, Any] | None, default: dict[str, Any]) -> dict[str, Any]:
    """Parse a mapping from a native dict, JSON/key-value string, or ``None``."""
    if param is None:
        return default
    if isinstance(param, dict):
        return param
    if not isinstance(param, str):
        raise ValueError(f"Cannot parse dict from type {type(param)}")

    value = param.strip()
    if not value:
        return default
    if value.startswith("{"):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
            raise ValueError(f"JSON parsed to {type(parsed)}, expected dict")
        except json.JSONDecodeError:
            pass
    if "=" in value:
        result: dict[str, Any] = {}
        for pair in value.split(","):
            if "=" not in pair:
                continue
            key, raw_value = pair.split("=", 1)
            key = key.strip()
            raw_value = raw_value.strip()
            try:
                result[key] = int(raw_value) if "." not in raw_value else float(raw_value)
            except ValueError:
                if raw_value.lower() == "true":
                    result[key] = True
                elif raw_value.lower() == "false":
                    result[key] = False
                else:
                    result[key] = raw_value
        return result
    raise ValueError(f"Cannot parse dict from type {type(param)}")


def parse_image_size_param(
    param: list[int] | str | tuple[Any, ...] | None, default: list[int]
) -> list[int]:
    """Parse an image size from a sequence, JSON, ``WxH``, CSV, or ``None``."""
    if param is None:
        return default
    if isinstance(param, list | tuple):
        if len(param) == 2:
            return [int(param[0]), int(param[1])]
        raise ValueError(f"Image size must have 2 values, got {len(param)}")
    if isinstance(param, str):
        value = param.strip()
        if value.startswith("["):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list) and len(parsed) == 2:
                    return [int(parsed[0]), int(parsed[1])]
            except (json.JSONDecodeError, ValueError):
                pass
        if "x" in value:
            parts = value.split("x")
            if len(parts) == 2:
                return [int(parts[0].strip()), int(parts[1].strip())]
        if "," in value and not value.startswith("["):
            parts = value.split(",")
            if len(parts) == 2:
                return [int(parts[0].strip()), int(parts[1].strip())]
    raise ValueError(f"Cannot parse image size from {param}")
