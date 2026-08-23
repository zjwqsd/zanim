import {
  Camera2D,
  CanvasRenderer,
  CachedBatch2D,
  DEFAULT_WASM_URL,
  Easing,
  Frame,
  Group,
  LOCAL,
  PARENT,
  WORLD,
  Polyline,
  PolylineInterpolation,
  PrimitiveInterpolation,
  ScalarValue,
  Transform2D,
  Vec2,
  ZObject,
  ZanimWasm,
  appendOrdered,
  assignState,
  cloneState,
  lerpColorValue,
  lerpNumber,
  lerpStyleState,
  snapshotStyle,
} from './core.js';
import {
  evaluateBatch,
  evaluateObjectState,
  evaluateValue,
  parentWorldAt,
  worldTransformAt,
} from './evaluator.js';
import { destroyScene, pauseScene, playScene, renderScene, seekScene } from './player.js';

class HeadlessRenderer {
  constructor({ width = 1280, height = 720, unitSize = 90 } = {}) {
    this.canvas = { width, height };
    this.baseUnitSize = unitSize;
    this.unitSize = unitSize;
    this.dpr = 1;
  }
  resize() {}
  clear() { throw new Error('headless Scene cannot render; compile it with @zanim/web/ir'); }
}

function spansOverlap(a0, a1, b0, b1) {
  if (a0 === a1 || b0 === b1) return false;
  return a0 < b1 - 1e-12 && b0 < a1 - 1e-12;
}

function spansTouch(a0, a1, b0, b1) {
  if (a0 === a1 && b0 === b1) return Math.abs(a0 - b0) <= 1e-12;
  if (a0 === a1) return b0 - 1e-12 <= a0 && a0 < b1 - 1e-12;
  if (b0 === b1) return a0 - 1e-12 <= b0 && b0 < a1 - 1e-12;
  return a0 < b1 - 1e-12 && b0 < a1 - 1e-12;
}

export class Scene {
  constructor(renderer, { fps = 60 } = {}) {
    this.renderer = renderer;
    this.objects = [];
    this.fps = fps;
    this.cursor = 0;
    this.duration = 0;
    this.clips = [];
    this.valueClips = [];
    this.values = [];
    this.interpolations = [];
    this.initial = new Map();
    this._trackedObjects = new Map();
    this._clipsByObject = new Map();
    this._valueClipsByValue = new Map();
    this._batchInitial = new Map();
    this._batchClipsByObject = new Map();
    this._mediaClipsByObject = new Map();
    this._worldSpaceSpans = new Map();
    this._parallelBase = null;
    this._parallelEnd = null;
    this._parallelDuration = null;
    this._renderList = [];
    this._renderListDirty = true;
    this.playing = false;
    this._raf = null;
    this._start = 0;
    this.time = 0;
    this.stats = { renderMs: 0, seekMs: 0, frames: 0 };
    this._resizeObserver = null;
    this.renderer.resize?.();
    this.camera = new Camera2D(this);
    this._track(this.camera, 0);
  }

  static headless({ width = 1280, height = 720, unitSize = 90, fps = 60 } = {}) {
    return new Scene(new HeadlessRenderer({ width, height, unitSize }), { fps });
  }

  static async create(canvas, { wasmURL = DEFAULT_WASM_URL, wasm = null, renderer = {}, fps = 60, observeResize = true } = {}) {
    const target = typeof canvas === 'string' ? document.querySelector(canvas) : canvas;
    if (!target || typeof target.getContext !== 'function') throw new TypeError('Scene.create requires a canvas element or selector');
    const engine = wasm ?? await ZanimWasm.load(wasmURL);
    const scene = new Scene(new CanvasRenderer(target, engine, renderer), { fps });
    if (observeResize && typeof ResizeObserver !== 'undefined') {
      scene._resizeObserver = new ResizeObserver(() => scene.render());
      scene._resizeObserver.observe(target);
    }
    scene.render();
    return scene;
  }

  _track(object, birth = this.cursor) {
    if (!this._trackedObjects.has(object.id)) {
      this._trackedObjects.set(object.id, object);
      object._scene = this;
      object.birth = birth;
      this.initial.set(object.id, cloneState(object));
      if (object instanceof CachedBatch2D) this._batchInitial.set(object.id, object.items.map(item => [...item]));
      if (object instanceof Group) {
        for (const child of object.children) {
          child._parent = object;
          this._track(child, birth);
        }
      }
    }
    return object;
  }

  add(...objects) {
    this._requireLifetimeBoundary();
    for (const object of objects) {
      if (!this.objects.includes(object)) {
        this.objects.push(object);
        this._renderListDirty = true;
      }
      this._track(object, this.cursor);
    }
    return objects.length === 1 ? objects[0] : objects;
  }

  addLater(...objects) { return this.add(...objects); }
  remove(...objects) {
    this._requireLifetimeBoundary();
    for (const object of objects) {
      if (!this._trackedObjects.has(object.id)) throw new Error('object is not in this scene');
      if (object === this.camera) throw new TypeError('Camera2D cannot be removed from Scene');
      if (Number.isFinite(object.death)) throw new Error('object has already been removed from this scene');
      if (this.cursor < object.birth) throw new Error('object cannot be removed before it is added');
      object.death = this.cursor;
    }
    return this;
  }
  invalidateOrder() { this._renderListDirty = true; return this; }

  addValue(...values) {
    for (const value of values) if (!this.values.includes(value)) this.values.push(value);
    return values.length === 1 ? values[0] : values;
  }

  _scheduleBase() { return this._parallelBase == null ? this.cursor : this._parallelBase; }

  _resolveDuration(duration) {
    const value = duration ?? this._parallelDuration ?? 1;
    if (!(value >= 0)) throw new RangeError('duration must be >= 0');
    return Number(value);
  }

  _span(duration, at = 0) {
    const resolved = this._resolveDuration(duration);
    const start = this._scheduleBase() + Number(at);
    return { start, end: start + resolved, duration: resolved };
  }

  _advanceAfterSchedule(end) {
    if (this._parallelBase == null) this.cursor = end;
    else this._parallelEnd = Math.max(this._parallelEnd, end);
    this.duration = Math.max(this.duration, end);
  }

  animateValue(value, { to, duration = null, easing = Easing.SMOOTHSTEP, at = 0 } = {}) {
    if (!this.values.includes(value)) this.addValue(value);
    const span = this._span(duration, at);
    const existing = this._valueClipsByValue.get(value.id) ?? [];
    if (existing.some(clip => spansOverlap(span.start, span.end, clip.start, clip.end))) throw new Error(`overlapping value channel for value ${value.id}`);
    if (existing.length && span.start < existing.at(-1).start - 1e-12) throw new Error('clips on the same channel must be authored in chronological order');
    const before = this.valueAt(value, span.start);
    const clip = { value, start: span.start, end: span.end, before, after: Number(to), easing };
    this.valueClips.push(clip);
    appendOrdered(this._valueClipsByValue, value.id, clip);
    this._advanceAfterSchedule(clip.end);
    value.value = Number(to);
    return value;
  }

  valueAt(value, time) { return evaluateValue(this, value, time); }

  wait(seconds = 1) {
    if (this._parallelBase != null) throw new Error('wait() is not allowed inside parallel()');
    this.cursor += seconds;
    this.duration = Math.max(this.duration, this.cursor);
    return this;
  }
  at(seconds) {
    if (this._parallelBase != null) throw new Error('at() is not allowed inside parallel()');
    this.cursor = Number(seconds);
    this.duration = Math.max(this.duration, this.cursor);
    return this;
  }

  _scheduleClip(object, clip) {
    this.clips.push(clip);
    appendOrdered(this._clipsByObject, object.id, clip);
    this._advanceAfterSchedule(clip.end);
    return clip;
  }

  _requireLifetimeBoundary() {
    if (this._parallelBase != null) throw new Error('add() and remove() are not allowed inside parallel()');
  }

  _effectiveLifetime(object) {
    let birth = object.birth;
    let death = object.death;
    for (const parent of this._ancestors(object)) {
      birth = Math.max(birth, parent.birth);
      death = Math.min(death, parent.death);
    }
    return { birth, death };
  }

  _requireAliveForSpan(object, span) {
    if (!this._trackedObjects.has(object.id)) throw new Error('object must be added before animation');
    const { birth, death } = this._effectiveLifetime(object);
    if (span.start < birth - 1e-12) throw new Error(`animation starts at ${span.start}, before object lifetime begins at ${birth}`);
    if (Number.isFinite(death) && (span.end > death + 1e-12 || span.start >= death - 1e-12)) throw new Error(`animation lies outside object lifetime ending at ${death}`);
  }

  _clipChannels(clip) {
    if (clip.kind === 'transformFunction') return ['transform'];
    if (clip.kind !== 'state') return [];
    return Object.keys(clip.changes).map(key => key === 'reveal' ? 'trim' : key);
  }

  _assertObjectChannelsAvailable(object, channels, span) {
    const wanted = new Set(channels);
    let latestStart = -Infinity;
    for (const clip of this._clipsByObject.get(object.id) ?? []) {
      if (!this._clipChannels(clip).some(channel => wanted.has(channel))) continue;
      latestStart = Math.max(latestStart, clip.start);
      if (spansOverlap(span.start, span.end, clip.start, clip.end)) throw new Error(`overlapping animation channel for object ${object.id}`);
    }
    if (span.start < latestStart - 1e-12) throw new Error(`clips on the same channel must be authored in chronological order`);
  }

  _transformClips(object) {
    return (this._clipsByObject.get(object.id) ?? []).filter(
      clip => clip.kind === 'transformFunction' || clip.changes?.transform,
    );
  }

  _ancestors(object) {
    const out = [];
    let parent = object._parent;
    while (parent) { out.push(parent); parent = parent._parent; }
    return out;
  }

  _isAncestor(ancestor, object) {
    let parent = object._parent;
    while (parent) {
      if (parent === ancestor) return true;
      parent = parent._parent;
    }
    return false;
  }

  _assertWorldParentStatic(object, start, end) {
    for (const parent of this._ancestors(object)) {
      for (const clip of this._transformClips(parent)) {
        if (spansTouch(start, end, clip.start, clip.end)) {
          throw new Error('WORLD transform on a nested object requires all ancestors to remain transform-static over the same span; use LOCAL/PARENT for articulated motion');
        }
      }
    }
  }

  _assertNoDescendantWorldDependency(object, start, end) {
    for (const [id, spans] of this._worldSpaceSpans) {
      const child = this._trackedObjects.get(id);
      if (!child || !this._isAncestor(object, child)) continue;
      if (spans.some(([s0, s1]) => spansTouch(start, end, s0, s1))) {
        throw new Error('ancestor transform overlaps a nested WORLD transform; use LOCAL/PARENT for articulated motion');
      }
    }
  }

  _recordWorldSpan(object, start, end) {
    let spans = this._worldSpaceSpans.get(object.id);
    if (!spans) this._worldSpaceSpans.set(object.id, spans = []);
    spans.push([start, end]);
  }

  animate(object, { transform = undefined, opacity = undefined, reveal = undefined, style = undefined, duration = null, easing = Easing.SMOOTHSTEP, at = 0 } = {}) {
    const span = this._span(duration, at);
    this._requireAliveForSpan(object, span);
    if (transform !== undefined) this._assertNoDescendantWorldDependency(object, span.start, span.end);
    const before = this.stateAt(object, span.start);
    const changes = {};
    if (transform !== undefined) changes.transform = { before: before.transform, after: transform };
    if (opacity !== undefined) changes.opacity = { before: before.opacity, after: Number(opacity) };
    if (reveal !== undefined) changes.reveal = { before: before.reveal, after: Number(reveal) };
    if (style !== undefined) changes.style = { before: before.style, after: style };
    this._assertObjectChannelsAvailable(object, Object.keys(changes).map(key => key === 'reveal' ? 'trim' : key), span);
    const clip = { kind: 'state', object, start: span.start, end: span.end, easing, changes };
    this._scheduleClip(object, clip);
    const authored = { ...before };
    for (const [key, value] of Object.entries(changes)) authored[key] = value.after;
    assignState(object, authored);
    return object;
  }

  transformFunction(object, provider, { duration = null, easing = Easing.SMOOTHSTEP, at = 0 } = {}) {
    const span = this._span(duration, at);
    this._requireAliveForSpan(object, span);
    this._assertNoDescendantWorldDependency(object, span.start, span.end);
    this._assertObjectChannelsAvailable(object, ['transform'], span);
    const before = this.stateAt(object, span.start);
    const target = provider(1);
    if (!(target instanceof Transform2D)) throw new TypeError('transformFunction provider must return Transform2D');
    const clip = { kind: 'transformFunction', object, start: span.start, end: span.end, easing, provider, before: before.transform, after: target };
    this._scheduleClip(object, clip);
    object.transform = target;
    return object;
  }

  fadeIn(object, { duration = null, easing = Easing.SMOOTHSTEP, at = 0 } = {}) {
    const before = this.stateAt(object, this._span(duration, at).start);
    if (Math.abs(before.opacity) > 1e-12) throw new Error(`fadeIn() requires opacity 0, got ${before.opacity}`);
    return this.animate(object, { opacity: 1, duration, easing, at });
  }
  fadeOut(object, { duration = null, easing = Easing.SMOOTHSTEP, at = 0 } = {}) { return this.animate(object, { opacity: 0, duration, easing, at }); }
  style(object, { to, duration = null, easing = Easing.SMOOTHSTEP, at = 0 } = {}) { if (!snapshotStyle(object)) throw new TypeError('style() requires a styled 2D object'); return this.animate(object, { style: to, duration, easing, at }); }
  trim(object, { to, duration = null, easing = Easing.SMOOTHSTEP, at = 0 } = {}) { if (!('reveal' in object)) throw new TypeError('trim() requires a path-trimmable object'); if (!(to >= 0 && to <= 1)) throw new RangeError('trim target must be in [0,1]'); return this.animate(object, { reveal: to, duration, easing, at }); }
  create(object, { duration = null, easing = Easing.SMOOTHSTEP, at = 0 } = {}) { const before = this.stateAt(object, this._span(duration, at).start); if (before.reveal == null) throw new TypeError('create() currently supports path objects'); if (Math.abs(before.reveal) > 1e-12) throw new Error(`create() requires trim 0, got ${before.reveal}`); return this.trim(object, { to: 1, duration, easing, at }); }

  batchAt(object, time) { return evaluateBatch(this, object, time); }

  media(object, { duration = null, sourceStart = 0, speed = 1, loop = false, sourceDuration = object?.duration ?? null, at = 0 } = {}) {
    if (!object || !object._mediaKind) throw new TypeError('media() requires a Web media object');
    const rate = Number(speed);
    if (!(rate > 0) || !Number.isFinite(rate)) throw new RangeError('media speed must be positive');
    const startAt = Number(sourceStart);
    if (startAt < 0 || !Number.isFinite(startAt)) throw new RangeError('media sourceStart must be >= 0');
    let resolvedDuration = duration;
    const sourceLength = sourceDuration == null ? null : Number(sourceDuration);
    if (resolvedDuration == null) {
      if (!(sourceLength >= 0) || !Number.isFinite(sourceLength)) throw new Error('media playback needs duration until source metadata is available');
      resolvedDuration = Math.max(0, sourceLength - startAt) / rate;
    }
    const span = this._span(resolvedDuration, at);
    this._requireAliveForSpan(object, span);
    const existing = this._mediaClipsByObject.get(object.id) ?? [];
    if (existing.some(clip => spansOverlap(span.start, span.end, clip.start, clip.end))) throw new Error(`overlapping media channel for object ${object.id}`);
    if (existing.length && span.start < existing.at(-1).start - 1e-12) throw new Error('clips on the same channel must be authored in chronological order');
    const clip = { kind:'media', object, start:span.start, end:span.end, sourceStart:startAt, speed:rate, loop:!!loop, sourceDuration:sourceLength };
    appendOrdered(this._mediaClipsByObject, object.id, clip);
    this.clips.push(clip);
    this._advanceAfterSchedule(span.end);
    return object;
  }

  mediaPlaybackAt(object, time) {
    for (const clip of this._mediaClipsByObject.get(object.id) ?? []) if (time >= clip.start && time < clip.end) return clip;
    return null;
  }

  mediaTimeAt(object, time) {
    const clips = this._mediaClipsByObject.get(object.id) ?? [];
    if (!clips.length) return 0;
    const clip = this.mediaPlaybackAt(object, time);
    if (!clip) return null;
    const sourceDuration = clip.sourceDuration ?? object.duration;
    if (!(sourceDuration >= 0)) return clip.sourceStart;
    const elapsed = Math.max(0, Number(time) - clip.start) * clip.speed;
    if (clip.loop) {
      const length = sourceDuration - clip.sourceStart;
      return length > 0 ? clip.sourceStart + (elapsed % length) : clip.sourceStart;
    }
    return Math.min(sourceDuration, clip.sourceStart + elapsed);
  }

  batch(object, { to, duration = null, easing = Easing.SMOOTHSTEP, at = 0 } = {}) {
    if (!(object instanceof CachedBatch2D)) throw new TypeError('batch() requires a batch object');
    const target = to instanceof CachedBatch2D ? to.items : to;
    if (!Array.isArray(target)) throw new TypeError('batch target must be an item array or batch object');
    const span = this._span(duration, at);
    this._requireAliveForSpan(object, span);
    const existing = this._batchClipsByObject.get(object.id) ?? [];
    if (existing.some(clip => spansOverlap(span.start, span.end, clip.start, clip.end))) throw new Error(`overlapping batch channel for object ${object.id}`);
    if (existing.length && span.start < existing.at(-1).start - 1e-12) throw new Error('clips on the same channel must be authored in chronological order');
    const before = this.batchAt(object, span.start);
    if (before.length !== target.length) throw new RangeError('batch interpolation requires matching item counts');
    const clip = { kind: 'batch', object, start: span.start, end: span.end, before, after: target.map(item => [...item]), easing };
    appendOrdered(this._batchClipsByObject, object.id, clip);
    this.clips.push(clip);
    this._advanceAfterSchedule(clip.end);
    object.items = clip.after.map(item => [...item]);
    return object;
  }

  _parentWorldAt(object, time) { return parentWorldAt(this, object, time); }

  worldTransformAt(object, time = this.cursor) { return worldTransformAt(this, object, time); }

  move(object, by, { frame = WORLD, duration = null, easing = Easing.SMOOTHSTEP, at = 0 } = {}) {
    const span = this._span(duration, at);
    const v = Vec2.from(by), current = object.transform, delta = Transform2D.translation(v.x, v.y);
    let target;
    if (frame === LOCAL) target = current.mul(delta);
    else if (frame === PARENT) target = delta.mul(current);
    else if (frame === WORLD) {
      const parent = this._parentWorldAt(object, span.start);
      if (object._parent) this._assertWorldParentStatic(object, span.start, span.end);
      this._assertNoDescendantWorldDependency(object, span.start, span.end);
      target = parent.inverse().mul(delta).mul(parent).mul(current);
      if (object._parent) this._recordWorldSpan(object, span.start, span.end);
    } else throw new Error(`unknown frame ${frame}`);
    return this.animate(object, { transform: target, duration, easing, at });
  }

  rotate(object, by, { frame = PARENT, about = null, duration = null, easing = Easing.SMOOTHSTEP, at = 0 } = {}) {
    const span = this._span(duration, at);
    const current = object.transform, R = Transform2D.rotation(by);
    let target;
    if (about) {
      const q = Vec2.from(about), parent = this._parentWorldAt(object, span.start);
      if (object._parent) this._assertWorldParentStatic(object, span.start, span.end);
      this._assertNoDescendantWorldDependency(object, span.start, span.end);
      const op = Transform2D.translation(q.x, q.y).mul(R).mul(Transform2D.translation(-q.x, -q.y));
      target = parent.inverse().mul(op).mul(parent).mul(current);
      if (object._parent) this._recordWorldSpan(object, span.start, span.end);
    } else if (frame === LOCAL) target = current.mul(R);
    else if (frame === PARENT) target = R.mul(current);
    else if (frame === WORLD) {
      const parent = this._parentWorldAt(object, span.start);
      if (object._parent) this._assertWorldParentStatic(object, span.start, span.end);
      this._assertNoDescendantWorldDependency(object, span.start, span.end);
      target = parent.inverse().mul(R).mul(parent).mul(current);
      if (object._parent) this._recordWorldSpan(object, span.start, span.end);
    } else throw new Error(`unknown frame ${frame}`);
    return this.animate(object, { transform: target, duration, easing, at });
  }

  scale(object, by, { frame = PARENT, about = null, duration = null, easing = Easing.SMOOTHSTEP, at = 0 } = {}) {
    const span = this._span(duration, at);
    const S = Transform2D.scaling(by), current = object.transform;
    let target;
    if (about) {
      const q = Vec2.from(about), parent = this._parentWorldAt(object, span.start);
      if (object._parent) this._assertWorldParentStatic(object, span.start, span.end);
      this._assertNoDescendantWorldDependency(object, span.start, span.end);
      const op = Transform2D.translation(q.x, q.y).mul(S).mul(Transform2D.translation(-q.x, -q.y));
      target = parent.inverse().mul(op).mul(parent).mul(current);
      if (object._parent) this._recordWorldSpan(object, span.start, span.end);
    } else if (frame === LOCAL) target = current.mul(S);
    else if (frame === PARENT) target = S.mul(current);
    else if (frame === WORLD) {
      const parent = this._parentWorldAt(object, span.start);
      if (object._parent) this._assertWorldParentStatic(object, span.start, span.end);
      this._assertNoDescendantWorldDependency(object, span.start, span.end);
      target = parent.inverse().mul(S).mul(parent).mul(current);
      if (object._parent) this._recordWorldSpan(object, span.start, span.end);
    } else throw new Error(`unknown frame ${frame}`);
    return this.animate(object, { transform: target, duration, easing, at });
  }

  affine(object, { position = [0, 0], rotation = 0, scale = 1, shear = [0, 0], duration = null, easing = Easing.SMOOTHSTEP, at = 0 } = {}) {
    return this.animate(object, { transform: Transform2D.affine({ position, rotation, scale, shear }), duration, easing, at });
  }

  interpolate(source, target, { duration = null, easing = Easing.SMOOTHSTEP, at = 0 } = {}) {
    const span = this._span(duration, at);
    const transient = (source instanceof Polyline && target instanceof Polyline && !source.closed && !target.closed)
      ? new PolylineInterpolation(source, target, span.start, span.end, easing)
      : new PrimitiveInterpolation(source, target, span.start, span.end, easing);
    transient._transientInterpolation = true;
    this.objects.push(transient);
    this._track(transient, span.start);
    transient.birth = span.start;
    transient.death = span.end;
    this.interpolations.push({ source, target, start: span.start, end: span.end, easing, transient });
    this._renderListDirty = true;
    this._advanceAfterSchedule(span.end);
    return transient;
  }

  replace(source, target, { duration = 1, easing = Easing.SMOOTHSTEP } = {}) {
    if (!this.objects.includes(source)) throw new Error('replace() source must be a top-level scene object');
    if (this._trackedObjects.has(target.id)) throw new Error('replace() target must not already be in the scene');
    const start = this.cursor, end = start + duration;
    this.interpolate(source, target, { duration, easing, at: 0 });
    source.death = start;
    this.objects.push(target);
    this._track(target, end);
    target.birth = end;
    this._renderListDirty = true;
    this.cursor = end;
    this.duration = Math.max(this.duration, end);
    return target;
  }

  parallel(durationOrCallback, maybeCallback) {
    if (this._parallelBase != null) throw new Error('nested parallel() blocks are not supported');
    const shared = typeof durationOrCallback === 'function' ? null : Number(durationOrCallback);
    const callback = typeof durationOrCallback === 'function' ? durationOrCallback : maybeCallback;
    if (typeof callback !== 'function') throw new TypeError('parallel requires a callback');
    if (shared != null && shared < 0) throw new RangeError('parallel duration must be >= 0');
    this._parallelBase = this.cursor;
    this._parallelEnd = this.cursor;
    this._parallelDuration = shared;
    const withShared = opts => shared == null || opts?.duration != null ? (opts ?? {}) : { ...(opts ?? {}), duration: shared };
    const api = {
      animate: (obj, opts = {}) => this.animate(obj, withShared(opts)),
      animateValue: (value, opts = {}) => this.animateValue(value, withShared(opts)),
      transformFunction: (obj, provider, opts = {}) => this.transformFunction(obj, provider, withShared(opts)),
      fadeIn: (obj, opts = {}) => this.fadeIn(obj, withShared(opts)),
      fadeOut: (obj, opts = {}) => this.fadeOut(obj, withShared(opts)),
      create: (obj, opts = {}) => this.create(obj, withShared(opts)),
      style: (obj, opts = {}) => this.style(obj, withShared(opts)),
      batch: (obj, opts = {}) => this.batch(obj, withShared(opts)),
      media: (obj, opts = {}) => this.media(obj, withShared(opts)),
      move: (obj, by, opts = {}) => this.move(obj, by, withShared(opts)),
      rotate: (obj, by, opts = {}) => this.rotate(obj, by, withShared(opts)),
      scale: (obj, by, opts = {}) => this.scale(obj, by, withShared(opts)),
      affine: (obj, opts = {}) => this.affine(obj, withShared(opts)),
      interpolate: (source, target, opts = {}) => this.interpolate(source, target, withShared(opts)),
    };
    try { callback(api); }
    finally {
      this.cursor = Math.max(this.cursor, this._parallelEnd);
      this._parallelBase = null;
      this._parallelEnd = null;
      this._parallelDuration = null;
    }
    return this;
  }

  stateAt(object, time) { return evaluateObjectState(this, object, time); }

  get frame() { return Frame.fromRenderer(this.renderer); }

  layout(...args) {
    let options = args.at(-1);
    if (!options || typeof options !== 'object' || !('to' in options)) throw new TypeError('Scene.layout requires {to, duration?, easing?, at?}');
    args = args.slice(0, -1);
    const objects = args.length === 1 && args[0] instanceof Group ? args[0].children : args;
    const targets = options.to.targets(...objects);
    this.parallel(options.duration ?? 1, api => objects.forEach((object, i) => api.animate(object, { transform: targets[i], easing: options.easing ?? Easing.SMOOTHSTEP, at: options.at ?? 0 })));
    return objects;
  }

  seek(time) { return seekScene(this, time); }
  render() { return renderScene(this); }
  play(options = {}) { return playScene(this, options); }
  pause() { return pauseScene(this); }
  destroy() { return destroyScene(this); }
  setMatrix(matrix) { for (const object of this.objects) object.transform = Transform2D.fromMat2(matrix); for (const object of this.objects) this.initial.set(object.id, cloneState(object)); this.render(); }
  animateTo(target, duration = 1000) { const seconds = duration / 1000, start = this.time || 0, targets = this.objects.map(object => [object, Transform2D.fromMat2(target)]); this.at(start); this.parallel(seconds, api => { for (const [object, transform] of targets) api.animate(object, { transform }); }); this.play({ from: start }); }
}
