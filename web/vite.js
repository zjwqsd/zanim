import { parse } from '@babel/parser';
import MagicString from 'magic-string';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { extname, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { mkdtempSync, rmSync } from 'node:fs';

const VIRTUAL_PREFIX='\0zanim:typst-svg:';
const PUBLIC_PREFIX='virtual:zanim-typst-svg:';
const DEFAULT_MATH_COLOR='#eef2fa';

function walk(node,visit){if(!node||typeof node!=='object')return;if(typeof node.type==='string')visit(node);for(const value of Object.values(node)){if(Array.isArray(value)){for(const child of value)if(child&&typeof child==='object'&&typeof child.type==='string')walk(child,visit);}else if(value&&typeof value==='object'&&typeof value.type==='string')walk(value,visit);}}
function staticValue(node,constants){if(!node)return undefined;if(node.type==='StringLiteral'||node.type==='NumericLiteral'||node.type==='BooleanLiteral')return node.value;if(node.type==='TemplateLiteral'&&node.expressions.length===0)return node.quasis.map(q=>q.value.cooked??q.value.raw).join('');if(node.type==='Identifier'&&constants.has(node.name))return constants.get(node.name);if(node.type==='UnaryExpression'&&(node.operator==='+'||node.operator==='-')){const v=staticValue(node.argument,constants);if(typeof v==='number')return node.operator==='-'?-v:v;}return undefined;}
function keyName(node){if(node.type==='Identifier')return node.name;if(node.type==='StringLiteral')return node.value;return null;}
function normalizedColor(value){
  if(typeof value!=='string')throw new TypeError('Math color must be a build-time string');
  const v=value.trim();
  if(v.startsWith('#')){let h=v.slice(1);if(h.length===3||h.length===4)h=[...h].map(c=>c+c).join('');if(h.length===6)h+='ff';if(h.length!==8||!/^[0-9a-f]+$/i.test(h))throw new TypeError(`unsupported Math color ${value}`);return `#${h.toLowerCase()}`;}
  const m=v.match(/^rgba?\(([^)]+)\)$/i);if(m){const q=m[1].split(',').map(x=>x.trim());if(q.length<3||q.length>4)throw new TypeError(`unsupported Math color ${value}`);const rgb=q.slice(0,3).map(x=>Math.max(0,Math.min(255,Math.round(Number(x)))));const a=q.length===4?Math.max(0,Math.min(255,Math.round(Number(q[3])*255))):255;return `#${[...rgb,a].map(x=>x.toString(16).padStart(2,'0')).join('')}`;}
  throw new TypeError(`Math color must use #hex or rgb()/rgba() for build-time compilation, got ${value}`);
}
function mathSource(source,fontSize,color){return `#set page(width: auto, height: auto, margin: 0pt, fill: none)\n#set text(size: ${Number(fontSize)}pt, fill: rgb(\"${normalizedColor(color)}\"))\n$ ${source} $\n`;}
function scriptsFor(id,code){if(extname(id.split('?')[0])!=='.vue')return[{code,offset:0}];const out=[];const re=/<script\b[^>]*>([\s\S]*?)<\/script>/gi;let m;while((m=re.exec(code))){const start=m.index+m[0].indexOf(m[1]);out.push({code:m[1],offset:start});}return out;}
function parseModule(code){return parse(code,{sourceType:'module',errorRecovery:false,plugins:['typescript','jsx','importAttributes','topLevelAwait']});}
function analyze(id,code){
  const found=[];
  for(const part of scriptsFor(id,code)){
    let ast;try{ast=parseModule(part.code);}catch(error){if(extname(id.split('?')[0])==='.vue')continue;throw error;}
    const constants=new Map(),aliases=new Map(),namespaces=new Set();
    walk(ast,node=>{if(node.type==='VariableDeclarator'&&node.id?.type==='Identifier'&&node.init){const value=staticValue(node.init,constants);if(value!==undefined)constants.set(node.id.name,value);}});
    walk(ast,node=>{if(node.type!=='ImportDeclaration'||node.source?.value!=='@zanim/web')return;for(const spec of node.specifiers){if(spec.type==='ImportSpecifier'){const imported=spec.imported.name??spec.imported.value;if(imported==='Math'||imported==='Typst')aliases.set(spec.local.name,imported);}else if(spec.type==='ImportNamespaceSpecifier')namespaces.add(spec.local.name);}});
    walk(ast,node=>{
      if(node.type!=='NewExpression')return;
      let kind=null;
      if(node.callee.type==='Identifier'&&aliases.has(node.callee.name))kind=aliases.get(node.callee.name);
      else if(node.callee.type==='MemberExpression'&&!node.callee.computed&&node.callee.object.type==='Identifier'&&namespaces.has(node.callee.object.name)&&(node.callee.property.name==='Math'||node.callee.property.name==='Typst'))kind=node.callee.property.name;
      if(!kind)return;
      if(node.arguments.length<1||node.arguments.length>2)throw new Error(`[zanim] ${kind} in ${id} must use one source argument and optional options object`);
      const source=staticValue(node.arguments[0],constants);if(typeof source!=='string')throw new Error(`[zanim] ${kind} source in ${id} must be build-time static. Use DynamicNumber / FormulaTemplate for runtime-changing content.`);
      let fontSize=36,color=DEFAULT_MATH_COLOR;
      const options=node.arguments[1]??null;
      if(kind==='Math'&&options){if(options.type!=='ObjectExpression')throw new Error(`[zanim] Math options in ${id} must be an object literal so fontSize/color are known at build time`);for(const prop of options.properties){if(prop.type==='SpreadElement')throw new Error(`[zanim] Math options in ${id} cannot spread unknown values because fontSize/color must be build-time static`);if(prop.type!=='ObjectProperty')continue;const key=keyName(prop.key);if(key==='fontSize'){const value=staticValue(prop.value,constants);if(typeof value!=='number')throw new Error(`[zanim] Math fontSize in ${id} must be build-time numeric`);fontSize=value;}else if(key==='color'){const value=staticValue(prop.value,constants);if(typeof value!=='string')throw new Error(`[zanim] Math color in ${id} must be build-time static`);color=value;}}}
      found.push({kind,source,fontSize,color,start:part.offset+node.start,end:part.offset+node.end,arg0Start:part.offset+node.arguments[0].start,arg0End:part.offset+node.arguments[0].end,optionsStart:options?part.offset+options.start:null,optionsEnd:options?part.offset+options.end:null,calleeStart:part.offset+node.callee.start,calleeEnd:part.offset+node.callee.end,importOffset:part.offset});
    });
  }
  return found;
}
function executableCandidates(root,explicit){const exe=process.platform==='win32'?'typst.exe':'typst';return [explicit,process.env.ZANIM_TYPST,join(root,'.tools','typst',exe),exe].filter(Boolean);}
function resolveTypst(root,explicit){for(const candidate of executableCandidates(root,explicit)){if(candidate.includes('/')||candidate.includes('\\')){if(!existsSync(candidate))continue;}const probe=spawnSync(candidate,['--version'],{encoding:'utf8'});if(probe.status===0)return{path:candidate,version:(probe.stdout||probe.stderr).trim()};}throw new Error(`[zanim] Typst is required while developing/building Web Math. Set ZANIM_TYPST, place Typst at ${join(root,'.tools','typst',process.platform==='win32'?'typst.exe':'typst')}, or install typst on PATH.`);}

export function zanim(options={}){
  let config=null,typst=null,cacheDir=null;const compiled=new Map();
  function compile(entry){
    typst??=resolveTypst(config.root,options.typst);
    const source=entry.kind==='Math'?mathSource(entry.source,entry.fontSize,entry.color):entry.source;
    const digest=createHash('sha256').update('zanim-web-typst-v1\0').update(typst.version).update('\0').update(source).digest('hex');
    if(compiled.has(digest))return digest;
    mkdirSync(cacheDir,{recursive:true});const cached=join(cacheDir,`${digest}.svg`);
    if(!existsSync(cached)){
      const temp=mkdtempSync(join(tmpdir(),'zanim-typst-'));try{const input=join(temp,'source.typ'),output=join(temp,'result.svg');writeFileSync(input,source,'utf8');const result=spawnSync(typst.path,['compile',input,output],{encoding:'utf8'});if(result.status!==0)throw new Error(`[zanim] Typst compilation failed:\n${result.stderr||result.stdout}`);writeFileSync(cached,readFileSync(output));}finally{rmSync(temp,{recursive:true,force:true});}
    }
    compiled.set(digest,{svg:readFileSync(cached,'utf8')});return digest;
  }
  return{
    name:'zanim-typst',enforce:'pre',
    configResolved(resolved){config=resolved;cacheDir=resolve(options.cacheDir??join(config.root,'node_modules','.cache','zanim','typst'));},
    resolveId(id){if(id.startsWith(PUBLIC_PREFIX))return VIRTUAL_PREFIX+id.slice(PUBLIC_PREFIX.length);return null;},
    load(id){if(!id.startsWith(VIRTUAL_PREFIX))return null;const digest=id.slice(VIRTUAL_PREFIX.length),record=compiled.get(digest);if(!record)throw new Error(`[zanim] missing compiled Typst asset ${digest}`);if(config.command==='serve')return `export default ${JSON.stringify(record.svg)};`;const ref=this.emitFile({type:'asset',name:`zanim-typst-${digest.slice(0,12)}.svg`,source:record.svg});return `export default import.meta.ROLLUP_FILE_URL_${ref};`;},
    transform(code,id){if(id.includes('/node_modules/')||id.startsWith('\0'))return null;const clean=id.split('?')[0];if(!/\.(?:[cm]?[jt]sx?|vue)$/.test(clean))return null;const entries=analyze(clean,code);if(!entries.length)return null;const magic=new MagicString(code),importsByOffset=new Map();entries.forEach((entry,index)=>{const digest=compile(entry),local=`__zanim_typst_${index}`,source=`${PUBLIC_PREFIX}${digest}`;const imports=importsByOffset.get(entry.importOffset)??[];imports.push(`import ${local} from ${JSON.stringify(source)};`);importsByOffset.set(entry.importOffset,imports);const originalSource=code.slice(entry.arg0Start,entry.arg0End);const callee=code.slice(entry.calleeStart,entry.calleeEnd);const optionsText=entry.optionsStart==null?null:code.slice(entry.optionsStart,entry.optionsEnd);const injected=optionsText==null?`{__zanimCompiledSvg:${local}}`:`Object.assign({},${optionsText},{__zanimCompiledSvg:${local}})`;magic.overwrite(entry.start,entry.end,`new ${callee}(${originalSource},${injected})`);});for(const[offset,imports]of[...importsByOffset.entries()].sort((a,b)=>b[0]-a[0])){magic.appendLeft(offset,`${imports.join('\n')}\n`);}return{code:magic.toString(),map:magic.generateMap({hires:true,source:id})};},
  };
}

export default zanim;
