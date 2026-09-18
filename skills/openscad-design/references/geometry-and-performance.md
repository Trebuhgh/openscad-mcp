# Geometry and performance guidance

Read this reference when building non-trivial OpenSCAD geometry, using imported
geometry, or diagnosing an empty, slow, or non-manifold result.

## OpenSCAD evaluation rules

OpenSCAD variables are scoped and resolved declaratively; assignment is not ordinary
imperative mutation. The final assignment in a scope wins for that scope. Do not try
to update an outer variable inside an `if` or accumulate it in a `for` loop. Use a
conditional expression, list comprehension, or function instead.

```openscad
height = tall ? 20 : 10;
values = [for (i = [0:n-1]) expression(i)];
```

In `difference()`, the first child is the base and every later child is subtracted.
When a result is unexpectedly empty, inspect the child order and cutter extents.

OpenSCAD does not combine 2D and 3D geometry in one Boolean operation. Extrude a 2D
profile before combining it with solids.

## Robust Boolean construction

- Avoid zero-thickness walls and solids that meet only on an exact face or edge.
- Extend cutters beyond both faces by `eps` and overlap solids that are intended to
  form one printable body. Do not use that overlap between separate assembly parts.
- Keep `eps` far smaller than the smallest functional tolerance and independent of
  fit clearances.
- For repeated patterns, prove one instance first, then generate the array.
- For a complex `polyhedron()`, establish vertex winding and manifoldness on the
  smallest possible example before adding faces.

Use `hull()` only for the convex envelope that it actually computes. A hull between
two poses is generally not a valid swept volume, especially for rotation. Use motion
checks or explicit swept geometry instead. Avoid broad `minkowski()` operations on
high-resolution meshes; they multiply complexity and memory use. Prefer offsets of a
2D profile, native rounded primitives, or localized operations when equivalent.

## Parameter boundaries and variants

A default size passing does not prove that an adjustable design works at its limits.
Record the supported ranges and add meaningful constraints: positive inner spans,
minimum ligament around a bore, remaining floor under a pocket, and enough material
between repeated features. Use `assert()` for forbidden combinations. Keep acceptance
limits independent of the expressions generating geometry; checking an expression
against itself cannot detect a design mistake.

Use the existing predicate sweep for a cheap first pass (at most 12 values per call):

```text
validate(scad_file="bracket.scad", mode="predicates",
         predicates=["wall >= min_wall",
                     "(boss_d - hole_d) / 2 >= min_ligament"],
         sweep={"variable": "hole_d", "values": [3, 4, 5]})
```

This example assumes those named parameters exist in the model. `valid` requires
the base configuration and every sampled variant to pass. Inspect `sweep.points`
for per-value errors, warnings, and failed expressions; `success` alone only says
the tool ran. `first_failure` follows input order, and `crossing` brackets a change
between adjacent samples, not an exact threshold or proof of continuous validity.

Include the minimum, nominal, and maximum intended values and values near a topology
change, such as two holes merging. For interacting parameters, repeat the sweep with
`variables` fixing the other dimensions at relevant extremes. Independent sweeps
around nominal settings do not cover combinations such as largest bore with smallest
boss. Keep rejected cases explicit instead of silently clamping dimensions.

Predicates evaluate expressions, not the final mesh. For representative variants,
especially the tightest interfaces, run `measure` and `validate(mode="geometry")`
with the same `variables`; for assemblies also run `check(mode="rules")` with those
overrides. Use consistent quality, variables, and part placement across checks and
final exports. Limit the verification claim to the configurations actually tested.

## Tessellation

Do not set a large global `$fn`. Prefer `$fa` and `$fs`, local `$fn` values on the
few critical primitives, or the server's quality control. Select resolution from the
required geometric tolerance: small radii usually need fewer segments than large
radii for the same maximum chord error.

Mesh-derived area, volume, curved clearances, and contact positions vary with
tessellation. When a result is close to a limit, repeat it at higher quality. A value
inside the reported tessellation error bound is unresolved, not passing.

## Imports and libraries

Use `get_libraries` before adding a library dependency. For imported meshes and
complex extrusions, set an adequate `convexity` for correct preview rendering, for
example `import(file, convexity=10)`. `convexity` affects preview visibility, not the
underlying mesh validity.

Treat imported STL geometry as reference data until it has been measured and checked.
Use `measure(mesh=...)` when no SCAD source exists. Do not infer nominal dimensions or
fit intent solely from a tessellated surface.
