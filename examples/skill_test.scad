// Units: mm. Right-handed, Z up; origin at the centre of the bottom face.
// FDM example: flat bottom on the bed; no fit compensation implied.
width_x = 30;
depth_y = 20;
height_z = 10;
hole_d = 5;
hole_fn = 64;
eps = 0.01;

assert(width_x > hole_d && depth_y > hole_d && hole_d > 0);
assert(height_z > 0 && eps > 0 && hole_fn >= 12);

module part() {
    difference() {
        translate([-width_x/2, -depth_y/2, 0])
            cube([width_x, depth_y, height_z]);
        translate([0, 0, -eps])
            cylinder(d=hole_d, h=height_z + 2*eps, $fn=hole_fn);
    }
}

part();
