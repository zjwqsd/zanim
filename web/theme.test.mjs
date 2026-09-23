import assert from 'node:assert/strict';
import {
  Arrow,
  CanvasRenderer,
  Dot,
  MANIM,
  Scene,
  Square,
  Text,
  applyConfig,
  configFromObject,
  createTheme,
  getTheme,
  setTheme,
} from './src/zanim.js';
import { sceneToIR } from './src/ir.js';

setTheme('manim');
assert.equal(getTheme(), MANIM);
assert.equal(MANIM.canvas.width, 1920);
assert.equal(MANIM.canvas.height, 1080);
assert.equal(MANIM.canvas.unitSize, 135);
assert.equal(MANIM.canvas.background, '#000000');
assert.equal(MANIM.style.strokeWidth, 4 / 135);

const fakeContext = { save(){}, restore(){}, setTransform(){}, fillRect(){}, get globalAlpha(){return 1}, set globalAlpha(_v){}, set fillStyle(_v){} };
const responsiveCanvas = { width: 0, height: 0, getContext: () => fakeContext, getBoundingClientRect: () => ({ width: 1280, height: 720 }) };
const responsiveRenderer = new CanvasRenderer(responsiveCanvas, null);
responsiveRenderer.resize();
assert.equal(responsiveRenderer.unitSize, 90);
assert.equal(responsiveRenderer.background, '#000000');

const custom = createTheme('manim', {
  name: 'test',
  canvas: { width: 640, height: 360, unitSize: 45, fps: 24, background: '#010203' },
  style: { fill: '#04050650', stroke: '#070809', strokeWidth: .125 },
  text: { fontSize: 31, color: '#0a0b0c', fontFamily: 'Test Sans' },
  animation: { duration: 2.5, waitDuration: .75, easing: 'linear' },
  shape: { dotRadius: .2, arrowTipLength: .5, arrowTipWidth: .4, arrowBuff: .1 },
  mesh3dColor: '#101112',
});
setTheme(custom);

const scene = Scene.headless();
assert.equal(scene.renderer.canvas.width, 640);
assert.equal(scene.renderer.canvas.height, 360);
assert.equal(scene.renderer.unitSize, 45);
assert.equal(scene.fps, 24);
assert.equal(scene.renderer.background, '#010203');
assert.deepEqual(sceneToIR(scene).canvas.background, [1, 2, 3, 255]);

const square = new Square(1);
assert.equal(square.fill, '#04050650');
assert.equal(square.stroke, '#070809');
assert.equal(square.width, .125);

const dot = new Dot();
assert.equal(dot.radius, .2);
assert.equal(dot.fill, '#070809');
const arrow = new Arrow([0, 0], [2, 0]);
assert.equal(arrow.buff, .1);
assert.equal(arrow.tipLength, .5);
assert.equal(arrow.width, .125);
const text = new Text('theme');
assert.equal(text.fontSize, 31);
assert.equal(text.color, '#0a0b0c');
assert.equal(text.fontFamily, 'Test Sans');

scene.add(new Square(1));
scene.objects[0].move([1, 0]);
assert.equal(scene.duration, 2.5);
assert.equal(scene.clips.at(-1).easing, (await import('./src/core.js')).Easing.LINEAR);
scene.wait();
assert.equal(scene.duration, 3.25);

const cfg = configFromObject({ theme: { base: 'manim', canvas: { unit_size: 72 }, style: { stroke: '#abcdef', stroke_width: .05 }, animation: { wait_duration: .25 } } });
assert.equal(cfg.theme.canvas.unitSize, 72);
assert.equal(cfg.theme.style.stroke, '#abcdef');
assert.equal(cfg.theme.style.strokeWidth, .05);
assert.equal(cfg.theme.animation.waitDuration, .25);
const named = configFromObject({ theme: { base: 'manim', name: 'paper', canvas: { fps: 25 } } });
assert.equal(named.theme.name, 'paper');
assert.equal(named.theme.canvas.fps, 25);
await applyConfig({ theme: { base: 'manim', canvas: { unitSize: 80 } } });
assert.equal(getTheme().canvas.unitSize, 80);

setTheme('manim');
console.log('theme: Manim defaults, runtime switching and config overrides passed');
