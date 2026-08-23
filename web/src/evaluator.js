import { Transform2D, lerpColorValue, lerpNumber, lerpStyleState } from './core.js';

export function evaluateValue(scene, value, time) {
  let out = value.initial;
  for (const clip of scene._valueClipsByValue.get(value.id) ?? []) {
    if (time < clip.start) break;
    if (time >= clip.end) { out = clip.after; continue; }
    const alpha = clip.end === clip.start ? 1 : (time - clip.start) / (clip.end - clip.start);
    out = lerpNumber(clip.before, clip.after, clip.easing(alpha));
    break;
  }
  return out;
}

function lerpBatchItem(a, b, t) {
  return a.map((value, i) => {
    if (typeof value === 'number' && typeof b[i] === 'number') return lerpNumber(value, b[i], t);
    if (typeof value === 'string' || typeof b[i] === 'string') return lerpColorValue(typeof value === 'string' ? value : null, typeof b[i] === 'string' ? b[i] : null, t);
    return t < 1 ? value : b[i];
  });
}

export function evaluateBatch(scene, object, time) {
  let out = (scene._batchInitial.get(object.id) ?? object.items).map(item => [...item]);
  for (const clip of scene._batchClipsByObject.get(object.id) ?? []) {
    if (time < clip.start) break;
    if (time >= clip.end) { out = clip.after.map(item => [...item]); continue; }
    const alpha = clip.end === clip.start ? 1 : (time - clip.start) / (clip.end - clip.start);
    const t = clip.easing(alpha);
    out = clip.before.map((item, i) => lerpBatchItem(item, clip.after[i], t));
    break;
  }
  return out;
}

export function evaluateObjectState(scene, object, time) {
  let state = { ...(scene.initial.get(object.id) ?? {}) };
  for (const clip of scene._clipsByObject.get(object.id) ?? []) {
    if (time < clip.start) break;
    if (clip.kind === 'transformFunction') {
      if (time >= clip.end) state.transform = clip.after;
      else {
        const alpha = clip.end === clip.start ? 1 : (time - clip.start) / (clip.end - clip.start);
        state.transform = clip.provider(clip.easing(alpha));
      }
      continue;
    }
    for (const [key, change] of Object.entries(clip.changes)) {
      if (time >= clip.end) state[key] = change.after;
      else {
        const alpha = clip.end === clip.start ? 1 : (time - clip.start) / (clip.end - clip.start);
        const t = clip.easing(alpha);
        if (key === 'transform') state.transform = Transform2D.lerp(change.before, change.after, t);
        else if (key === 'style') state.style = lerpStyleState(change.before, change.after, t);
        else state[key] = lerpNumber(change.before, change.after, t);
      }
    }
  }
  return state;
}

export function parentWorldAt(scene, object, time) {
  const chain = [];
  let parent = object._parent;
  while (parent) { chain.push(parent); parent = parent._parent; }
  let out = Transform2D.identity();
  for (let i = chain.length - 1; i >= 0; i--) out = out.mul(evaluateObjectState(scene, chain[i], time).transform);
  return out;
}

export function worldTransformAt(scene, object, time) {
  return parentWorldAt(scene, object, time).mul(evaluateObjectState(scene, object, time).transform);
}
