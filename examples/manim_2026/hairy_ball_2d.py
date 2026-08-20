from __future__ import annotations

import argparse
import math
from pathlib import Path

from zanim import (
    Arrow, BatchObject2D, Canvas, Circle, Color, DOWN, DynamicNumber, Easing,
    Group2D, LEFT, Line, LineSet, Math, NumberFormat, Object2D, Polygon,
    RectSet, Rectangle, RIGHT, ScalarValue, Scene, Square, StrokeStyle, Style,
    Text, Transform2D, UP, Vec2,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "media" / "manim_2026" / "hairy_ball"
CANVAS = Canvas(width=1920, height=1080, unit_size=135)
DRAFT = Canvas(width=960, height=540, unit_size=67.5)

BG = Color(14, 17, 24)
WHITE = Color(240, 242, 248)
GREY = Color(150, 158, 178)
BLUE = Color(83, 148, 255)
GREEN = Color(80, 205, 128)
RED = Color(245, 82, 98)
YELLOW = Color(249, 211, 79)


def scene(*, draft: bool = False) -> Scene:
    return Scene(canvas=DRAFT if draft else CANVAS, fps=30 if draft else 60)


def stroke(color=WHITE, width=0.025):
    return StrokeStyle(color, width)


def outline_rect(w, h, *, color=WHITE, width=0.025, fill=None, z=0):
    return Object2D(Rectangle(w, h), style=Style(fill=fill, stroke=stroke(color, width)), z_index=z)


def text_row(parts: list[tuple[str, Color]], *, font_size=46, buff=0.08) -> Group2D:
    row = Group2D([Text(part, font_size=font_size, color=color) for part, color in parts])
    row.arrange(RIGHT, buff=buff)
    return row


def rename_theorem(*, draft=False) -> Scene:
    sc = scene(draft=draft)
    name1 = Text("Hairy Ball Theorem", font_size=62)
    name2 = Text("Sphere Vector Field Theorem", font_size=62, opacity=0)
    name1.move_to(Vec2(-2.2, 1.05)); name2.move_to(Vec2(-1.45, -1.0))
    l1 = Object2D(Line(Vec2(-4.75, 1.05), Vec2(-3.35, 1.05)), style=Style(fill=None, stroke=stroke(RED, .055)))
    l2 = Object2D(Line(Vec2(-3.15, 1.05), Vec2(-2.05, 1.05)), style=Style(fill=None, stroke=stroke(RED, .055)))
    l1.trim = l2.trim = 0.0
    sc.add(name1, name2, l1, l2)
    sc.wait(1)
    sc.create(l2, .7); sc.wait(.15)
    sc.create(l1, .7)
    with sc.parallel():
        sc.fade_out(name1, 1.0)
        sc.fade_in(name2, 1.0)
    sc.wait(1.2)
    return sc


def simple_implies(*, draft=False) -> Scene:
    sc = scene(draft=draft)
    arrow = Math("==>", font_size=125)
    sc.add(arrow); sc.create(arrow, 1.2); sc.wait(1.0)
    return sc


def wing_code(*, draft=False) -> Scene:
    sc = scene(draft=draft)
    code = Text(
        'def wing_vect(heading_vect):\n    """Return 3d vector perpendicular\n    to heading_vect"""\n    ...',
        font_size=34,
    )
    code.move_to(Vec2(-1.5, .5)); sc.add(code); sc.create(code, 2.0, Easing.LINEAR); sc.wait(1.0)
    return sc


def lazy_perp_code(*, draft=False) -> Scene:
    sc = scene(draft=draft)
    code = Text(
        "def lazy_perp(heading):\n"
        "    # normalized cross product of (0,0,1) and heading\n"
        "    # note the division by 0 for x=y=0\n"
        "    x, y, z = heading\n"
        "    return [-y, x, 0] / sqrt(x*x + y*y)",
        font_size=28,
    )
    code.move_to(Vec2(-.65, 1.3)); sc.add(code); sc.create(code, 2.2, Easing.LINEAR); sc.wait(1.0)
    return sc


def statement_of_theorem(*, draft=False) -> Scene:
    sc = scene(draft=draft)
    title = Text("Hairy Ball Theorem", font_size=65); title.move_to(Vec2(-2.75, 3.15))
    underline = Object2D(Line(Vec2(-5.15, 2.68), Vec2(-0.8, 2.68)), style=Style(fill=None, stroke=stroke(WHITE, .025)))

    line1a = text_row([("Any ", WHITE), ("continuous", WHITE), (" vector field", WHITE)], font_size=45)
    line1b = text_row([("Any ", WHITE), ("continuous", BLUE), (" vector field", WHITE)], font_size=45)
    line2 = Text("on a sphere must have at least", font_size=45)
    line3a = text_row([("one null vector", WHITE), (".", WHITE)], font_size=45)
    line3b = text_row([("one null vector", YELLOW), (".", WHITE)], font_size=45)
    for g in (line1a, line1b): g.move_to(Vec2(-2.2, 1.45))
    line2.move_to(Vec2(-2.15, .45))
    for g in (line3a, line3b): g.move_to(Vec2(-3.45, -.55))
    line1b.opacity = 0; line3b.opacity = 0
    statement = Group2D([line1a, line2, line3a])
    sc.add(title, underline, statement, line1b, line3b)
    sc.create(title, 1.0); sc.create(underline, .5)
    with sc.parallel():
        sc.create(line1a, 1.4)
        sc.create(line2, 1.8, at=.35)
        sc.create(line3a, 1.4, at=.75)
    sc.wait(1)
    with sc.parallel(): sc.fade_out(line1a, .55); sc.fade_in(line1b, .55)
    sc.wait(.8)
    with sc.parallel(): sc.fade_out(line3a, .55); sc.fade_in(line3b, .55)
    sc.wait(1.0)
    return sc


def write_antipode(*, draft=False) -> Scene:
    sc = scene(draft=draft)
    a = Text("“Antipodes”", font_size=68); b = Text("Antipode map", font_size=68, opacity=0)
    for obj in (a, b): obj.move_to(Vec2(-3.85, 2.7))
    sc.add(a, b); sc.create(a, 1.5); sc.wait(.8)
    with sc.parallel(): sc.fade_out(a, .7); sc.fade_in(b, .7)
    sc.wait(.8); return sc


def three_cases(*, draft=False) -> Scene:
    sc = scene(draft=draft)
    xs = (-4.35, 0, 4.35)
    top = ["2 null points", "1 null point", "0 null points"]
    bottom = ["Obvious", "Clever", "Very clever"]
    top_objs=[]; bottom_objs=[]
    for x, a, b in zip(xs, top, bottom):
        ta=Text(a,font_size=38,color=GREY); tb=Text(b,font_size=52,opacity=0)
        ta.move_to(Vec2(x,2.45)); tb.move_to(Vec2(x,1.45)); top_objs.append(ta); bottom_objs.append(tb)
    cross1=Object2D(Line(Vec2(3.35,.95),Vec2(5.35,1.95)),style=Style(fill=None,stroke=stroke(RED,.055)),opacity=0)
    cross2=Object2D(Line(Vec2(3.35,1.95),Vec2(5.35,.95)),style=Style(fill=None,stroke=stroke(RED,.055)),opacity=0)
    why=Text("Why not?",font_size=38,color=YELLOW,opacity=0); why.move_to(Vec2(4.35,.25))
    sc.add(*(top_objs+bottom_objs+[cross1,cross2,why])); sc.wait(.5)
    for obj in bottom_objs: sc.fade_in(obj,.55)
    sc.wait(.7)
    with sc.parallel(): sc.fade_in(cross1,.45); sc.fade_in(cross2,.45)
    sc.fade_in(why,.6); sc.wait(1.0); return sc


def proof_outline(*, draft=False) -> Scene:
    sc = scene(draft=draft)
    title=Text("Proof by Contradiction",font_size=64); title.move_to(Vec2(0,3.15))
    left=outline_rect(3.2,3.2); left.move_to(Vec2(-3.45,.45)); left.opacity=0
    right=outline_rect(3.2,3.2); right.move_to(Vec2(3.45,.45)); right.opacity=0
    implies=Math("==>",font_size=100,opacity=0); implies.move_to(Vec2(0,.45))
    impossible=Text("Impossibility",font_size=62,color=RED,opacity=0); impossible.move_to(Vec2(4.9,2.45))
    question=Text("What do we\nshow here?",font_size=52,opacity=0); question.move_to(Vec2(.25,.2))
    brace=Object2D(Line(Vec2(-1.55,-1.15),Vec2(-1.55,2.05)),style=Style(fill=None,stroke=stroke(WHITE,.035)),opacity=0)
    sc.add(title,left,right,implies,impossible,question,brace)
    sc.create(title,1.4); sc.wait(.6); sc.fade_in(left,.7); sc.wait(.7)
    sc.fade_in(implies,.6); sc.fade_in(impossible,.7); sc.wait(.6)
    with sc.parallel():
        sc.fade_in(right,.8)
        sc.play_transform(impossible,Transform2D.translation(3.45,2.45).scale(.6),.8)
    sc.wait(.7); sc.fade_out(impossible,.5)
    with sc.parallel(): sc.fade_out(implies,.5); sc.fade_out(right,.5)
    with sc.parallel(): sc.fade_in(brace,.5); sc.fade_in(question,.8)
    sc.wait(1.0); return sc


def two_facts(*, draft=False) -> Scene:
    sc=scene(draft=draft)
    a=Math("p ==> -p",font_size=66); b=Text("2) Motion varies continuously with p",font_size=50)
    a.move_to(Vec2(-2.2,1.3)); b.move_to(Vec2(-1.3,-1.0)); a.opacity=b.opacity=0
    sc.add(a,b); sc.fade_in(a,.8); sc.wait(.7); sc.fade_in(b,.9); sc.wait(1.2); return sc


def two_key_features(*, draft=False) -> Scene:
    sc=scene(draft=draft)
    f0=Text("1) Inside out",font_size=54,opacity=0); f1=Text("2) Avoids the origin",font_size=54,opacity=0)
    f0.move_to(Vec2(-4.15,1.55)); f1.move_to(Vec2(-3.5,-.1))
    r0=outline_rect(4.0,.85,color=BLUE,width=.025); r0.move_to(Vec2(-4.15,1.55)); r0.opacity=0
    r1=outline_rect(5.35,.85,color=BLUE,width=.025); r1.move_to(Vec2(-3.5,-.1)); r1.opacity=0
    i0=Math("==>",font_size=65,opacity=0); i0.move_to(Vec2(-.9,1.55))
    i1=Math("==>",font_size=65,opacity=0); i1.move_to(Vec2(-.2,-.1))
    flux0=Text("Final Flux = -1.0",font_size=44,color=RED,opacity=0); flux0.move_to(Vec2(2.25,1.55))
    flux1=Text("Final Flux = +1.0",font_size=44,color=GREEN,opacity=0); flux1.move_to(Vec2(2.95,-.1))
    contra=Text("⊥",font_size=80,color=RED,opacity=0); contra.move_to(Vec2(5.45,-2.65))
    sc.add(f0,f1,r0,r1,i0,i1,flux0,flux1,contra)
    sc.fade_in(f0,.65); sc.wait(.5); sc.fade_in(f1,.65); sc.wait(.6)
    with sc.parallel(): sc.fade_in(r0,.4); sc.fade_in(i0,.4); sc.fade_in(flux0,.7,at=.3)
    sc.wait(.7)
    with sc.parallel(): sc.fade_in(r1,.4); sc.fade_in(i1,.4); sc.fade_in(flux1,.7,at=.3)
    sc.wait(.7); sc.fade_in(contra,.7); sc.wait(1.0); return sc


def inside_outside(*, draft=False) -> Scene:
    sc=scene(draft=draft)
    a=Text("Inside?",font_size=74,opacity=0); b=Text("Outside?",font_size=74,opacity=0)
    sc.add(a,b); sc.fade_in(a,.7); sc.wait(.7)
    with sc.parallel(): sc.fade_out(a,.7); sc.fade_in(b,.7)
    sc.wait(.8); return sc


def p_to_neg_p(*, draft=False) -> Scene:
    sc=scene(draft=draft)
    p=Math("p",font_size=100); arrow=Math("==>",font_size=100,opacity=0); neg=Math("-p",font_size=100,opacity=0)
    p.move_to(Vec2(-2.5,2.2)); arrow.move_to(Vec2(0,2.2)); neg.move_to(Vec2(2.5,2.2))
    sc.add(p,arrow,neg); sc.create(p,.7); sc.fade_in(arrow,.6); sc.fade_in(neg,.7); sc.wait(1.0); return sc


def simpler_inside_out(*, draft=False) -> Scene:
    sc=scene(draft=draft)
    a=Math("(x, y, z)",font_size=60); b=Math("(-x, -y, z)",font_size=60,opacity=0); c=Math("(-x, -y, -z)",font_size=60,opacity=0)
    ar1=Arrow(Vec2(0,1.4),Vec2(0,.55),color=WHITE,opacity=0); ar2=Arrow(Vec2(0,-.45),Vec2(0,-1.3),color=WHITE,opacity=0)
    a.move_to(Vec2(0,2.0)); b.move_to(Vec2(0,0)); c.move_to(Vec2(0,-2.0))
    sc.add(a,ar1,b,ar2,c); sc.wait(.7)
    with sc.parallel(): sc.fade_in(ar1,.5); sc.fade_in(b,.7)
    sc.wait(.6)
    with sc.parallel(): sc.fade_in(ar2,.5); sc.fade_in(c,.7)
    sc.wait(1.0); return sc


def flux_decimals(*, draft=False) -> Scene:
    sc=scene(draft=draft)
    value=ScalarValue(1.0); sc.add(value)
    label=Text("Flux:",font_size=58); unit=Text("L/s",font_size=50)
    label.move_to(Vec2(3.8,2.85)); unit.move_to(Vec2(5.55,2.85))
    nums=[]
    for color,opacity in ((GREEN,1),(YELLOW,0),(RED,0)):
        n=DynamicNumber(value,number_format=NumberFormat(width=6,decimals=3,sign="always"),font_size=58,color=color,opacity=opacity)
        n.move_to(Vec2(4.8,2.85)); nums.append(n)
    sc.add(label,unit,*nums); sc.wait(.7)
    targets=[(.014,GREEN),(-.014,RED),(.014,GREEN),(1.0,GREEN),(0.0,YELLOW)]
    current=0
    color_index={GREEN:0,YELLOW:1,RED:2}
    for target,color in targets:
        nxt=color_index[color]
        with sc.parallel():
            sc.play_value(value,target,1.0 if abs(target)!=1 else 2.5,Easing.SMOOTHSTEP)
            if nxt!=current:
                sc.fade_out(nums[current],.35,at=.35); sc.fade_in(nums[nxt],.35,at=.35)
        current=nxt; sc.wait(.45)
    sc.wait(.6); return sc


def frame_intuition(*, draft=False) -> Scene:
    sc=scene(draft=draft)
    h=Object2D(Line(Vec2(-7,2.1),Vec2(7,2.1)),style=Style(fill=None,stroke=stroke(WHITE,.02)))
    v=Object2D(Line(Vec2(0,-4),Vec2(0,4)),style=Style(fill=None,stroke=stroke(WHITE,.02)))
    intuitive=Text("Intuitive idea",font_size=54); intuitive.move_to(Vec2(-3.5,3.05))
    counter=Text("Counterexample",font_size=54,opacity=0); clever=Text("Clever proof",font_size=54,opacity=0)
    counter.move_to(Vec2(3.5,3.05)); clever.move_to(Vec2(3.5,3.05))
    idea1=Text("Turning a sphere\ninside-out must crease it",font_size=38,color=GREY,opacity=0); idea1.move_to(Vec2(-3.5,.65))
    idea2=Text("All closed loops\nhave inscribed rectangles",font_size=38,color=GREY,opacity=0); idea2.move_to(Vec2(-3.5,.65))
    sc.add(h,v,intuitive,counter,clever,idea1,idea2); sc.wait(.5); sc.fade_in(idea1,.7); sc.fade_in(counter,.7); sc.wait(.7)
    with sc.parallel(): sc.fade_out(idea1,.6); sc.fade_in(idea2,.6); sc.fade_out(counter,.6); sc.fade_in(clever,.6)
    sc.wait(1.0); return sc


def dimension_generalization(*, draft=False) -> Scene:
    sc=scene(draft=draft)
    # One retained line batch, not dozens of Square objects.
    x0=-5.9; cell_w=.78; y_top=2.75; row_h=1.0; n=15
    starts=[]; ends=[]
    for i in range(n+1):
        x=x0+i*cell_w; starts.append(Vec2(x,y_top)); ends.append(Vec2(x,y_top-2*row_h))
    for j in range(3):
        y=y_top-j*row_h; starts.append(Vec2(x0,y)); ends.append(Vec2(x0+n*cell_w,y))
    grid=BatchObject2D(LineSet(tuple(starts),tuple(ends),tuple(WHITE for _ in starts),tuple(.012 for _ in starts)))
    title=Text("Dimension",font_size=28); title.move_to(Vec2(-5.35,3.35))
    question=Text("Can you comb a ball?",font_size=27); question.move_to(Vec2(-4.65,1.15))
    dims=[]; marks=[]
    for i,dim in enumerate(range(2,17)):
        x=x0+(i+.5)*cell_w
        d=Math(str(dim),font_size=30); d.move_to(Vec2(x,2.25)); dims.append(d)
        mark=Text("✓" if dim%2==0 else "✗",font_size=35,color=GREEN if dim%2==0 else RED,opacity=0)
        mark.move_to(Vec2(x,1.25)); marks.append(mark)
    sc.add(grid,title,question,*dims,*marks); sc.wait(.6)
    # reveal first few, then propagate parity across the row
    for i in range(3): sc.fade_in(marks[i],.35)
    with sc.parallel():
        for i in range(3,n): sc.fade_in(marks[i],.35,at=(i-3)*.12)
    sc.wait(.8)
    det=Text("det(-Iₙ) = (-1)ⁿ",font_size=52,color=YELLOW,opacity=0); det.move_to(Vec2(0,-1.55)); sc.add(det); sc.fade_in(det,.7); sc.wait(1.2)
    return sc


def rotation_in_2d(*, draft=False) -> Scene:
    sc=scene(draft=draft)
    starts=[]; ends=[]
    for k in range(-5,6):
        starts += [Vec2(k,-4),Vec2(-7,k)]; ends += [Vec2(k,4),Vec2(7,k)]
    back=BatchObject2D(LineSet(tuple(starts),tuple(ends),tuple(Color(85,90,105,100) for _ in starts),tuple(.008 for _ in starts)))
    front=BatchObject2D(LineSet(tuple(starts),tuple(ends),tuple(Color(120,140,180,150) for _ in starts),tuple(.012 for _ in starts)))
    e1=Arrow(Vec2(),Vec2(1.0,0),color=GREEN); e2=Arrow(Vec2(),Vec2(0,1.0),color=RED); basis=Group2D([e1,e2])
    sc.add(back,front,basis); sc.wait(.8)
    with sc.parallel():
        sc.play_transform(front,Transform2D.rotation(math.pi),5.0,Easing.SMOOTHSTEP)
        sc.play_transform(basis,Transform2D.rotation(math.pi),5.0,Easing.SMOOTHSTEP)
    sc.wait(.8); return sc


def hypersphere_words(*, draft=False) -> Scene:
    sc=scene(draft=draft)
    a=Text("Hairs on a neatly-combed 4d hypersphere",font_size=54); a.move_to(Vec2(-1.1,2.5))
    b=Text("Represented via stereographic projection into 3d space",font_size=40,color=GREY,opacity=0); b.move_to(Vec2(-.2,1.5))
    sc.add(a,b); sc.wait(.7); sc.fade_in(b,1.2); sc.wait(1.0); return sc


BUILDERS = {
    "RenameTheorem": rename_theorem,
    "SimpleImplies": simple_implies,
    "WingVectCodeSnippet": wing_code,
    "LazyPerpCodeSnippet": lazy_perp_code,
    "StatementOfTheorem": statement_of_theorem,
    "WriteAntipode": write_antipode,
    "ThreeCases": three_cases,
    "ProofOutline": proof_outline,
    "TwoFactsForEachPoint": two_facts,
    "TwoKeyFeatures": two_key_features,
    "InsideOutsideQuestion": inside_outside,
    "PToNegP": p_to_neg_p,
    "SimplerInsideOutProgression": simpler_inside_out,
    "FluxDecimals": flux_decimals,
    "FrameIntuitionVsExamples": frame_intuition,
    "DimensionGeneralization": dimension_generalization,
    "RotationIn2D": rotation_in_2d,
    "HypersphereWords": hypersphere_words,
}


def render_one(name: str, *, draft=False, workers=4, preset="veryfast") -> Path:
    sc=BUILDERS[name](draft=draft)
    out_dir=OUT/("draft" if draft else "")
    out_dir.mkdir(parents=True,exist_ok=True)
    out=out_dir/f"{name}.mp4"
    sc.render_video(out,workers=workers,preset=preset,verify_random_access=True)
    print(f"{name}: duration={sc.timeline.cursor:.2f}s random-access=ok -> {out}")
    return out


def main():
    ap=argparse.ArgumentParser(description="2D supplements from 3Blue1Brown's 2026 Hairy Ball video")
    ap.add_argument("scene",nargs="?",choices=[*BUILDERS,"all"],default="all")
    ap.add_argument("--draft",action="store_true")
    ap.add_argument("--workers",type=int,default=4)
    ap.add_argument("--preset",default="veryfast")
    args=ap.parse_args()
    names=BUILDERS if args.scene=="all" else [args.scene]
    for name in names: render_one(name,draft=args.draft,workers=args.workers,preset=args.preset)


if __name__ == "__main__":
    main()
