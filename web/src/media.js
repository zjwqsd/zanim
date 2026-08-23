import { Bounds2D, Transform2D, ZObject, setWorldCanvasTransform } from './core.js';

function finitePositive(value, name) {
  const n = Number(value);
  if (!(n > 0) || !Number.isFinite(n)) throw new RangeError(`${name} must be positive`);
  return n;
}

function mediaBounds(width, height, m) {
  const hx = width * .5, hy = height * .5;
  const points = [[-hx,-hy],[hx,-hy],[hx,hy],[-hx,hy]].map(([x,y]) => m.apply(x,y));
  return new Bounds2D(
    Math.min(...points.map(p => p[0])), Math.min(...points.map(p => p[1])),
    Math.max(...points.map(p => p[0])), Math.max(...points.map(p => p[1])),
  );
}

function normalizeSize(sourceWidth, sourceHeight, width, height) {
  const aspect = sourceWidth > 0 && sourceHeight > 0 ? sourceWidth / sourceHeight : null;
  if (width == null && height == null) {
    if (aspect) return [sourceWidth / 100, sourceHeight / 100];
    return [4, 3];
  }
  if (width == null) return [finitePositive(height, 'height') * (aspect ?? 4/3), finitePositive(height, 'height')];
  if (height == null) return [finitePositive(width, 'width'), finitePositive(width, 'width') / (aspect ?? 4/3)];
  return [finitePositive(width, 'width'), finitePositive(height, 'height')];
}

export class MediaObject2D extends ZObject {
  constructor(url, { width = null, height = null, sourceWidth = 0, sourceHeight = 0, duration = null, crossOrigin = null, ...rest } = {}) {
    super(rest);
    this.url = String(url);
    this.sourceWidth = Number(sourceWidth) || 0;
    this.sourceHeight = Number(sourceHeight) || 0;
    this.duration = duration == null ? null : Number(duration);
    this.crossOrigin = crossOrigin;
    [this.width, this.height] = normalizeSize(this.sourceWidth, this.sourceHeight, width, height);
    this._explicitWidth = width != null;
    this._explicitHeight = height != null;
    this._mediaKind = 'media';
    this._webRuntimeOnly = 'media';
    this._element = null;
    this._loadError = null;
    this.ready = Promise.resolve(this);
  }

  _updateNaturalSize(width, height) {
    this.sourceWidth = Number(width) || this.sourceWidth;
    this.sourceHeight = Number(height) || this.sourceHeight;
    if (!this._explicitWidth || !this._explicitHeight) {
      const next = normalizeSize(this.sourceWidth, this.sourceHeight, this._explicitWidth ? this.width : null, this._explicitHeight ? this.height : null);
      this.width = next[0]; this.height = next[1];
    }
    return this;
  }

  _boundsWithTransform(m) { return mediaBounds(this.width, this.height, m); }
  bounds() { return this._boundsWithTransform(this.transform); }
  media(options = {}) { this._bound().media(this, options); return this; }

  _drawElement(renderer, parent, element) {
    if (!element) return;
    const ctx = renderer.ctx, m = this.world(parent);
    ctx.save();
    ctx.globalAlpha *= Math.max(0, Math.min(1, this.opacity));
    setWorldCanvasTransform(renderer, ctx, m);
    // Canvas world coordinates point upward; flip the bitmap once so source
    // scanlines retain their normal top-to-bottom orientation.
    ctx.drawImage(element, -this.width / 2, this.height / 2, this.width, -this.height);
    ctx.restore();
  }
}

class ImageLikeMedia extends MediaObject2D {
  constructor(url, options = {}) {
    super(url, options);
    const image = new globalThis.Image();
    if (this.crossOrigin != null) image.crossOrigin = this.crossOrigin;
    image.decoding = 'async';
    this._element = image;
    this.ready = new Promise((resolve, reject) => {
      image.addEventListener('load', () => { this._updateNaturalSize(image.naturalWidth, image.naturalHeight); if(this._scene?.renderer?.ctx)this._scene.render(); resolve(this); }, { once:true });
      image.addEventListener('error', () => { const err = new Error(`failed to load media ${this.url}`); this._loadError = err; reject(err); }, { once:true });
    });
    image.src = this.url;
  }
  draw(renderer, parent = Transform2D.identity()) { const time=renderer.time??0;if(this._scene&&this._scene.mediaTimeAt(this,time)==null)return;if(this._element?.complete&&this._element.naturalWidth)this._drawElement(renderer,parent,this._element); }
}

export class Image extends ImageLikeMedia {
  constructor(url, options = {}) { super(url, options); this._mediaKind = 'image'; }
}

export class GIF extends MediaObject2D {
  constructor(url, options = {}) {
    super(url, options);
    this._mediaKind = 'gif';
    this._frame = null;
    this._frameIndex = -1;
    this._requestedIndex = -1;
    this._starts = [0];
    this._decoder = null;
    this._fallback = null;
    this.ready = this._load();
  }

  async _load() {
    if (typeof globalThis.ImageDecoder !== 'function') {
      const image = new globalThis.Image();
      if (this.crossOrigin != null) image.crossOrigin = this.crossOrigin;
      this._fallback = image;
      await new Promise((resolve, reject) => {
        image.addEventListener('load', resolve, { once:true });
        image.addEventListener('error', () => reject(new Error(`failed to load GIF ${this.url}`)), { once:true });
        image.src = this.url;
      });
      this._updateNaturalSize(image.naturalWidth, image.naturalHeight);
      if (this._scene?.renderer?.ctx) this._scene.render();
      return this;
    }
    const response = await fetch(this.url);
    if (!response.ok) throw new Error(`failed to load GIF ${this.url} (${response.status})`);
    const data = await response.arrayBuffer();
    const decoder = new ImageDecoder({ data, type:'image/gif', preferAnimation:true });
    await decoder.tracks.ready;
    const track = decoder.tracks.selectedTrack;
    if (!track) throw new Error(`GIF has no selected track: ${this.url}`);
    this._decoder = decoder;
    const count = Math.max(1, Number(track.frameCount) || 1);
    const starts = [];
    let total = 0;
    for (let index = 0; index < count; index++) {
      const result = await decoder.decode({ frameIndex:index });
      const frame = result.image;
      if (index === 0) this._updateNaturalSize(frame.displayWidth, frame.displayHeight);
      starts.push(total);
      total += Math.max(1, Number(frame.duration) || 100_000) / 1_000_000;
      frame.close();
    }
    this._starts = starts;
    this.duration = total;
    await this._requestFrame(0);
    if (this._scene?.renderer?.ctx) this._scene.render();
    return this;
  }

  _indexAt(sourceTime) {
    if (this._starts.length <= 1) return 0;
    const t = Math.max(0, Math.min(Number(sourceTime), Math.max(0, (this.duration ?? 0) - 1e-9)));
    let lo=0, hi=this._starts.length;
    while (lo < hi) { const mid=(lo+hi)>>1; if (this._starts[mid] <= t + 1e-12) lo=mid+1; else hi=mid; }
    return Math.max(0, Math.min(this._starts.length-1, lo-1));
  }

  async _requestFrame(index) {
    if (!this._decoder || index === this._frameIndex || index === this._requestedIndex) return;
    this._requestedIndex = index;
    try {
      const result = await this._decoder.decode({ frameIndex:index });
      if (this._requestedIndex !== index) { result.image.close(); return; }
      this._frame?.close();
      this._frame = result.image;
      this._frameIndex = index;
      if (this._scene?.renderer?.ctx) this._scene.render();
    } finally {
      if (this._requestedIndex === index) this._requestedIndex = -1;
    }
  }

  draw(renderer, parent = Transform2D.identity()) {
    const time = renderer.time ?? 0, sourceTime = this._scene ? this._scene.mediaTimeAt(this, time) : 0;
    if (sourceTime == null) return;
    if (this._fallback) { this._drawElement(renderer, parent, this._fallback); return; }
    const index = this._indexAt(sourceTime);
    if (index !== this._frameIndex) this._requestFrame(index).catch(() => {});
    if (this._frame && this._frameIndex === index) this._drawElement(renderer, parent, this._frame);
  }

  destroy() {
    this._frame?.close();
    this._frame = null;
    this._decoder?.close?.();
    this._decoder = null;
    if (this._fallback) this._fallback.src = '';
  }
}

export class Video extends MediaObject2D {
  constructor(url, { muted = true, playsInline = true, preload = 'auto', ...options } = {}) {
    super(url, options);
    const video = document.createElement('video');
    if (this.crossOrigin != null) video.crossOrigin = this.crossOrigin;
    video.preload = preload;
    video.muted = !!muted;
    video.playsInline = !!playsInline;
    this._element = video;
    this._mediaKind = 'video';
    this.ready = new Promise((resolve, reject) => {
      video.addEventListener('loadedmetadata', () => {
        this.duration = Number.isFinite(video.duration) ? video.duration : this.duration;
        this._updateNaturalSize(video.videoWidth, video.videoHeight);
        resolve(this);
      }, { once:true });
      video.addEventListener('loadeddata', () => { if(this._scene?.renderer?.ctx)this._scene.render(); });
      video.addEventListener('seeked', () => { if(this._scene?.renderer?.ctx&&!this._scene.playing)this._scene.render(); });
      video.addEventListener('error', () => { const err = new Error(`failed to load video ${this.url}`); this._loadError = err; reject(err); }, { once:true });
    });
    video.src = this.url;
    video.load();
  }

  _sync(time) {
    const scene = this._scene;
    if (!scene || !this._element || this._element.readyState < 1) return false;
    const playback = scene.mediaPlaybackAt(this, time);
    const desired = scene.mediaTimeAt(this, time);
    if (desired == null) { this._element.pause(); return false; }
    if (scene.playing && playback) {
      this._element.playbackRate = Math.max(.0625, Math.min(16, playback.speed));
      this._element.loop = !!playback.loop;
      if (Math.abs(this._element.currentTime - desired) > .15) this._element.currentTime = desired;
      this._element.play().catch(() => {});
    } else {
      this._element.pause();
      if (Math.abs(this._element.currentTime - desired) > 1 / 120) this._element.currentTime = desired;
    }
    return this._element.readyState >= 2;
  }

  draw(renderer, parent = Transform2D.identity()) {
    if (this._sync(renderer.time ?? 0)) this._drawElement(renderer, parent, this._element);
  }

  destroy() {
    this._element?.pause();
    if (this._element) this._element.removeAttribute('src');
    this._element?.load();
  }
}

export class Audio extends ZObject {
  constructor(url, { gain = 1, duration = null, crossOrigin = null, preload = 'auto', ...rest } = {}) {
    super(rest);
    this.url = String(url);
    this.duration = duration == null ? null : Number(duration);
    this.gain = Math.max(0, Number(gain));
    this.crossOrigin = crossOrigin;
    this._mediaKind = 'audio';
    this._webRuntimeOnly = 'audio';
    const audio = document.createElement('audio');
    if (crossOrigin != null) audio.crossOrigin = crossOrigin;
    audio.preload = preload;
    audio.volume = Math.max(0, Math.min(1, this.gain));
    this._element = audio;
    this.ready = new Promise((resolve, reject) => {
      audio.addEventListener('loadedmetadata', () => { this.duration = Number.isFinite(audio.duration) ? audio.duration : this.duration; resolve(this); }, { once:true });
      audio.addEventListener('error', () => reject(new Error(`failed to load audio ${this.url}`)), { once:true });
    });
    audio.src = this.url;
    audio.load();
  }

  media(options = {}) { this._bound().media(this, options); return this; }

  draw(renderer) {
    const scene = this._scene;
    if (!scene || this._element.readyState < 1) return;
    const time = renderer.time ?? 0, playback = scene.mediaPlaybackAt(this, time), desired = scene.mediaTimeAt(this, time);
    if (desired == null) { this._element.pause(); return; }
    this._element.volume = Math.max(0, Math.min(1, this.gain));
    if (scene.playing && playback) {
      this._element.playbackRate = Math.max(.0625, Math.min(16, playback.speed));
      this._element.loop = !!playback.loop;
      if (Math.abs(this._element.currentTime - desired) > .15) this._element.currentTime = desired;
      this._element.play().catch(() => {});
    } else {
      this._element.pause();
      if (Math.abs(this._element.currentTime - desired) > 1 / 120) this._element.currentTime = desired;
    }
  }

  destroy() {
    this._element?.pause();
    if (this._element) this._element.removeAttribute('src');
    this._element?.load();
  }
}
