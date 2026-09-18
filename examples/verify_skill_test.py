"""Verify the example with the server functions and an actual OpenSCAD binary.

Run from the repository root: uv run python examples/verify_skill_test.py
No final mesh is exported. A temporary render and cache are removed on exit.
"""

import asyncio
import json
import math
import tempfile
from pathlib import Path

from openscad_mcp import server
from openscad_mcp.utils.config import CacheConfig, Config, set_config


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def checked(result):
    require(result.get("success") and not result.get("errors"), str(result))
    require(not result.get("warnings"), str(result))
    return result


async def main():
    model = Path(__file__).with_name("skill_test.scad").resolve()
    with tempfile.TemporaryDirectory(prefix="openscad-skill-test-") as scratch:
        config = Config.from_env()
        config.temp_dir = Path(scratch)
        config.cache = CacheConfig(enabled=False, directory=Path(scratch) / "cache")
        set_config(config)
        syntax = checked(
            await server._tool_fn(server.validate)(mode="syntax", scad_file=str(model))
        )
        values = checked(
            await server._tool_fn(server.scad_eval)(
                scad_file=str(model), expressions=["width_x", "depth_y", "height_z", "hole_d"]
            )
        )
        require([r["value"] for r in values["results"]] == [30, 20, 10, 5], "Wrong parameters")
        # Check a minimum 2 mm ligament, including one deliberately rejected variant.
        predicates = ["(min(width_x, depth_y) - hole_d) / 2 >= 2"]
        accepted = checked(
            await server._tool_fn(server.validate)(
                mode="predicates", scad_file=str(model), predicates=predicates,
                sweep={"variable": "hole_d", "values": [5, 10, 16]},
            )
        )
        require(accepted["valid"] and accepted["sweep"]["all_pass"], "Valid range rejected")
        rejected = checked(
            await server._tool_fn(server.validate)(
                mode="predicates", scad_file=str(model), predicates=predicates,
                sweep={"variable": "hole_d", "values": [5, 16, 18]},
            )
        )
        require(not rejected["valid"], "Unsafe ligament accepted")
        require(rejected["sweep"]["first_failure"] == 18, "Wrong failing variant")
        measured = checked(
            await server._tool_fn(server.measure)(
                mode="model", scad_file=str(model), response_format="detailed"
            )
        )
        require(measured["dimensions"] == [30, 20, 10], "Wrong bounding box")
        require(measured["bbox_min"] == [-15, -10, 0], "Wrong datum")
        require(measured["component_count"] == 1 and measured["is_watertight"], "Broken solid")
        # The cylindrical cut is an inscribed regular polygon, not an analytic circle.
        expected_volume = 6000 - 64 / 2 * 2.5**2 * math.sin(2 * math.pi / 64) * 10
        require(abs(measured["volume"] - expected_volume) < 0.01, "Wrong polygonal hole volume")
        features = checked(
            await server._tool_fn(server.measure)(
                mode="features", scad_file=str(model), response_format="detailed"
            )
        )
        geometry = checked(
            await server._tool_fn(server.validate)(mode="geometry", scad_file=str(model))
        )
        require(geometry["mesh_health"]["manifold"] is True, "Manifold check did not pass")
        rendered = await server._tool_fn(server.render)(
            scad_file=str(model), grounded=True, views=["isometric"]
        )
        metadata = None
        for item in rendered:
            text = item if isinstance(item, str) else getattr(item, "text", "")
            if text.startswith("{"):
                metadata = checked(json.loads(text))
        require(metadata is not None, "No render metadata")
        print(
            json.dumps(
                {
                    "syntax_valid": syntax["valid"],
                    "parameter_checks": {
                        "accepted_hole_d_mm": [5, 10, 16],
                        "rejected_hole_d_mm": rejected["sweep"]["first_failure"],
                        "min_ligament_mm": 2,
                    },
                    "dimensions_mm": measured["dimensions"],
                    "volume_mm3": measured["volume"],
                    "manifold": True,
                    "features": features["features"],
                    "render_success": metadata["success"],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
