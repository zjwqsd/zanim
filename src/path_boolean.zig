const std = @import("std");
const Vec2 = @import("math.zig").Vec2;

pub const Operation = enum(u32) {
    intersection = 0,
    union_ = 1,
    difference = 2,
    exclusion = 3,
};

pub const Shape = struct {
    points: []const Vec2,
    contour_ends: []const u32,
};

pub const Result = struct {
    points: []Vec2,
    contour_ends: []u32,

    pub fn deinit(self: *Result, allocator: std.mem.Allocator) void {
        allocator.free(self.points);
        allocator.free(self.contour_ends);
        self.* = .{ .points = &.{}, .contour_ends = &.{} };
    }
};

const Segment = struct {
    a: Vec2,
    b: Vec2,
};

const DirectedEdge = struct {
    a: Vec2,
    b: Vec2,
};

fn add(a: Vec2, b: Vec2) Vec2 {
    return .{ .x = a.x + b.x, .y = a.y + b.y };
}
fn sub(a: Vec2, b: Vec2) Vec2 {
    return .{ .x = a.x - b.x, .y = a.y - b.y };
}
fn mul(a: Vec2, s: f64) Vec2 {
    return .{ .x = a.x * s, .y = a.y * s };
}
fn dot(a: Vec2, b: Vec2) f64 {
    return a.x * b.x + a.y * b.y;
}
fn cross(a: Vec2, b: Vec2) f64 {
    return a.x * b.y - a.y * b.x;
}
fn lengthSq(a: Vec2) f64 {
    return dot(a, a);
}
fn distanceSq(a: Vec2, b: Vec2) f64 {
    return lengthSq(sub(a, b));
}
fn lerp(a: Vec2, b: Vec2, t: f64) Vec2 {
    return .{ .x = a.x + (b.x - a.x) * t, .y = a.y + (b.y - a.y) * t };
}
fn clamp01(v: f64) f64 {
    return @max(0.0, @min(1.0, v));
}

fn validateShape(shape: Shape) bool {
    if (shape.contour_ends.len == 0 or shape.points.len < 3) return false;
    var previous: usize = 0;
    for (shape.contour_ends) |end_u32| {
        const end: usize = @intCast(end_u32);
        if (end <= previous or end > shape.points.len) return false;
        if (end - previous < 3) return false;
        previous = end;
    }
    return previous == shape.points.len;
}

fn buildSegments(
    allocator: std.mem.Allocator,
    shape: Shape,
    epsilon: f64,
) ![]Segment {
    var out = std.ArrayList(Segment).empty;
    errdefer out.deinit(allocator);

    const eps2 = epsilon * epsilon;
    var start: usize = 0;
    for (shape.contour_ends) |end_u32| {
        const end: usize = @intCast(end_u32);
        var count = end - start;
        if (count >= 2 and distanceSq(shape.points[start], shape.points[end - 1]) <= eps2) {
            count -= 1;
        }
        if (count >= 3) {
            var i: usize = 0;
            while (i < count) : (i += 1) {
                const a = shape.points[start + i];
                const b = shape.points[start + ((i + 1) % count)];
                if (distanceSq(a, b) > eps2) {
                    try out.append(allocator, .{ .a = a, .b = b });
                }
            }
        }
        start = end;
    }
    return try out.toOwnedSlice(allocator);
}

fn pointInside(shape: Shape, p: Vec2, epsilon: f64) bool {
    var winding: i32 = 0;
    var start: usize = 0;
    const eps2 = epsilon * epsilon;
    for (shape.contour_ends) |end_u32| {
        const end: usize = @intCast(end_u32);
        var count = end - start;
        if (count >= 2 and distanceSq(shape.points[start], shape.points[end - 1]) <= eps2) {
            count -= 1;
        }
        if (count < 3) {
            start = end;
            continue;
        }

        var i: usize = 0;
        while (i < count) : (i += 1) {
            const a = shape.points[start + i];
            const b = shape.points[start + ((i + 1) % count)];
            const side = cross(sub(b, a), sub(p, a));
            if (a.y <= p.y) {
                if (b.y > p.y and side > epsilon) winding += 1;
            } else {
                if (b.y <= p.y and side < -epsilon) winding -= 1;
            }
        }
        start = end;
    }
    return winding != 0;
}

fn resultInside(operation: Operation, inside_a: bool, inside_b: bool) bool {
    return switch (operation) {
        .intersection => inside_a and inside_b,
        .union_ => inside_a or inside_b,
        .difference => inside_a and !inside_b,
        .exclusion => inside_a != inside_b,
    };
}

fn addSplitUnique(
    allocator: std.mem.Allocator,
    splits: *std.ArrayList(f64),
    value_raw: f64,
    epsilon: f64,
) !void {
    const value = clamp01(value_raw);
    for (splits.items) |existing| {
        if (@abs(existing - value) <= epsilon) return;
    }
    try splits.append(allocator, value);
}

fn addPairIntersections(
    allocator: std.mem.Allocator,
    a: Segment,
    b: Segment,
    a_splits: *std.ArrayList(f64),
    b_splits: *std.ArrayList(f64),
    epsilon: f64,
) !void {
    const r = sub(a.b, a.a);
    const s = sub(b.b, b.a);
    const qp = sub(b.a, a.a);
    const rxs = cross(r, s);
    const qpxr = cross(qp, r);

    if (@abs(rxs) > epsilon) {
        const t = cross(qp, s) / rxs;
        const u = qpxr / rxs;
        if (t >= -epsilon and t <= 1.0 + epsilon and u >= -epsilon and u <= 1.0 + epsilon) {
            try addSplitUnique(allocator, a_splits, t, epsilon);
            try addSplitUnique(allocator, b_splits, u, epsilon);
        }
        return;
    }

    if (@abs(qpxr) > epsilon) return;

    const rr = lengthSq(r);
    const ss = lengthSq(s);
    if (rr <= epsilon * epsilon or ss <= epsilon * epsilon) return;

    const ta0 = dot(sub(b.a, a.a), r) / rr;
    const ta1 = dot(sub(b.b, a.a), r) / rr;
    if (ta0 >= -epsilon and ta0 <= 1.0 + epsilon) try addSplitUnique(allocator, a_splits, ta0, epsilon);
    if (ta1 >= -epsilon and ta1 <= 1.0 + epsilon) try addSplitUnique(allocator, a_splits, ta1, epsilon);

    const ub0 = dot(sub(a.a, b.a), s) / ss;
    const ub1 = dot(sub(a.b, b.a), s) / ss;
    if (ub0 >= -epsilon and ub0 <= 1.0 + epsilon) try addSplitUnique(allocator, b_splits, ub0, epsilon);
    if (ub1 >= -epsilon and ub1 <= 1.0 + epsilon) try addSplitUnique(allocator, b_splits, ub1, epsilon);
}

fn classifyBoundaryEdge(
    segment: DirectedEdge,
    a_shape: Shape,
    b_shape: Shape,
    operation: Operation,
    epsilon: f64,
) ?DirectedEdge {
    const d = sub(segment.b, segment.a);
    const len2 = lengthSq(d);
    if (len2 <= epsilon * epsilon) return null;
    const len = @sqrt(len2);
    const midpoint = mul(add(segment.a, segment.b), 0.5);
    const nx = -d.y / len;
    const ny = d.x / len;

    // Probe just off the exact boundary. Scale epsilon by edge length so very
    // short split edges still classify reliably without crossing nearby detail.
    const probe = @max(epsilon * 8.0, @min(len * 1e-4, 1e-5));
    const left = Vec2{ .x = midpoint.x + nx * probe, .y = midpoint.y + ny * probe };
    const right = Vec2{ .x = midpoint.x - nx * probe, .y = midpoint.y - ny * probe };

    const left_inside = resultInside(
        operation,
        pointInside(a_shape, left, epsilon),
        pointInside(b_shape, left, epsilon),
    );
    const right_inside = resultInside(
        operation,
        pointInside(a_shape, right, epsilon),
        pointInside(b_shape, right, epsilon),
    );

    if (left_inside == right_inside) return null;
    if (left_inside) return segment;
    return .{ .a = segment.b, .b = segment.a };
}

fn samePoint(a: Vec2, b: Vec2, epsilon: f64) bool {
    return distanceSq(a, b) <= epsilon * epsilon;
}

fn sameDirectedEdge(a: DirectedEdge, b: DirectedEdge, epsilon: f64) bool {
    return samePoint(a.a, b.a, epsilon) and samePoint(a.b, b.b, epsilon);
}

fn appendUniqueEdge(
    allocator: std.mem.Allocator,
    edges: *std.ArrayList(DirectedEdge),
    edge: DirectedEdge,
    epsilon: f64,
) !void {
    for (edges.items) |existing| {
        if (sameDirectedEdge(existing, edge, epsilon)) return;
    }
    try edges.append(allocator, edge);
}

fn splitAndClassify(
    allocator: std.mem.Allocator,
    segments: []const Segment,
    splits: []std.ArrayList(f64),
    a_shape: Shape,
    b_shape: Shape,
    operation: Operation,
    epsilon: f64,
    out: *std.ArrayList(DirectedEdge),
) !void {
    var i: usize = 0;
    while (i < segments.len) : (i += 1) {
        const values = splits[i].items;
        std.mem.sort(f64, values, {}, comptime std.sort.asc(f64));
        if (values.len < 2) continue;

        var j: usize = 0;
        while (j + 1 < values.len) : (j += 1) {
            if (values[j + 1] - values[j] <= epsilon) continue;
            const candidate = DirectedEdge{
                .a = lerp(segments[i].a, segments[i].b, values[j]),
                .b = lerp(segments[i].a, segments[i].b, values[j + 1]),
            };
            if (classifyBoundaryEdge(candidate, a_shape, b_shape, operation, epsilon)) |edge| {
                try appendUniqueEdge(allocator, out, edge, epsilon * 8.0);
            }
        }
    }
}

fn removeCollinear(points: *std.ArrayList(Vec2), epsilon: f64) void {
    if (points.items.len < 3) return;
    var changed = true;
    while (changed and points.items.len >= 3) {
        changed = false;
        var i: usize = 0;
        while (i < points.items.len) : (i += 1) {
            const n = points.items.len;
            const prev = points.items[(i + n - 1) % n];
            const cur = points.items[i];
            const next = points.items[(i + 1) % n];
            const a = sub(cur, prev);
            const b = sub(next, cur);
            const scale = @sqrt(lengthSq(a) * lengthSq(b));
            if (scale > 0 and @abs(cross(a, b)) <= epsilon * scale) {
                _ = points.orderedRemove(i);
                changed = true;
                break;
            }
        }
    }
}

fn buildContours(
    allocator: std.mem.Allocator,
    edges: []const DirectedEdge,
    epsilon: f64,
) !Result {
    var used = try allocator.alloc(bool, edges.len);
    defer allocator.free(used);
    @memset(used, false);

    var points_out = std.ArrayList(Vec2).empty;
    errdefer points_out.deinit(allocator);
    var ends_out = std.ArrayList(u32).empty;
    errdefer ends_out.deinit(allocator);

    var seed: usize = 0;
    while (seed < edges.len) : (seed += 1) {
        if (used[seed]) continue;

        var contour = std.ArrayList(Vec2).empty;
        defer contour.deinit(allocator);

        const start = edges[seed].a;
        var current = edges[seed].b;
        used[seed] = true;
        try contour.append(allocator, start);
        try contour.append(allocator, current);

        var guard: usize = 0;
        while (!samePoint(current, start, epsilon * 12.0)) {
            guard += 1;
            if (guard > edges.len + 2) return error.OpenContour;

            var found: ?usize = null;
            var best_clockwise = std.math.inf(f64);
            const previous = contour.items[contour.items.len - 2];
            const incoming = sub(current, previous);
            const reverse_incoming = mul(incoming, -1.0);

            var k: usize = 0;
            while (k < edges.len) : (k += 1) {
                if (used[k]) continue;
                if (!samePoint(edges[k].a, current, epsilon * 12.0)) continue;
                const outgoing = sub(edges[k].b, edges[k].a);
                const signed = std.math.atan2(cross(reverse_incoming, outgoing), dot(reverse_incoming, outgoing));
                var clockwise = -signed;
                while (clockwise < 0) clockwise += std.math.tau;
                while (clockwise >= std.math.tau) clockwise -= std.math.tau;
                if (clockwise < best_clockwise) {
                    best_clockwise = clockwise;
                    found = k;
                }
            }
            if (found == null) return error.OpenContour;
            const idx = found.?;
            used[idx] = true;
            current = edges[idx].b;
            if (!samePoint(current, start, epsilon * 12.0)) {
                try contour.append(allocator, current);
            }
        }

        removeCollinear(&contour, epsilon * 16.0);
        if (contour.items.len >= 3) {
            try points_out.appendSlice(allocator, contour.items);
            try ends_out.append(allocator, @intCast(points_out.items.len));
        }
    }

    return .{
        .points = try points_out.toOwnedSlice(allocator),
        .contour_ends = try ends_out.toOwnedSlice(allocator),
    };
}

pub fn combine(
    allocator: std.mem.Allocator,
    a_shape: Shape,
    b_shape: Shape,
    operation: Operation,
    epsilon_raw: f64,
) !Result {
    if (!validateShape(a_shape) or !validateShape(b_shape)) return error.InvalidShape;
    const epsilon = if (epsilon_raw > 0 and std.math.isFinite(epsilon_raw)) epsilon_raw else 1e-9;

    const a_segments = try buildSegments(allocator, a_shape, epsilon);
    defer allocator.free(a_segments);
    const b_segments = try buildSegments(allocator, b_shape, epsilon);
    defer allocator.free(b_segments);

    var a_splits = try allocator.alloc(std.ArrayList(f64), a_segments.len);
    defer allocator.free(a_splits);
    var b_splits = try allocator.alloc(std.ArrayList(f64), b_segments.len);
    defer allocator.free(b_splits);

    for (a_splits) |*list| list.* = .empty;
    for (b_splits) |*list| list.* = .empty;
    defer for (a_splits) |*list| list.deinit(allocator);
    defer for (b_splits) |*list| list.deinit(allocator);

    for (a_splits) |*list| {
        try list.append(allocator, 0.0);
        try list.append(allocator, 1.0);
    }
    for (b_splits) |*list| {
        try list.append(allocator, 0.0);
        try list.append(allocator, 1.0);
    }

    var i: usize = 0;
    while (i < a_segments.len) : (i += 1) {
        var j: usize = 0;
        while (j < b_segments.len) : (j += 1) {
            try addPairIntersections(
                allocator,
                a_segments[i],
                b_segments[j],
                &a_splits[i],
                &b_splits[j],
                epsilon,
            );
        }
    }

    var boundary = std.ArrayList(DirectedEdge).empty;
    defer boundary.deinit(allocator);

    try splitAndClassify(
        allocator,
        a_segments,
        a_splits,
        a_shape,
        b_shape,
        operation,
        epsilon,
        &boundary,
    );
    try splitAndClassify(
        allocator,
        b_segments,
        b_splits,
        a_shape,
        b_shape,
        operation,
        epsilon,
        &boundary,
    );

    if (boundary.items.len == 0) {
        return .{
            .points = try allocator.alloc(Vec2, 0),
            .contour_ends = try allocator.alloc(u32, 0),
        };
    }
    return buildContours(allocator, boundary.items, epsilon);
}

fn polygonShape(points: []const Vec2) Shape {
    const ends = &[_]u32{@intCast(points.len)};
    return .{ .points = points, .contour_ends = ends };
}

test "vector boolean overlapping rectangles" {
    const allocator = std.testing.allocator;
    const a = [_]Vec2{
        .{ .x = -2, .y = -1 }, .{ .x = 1, .y = -1 },
        .{ .x = 1, .y = 1 }, .{ .x = -2, .y = 1 },
    };
    const b = [_]Vec2{
        .{ .x = -1, .y = -2 }, .{ .x = 2, .y = -2 },
        .{ .x = 2, .y = 2 }, .{ .x = -1, .y = 2 },
    };

    var inter = try combine(allocator, polygonShape(&a), polygonShape(&b), .intersection, 1e-9);
    defer inter.deinit(allocator);
    try std.testing.expectEqual(@as(usize, 1), inter.contour_ends.len);
    try std.testing.expect(inter.points.len >= 4);

    var uni = try combine(allocator, polygonShape(&a), polygonShape(&b), .union_, 1e-9);
    defer uni.deinit(allocator);
    try std.testing.expectEqual(@as(usize, 1), uni.contour_ends.len);
    try std.testing.expect(uni.points.len >= 8);

    var diff = try combine(allocator, polygonShape(&a), polygonShape(&b), .difference, 1e-9);
    defer diff.deinit(allocator);
    try std.testing.expectEqual(@as(usize, 1), diff.contour_ends.len);

    var xor = try combine(allocator, polygonShape(&a), polygonShape(&b), .exclusion, 1e-9);
    defer xor.deinit(allocator);
    try std.testing.expectEqual(@as(usize, 2), xor.contour_ends.len);
}

test "vector boolean disjoint union yields two contours" {
    const allocator = std.testing.allocator;
    const a = [_]Vec2{
        .{ .x = -3, .y = -1 }, .{ .x = -1, .y = -1 },
        .{ .x = -1, .y = 1 }, .{ .x = -3, .y = 1 },
    };
    const b = [_]Vec2{
        .{ .x = 1, .y = -1 }, .{ .x = 3, .y = -1 },
        .{ .x = 3, .y = 1 }, .{ .x = 1, .y = 1 },
    };
    var result = try combine(allocator, polygonShape(&a), polygonShape(&b), .union_, 1e-9);
    defer result.deinit(allocator);
    try std.testing.expectEqual(@as(usize, 2), result.contour_ends.len);
}

fn signedArea(points: []const Vec2) f64 {
    var area: f64 = 0;
    if (points.len < 3) return 0;
    var j: usize = points.len - 1;
    for (points, 0..) |p, i| {
        const q = points[j];
        area += q.x * p.y - p.x * q.y;
        j = i;
    }
    return area * 0.5;
}

test "difference containment emits outer contour and hole with opposite orientation" {
    const allocator = std.testing.allocator;
    const outer = [_]Vec2{
        .{ .x = -3, .y = -3 }, .{ .x = 3, .y = -3 },
        .{ .x = 3, .y = 3 }, .{ .x = -3, .y = 3 },
    };
    const inner = [_]Vec2{
        .{ .x = -1, .y = -1 }, .{ .x = 1, .y = -1 },
        .{ .x = 1, .y = 1 }, .{ .x = -1, .y = 1 },
    };
    var result = try combine(allocator, polygonShape(&outer), polygonShape(&inner), .difference, 1e-9);
    defer result.deinit(allocator);
    try std.testing.expectEqual(@as(usize, 2), result.contour_ends.len);
    const first_end: usize = @intCast(result.contour_ends[0]);
    const second_end: usize = @intCast(result.contour_ends[1]);
    const a0 = signedArea(result.points[0..first_end]);
    const a1 = signedArea(result.points[first_end..second_end]);
    try std.testing.expect(a0 * a1 < 0);
}

test "identical polygons deduplicate coincident boundaries" {
    const allocator = std.testing.allocator;
    const square = [_]Vec2{
        .{ .x = -1, .y = -1 }, .{ .x = 1, .y = -1 },
        .{ .x = 1, .y = 1 }, .{ .x = -1, .y = 1 },
    };
    var uni = try combine(allocator, polygonShape(&square), polygonShape(&square), .union_, 1e-9);
    defer uni.deinit(allocator);
    try std.testing.expectEqual(@as(usize, 1), uni.contour_ends.len);
    try std.testing.expectEqual(@as(usize, 4), uni.points.len);

    var diff = try combine(allocator, polygonShape(&square), polygonShape(&square), .difference, 1e-9);
    defer diff.deinit(allocator);
    try std.testing.expectEqual(@as(usize, 0), diff.contour_ends.len);
    try std.testing.expectEqual(@as(usize, 0), diff.points.len);
}

test "disjoint intersection is empty" {
    const allocator = std.testing.allocator;
    const a = [_]Vec2{
        .{ .x = -3, .y = -1 }, .{ .x = -1, .y = -1 },
        .{ .x = -1, .y = 1 }, .{ .x = -3, .y = 1 },
    };
    const b = [_]Vec2{
        .{ .x = 1, .y = -1 }, .{ .x = 3, .y = -1 },
        .{ .x = 3, .y = 1 }, .{ .x = 1, .y = 1 },
    };
    var result = try combine(allocator, polygonShape(&a), polygonShape(&b), .intersection, 1e-9);
    defer result.deinit(allocator);
    try std.testing.expectEqual(@as(usize, 0), result.contour_ends.len);
}
