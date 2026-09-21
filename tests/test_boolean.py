from zanim import Circle, Difference, Exclusion, Intersection, Union, Vec2, WHITE
from zanim.vector import VectorObject2D


def _pair():
    a = Circle(1, position=(-0.5, 0), fill=WHITE, stroke=None)
    b = Circle(1, position=(0.5, 0), fill=WHITE, stroke=None)
    return a, b


def _contours(obj):
    assert isinstance(obj, VectorObject2D)
    assert obj.backend == "vector"
    if not obj.document.paths:
        return ()
    return obj.document.paths[0].contours


def _poly_points(contour):
    return tuple(seg.p0 for seg in contour.segments)


def _winding(contours, p: Vec2) -> int:
    winding = 0
    for contour in contours:
        points = _poly_points(contour)
        for i, a in enumerate(points):
            b = points[(i + 1) % len(points)]
            side = (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x)
            if a.y <= p.y:
                if b.y > p.y and side > 0:
                    winding += 1
            elif b.y <= p.y and side < 0:
                winding -= 1
    return winding


def test_boolean_results_are_true_vector_paths():
    a, b = _pair()
    results = [Intersection(a, b), Union(a, b), Difference(a, b), Exclusion(a, b)]
    assert all(isinstance(obj, VectorObject2D) for obj in results)
    assert all(obj.backend == "vector" for obj in results)
    assert len(_contours(results[0])) == 1
    assert len(_contours(results[1])) == 1
    assert len(_contours(results[2])) == 1
    assert len(_contours(results[3])) == 2


def test_boolean_vector_semantics():
    a, b = _pair()
    intersection = _contours(Intersection(a, b, stroke_width=0))
    union = _contours(Union(a, b, stroke_width=0))
    difference = _contours(Difference(a, b, stroke_width=0))
    exclusion = _contours(Exclusion(a, b, stroke_width=0))

    assert _winding(intersection, Vec2(0, 0)) != 0
    assert _winding(intersection, Vec2(-1.2, 0)) == 0

    assert _winding(union, Vec2(-1.2, 0)) != 0
    assert _winding(union, Vec2(0, 0)) != 0
    assert _winding(union, Vec2(1.2, 0)) != 0

    assert _winding(difference, Vec2(-1.2, 0)) != 0
    assert _winding(difference, Vec2(0, 0)) == 0

    assert _winding(exclusion, Vec2(-1.2, 0)) != 0
    assert _winding(exclusion, Vec2(0, 0)) == 0
    assert _winding(exclusion, Vec2(1.2, 0)) != 0


def test_boolean_bounds_are_result_bounds():
    a, b = _pair()
    intersection = Intersection(a, b)
    union = Union(a, b)
    difference = Difference(a, b)

    assert intersection.bounds().width < union.bounds().width
    assert difference.bounds().width < union.bounds().width
    assert difference.center.x < 0
