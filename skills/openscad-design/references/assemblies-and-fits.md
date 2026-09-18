# Assemblies, fits, and purchased parts

Read this reference for any design with multiple manufactured parts, mating features,
fasteners, purchased components, or motion.

## Part identity and coordinate frames

Define one module per logical part and a separate assembly view. Pass each part to
`check` by name so it is exported independently and retains its identity:

```text
check(scad_file="assembly.scad", mode="interference",
      parts=[{"name": "bracket", "code": "bracket();"},
             {"name": "motor", "code": "motor();",
              "place": "translate(MOTOR_POS)", "ghost": true,
              "mass_g": 34}])
```

Keep placements and check coordinates as expressions of model parameters, not copied
numeric values. In a YAML check file, write values such as
`point: "[BOLT_R, 0, BASE_H]"` and `min_mm: "GAP_MIN"` so checks remain valid after
parameter edits.

## Choose the check that proves the requirement

- `interference`: determine whether distinct parts overlap. Flush contact is contact,
  not interference.
- `clearance`: measure the minimum separation and closest points.
- `contact`: prove intended static or sliding contact.
- `alignment`: compare axes or features such as mating holes. Interference and
  clearance alone cannot prove coaxiality.
- `motion`: sweep a part along a translation or rotation and test the full path.
- `rules`: run the assembly's repeatable YAML acceptance suite.

Every result includes tessellation quality. If a distance is within the error bound
and returns `UNRESOLVED`, increase quality and rerun; never promote it to a pass.

Use `measure(mode="features")` to inspect holes and their axes, diameters, depths, and
declared fit. Use `measure(mode="probe")` for point-in-solid, ray, visibility, or
line-of-sight questions. Use `measure(mode="mass")` and mass rules when total mass,
centre of mass, or inertia is an acceptance criterion.

## Fits and process compensation

Query `reference(topic="fits")` with the relevant diameter or shaft/bore dimensions.
Also use the dedicated reference topics for fasteners, inserts, bearings, magnets,
joints, DFM, and materials. Do not treat an example clearance as universal: fit
depends on process, material, orientation, machine calibration, and the intended
press/slip/free relation.

Represent nominal size, functional clearance or interference, and manufacturing
compensation as separate parameters. For critical fits, expose them to the user and
recommend a calibration coupon when machine capability is unknown.

## Purchased parts

Query `reference(topic="parts")` for the current catalog; do not rely on a hard-coded
list. Create an available catalog model with
`model(action="create", template="part:<id>")`. Use its documented module names,
anchors, verification dimensions, and clearance mask.

Confirm catalog verification dimensions against the actual physical component when
the fit is critical. A clearance mask expresses the intended pocket more reliably
than indiscriminately growing the visible part with `minkowski()`.

## Repeatable verification

Once interfaces stabilize, create a check file containing the model, frames, quality,
named parts, and checks. Run `check(check_file=..., mode="rules")` after edits that can
affect geometry or placement. A CLI or CI run can execute the same file with
`openscad-mcp check`.

Before manufacture, evaluate the chosen assembly orientation and each printable part
separately. `measure(mode="orientation")` presents candidates but does not choose the
best cosmetic or functional face. `measure(mode="printability")` supplies geometric
facts; `validate(mode="printability")` evaluates them against thresholds.
