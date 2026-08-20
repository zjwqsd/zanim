from __future__ import annotations

import math

from zanim import (
    BatchObject2D, Canvas, Circle, CircleSet, Color, DOWN, DynamicGeometryObject2D,
    Easing, Group2D, LEFT, Object2D, Polygon, RasterObject2D, Rectangle, RIGHT,
    Scene, Style, Text, Transform2D, UP, Vec2,
)
from zanim.raster import AlphaMaskSource, SceneRasterSource

WHITE = Color(245, 247, 251)
YELLOW = Color(248, 210, 68)
LIGHT_BROWN = Color(183, 139, 100)
PURPLE_E = Color(92, 55, 130)
MASK_CANVAS = Canvas(width=960, height=540, unit_size=67.5)
FRAME_W = MASK_CANVAS.width / MASK_CANVAS.unit_size
FRAME_H = MASK_CANVAS.height / MASK_CANVAS.unit_size


def _subscene() -> Scene:
    return Scene(canvas=MASK_CANVAS, fps=30)


def _full(source) -> RasterObject2D:
    return RasterObject2D(source, width=FRAME_W, height=FRAME_H)


def _smooth(a: float) -> float:
    a=max(0.0,min(1.0,a)); return a*a*(3-2*a)


def _rect_circle_polygon(t: float, *, width=6.1, height=1.25, radius=1.25, count=64) -> Polygon:
    a=_smooth(t)
    pts=[]
    for i in range(count):
        angle=math.tau*i/count
        c,s=math.cos(angle),math.sin(angle)
        scale=min(width/(2*max(abs(c),1e-9)),height/(2*max(abs(s),1e-9)))
        rx,ry=c*scale,s*scale
        cx,cy=c*radius,s*radius
        pts.append(Vec2(rx+(cx-rx)*a,ry+(cy-ry)*a))
    return Polygon(tuple(pts))


def _stage1(duration=4.0) -> Scene:
    content=_subscene()
    chars=[Text(ch,font_size=56) for ch in 'Mask Example!']
    group=Group2D(chars); group.arrange(RIGHT,buff=0.015); group.move_to(Vec2(0,0.45))
    finals=[c.transform for c in chars]
    for c in chars: c.shift(Vec2(0,-1.65))
    content.add(group)
    with content.parallel():
        for i,(c,target) in enumerate(zip(chars,finals)):
            content.play_transform(c,target,duration=1.15,easing=Easing.SMOOTHSTEP,at=0.55+i*0.09)
    content.wait(max(0.0,duration-content.timeline.cursor))

    mask=_subscene()
    mask.add(Object2D(Rectangle(6.25,1.28),transform=Transform2D.translation(0,0.45),style=Style(fill=WHITE,stroke=None)))
    mask.wait(duration)

    stage=_subscene(); stage.add(_full(AlphaMaskSource(SceneRasterSource(content),SceneRasterSource(mask))))
    stage.play_media(stage.objects[0],duration=duration)
    return stage


def _stage2(duration=9.8) -> Scene:
    content=_subscene()
    txt=Text('Mask Example!',font_size=64)
    txt2=Text('The mask should be hold',font_size=54,opacity=0)
    content.add(txt,txt2)
    left=Transform2D.translation(-1,0); right=Transform2D.translation(1,0)
    with content.parallel():
        content.play_transform(txt,left,duration=0.9,at=3.0)
        content.play_transform(txt,right,duration=0.9,at=3.9)
        content.play_transform(txt,Transform2D(),duration=0.9,at=4.8)
        content.fade_out(txt,duration=1.0,at=6.1)
        content.fade_in(txt2,duration=1.0,at=6.1)
    content.wait(max(0.0,duration-content.timeline.cursor))

    mask=_subscene()
    shape=DynamicGeometryObject2D(
        lambda t:_rect_circle_polygon(min(1.0,t/1.1)),
        transform=Transform2D.translation(0,0.5),
        style=Style(fill=WHITE,stroke=None),
    )
    mask.add(shape); mask.wait(duration)
    feather=lambda t: 0.0 if t<2.4 else 10.0*_smooth((t-2.4)/1.0)
    masked=AlphaMaskSource(SceneRasterSource(content),SceneRasterSource(mask),feather=feather)

    stage=_subscene()
    brown=Object2D(Rectangle(3,3),style=Style(fill=LIGHT_BROWN,stroke=None),opacity=0,z_index=-2)
    layer=_full(masked); layer.z_index=1
    stage.add(brown,layer)
    with stage.parallel():
        stage.play_media(layer,duration=duration)
        stage.fade_in(brown,duration=0.8,at=1.8)
        stage.fade_out(brown,duration=0.8,at=7.9)
    return stage


def _circle_mask(center: Vec2, duration: float) -> SceneRasterSource:
    sc=_subscene(); sc.add(Object2D(Circle(1.5),transform=Transform2D.translation(center.x,center.y),style=Style(fill=WHITE,stroke=None))); sc.wait(duration)
    return SceneRasterSource(sc)


def _stage3(duration=6.0) -> Scene:
    text=_subscene(); label=Text('Some Example Text Here',font_size=44); text.add(label); text.wait(duration)
    text_source=SceneRasterSource(text)
    m1=_circle_mask(Vec2(-1,0),duration); m2=_circle_mask(Vec2(1,0),duration)
    union_scene=_subscene()
    union_scene.add(
        Object2D(Circle(1.5),transform=Transform2D.translation(-1,0),style=Style(fill=WHITE,stroke=None)),
        Object2D(Circle(1.5),transform=Transform2D.translation(1,0),style=Style(fill=WHITE,stroke=None)),
    ); union_scene.wait(duration)
    union=AlphaMaskSource(text_source,SceneRasterSource(union_scene))
    intersection_mask=AlphaMaskSource(m1,m2)
    intersection=AlphaMaskSource(text_source,intersection_mask)

    stage=_subscene()
    d1=Object2D(Circle(1.5),transform=Transform2D.translation(-1,0),style=Style(fill=Color(YELLOW.r,YELLOW.g,YELLOW.b,64),stroke=None))
    d2=Object2D(Circle(1.5),transform=Transform2D.translation(1,0),style=Style(fill=Color(YELLOW.r,YELLOW.g,YELLOW.b,64),stroke=None))
    u=_full(union); i=_full(intersection)
    stage.add(d1,d2,u,i)
    # union -> intersection -> union, with brief holds matching the reference rhythm
    stage.play_media(u,duration=1.8)
    stage.play_media(i,duration=1.2)
    stage.play_media(u,duration=1.2)
    stage.wait(duration-stage.timeline.cursor)
    return stage


def _stage4(duration=8.9) -> Scene:
    content=_subscene()
    centers=tuple(Vec2(i*0.3+0.15,j*0.3) for j in range(20,-40,-1) for i in range(-23,23))
    dots=BatchObject2D(CircleSet(centers,tuple(0.10 for _ in centers),tuple(PURPLE_E for _ in centers)))
    content.add(dots)
    content.play_transform(dots,Transform2D.translation(0,3),duration=5.0,easing=Easing.LINEAR)
    content.wait(duration-content.timeline.cursor)

    mask=_subscene(); fashion=Text('Fashion',font_size=250); mask.add(fashion); mask.wait(duration)
    def invert(t): return _smooth((t-4.7)/0.9)
    masked=AlphaMaskSource(SceneRasterSource(content),SceneRasterSource(mask),invert=invert,feather=1.5)
    stage=_subscene(); layer=_full(masked); stage.add(layer); stage.play_media(layer,duration=duration)
    return stage


def build_mask_example() -> Scene:
    main=Scene(canvas=Canvas(width=1920,height=1080,unit_size=135),fps=30)
    for stage in (_stage1(),_stage2(),_stage3(),_stage4()):
        source=SceneRasterSource(stage)
        obj=RasterObject2D(source,width=1920/135,height=1080/135)
        main.add(obj)
        main.play_media(obj,duration=source.duration)
    return main
