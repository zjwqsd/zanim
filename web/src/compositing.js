import {
  Bounds2D,
  Transform2D,
  ZObject,
  sampleValue,
  setWorldCanvasTransform,
} from './core.js';

function finitePositive(value, name) {
  const number = Number(value);
  if (!(number > 0) || !Number.isFinite(number)) {
    throw new RangeError(`${name} must be a positive finite number`);
  }
  return number;
}

function sceneCanvas(scene) {
  const canvas = scene?.renderer?.canvas;
  if (!canvas || typeof canvas.width !== 'number' || typeof canvas.height !== 'number') {
    throw new TypeError('SceneRasterObject2D requires a renderable child Scene');
  }
  return canvas;
}

function transformedBounds(width, height, transform) {
  const hx = width / 2;
  const hy = height / 2;
  const points = [
    transform.apply(-hx, -hy),
    transform.apply(hx, -hy),
    transform.apply(hx, hy),
    transform.apply(-hx, hy),
  ];
  return new Bounds2D(
    Math.min(...points.map(point => point[0])),
    Math.min(...points.map(point => point[1])),
    Math.max(...points.map(point => point[0])),
    Math.max(...points.map(point => point[1])),
  );
}

/**
 * Draw another Zanim Scene as one transformable object.
 *
 * The child Scene keeps its own renderer/canvas and timeline. The parent only
 * samples that surface, so embedding never flattens the child into a low-res
 * screenshot and the child can later be promoted/reused without recompiling.
 */
export class SceneRasterObject2D extends ZObject {
  constructor(
    scene,
    {
      width = null,
      height = null,
      sourceTime = 0,
      ownsScene = false,
      ...rest
    } = {},
  ) {
    super(rest);
    const canvas = sceneCanvas(scene);
    const sourceWidth = Math.max(1, Number(canvas.width) || 1);
    const sourceHeight = Math.max(1, Number(canvas.height) || 1);
    const aspect = sourceWidth / sourceHeight;

    if (width == null && height == null) {
      width = sourceWidth / 100;
      height = sourceHeight / 100;
    } else if (width == null) {
      height = finitePositive(height, 'height');
      width = height * aspect;
    } else if (height == null) {
      width = finitePositive(width, 'width');
      height = width / aspect;
    } else {
      width = finitePositive(width, 'width');
      height = finitePositive(height, 'height');
    }

    this.scene = scene;
    this.width = width;
    this.height = height;
    this.sourceTime = sourceTime;
    this.ownsScene = Boolean(ownsScene);
    this._lastSample = null;
    this._webRuntimeOnly = 'scene-raster';
  }

  _boundsWithTransform(transform) {
    return transformedBounds(this.width, this.height, transform);
  }

  bounds() {
    return this._boundsWithTransform(this.transform);
  }

  sample(time) {
    const target = Math.max(0, sampleValue(this.sourceTime, time));
    const duration = Number(this.scene.duration) || 0;
    const resolved = duration > 0 ? Math.min(target, duration) : target;
    if (this._lastSample == null || Math.abs(this._lastSample - resolved) > 1e-12) {
      this.scene.seek(resolved);
      this._lastSample = resolved;
    } else if (!this.scene.stats?.frames) {
      this.scene.render();
    }
    return this;
  }

  draw(renderer, parent = Transform2D.identity()) {
    const childCanvas = sceneCanvas(this.scene);
    if (childCanvas === renderer.canvas) {
      throw new Error('SceneRasterObject2D cannot sample from its parent render target');
    }
    this.sample(renderer.time ?? 0);

    const ctx = renderer.ctx;
    const transform = this.world(parent);
    ctx.save();
    ctx.globalAlpha *= Math.max(0, Math.min(1, this.opacity));
    setWorldCanvasTransform(renderer, ctx, transform);
    ctx.scale(1, -1);
    ctx.drawImage(
      childCanvas,
      -this.width / 2,
      -this.height / 2,
      this.width,
      this.height,
    );
    ctx.restore();
  }

  destroy() {
    if (this.ownsScene) this.scene.destroy?.();
  }
}
