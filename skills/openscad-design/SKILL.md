---
name: openscad-design
description: Design, modify, and verify parametric OpenSCAD parts and assemblies with openscad-mcp. Use for printable parts, enclosures, adapters, jigs, mechanisms, or existing SCAD/STL geometry that must be measured, fit-checked, repaired, or exported.
license: MIT
---

# OpenSCAD design and verification

The governing rule is: **numbers decide; pictures confirm.** A render can reveal a
feature on the wrong face, but it cannot prove wall thickness, clearance,
watertightness, or manifoldness. Make claims from `measure`, `validate`, and `check`;
use `render` as visual confirmation.

## Establish the design contract

Before writing geometry, extract or state:

- units (convert supplied dimensions to millimetres for these tools),
- axis directions, handedness, print-bed face, and origin/datum,
- manufacturing process, material, nozzle width, and layer height when relevant,
- required dimensions and tolerances, mating parts, loads, and motion,
- keep-in and keep-out volumes, critical surfaces, and mounting interfaces,
- requested outputs and measurable acceptance criteria.

Ask only when a missing value would materially change the geometry or make the result
unsafe. Otherwise choose a conservative assumption, state it briefly, and keep it as
a named parameter so the user can change it.

Never invent critical connector positions or mounting coordinates for a real device.
Obtain a dimensioned reference or ask for the missing dimensions. Checking a housing
against a guessed reference only proves that the two guesses agree.

For an existing project, inspect its files and dependency graph with
`get_project_files` before editing. Preserve the project's coordinate system, naming,
style, and user-authored changes unless the task requires otherwise. Use
`get_libraries` instead of guessing which library or import spelling is installed.

## Structure the model

Put meaningful dimensions at the top of the file. Separate them conceptually into:

1. nominal interface dimensions,
2. functional clearance or interference,
3. process compensation,
4. derived geometry.

Do not hide process compensation inside nominal dimensions. Derive repeated values
with expressions and use a small named `eps` only to make Boolean operations robust;
`eps` is not a fit allowance.

```openscad
shaft_d               = 8;
radial_clearance      = 0.20;
diameter_compensation = 0.10;
bore_d = shaft_d + 2 * radial_clearance + diameter_compensation;
eps = 0.01;
```

Use one module per logical part and small modules for repeated or testable features.
A printable part may use `union()` internally. Do not union distinct assembly parts
merely to simplify rendering or checking. Keep a separate assembly view that places
the named part modules in a shared coordinate frame.

## Build complex geometry in stages

Do not attempt a fully detailed complex model in one pass. Build and verify:

1. reference envelopes, datums, and keep-out volumes,
2. primary structural bodies,
3. mounting and mating interfaces,
4. holes, channels, pockets, and motion spaces,
5. ribs, transitions, chamfers, and cosmetic details,
6. manufacturing and printability adjustments.

At each stage, test the smallest independently meaningful module. Prefer simple
profiles, extrusions, revolutions, and Boolean construction over a large hand-written
`polyhedron()`. Use `hull()` and `minkowski()` only when they express the intended
geometry and their performance cost is justified.

For OpenSCAD language and geometry failure modes, read
[references/geometry-and-performance.md](references/geometry-and-performance.md)
when creating non-trivial geometry or diagnosing a failure.

For adjustable designs, verify the intended parameter range as well as the default
size. Use the parameter-boundary workflow in that reference: predicate sweeps check
dimension constraints, then mesh and assembly checks verify representative variants.
Do not claim a family of parts is verified from a single successful default render.

## Verification loop

Repeat this loop after every material change:

1. Run `validate(mode="syntax")` before rendering, measuring, or exporting. OpenSCAD
   may exit successfully while reporting a failed assertion, missing include, unknown
   module, or invalid geometry on stderr. Do not proceed while `errors` is non-empty;
   investigate warnings that imply omitted or altered geometry.
2. Use `scad_eval` for important derived expressions. Treat `undef`, a wrong type, or
   a non-finite value as a model error.
3. Run `measure(mode="model")` and compare the bounding box, dimensions, volume,
   component count, and watertightness with explicit expected values. Measurements
   describe the exported mesh; curved area, volume, and small clearances are limited
   by tessellation quality rather than being analytic CAD values.
4. Use the narrowest additional measurement that answers the open question:
   `parts`, `section`, `features`, `probe`, `mass`, `anchors`, `printability`, or
   `orientation`.
5. Run `validate(mode="geometry")`. Passing requires
   `mesh_health.manifold == true`; `false` is a failure and `null` means the check did
   not run.
6. Only after the numerical checks agree, run `render(grounded=true)` with the one to
   three views needed to confirm orientation, topology, feature placement, and visual
   intent. Read the render's text digest before inspecting the image, and use a
   section view for hidden internal geometry. Treat the stated mm/px scale as valid
   only for the orthographic projection selected by `grounded=true`.

On every tool response, read `errors`, then `warnings`, then `hints`, then the
payload. Check `cached`; after a dependency edit, do not trust a suspicious stale
result. Re-run fresh or use `clear_cache` when necessary.

`UNRESOLVED` is not `PASS`. Increase the relevant quality or `$fn` and retry. If the
result remains unresolved, report the uncertainty and do not claim the condition
passed. If repeated retries reproduce the same failure, isolate or simplify the
smallest failing module instead of blindly increasing resolution.

## Assemblies and fits

For any design with mating, moving, or separately manufactured parts, read and follow
[references/assemblies-and-fits.md](references/assemblies-and-fits.md).

In particular:

- query `reference(topic="fits")` rather than inventing a clearance,
- pass named parts separately to `check`, preserving their identity,
- use `interference`, `clearance`, `contact`, `alignment`, and `motion` according to
  the actual relation being proved,
- freeze repeatable acceptance criteria in a YAML check file and run
  `check(mode="rules")` after relevant edits.

Mesh component counts describe connected solids, not semantic part names.
`measure(mode="parts", parts=[...])` also supports independently exported named parts
in the assembly frame. Use component counts to detect islands or fusions and named
part checks to prove assembly relationships.

## Completion gate

Before declaring a design complete, verify all user requirements and report the
evidence. At minimum:

- syntax has no errors,
- evaluated critical dimensions have the expected values,
- bounding box and component count are explained,
- watertightness and manifoldness pass,
- required fit, alignment, contact, clearance, and motion checks pass,
- printability has been evaluated for the intended orientation when the result will
  be manufactured,
- the final render agrees with the coordinate system and intended feature placement.

Export only after these gates pass, and only in the format the user needs. Prefer 3MF
when units, metadata, or named parts matter; use STL when the downstream workflow
requires it. If a gate cannot be run, state which evidence is missing rather than
implying that the design was verified.
