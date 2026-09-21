
from math import isclose
from zanim import Circle, Dot, Easing, Scene, WORLD, Vec2

def test_circle():
    scene=Scene()
    circle=scene.add(Circle(1, fill=None))
    dot=scene.add(Dot((1,0)))
    dot.move_along(circle,duration=2,easing=Easing.LINEAR)
    pts=[scene.world_transform(dot.raw,time=t).apply(Vec2()) for t in (0,.5,1,1.5,2)]
    expected=[(1,0),(0,1),(-1,0),(0,-1),(1,0)]
    for q,(x,y) in zip(pts,expected):
        assert isclose(q.x,x,abs_tol=3e-3)
        assert isclose(q.y,y,abs_tol=3e-3)
    assert isclose(scene.duration,2)

def test_snapshot():
    scene=Scene()
    circle=scene.add(Circle(1,fill=None))
    dot=scene.add(Dot((1,0)))
    circle.move(by=(2,0),frame=WORLD,duration=1)
    dot.move(by=(2,0),frame=WORLD,duration=1)
    dot.move_along(circle,duration=2,easing=Easing.LINEAR)
    mid=scene.world_transform(dot.raw,time=3).apply(Vec2())
    assert isclose(mid.x,1,abs_tol=3e-3)
    assert isclose(mid.y,0,abs_tol=3e-3)
