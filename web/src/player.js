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
      let batchRestore = null;
      savedObjects.push([object, cloneState(object), batchRestore]);
      assignState(object, scene.stateAt(object, scene.time));
      const batchClips = object instanceof CachedBatch2D
        ? scene._batchClipsByObject.get(object.id)
        : null;
      if (
        batchClips?.length
        && scene.time >= object.birth
        && scene.time < object.death
      ) {
        // Batch clips temporarily replace retained geometry for this sample.
        // Preserve the authored references/cache directly: going through the
        // public items setter would invalidate an otherwise reusable Path2D
        // cache on every render, defeating CachedBatch2D entirely.
        batchRestore = [object._items, object._cache];
        savedObjects[savedObjects.length - 1][2] = batchRestore;
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
      const [object, state, batchRestore] = savedObjects[i];
      assignState(object, state);
      if (batchRestore) {
        object._items = batchRestore[0];
        object._cache = batchRestore[1];
      }
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
