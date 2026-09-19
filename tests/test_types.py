"""Tests for the public Pydantic models in :mod:`openscad_mcp.types`."""

import pytest
from pydantic import ValidationError

from openscad_mcp.types import (
    ColorScheme,
    ImageSize,
    OpenSCADInfo,
    ServerInfo,
    TransportType,
    Vector3D,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"x": 1, "y": 2, "z": 3}, (1.0, 2.0, 3.0)),
        ([1, 2, 3], (1.0, 2.0, 3.0)),
        ((1, 2, 3), (1.0, 2.0, 3.0)),
        ("[1, 2, 3]", (1.0, 2.0, 3.0)),
        ('{"x": 1, "y": 2, "z": 3}', (1.0, 2.0, 3.0)),
    ],
)
def test_vector3d_accepts_supported_input_forms(value, expected):
    assert Vector3D.model_validate(value).to_tuple() == expected


def test_vector3d_tuple_constructor_round_trips():
    assert Vector3D.from_tuple((1.5, 2.5, 3.5)).to_tuple() == (1.5, 2.5, 3.5)


@pytest.mark.parametrize("value", ["not-json", [1, 2], {"x": 1}])
def test_vector3d_rejects_malformed_values(value):
    with pytest.raises((ValueError, ValidationError)):
        Vector3D.model_validate(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"width": 640, "height": 480}, (640, 480)),
        ([640, 480], (640, 480)),
        ((640, 480), (640, 480)),
        ("[640, 480]", (640, 480)),
        ('{"width": 640, "height": 480}', (640, 480)),
    ],
)
def test_image_size_accepts_supported_input_forms(value, expected):
    assert ImageSize.model_validate(value).to_tuple() == expected


def test_image_size_defaults_and_tuple_constructor():
    assert ImageSize.model_validate({}).to_tuple() == (800, 600)
    assert ImageSize.from_tuple((1024, 768)).to_tuple() == (1024, 768)


@pytest.mark.parametrize("value", ["not-json", [640], {"width": 0, "height": 480}, [4097, 480]])
def test_image_size_rejects_malformed_or_out_of_range_values(value):
    with pytest.raises((ValueError, ValidationError)):
        ImageSize.model_validate(value)


def test_information_models_apply_defaults():
    openscad = OpenSCADInfo(installed=False)
    assert openscad.version is None
    assert openscad.path is None
    assert openscad.searched_paths is None

    server = ServerInfo(
        version="1.0",
        max_concurrent_renders=2,
        active_operations=0,
        cache_enabled=True,
    )
    assert server.supported_formats == ["png"]
    assert server.imagemagick_available is False


def test_public_enums_use_protocol_values():
    assert ColorScheme.CORNFIELD.value == "Cornfield"
    assert TransportType.STDIO.value == "stdio"
