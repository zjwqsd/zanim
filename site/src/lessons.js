import {
  BLUE,
  Box3D,
  CYAN,
  Circle,
  Column,
  Easing,
  GREEN,
  Grid,
  Group,
  InfiniteGrid,
  InfiniteLine,
  LOCAL,
  Line,
  ORANGE,
  PARENT,
  PI,
  PURPLE,
  Polygon,
  RED,
  Rectangle,
  RegularPolygon,
  Row,
  Scene,
  Scene3DLayer,
  Square,
  TAU,
  Transform2D,
  Transform3D,
  Vec3,
  Camera3D,
  Cube3D,
  WHITE,
  WORLD,
  YELLOW,
} from '@zanim/web'

const T = (x = 0, y = 0, rotation = 0, scale = 1) =>
  Transform2D.affine({ position: [x, y], rotation, scale })

async function makeScene(canvas, { unitSize = 72, fps = 60 } = {}) {
  const rect = canvas.getBoundingClientRect()
  const scale = Math.max(0.42, rect.width / 760)
  return Scene.create(canvas, {
    fps,
    renderer: { unitSize: unitSize * scale, background: '#080b12' },
  })
}

function axis(color, end) {
  return new Line([0, 0], end, { stroke: color, strokeWidth: 0.035 })
}

function framePanel(centerX) {
  const body = new Square(0.72, { fill: '#5aa7ffd0', stroke: WHITE })
  const tool = new Group(
    [body, axis(RED, [0.78, 0]), axis(GREEN, [0, 0.78])],
    { transform: T(-0.55, -0.1, -33 * PI / 180) },
  )
  const panel = new Group(
    [axis(RED, [1.5, 0]), axis(GREEN, [0, 1.15]), new Circle(0.07, { fill: WHITE, stroke: null }), tool],
    { transform: T(centerX, -0.2, 20 * PI / 180) },
  )
  return [panel, tool]
}

export async function heroBuilder(canvas) {
  const scene = await makeScene(canvas, { unitSize: 78 })
  const dots = Array.from({ length: 14 }, (_, i) => {
    const a = TAU * i / 14
    return new Circle(0.11 + 0.025 * (i % 3), {
      fill: i % 3 === 0 ? CYAN : i % 3 === 1 ? BLUE : PURPLE,
      stroke: null,
      transform: T(2.3 * Math.cos(a), 2.3 * Math.sin(a)),
      opacity: 0.9,
    })
  })
  const core = new Square(1.05, { fill: '#66aaff20', stroke: CYAN, strokeWidth: 0.045 })
  const orbit = new Circle(2.3, { fill: null, stroke: '#82a5d52c', strokeWidth: 0.018 })
  scene.add(orbit, core, ...dots)
  scene.parallel(6, api => {
    api.rotate(core, TAU, { frame: WORLD, easing: Easing.LINEAR })
    dots.forEach((dot, i) => {
      const phase = TAU * i / dots.length
      api.transformFunction(
        dot,
        a => T(
          2.3 * Math.cos(phase + TAU * a),
          2.3 * Math.sin(phase + TAU * a),
          -TAU * a,
          0.85 + 0.25 * Math.sin(phase + TAU * a),
        ),
        { easing: Easing.LINEAR },
      )
    })
  })
  return scene
}

export const lessons = [
  {
    id: 'scene',
    index: '01',
    title: 'Scene owns time',
    eyebrow: 'Start here',
    summary: 'Objects describe state. Scene.add() captures that state and becomes the explicit owner of every later change.',
    points: ['Declare first', 'add() is the ownership boundary', 'Animations update the Scene-authored head'],
    python: `from zanim import BLUE, ORANGE, PI, WORLD, Circle, Scene, Square

scene = Scene()
square, circle = scene.add(
    Square(1.25, fill=BLUE),
    Circle(0.68, fill=ORANGE),
)

with scene.parallel(duration=1.4):
    square.move(by=(2.4, 0.4), frame=WORLD)
    circle.rotate(by=PI, frame=WORLD)

with scene.parallel(duration=1.0):
    square.scale(by=1.3)
    circle.move(by=(-2.4, -0.4), frame=WORLD)`,
    js: `import { BLUE, ORANGE, PI, WORLD, Circle, Scene, Square } from '@zanim/web'

const scene = await Scene.create('#canvas')
const square = new Square(1.25, { fill: BLUE })
const circle = new Circle(0.68, { fill: ORANGE })
scene.add(square, circle)

scene.parallel(1.4, api => {
  api.move(square, [2.4, 0.4], { frame: WORLD })
  api.rotate(circle, PI, { frame: WORLD })
})

scene.parallel(1.0, api => {
  api.scale(square, 1.3)
  api.move(circle, [-2.4, -0.4], { frame: WORLD })
})`,
    async builder(canvas) {
      const scene = await makeScene(canvas)
      const square = new Square(1.25, { fill: '#5aa7ffd0', stroke: '#dce9ff', transform: T(-1.6, 0) })
      const circle = new Circle(0.68, { fill: '#ffad66d0', stroke: '#fff0dc', transform: T(1.6, 0) })
      scene.add(square, circle)
      scene.parallel(1.4, api => {
        api.move(square, [2.4, 0.4], { frame: WORLD })
        api.rotate(circle, PI, { frame: WORLD })
      })
      scene.parallel(1.0, api => {
        api.scale(square, 1.3)
        api.move(circle, [-2.4, -0.4], { frame: WORLD })
      })
      scene.wait(0.35)
      return scene
    },
  },
  {
    id: 'timeline',
    index: '02',
    title: 'Sequential by default. Parallel when explicit.',
    eyebrow: 'Timeline',
    summary: 'Each authored operation advances the cursor. parallel() freezes one shared scheduling base, so concurrency is visible in the code.',
    points: ['No hidden async model', 'Offsets stay explicit', 'One absolute-time timeline'],
    python: `# Top row: three sequential moves.
for dot in top:
    dot.move(by=(1.15, 0), duration=0.8)

# Bottom row: same three moves, one shared span.
scene.at(0.25)
with scene.parallel(duration=0.8):
    for dot in bottom:
        dot.move(by=(1.15, 0))`,
    js: `// Top row: sequential.
scene.at(0.25)
for (const dot of top) {
  scene.move(dot, [1.15, 0], { duration: 0.8 })
}

// Bottom row: parallel.
scene.at(0.25)
scene.parallel(0.8, api => {
  bottom.forEach(dot => api.move(dot, [1.15, 0]))
})`,
    async builder(canvas) {
      const scene = await makeScene(canvas)
      const colors = [BLUE, PURPLE, ORANGE]
      const top = colors.map((fill, i) => new Circle(0.38, { fill, stroke: null, transform: T(-2.4 + i * 1.6, 1.05) }))
      const bottom = colors.map((fill, i) => new Square(0.7, { fill, stroke: null, transform: T(-2.4 + i * 1.6, -1.05) }))
      scene.add(...top, ...bottom)
      scene.at(0.25)
      for (const dot of top) scene.move(dot, [1.15, 0], { duration: 0.8 })
      scene.at(0.25)
      scene.parallel(0.8, api => bottom.forEach(dot => api.move(dot, [1.15, 0])))
      scene.at(2.9)
      scene.wait(0.35)
      return scene
    },
  },
  {
    id: 'layout',
    index: '03',
    title: 'Layout is a target, not a constraint.',
    eyebrow: 'Composition',
    summary: 'Use Row / Column / Grid to compute placement. Before add() it is ordinary setup; after add() Scene.layout() animates toward a new arrangement.',
    points: ['Deterministic placement', 'No persistent layout solver', 'Layout composes with later transforms'],
    python: `items = [Square(1), Circle(.55), RegularPolygon(3, .68), Rectangle(1.35, .82)]
Row(gap=.7).place(*items)
scene.add(*items)

scene.layout(*items, to=Grid(rows=2, cols=2, gap=(.8, .6)), duration=1)
scene.layout(*items, to=Column(gap=.35), duration=1)
scene.layout(*items, to=Row(gap=.7), duration=1)`,
    js: `const items = [
  new Square(1), new Circle(.55),
  new RegularPolygon(3, .68), new Rectangle(1.35, .82),
]
new Row({ gap: .7 }).place(...items)
scene.add(...items)

scene.layout(...items, { to: new Grid({ rows: 2, cols: 2, gap: [.8, .6] }), duration: 1 })
scene.layout(...items, { to: new Column({ gap: .35 }), duration: 1 })
scene.layout(...items, { to: new Row({ gap: .7 }), duration: 1 })`,
    async builder(canvas) {
      const scene = await makeScene(canvas)
      const items = [
        new Square(1, { fill: '#5aa7ffc5', stroke: '#dce9ff' }),
        new Circle(0.55, { fill: '#ffad66c5', stroke: '#fff0dc' }),
        new RegularPolygon(3, 0.68, { fill: '#55d69ec5', stroke: '#ddfff1' }),
        new Rectangle(1.35, 0.82, { fill: '#a681ffc5', stroke: '#efe8ff' }),
      ]
      new Row({ gap: 0.7, at: [0, 0] }).place(...items)
      scene.add(...items)
      scene.wait(0.35)
      scene.layout(...items, { to: new Grid({ rows: 2, cols: 2, gap: [0.85, 0.62], at: [0, 0] }), duration: 1 })
      scene.wait(0.2)
      scene.layout(...items, { to: new Column({ gap: 0.35, at: [0, 0] }), duration: 1 })
      scene.wait(0.2)
      scene.layout(...items, { to: new Row({ gap: 0.7, at: [0, 0] }), duration: 1 })
      scene.wait(0.3)
      return scene
    },
  },
  {
    id: 'frames',
    index: '04',
    title: 'LOCAL / PARENT / WORLD are different operations.',
    eyebrow: 'Transforms',
    summary: 'Relative motion always names the basis that interprets the vector. Nested transforms stay readable because coordinate semantics are explicit.',
    points: ['LOCAL follows the object', 'PARENT follows its container', 'WORLD ignores both local rotations'],
    python: `with scene.parallel(duration=2.2):
    local_tool.move(by=(1.5, 0), frame=LOCAL)
    parent_tool.move(by=(1.5, 0), frame=PARENT)
    world_tool.move(by=(1.5, 0), frame=WORLD)`,
    js: `scene.parallel(2.2, api => {
  api.move(localTool, [1.5, 0], { frame: LOCAL })
  api.move(parentTool, [1.5, 0], { frame: PARENT })
  api.move(worldTool, [1.5, 0], { frame: WORLD })
})`,
    async builder(canvas) {
      const scene = await makeScene(canvas, { unitSize: 64 })
      const [lp, lt] = framePanel(-3.25)
      const [pp, pt] = framePanel(0)
      const [wp, wt] = framePanel(3.25)
      scene.add(lp, pp, wp)
      scene.wait(0.45)
      scene.parallel(2.2, api => {
        api.move(lt, [1.5, 0], { frame: LOCAL })
        api.move(pt, [1.5, 0], { frame: PARENT })
        api.move(wt, [1.5, 0], { frame: WORLD })
      })
      scene.wait(0.4)
      return scene
    },
  },
  {
    id: 'procedural',
    index: '05',
    title: 'A transform can be a function of time.',
    eyebrow: 'Procedural',
    summary: 'For continuous math, author the channel directly. Zanim samples absolute time; it does not accumulate frame-to-frame deltas.',
    points: ['Deterministic at any t', 'Ideal for math and simulation views', 'No numerical drift from replay'],
    python: `def transform(a: float):
    theta = .7 * sin(TAU * a)
    shear = .9 * sin(PI * a)
    return Transform2D.rotation(theta) @ Transform2D.shear(shear)

with scene.parallel(duration=5):
    for obj in (grid, x_axis, y_axis, shape):
        obj.transform_function(transform, easing=Easing.LINEAR)`,
    js: `const transform = a => {
  const theta = .7 * Math.sin(TAU * a)
  const shear = .9 * Math.sin(PI * a)
  return Transform2D.rotation(theta)
    .mul(new Transform2D(1, shear, 0, 1))
}

scene.parallel(5, api => {
  for (const obj of [grid, xAxis, yAxis, shape])
    api.transformFunction(obj, transform, { easing: Easing.LINEAR })
})`,
    async builder(canvas) {
      const scene = await makeScene(canvas, { unitSize: 67 })
      const grid = new InfiniteGrid({ step: 0.5, stroke: '#5f73954f', strokeWidth: 0.014, zIndex: -4 })
      const xAxis = new InfiniteLine([0, 0], [1, 0], { stroke: '#ff6f80dd', strokeWidth: 0.03, zIndex: -2 })
      const yAxis = new InfiniteLine([0, 0], [0, 1], { stroke: '#56d79add', strokeWidth: 0.03, zIndex: -2 })
      const shape = new Polygon(
        [[0.45, 0.35], [2.05, 0.35], [2.05, 0.85], [1.2, 0.85], [1.2, 1.75], [0.45, 1.75]],
        { fill: '#5aa7ff7d', stroke: CYAN, strokeWidth: 0.045, zIndex: 4 },
      )
      scene.add(grid, xAxis, yAxis, shape)
      const provider = a => {
        const theta = 0.7 * Math.sin(TAU * a)
        const shear = 0.9 * Math.sin(PI * a)
        return Transform2D.rotation(theta).mul(new Transform2D(1, shear, 0, 1))
      }
      scene.parallel(5, api => {
        for (const obj of [grid, xAxis, yAxis, shape]) {
          api.transformFunction(obj, provider, { easing: Easing.LINEAR })
        }
      })
      return scene
    },
  },
  {
    id: 'seek',
    index: '06',
    title: 'Seek directly. Never replay.',
    eyebrow: 'Random access',
    summary: 'The scene at t=3.2 is evaluated from authored state and timeline clips. Drag the scrubber below this demo: earlier frames do not need to execute first.',
    points: ['evaluate(t) is the model', 'Preview scrubbing is exact', 'Single frames and video use the same timeline'],
    python: `orbit.transform_function(
    lambda a: affine2d(
        position=(2.6*cos(TAU*a), 1.3*sin(TAU*a)),
        rotation=TAU*a,
    ),
    duration=5,
    easing=Easing.LINEAR,
)

scene.render(time=3.2)       # one frame
scene.render(start=1, end=4) # a range`,
    js: `scene.transformFunction(
  orbit,
  a => Transform2D.affine({
    position: [2.6*Math.cos(TAU*a), 1.3*Math.sin(TAU*a)],
    rotation: TAU*a,
  }),
  { duration: 5, easing: Easing.LINEAR },
)

scene.seek(3.2) // direct state evaluation`,
    async builder(canvas) {
      const scene = await makeScene(canvas)
      const path = new Circle(2.6, { fill: null, stroke: '#7288aa55', strokeWidth: 0.018 })
      const orbit = new Square(0.72, { fill: YELLOW, stroke: null })
      const center = new Circle(0.18, { fill: CYAN, stroke: null })
      scene.add(path, center, orbit)
      scene.transformFunction(
        orbit,
        a => T(2.6 * Math.cos(TAU * a), 1.3 * Math.sin(TAU * a), TAU * a),
        { duration: 5, easing: Easing.LINEAR },
      )
      return scene
    },
  },
  {
    id: 'three-d',
    index: '07',
    title: '2D and 3D share the same clock.',
    eyebrow: '3D',
    summary: '3D meshes render through the Zig/WASM rasterizer, then composite into the same Canvas2D scene. Absolute time still drives every transform.',
    points: ['Perspective camera', 'Depth + shading in Zig/WASM', 'Same Scene time as 2D'],
    python: `camera = Camera3D(position=Vec3(6, 4, 7), target=Vec3())
scene = Scene(camera3d=camera)

cube = Cube3D(
    1.5,
    color=BLUE,
    transform=lambda t: (
        Transform3D.translation(-1.2, 0, 0)
        @ Transform3D.rotation_y(.8 * t)
    ),
)
scene.add(cube)
scene.wait(6)`,
    js: `const camera = new Camera3D({
  position: new Vec3(6, 4, 7),
  target: new Vec3(),
})

const cube = Cube3D(1.5, {
  color: BLUE,
  transform: t => Transform3D.translation(-1.2, 0, 0)
    .mul(Transform3D.rotationY(.8 * t)),
})

scene.add(new Scene3DLayer([cube], { camera }))
scene.wait(6)`,
    async builder(canvas) {
      const scene = await makeScene(canvas, { unitSize: 64 })
      const camera = new Camera3D({
        position: new Vec3(6.2, 4.2, 7.2),
        target: new Vec3(0, 0, 0),
        fovYDegrees: 38,
      })
      const cubeA = Cube3D(1.55, {
        color: BLUE,
        transform: t => Transform3D.translation(-1.2, 0.15, 0)
          .mul(Transform3D.rotationAxis(new Vec3(1, 1, 0.3), 0.8 * t)),
      })
      const cubeB = Cube3D(1.2, {
        color: GREEN,
        transform: t => Transform3D.translation(1.25, -0.25, 0)
          .mul(Transform3D.rotationY(-0.65 * t)),
      })
      const floor = Box3D(new Vec3(5.5, 0.08, 4.4), {
        transform: Transform3D.translation(0, -1.2, 0),
        color: '#263249',
      })
      const layer = new Scene3DLayer([floor, cubeA, cubeB], { camera, resolution: 0.9 })
      scene.add(layer)
      scene.wait(6)
      return scene
    },
  },
  {
    id: 'ir',
    index: '08',
    title: 'Scene IR is the portable boundary.',
    eyebrow: 'Portability',
    summary: 'Python and Web author different frontends over one scene model. Scene IR carries portable objects, resources and timeline semantics between runtimes.',
    points: ['Python → IR → Web', 'Web → IR → native', 'Unsupported runtime callbacks fail explicitly'],
    python: `from zanim import scene_to_ir, write_scene_ir

scene = build_scene()
ir = scene_to_ir(scene)
write_scene_ir(ir, "scene.zanim.json")

# CLI:
# zanim render-ir scene.zanim.json -o scene.mp4`,
    js: `import { sceneToIR } from '@zanim/web/ir'

const scene = buildScene()
const ir = sceneToIR(scene)

const json = JSON.stringify(ir, null, 2)
// Store it, inspect it, or hand it to another runtime.`,
    async builder(canvas) {
      const scene = await makeScene(canvas)
      const square = new Square(1.15, { fill: '#5aa7ffb8', stroke: CYAN, transform: T(-2.0, 0) })
      const circle = new Circle(0.7, { fill: '#a681ffb8', stroke: '#ede5ff', transform: T(2.0, 0) })
      const bridge = new Line([-1.15, 0], [1.15, 0], { stroke: '#8ba0bf88', strokeWidth: 0.028, opacity: 0 })
      scene.add(square, bridge, circle)
      scene.fadeIn(bridge, { duration: 0.8 })
      scene.parallel(1.4, api => {
        api.move(square, [1.15, 0.65], { frame: WORLD })
        api.move(circle, [-1.15, -0.65], { frame: WORLD })
      })
      scene.parallel(0.9, api => {
        api.rotate(square, PI, { frame: WORLD })
        api.scale(circle, 1.25)
      })
      scene.parallel(1.0, api => {
        api.move(square, [0.85, -0.65], { frame: WORLD })
        api.move(circle, [-0.85, 0.65], { frame: WORLD })
      })
      scene.wait(0.3)
      return scene
    },
  },
]
