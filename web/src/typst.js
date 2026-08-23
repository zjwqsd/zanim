import { VectorObject2D } from './core.js';
import { vectorDocumentFromSvg } from './svg.js';

const EMPTY_DOCUMENT=Object.freeze({width:1,height:1,group_count:0,paths:[]});
let configuredCompiler=null;
const documentCache=new Map();

function colorCSS(value){if(value==null)return null;if(typeof value==='string')return value;const[r,g,b,a=255]=value.map(Number);return `#${[r,g,b,a].map(v=>globalThis.Math.max(0,globalThis.Math.min(255,globalThis.Math.round(v))).toString(16).padStart(2,'0')).join('')}`;}
function documentFromData(raw){if(!raw||!(Number(raw.width)>0)||!(Number(raw.height)>0)||!Array.isArray(raw.paths))throw new TypeError('Typst compiler returned an invalid VectorDocument');return{width:Number(raw.width),height:Number(raw.height),group_count:Number(raw.group_count??1),paths:raw.paths.map(path=>({group:Number(path.group??0),fill:colorCSS(path.fill),stroke:path.stroke?{color:colorCSS(path.stroke.color),width:Number(path.stroke.width)}:null,contours:path.contours.map(contour=>({closed:!!contour.closed,segments:contour.segments.map(seg=>seg.map(point=>[Number(point[0]),Number(point[1])]))}))}))};}
async function documentFromCompiledSvg(value){
  if(typeof value!=='string'||!value)throw new TypeError('precompiled Typst asset must be an SVG string or URL');
  if(documentCache.has(value))return documentCache.get(value);
  const svg=value.trimStart().startsWith('<svg')?value:await fetch(value).then(response=>{if(!response.ok)throw new Error(`failed to load precompiled Typst SVG (${response.status})`);return response.text();});
  const document=vectorDocumentFromSvg(svg);documentCache.set(value,document);return document;
}
function missingCompilerError(kind){return new Error(`${kind} requires authoring-time Typst compilation. With Vite, add zanim() from @zanim/web/vite. Otherwise call configureTypstCompiler(...) in your development environment. Production browsers never compile Typst.`);}

export function configureTypstCompiler(compiler){if(compiler!=null&&typeof compiler!=='function')throw new TypeError('Typst compiler must be a function or null');configuredCompiler=compiler;}
export function clearTypstCache(){documentCache.clear();}

export class Typst extends VectorObject2D {
  constructor(source,{compiler=null,__zanimCompiledSvg=null,reveal=1,...options}={}){super(EMPTY_DOCUMENT,{reveal,...options});this.source=String(source);this.compiler=compiler??configuredCompiler;this._compiledSvg=__zanimCompiledSvg;this._webRuntimeOnly='typst';this.ready=this.compile();}
  async compile(source=this.source){
    const nextSource=String(source);
    if(this._compiledSvg!=null&&nextSource!==this.source)throw new Error('precompiled Web Math/Typst source is immutable at runtime; change the source and rebuild, or use a development compiler explicitly');
    this.source=nextSource;
    if(this._compiledSvg!=null)this.document=await documentFromCompiledSvg(this._compiledSvg);
    else if(this.compiler){const result=await this.compiler({kind:'typst',source:this.source},{object:this});this.document=result?.paths?documentFromData(result):documentFromData(result?.document??result);}
    else throw missingCompilerError('Typst');
    this.invalidate();if(this._scene?.renderer?.ctx)this._scene.render();return this;
  }
}
export class Math extends Typst {
  constructor(source,{fontSize=36,color='#eef2fa',compiler=null,__zanimCompiledSvg=null,...options}={}){
    const resolvedCompiler=compiler??configuredCompiler;
    super(source,{...options,__zanimCompiledSvg,compiler:resolvedCompiler?async(payload,context)=>resolvedCompiler({kind:'math',source:payload.source,font_size:Number(fontSize),color},context):null});
    this.fontSize=Number(fontSize);this.color=color;this._webRuntimeOnly='math';
  }
}
