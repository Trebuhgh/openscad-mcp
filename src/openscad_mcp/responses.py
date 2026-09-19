"""Response-size management and image serialization helpers."""

import base64
import io
import json
import logging
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PIL import Image as PILImage

from .utils.config import get_config

logger = logging.getLogger(__name__)


def estimate_response_size(data: Any) -> int:
    """Estimate a JSON response size in tokens using four characters per token."""
    return len(json.dumps(data)) // 4


def save_image_to_file(base64_data: str, filename: str, output_dir: Path) -> str:
    """Decode a base64 image into ``output_dir`` and return its path."""
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / filename
        file_path.write_bytes(base64.b64decode(base64_data))
        return str(file_path)
    except Exception as exc:
        raise ValueError(f"Failed to save image to file: {exc}") from exc


def compress_base64_image(
    base64_data: str,
    quality: int = 85,
    optimize: bool = True,
    *,
    _image_module: Any = PILImage,
) -> str:
    """Decode, optimize, and re-encode a base64 PNG image."""
    try:
        image_data = base64.b64decode(base64_data)
        image = _image_module.open(io.BytesIO(image_data))
        buffer = io.BytesIO()
        image.save(
            buffer,
            format="PNG",
            optimize=optimize,
            compress_level=9 if quality < 50 else (6 if quality < 85 else 3),
        )
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as exc:
        raise ValueError(f"Failed to compress image: {exc}") from exc


def manage_response_size(
    images: dict[str, str] | list[dict[str, Any]],
    output_format: str = "auto",
    max_size: int = 25000,
    output_dir: Path | None = None,
    ctx: Any | None = None,
    *,
    _estimate: Callable[[Any], int] = estimate_response_size,
    _save: Callable[[str, str, Path], str] = save_image_to_file,
    _compress: Callable[[str], str] = compress_base64_image,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Keep image responses within a token budget.

    ``auto`` keeps small payloads inline, tries PNG compression for large
    payloads, and otherwise writes them to the configured temporary directory.
    The private callbacks let :mod:`openscad_mcp.server` preserve its historic
    monkey-patching surface while delegating the implementation here.
    """
    if output_dir is None:
        output_dir = Path(get_config().temp_dir) / "renders"

    if isinstance(images, dict):
        is_dict = True
        working_images = list(images.items())
    else:
        is_dict = False
        working_images = [
            (f"image_{index}", image.get("data", image)) for index, image in enumerate(images)
        ]

    if output_format == "auto":
        current_size = _estimate(images)
        if ctx:
            logger.info("Estimated response size: %s tokens", current_size)

        if current_size > max_size:
            for _name, data in working_images[:1]:
                try:
                    compressed = _compress(data)
                    if len(compressed) / len(data) < 0.7:
                        output_format = "compressed"
                        break
                except Exception:
                    pass
            if output_format == "auto":
                output_format = "file_path"
        else:
            output_format = "base64"

        if ctx:
            logger.info("Selected output format: %s", output_format)

    result: dict[str, dict[str, Any]] = {}
    for name, base64_data in working_images:
        if output_format == "file_path":
            filename = f"{name}_{uuid.uuid4().hex[:8]}.png"
            result[name] = {
                "type": "file_path",
                "path": _save(base64_data, filename, output_dir),
                "mime_type": "image/png",
            }
        elif output_format == "compressed":
            try:
                compressed_data = _compress(base64_data)
                result[name] = {
                    "type": "base64_compressed",
                    "data": compressed_data,
                    "mime_type": "image/png",
                    "compression_ratio": len(compressed_data) / len(base64_data),
                }
            except Exception as exc:
                if ctx:
                    logger.warning("Compression failed for %s: %s", name, exc)
                result[name] = {
                    "type": "base64",
                    "data": base64_data,
                    "mime_type": "image/png",
                }
        else:
            result[name] = {
                "type": "base64",
                "data": base64_data,
                "mime_type": "image/png",
            }

    if is_dict:
        if all(value["type"] == "base64" for value in result.values()):
            return {key: value["data"] for key, value in result.items()}
        return result
    return list(result.values())
