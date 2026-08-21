from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Callable

from zanim import (
    Axes2D, Canvas, Circle, Color, DOWN, DynamicGeometryObject2D,
    DynamicNumber, DynamicVectorObject2D, Easing, Group2D, Line, Math,
    NumberFormat, Object2D, Polygon, Polyline, Rectangle,
    RIGHT, Scene, Square, StrokeStyle, Style, Text, Transform2D,
    Vec2, VectorDocument, VectorPath, affine2d,
)

from .frame_effect_example import build_frame_effect_example
from .mask_example import build_mask_example
from .three_d_shapes_example import build_three_d_shapes_example
from zanim.vector import map_vector_document

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "media" / "janim_api"
CANVAS = Canvas(width=1920, height=1080, unit_size=135)
BG = Color(14, 17, 24)
WHITE = Color(238, 241, 247)
BLUE = Color(80, 145, 255)
BLUE_E = Color(34, 75, 135)
GREEN = Color(80, 210, 135)
RED = Color(245, 82, 98)
YELLOW = Color(250, 210, 78)
GOLD = Color(245, 180, 55)
ORANGE = Color(245, 135, 55)
PURPLE = Color(170, 100, 230)
MAROON = Color(185, 70, 105)
LIGHT_BROWN = Color(183, 139, 100)
PURPLE_E = Color(92, 55, 130)
TAU = math.tau
PI = math.pi


def scene() -> Scene:
    return Scene(canvas=CANVAS, fps=30)


def stroke(color=WHITE, width=0.035, alpha=255):
    return StrokeStyle(color.with_alpha(alpha), width)


def outlined(color=WHITE, fill=None, width=0.035):
    return Style.outline(color, width) if fill is None else Style.paint(fill, color, width)


def filled(color, alpha=255, stroke_color=None, stroke_width=0.025):
    fill = color.with_alpha(alpha)
    return Style.solid(fill) if stroke_color is None else Style.paint(fill, stroke_color, stroke_width)


def star_points(outer=1.0, inner=0.45, count=5, phase=PI/2):
    pts=[]
    for i in range(count*2):
        r=outer if i%2==0 else inner
        a=phase+i*PI/count
        pts.append(Vec2(r*math.cos(a), r*math.sin(a)))
    return tuple(pts)


def square_polygon(side: float, transform: Transform2D = Transform2D()) -> Polygon:
    h=side/2
    return Polygon(tuple(transform.apply(Vec2(x,y)) for x,y in ((-h,-h),(h,-h),(h,h),(-h,h))))


def circle_polygon(center: Vec2, radius: float, samples=48) -> Polygon:
    return Polygon(tuple(Vec2(center.x+radius*math.cos(TAU*i/samples), center.y+radius*math.sin(TAU*i/samples)) for i in range(samples)))


def triangle_polygon(center: Vec2, radius: float, phase=PI/2) -> Polygon:
    return Polygon(tuple(Vec2(center.x+radius*math.cos(phase+TAU*i/3), center.y+radius*math.sin(phase+TAU*i/3)) for i in range(3)))


def sector_polygon(start: float, sweep: float, radius: float, center=Vec2(), samples=30) -> Polygon:
    return Polygon((center, *tuple(Vec2(center.x+radius*math.cos(start+sweep*i/samples), center.y+radius*math.sin(start+sweep*i/samples)) for i in range(samples+1))))


def show_now(sc: Scene, obj):
    # add() itself means "exists from now"; no opacity trick is needed.
    sc.add(obj)
    return obj


def add_reveal_group(sc: Scene, group: Group2D, duration=1.0, lag=0.04):
    for child in group.children:
        if isinstance(child, (Text, Math)):
            child.reveal = 0.0
        else:
            child.opacity = 0.0
    sc.add(group)
    with sc.parallel():
        for i, child in enumerate(group.children):
            if isinstance(child, (Text, Math)):
                sc.reveal(child, duration=max(0.15, duration-lag*i), at=lag*i)
            else:
                sc.fade_in(child, duration=max(0.15, duration-lag*i), at=lag*i)


def hello_janim() -> Scene:
    sc=scene()
    circle=Object2D(Circle(1.0), stroke=BLUE, stroke_width=0.045, trim=0.0)
    circle=sc.add(circle)
    sc.wait(1)
    circle.create(duration=1)

    # This is a lifetime handoff, not a pure interpolation relation:
    # circle leaves when the morph starts, square joins when it finishes.
    square=Object2D(Square(2.0), fill=GREEN.with_alpha(128), stroke=GREEN, stroke_width=0.045)
    square=sc.replace(circle, square, duration=1)
    square.trim(to=0.0, duration=1)
    sc.wait(1)
    return sc


def basic_animation() -> Scene:
    sc=scene()
    circle=Object2D(Circle(1), stroke=WHITE, stroke_width=0.045, trim=0.0)
    star=Object2D(Polygon(star_points()), stroke=WHITE, stroke_width=0.045, scale=0.0)
    circle, star=sc.add(circle, star)
    sc.wait(1)

    circle.create()
    circle.affine(to=(-3, 0), scale=1.5)
    circle.paint(fill=RED.with_alpha(128), stroke=RED, stroke_width=0.045)

    star.transform_function(lambda a: affine2d(rotation=TAU*a, scale=1.5*a), duration=1)
    star.affine(to=(3, 0), scale=1.5)
    star.paint(fill=YELLOW.with_alpha(128), stroke=YELLOW, stroke_width=0.045)

    sc.wait(1)
    return sc


def rich_line(parts, font_size=28):
    children=[]
    for text,color,size_scale in parts:
        children.append(Text(text,font_size=font_size*size_scale,color=color))
    g=Group2D(children)
    g.arrange(RIGHT,buff=0.02)
    return g


def text_example() -> Scene:
    sc=scene()
    title=Text('Here is some text',font_size=64,reveal=0)
    d0=rich_line([
        ('You can also apply ',WHITE,1),('styles',BLUE,1),(' to the text.',WHITE,1)
    ])
    d1=rich_line([
        ('You can also apply ',WHITE,1),('styles',GREEN,1.4),(' to the text.',WHITE,1)
    ])
    title.move_to(Vec2(0,0.7)); d0.move_to(Vec2(0,-0.6)); d1.move_to(Vec2(0,-0.6))
    d0.opacity = 0.0; d1.opacity = 0.0
    sc.add(title,d0,d1)
    sc.wait(1)
    sc.reveal(title, duration=1)
    sc.fade_in(d0,duration=1)
    with sc.parallel():
        sc.fade_out(d0,duration=1)
        sc.fade_in(d1,duration=1)
    sc.wait(1)
    return sc


def typst_example() -> Scene:
    sc=scene()
    lines=[
        Text('Zanim provides Text and Math classes to insert Typst content.',font_size=27),
        Text('Math expressions are also supported.',font_size=27),
        Math('A = pi r^2',font_size=34),
        Math('"area" = pi dot "radius"^2',font_size=34),
        Math('cal(A) := { x in RR | x "is natural" }',font_size=31),
        Math('5 < 17',font_size=34),
        Text('Vector documents can also be composed as a full Typst-style document.',font_size=26),
    ]
    for item in lines: item.reveal = 0.0
    doc=Group2D(lines)
    doc.arrange(DOWN,buff=0.25)
    doc.move_to(Vec2(0,0.3))
    sc.add(doc)
    with sc.parallel():
        for i,item in enumerate(lines):
            sc.reveal(item,duration=3.2,at=i*0.12)
    sc.wait(1)
    sc.fade_out(doc,duration=1)

    cells=[
        Text('TypstText',font_size=34,color=BLUE),
        Text('This is a sentence with a math expression f(x)=x²',font_size=27),
        Text('TypstMath',font_size=34,color=BLUE),
        Math('sum_(i=1)^n x_i = x_1 + x_2 + dots.c + x_n',font_size=31),
    ]
    for item in cells: item.reveal = 0.0
    grid=Group2D(cells)
    # 2x2 manual layout closer to JAnim's arrange_in_grid.
    for item,pos in zip(cells,[Vec2(-3,0.8),Vec2(3,0.8),Vec2(-3,-0.8),Vec2(3,-0.8)]): item.move_to(pos)
    sc.add(grid)
    with sc.parallel():
        for i,item in enumerate(cells): sc.reveal(item,duration=1.5,at=i*0.10)
    sc.wait(1)
    sc.fade_out(grid,duration=1)
    return sc


def token_formula(tokens, font_size=95):
    objs=[Math(tok,font_size=font_size) for tok in tokens]
    g=Group2D(objs); g.arrange(RIGHT,buff=0.04); g.move_to(Vec2())
    return g,objs


def typst_colorize() -> Scene:
    sc=scene()
    tokens=['cos','space^2','theta','+','sin','space^2','theta','=','1']
    base,objs=token_formula(tokens)
    sc.add(base)
    sc.wait(1)

    def recolor(index,color,duration=1):
        old=objs[index]
        new=Math(tokens[index],font_size=95,color=color,transform=old.transform,opacity=0)
        sc.add(new)
        with sc.parallel():
            sc.fade_out(old,duration=duration)
            sc.fade_in(new,duration=duration)
        objs[index]=new

    recolor(0,BLUE)
    recolor(4,BLUE)
    recolor(2,GOLD)
    recolor(6,ORANGE)
    sc.wait(1)

    def recolor_many(indices, colors):
        replacements=[]
        for index,color in zip(indices,colors):
            old_obj=objs[index]
            new_obj=Math(tokens[index],font_size=95,color=color,transform=old_obj.transform,opacity=0)
            sc.add(new_obj); replacements.append((index,old_obj,new_obj))
        with sc.parallel():
            for _,old_obj,new_obj in replacements:
                sc.fade_out(old_obj,duration=1); sc.fade_in(new_obj,duration=1)
        for index,_,new_obj in replacements: objs[index]=new_obj

    recolor_many((2,6),(GREEN,GREEN))
    recolor_many((1,5),(RED,RED))
    sc.wait(1)
    return sc


def _lerp_color(a: Color, b: Color, alpha: float) -> Color:
    u=max(0.0,min(1.0,float(alpha)))
    return Color(*(
        round(x+(y-x)*u)
        for x,y in zip((a.r,a.g,a.b,a.a),(b.r,b.g,b.b,b.a))
    ))


def _recolor_vector(document: VectorDocument, color: Color) -> VectorDocument:
    paths=[]
    for path in document.paths:
        fill=color if path.fill is not None else None
        stroke_style=(
            StrokeStyle(color,path.stroke.width)
            if path.stroke is not None else None
        )
        paths.append(VectorPath(path.contours,fill=fill,stroke=stroke_style,group=path.group))
    return VectorDocument(tuple(paths),document.width,document.height,document.group_count)


def _pi_grid_document() -> VectorDocument:
    glyph=Math('pi',font_size=24,color=WHITE).document
    paths=[]
    for row in range(10):
        for col in range(10):
            transform=affine2d(to=((col-4.5)*0.68,(4.5-row)*0.62))
            placed=map_vector_document(glyph,transform.apply)
            for path in placed.paths:
                paths.append(VectorPath(path.contours,path.fill,path.stroke,0))
    return VectorDocument(
        tuple(paths),
        width=9*0.68+glyph.width,
        height=9*0.62+glyph.height,
        group_count=1,
    )


def animating_pi() -> Scene:
    sc=scene()
    base=_pi_grid_document()
    white=_recolor_vector(base,WHITE)
    yellow=_recolor_vector(base,YELLOW)
    blue=_recolor_vector(base,BLUE)
    shifted_yellow=map_vector_document(yellow,Transform2D.translation(-1,0).apply)

    fit=Transform2D.scaling(0.66/0.68,0.66/0.62)
    fitted_blue=map_vector_document(blue,fit.apply)

    def exp_point(p: Vec2) -> Vec2:
        magnitude=math.exp(p.x)
        return Vec2(magnitude*math.cos(p.y),magnitude*math.sin(p.y))

    exp_blue=map_vector_document(fitted_blue,exp_point)

    def wave_point(p: Vec2) -> Vec2:
        return Vec2(p.x+0.5*math.sin(p.y),p.y+0.5*math.sin(p.x))

    final_blue=map_vector_document(exp_blue,wave_point)

    def smooth(alpha: float) -> float:
        return Easing.SMOOTHSTEP.apply(alpha)

    def lerp_point(a: Vec2,b: Vec2,u: float) -> Vec2:
        return Vec2(a.x+(b.x-a.x)*u,a.y+(b.y-a.y)*u)

    def affine_between(a: Transform2D,b: Transform2D,u: float) -> Transform2D:
        return Transform2D(
            xx=a.xx+(b.xx-a.xx)*u, xy=a.xy+(b.xy-a.xy)*u,
            yx=a.yx+(b.yx-a.yx)*u, yy=a.yy+(b.yy-a.yy)*u,
            tx=a.tx+(b.tx-a.tx)*u, ty=a.ty+(b.ty-a.ty)*u,
        )

    shift=Transform2D.translation(-1,0)

    def document_at(t: float) -> VectorDocument:
        # Color changes are document paint changes; geometry and color remain
        # one dynamic vector value rather than 100 independently-updated glyphs.
        if t < 1:
            color_doc=white
        elif t < 2:
            color_doc=_recolor_vector(base,_lerp_color(WHITE,YELLOW,smooth(t-1)))
        elif t < 3:
            return shifted_yellow
        elif t < 4:
            color_doc=_recolor_vector(base,_lerp_color(YELLOW,BLUE,smooth(t-3)))
        else:
            color_doc=blue

        if t < 1:
            return map_vector_document(color_doc,Transform2D.translation(-smooth(t),0).apply)
        if t < 5:
            return map_vector_document(color_doc,shift.apply)
        if t < 6:
            transform=affine_between(shift,fit,smooth(t-5))
            return map_vector_document(color_doc,transform.apply)
        if t < 7:
            return fitted_blue
        if t < 12:
            u=smooth((t-7)/5)
            return map_vector_document(
                fitted_blue,
                lambda p: lerp_point(p,exp_point(p),u),
            )
        if t < 13:
            return exp_blue
        if t < 18:
            u=smooth((t-13)/5)
            return map_vector_document(
                exp_blue,
                lambda p: lerp_point(p,wave_point(p),u),
            )
        return final_blue

    grid=DynamicVectorObject2D(document_at)
    sc.add(grid)
    sc.wait(19)
    return sc


def number_plane() -> Scene:
    sc=scene()
    axes=Axes2D((-7,7),(-4,4),width=14,height=8)
    # Individual lines allow a true write-like stagger rather than batch fade.
    lines=[]
    for x in range(-7,8):
        lines.append(Object2D(Line(axes.c2p(x,-4),axes.c2p(x,4)), stroke=Color(95,105,130,120), stroke_width=0.012, trim=0.0))
    for y in range(-4,5):
        lines.append(Object2D(Line(axes.c2p(-7,y),axes.c2p(7,y)), stroke=Color(95,105,130,120), stroke_width=0.012, trim=0.0))
    plane=Group2D(lines)
    graph=axes.plot(math.sin,samples=320,color=BLUE,stroke_width=0.035)
    graph.trim = 0.0
    plane, graph = sc.add(plane, graph)
    lines = [sc.on(line) for line in lines]
    sc.wait(0.2)
    with sc.parallel():
        for i,line in enumerate(lines): line.create(duration=1.2,at=i*0.03)
    graph.create()
    sc.wait(1)
    matrix=Transform2D(xx=3,xy=-1,yx=1,yy=2)
    with sc.parallel():
        plane.transform(to=matrix, duration=2)
        graph.transform(to=matrix, duration=2)
    sc.wait(1)
    return sc


def updater_example() -> Scene:
    sc=scene()
    # Piecewise width function matches the square's visible animation exactly.
    def width_at(t):
        if t < 1: return 2.0
        if t < 2:
            a=(t-1); return 2*(1+a)
        if t < 3:
            a=t-2; return 4*(1-0.5*a)
        if t < 4:
            a=t-3; return 2+3*a
        if t < 9:
            a=(t-4)/5; return 5+2.5*math.sin(a*5)
        return 5.0
    def sq_geom(t): return Rectangle(max(0.05,width_at(t)),2.0)
    square=DynamicGeometryObject2D(sq_geom,style=filled(BLUE_E,255),z_index=0)
    def brace_geom(t):
        w=width_at(t); y=1.35; h=0.22
        return Polyline((Vec2(-w/2,y-h),Vec2(-w/2,y),Vec2(-0.12,y),Vec2(0,y+h),Vec2(0.12,y),Vec2(w/2,y),Vec2(w/2,y-h)))
    brace=DynamicGeometryObject2D(brace_geom, style=Style.outline(WHITE, 0.03), z_index=1)
    prefix=Text('Width =',font_size=25,transform=affine2d(to=(-0.55,2.05)))
    number=DynamicNumber(width_at,number_format=NumberFormat(width=5,decimals=2,sign='space'),font_size=25,transform=affine2d(to=(0.55,2.05)))
    sc.add(square,brace,prefix,number)
    # Timeline length/phase boundaries are encoded in width_at.
    sc.wait(1); sc.wait(1); sc.wait(1); sc.wait(1); sc.wait(5); sc.wait(1)
    return sc


def arrow_pointing() -> Scene:
    sc=scene()
    p1=Vec2(-3,0)
    def p2(t):
        a=TAU*max(0,min(1,t/4)); return Vec2(2-2*math.cos(a),-2*math.sin(a))
    dot1=Object2D(Circle(0.08), position=p1, fill=WHITE)
    dot2=Object2D(Circle(0.08), fill=WHITE)
    dot1, dot2 = sc.add(dot1,dot2)
    dot2.transform_function(lambda a: affine2d(to=(2-2*math.cos(TAU*a), -2*math.sin(TAU*a))), duration=4, easing=Easing.LINEAR)
    def arrow_poly(t):
        a=p1; b=p2(t); dx,dy=b.x-a.x,b.y-a.y; L=max(1e-6,math.hypot(dx,dy)); ux,uy=dx/L,dy/L; nx,ny=-uy,ux
        tip=min(0.22,L*0.25); shaft=0.025; half=0.075; bx,by=b.x-ux*tip,b.y-uy*tip
        return Polygon((Vec2(a.x+nx*shaft,a.y+ny*shaft),Vec2(bx+nx*shaft,by+ny*shaft),Vec2(bx+nx*half,by+ny*half),b,Vec2(bx-nx*half,by-ny*half),Vec2(bx-nx*shaft,by-ny*shaft),Vec2(a.x-nx*shaft,a.y-ny*shaft)))
    arrow=DynamicGeometryObject2D(arrow_poly,style=filled(YELLOW),z_index=2)
    sc.add(arrow)
    return sc


def combine_updaters() -> Scene:
    sc=scene()
    left=-6.0; right=6.0
    def state(t):
        segment=min(2,int(max(0,t)//2)); a=(t-segment*2)/2 if t<6 else 1
        x=left+(right-left)*max(0,min(1,a)); y=0; rot=0
        if segment>=1: y=math.sin(max(0,min(1,a))*4*PI)
        if segment>=2: rot=-TAU*max(0,min(1,a))
        return Transform2D.translation(x,y).rotate(rot)
    obj=DynamicGeometryObject2D(lambda t:square_polygon(2.0,state(t)),style=Style.outline(WHITE,0.04))
    obj=sc.add(obj)
    sc.wait(2); sc.wait(2)
    obj.outline(BLUE, width=0.04, duration=2, easing=Easing.LINEAR)
    return sc


def rotating_pie() -> Scene:
    sc=scene(); colors=[RED,PURPLE,MAROON,GOLD]; sectors=[]
    for i,c in enumerate(colors):
        ang=i*TAU/4; off=Vec2(0.05*math.cos(ang+PI/4),0.05*math.sin(ang+PI/4))
        sec=Object2D(sector_polygon(ang,TAU/4,1.5), position=off, fill=c)
        sectors.append(sec)
    pie=Group2D(sectors); pie=sc.add(pie)
    sector0=sc.on(sectors[0]); base0=sector0.transform_value
    with sc.parallel():
        pie.transform_function(lambda a: affine2d(rotation=TAU*a), duration=5, easing=Easing.LINEAR)
        sector0.transform_function(
            lambda a: affine2d(to=(
                base0.tx + math.sin(PI*a)/math.sqrt(2),
                base0.ty + math.sin(PI*a)/math.sqrt(2),
            )),
            duration=2, easing=Easing.LINEAR, at=2,
        )
    return sc


def marked_item() -> Scene:
    sc=scene()
    def tr(a): return Transform2D.translation(math.sin(4*PI*a),0).rotate(TAU*a)
    square=Object2D(Square(2), stroke=WHITE, stroke_width=0.04)
    square=sc.add(square)
    square.transform_function(tr,duration=4,easing=Easing.LINEAR)
    local1=Vec2(0.5,0); local2=Vec2(0,-0.5)
    def mark(local,t): return tr(max(0,min(1,t/4))).apply(local)
    tri1=DynamicGeometryObject2D(lambda t:triangle_polygon(mark(local1,t),0.20),style=outlined(GREEN,None,0.035),z_index=2)
    tri2=DynamicGeometryObject2D(lambda t:triangle_polygon(mark(local2,t),0.20),style=outlined(BLUE,None,0.035),z_index=2)
    d1=DynamicGeometryObject2D(lambda t:circle_polygon(mark(local1,t),0.055,16),style=filled(RED),z_index=3)
    d2=DynamicGeometryObject2D(lambda t:circle_polygon(mark(local2,t),0.055,16),style=filled(RED),z_index=3)
    sc.add(tri1,tri2,d1,d2)
    return sc



BUILDERS: dict[str, Callable[[], Scene]] = {
    'HelloJAnimExample': hello_janim,
    'BasicAnimationExample': basic_animation,
    'TextExample': text_example,
    'TypstExample': typst_example,
    'TypstColorizeExample': typst_colorize,
    'AnimatingPiExample': animating_pi,
    'NumberPlaneExample': number_plane,
    'UpdaterExample': updater_example,
    'ArrowPointingExample': arrow_pointing,
    'CombineUpdatersExample': combine_updaters,
    'RotatingPieExample': rotating_pie,
    'MarkedItemExample': marked_item,
    'FrameEffectExample': build_frame_effect_example,
    'MaskExample': build_mask_example,
    'ThreeDShapesExample': build_three_d_shapes_example,
}


WORKER_HINTS = {
    # Nonlinear VectorDocument construction is Python-heavy; extra workers only
    # contend on the GIL. Offscreen compositing benefits from a few workers but
    # has a larger per-frame RGBA working set.
    'AnimatingPiExample': 2,
    'FrameEffectExample': 4,
    'MaskExample': 4,
}


def render_one(name: str, *, workers: int | None = None):
    sc=BUILDERS[name]()
    OUT_DIR.mkdir(parents=True,exist_ok=True)
    out=OUT_DIR/f'{name}.mp4'
    resolved_workers = workers if workers is not None else WORKER_HINTS.get(name, 8)
    sc.render_video(
        out, fps=30, workers=resolved_workers, verify_random_access=True, preset='veryfast'
    )
    print(f'{name}: duration={sc.timeline.cursor:.2f}s workers={resolved_workers} -> {out}')
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('example',nargs='?',choices=[*BUILDERS,'all'],default='all')
    ap.add_argument('--workers',type=int,default=None)
    args=ap.parse_args()
    names=BUILDERS if args.example=='all' else [args.example]
    for name in names: render_one(name,workers=args.workers)


if __name__=='__main__': main()
