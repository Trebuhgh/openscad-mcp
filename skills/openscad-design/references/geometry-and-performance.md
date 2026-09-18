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

