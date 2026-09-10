import { CachedBatch2D, assignState, cloneState } from './core.js';

export function seekScene(scene, time) {
  const t0 = performance.now();
  scene.time = Math.max(0, Math.min(scene.duration || time, time));
  scene.renderer.time = scene.time;
  scene.render();
  scene.stats.seekMs = performance.now() - t0;
  return scene;
}

export function renderScene(scene) {
  const t0 = performance.now();
  scene.renderer.resize();
  scene.renderer.clear();
  scene.renderer.time = scene.time;
  if (scene._renderListDirty) {
    scene._renderList = [...scene.objects].sort((a, b) => a.zIndex - b.zIndex);
    scene._renderListDirty = false;
  }

  const savedObjects = [];
  const savedValues = scene.values.map(value => [value, value.value]);
  try {
    for (const object of scene._trackedObjects.values()) {
      const batch = object instanceof CachedBatch2D ? object.items.map(item => [...item]) : null;
      savedObjects.push([object, cloneState(object), batch]);
      assignState(object, scene.stateAt(object, scene.time));
      if (
        object instanceof CachedBatch2D
        && scene._batchInitial.has(object.id)
        && scene.time >= object.birth
        && scene.time < object.death
      ) {
        object.items = scene.batchAt(object, scene.time);
      }
    }
    for (const value of scene.values) value.value = scene.valueAt(value, scene.time);
    for (const object of scene._renderList) {
      if (object.visible && scene.time >= object.birth && scene.time < object.death) {
        object.draw(scene.renderer, scene.camera.transform);
      }
    }
  } finally {
    for (let i = savedObjects.length - 1; i >= 0; i--) {
      const [object, state, batch] = savedObjects[i];
      assignState(object, state);
      if (batch) object.items = batch;
    }
    for (const [value, raw] of savedValues) value.value = raw;
  }

  scene.stats.renderMs = performance.now() - t0;
  scene.stats.frames++;
}

export function playScene(scene, { loop = false, from = 0 } = {}) {
  pauseScene(scene);
  scene.playing = true;
  scene._start = performance.now() - from * 1000;
  const tick = now => {
    if (!scene.playing) return;
    let time = (now - scene._start) / 1000;
    if (scene.duration && time > scene.duration) {
      if (loop) { scene._start = now; time = 0; }
      else { scene.seek(scene.duration); pauseScene(scene); return; }
    }
    scene.seek(time);
    scene._raf = requestAnimationFrame(tick);
  };
  scene._raf = requestAnimationFrame(tick);
  return scene;
}

export function pauseScene(scene) {
  scene.playing = false;
  if (scene._raf) cancelAnimationFrame(scene._raf);
  scene._raf = null;
  return scene;
}

export function destroyScene(scene) {
  pauseScene(scene);
  for (const object of scene._trackedObjects.values()) object.destroy?.();
  scene._resizeObserver?.disconnect();
  scene._resizeObserver = null;
  return scene;
}
