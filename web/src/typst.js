import { VectorObject2D, WHITE } from './core.js';

const EMPTY_DOCUMENT = Object.freeze({ width:1, height:1, group_count:0, paths:[] });
let configuredCompiler = null;

function colorCSS(value) {
  if (value == null) return null;
  if (typeof value === 'string') return value;
  const [r,g,b,a=255] = value.map(Number);
  return `#${[r,g,b,a].map(v=>globalThis.Math.max(0,globalThis.Math.min(255,globalThis.Math.round(v))).toString(16).padStart(2,'0')).join('')}`;
}

function documentFromData(raw) {
  if (!raw || !(Number(raw.width) > 0) || !(Number(raw.height) > 0) || !Array.isArray(raw.paths)) throw new TypeError('Typst compiler returned an invalid VectorDocument');
  return {
    width:Number(raw.width), height:Number(raw.height), group_count:Number(raw.group_count ?? 1),
    paths:raw.paths.map(path=>({
      group:Number(path.group ?? 0),
      fill:colorCSS(path.fill),
      stroke:path.stroke ? { color:colorCSS(path.stroke.color), width:Number(path.stroke.width) } : null,
      contours:path.contours.map(contour=>({
        closed:!!contour.closed,
        segments:contour.segments.map(seg=>seg.map(point=>[Number(point[0]),Number(point[1])])),
      })),
    })),
  };
}

async function endpointCompiler(payload, { endpoint='/api/typst' } = {}) {
  const response = await fetch(endpoint, {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload),
  });
  const data = await response.json().catch(()=>({}));
  if (!response.ok) throw new Error(data.error ?? `Typst compile failed (${response.status})`);
  return documentFromData(data.document);
}

export function configureTypstCompiler(compiler) {
  if (compiler != null && typeof compiler !== 'function') throw new TypeError('Typst compiler must be a function or null');
  configuredCompiler = compiler;
}

export class Typst extends VectorObject2D {
  constructor(source, { compiler=null, endpoint='/api/typst', reveal=1, ...options } = {}) {
    super(EMPTY_DOCUMENT, { reveal, ...options });
    this.source = String(source);
    this.endpoint = endpoint;
    this.compiler = compiler ?? configuredCompiler ?? endpointCompiler;
    this._webRuntimeOnly = 'typst';
    this.ready = this.compile();
  }

  async compile(source=this.source) {
    this.source = String(source);
    const result = await this.compiler({ kind:'typst', source:this.source }, { endpoint:this.endpoint, object:this });
    this.document = result?.paths ? result : documentFromData(result?.document ?? result);
    this.invalidate();
    if (this._scene?.renderer?.ctx) this._scene.render();
    return this;
  }
}

export class Math extends Typst {
  constructor(source, { fontSize=36, color=WHITE, ...options } = {}) {
    super(source, { ...options, compiler:async (payload, context) => {
      const compiler = options.compiler ?? configuredCompiler ?? endpointCompiler;
      const result = await compiler({ kind:'math', source:String(source), font_size:Number(fontSize), color }, context);
      return result?.paths ? result : documentFromData(result?.document ?? result);
    }});
    this.fontSize = Number(fontSize);
    this.color = color;
    this._webRuntimeOnly = 'math';
  }
}
