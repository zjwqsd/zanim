import assert from 'node:assert/strict';
import { chmod, mkdtemp, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { zanim } from './vite.js';

const root=await mkdtemp(join(tmpdir(),'zanim-vite-test-'));
const fake=join(root,'typst');
await writeFile(fake,`#!/bin/sh
if [ "$1" = "--version" ]; then echo "typst 0.test"; exit 0; fi
if [ "$1" = "compile" ]; then cat > "$3" <<'SVG'
<svg viewBox="0 0 10 5" width="10pt" height="5pt" xmlns="http://www.w3.org/2000/svg"><path d="M0 0 L10 0 L10 5 Z" fill="#ffffff"/></svg>
SVG
exit 0; fi
exit 2
`);
await chmod(fake,0o755);

function plugin(command='build'){
  const p=zanim({typst:fake,cacheDir:join(root,'cache')});
  p.configResolved({root,command});
  return p;
}

const source=`import { Math as ZMath } from '@zanim/web';
const WHITE='#ffffff';
const expr='x^2 + 1';
export const formula=new ZMath(expr,{fontSize:32,color:WHITE,opacity:.8});`;
const build=plugin('build');
const transformed=build.transform.call({},source,join(root,'scene.js'));
assert.ok(transformed.code.includes('virtual:zanim-typst-svg:'));
assert.ok(transformed.code.includes('__zanimCompiledSvg'));
assert.ok(transformed.code.includes("new ZMath(expr,Object.assign({},"));
const virtual=transformed.code.match(/virtual:zanim-typst-svg:[0-9a-f]+/)?.[0];
assert.ok(virtual);
const resolved=build.resolveId(virtual);
let emitted=null;
const loaded=build.load.call({emitFile(value){emitted=value;return 'assetref';}},resolved);
assert.equal(emitted.type,'asset');
assert.match(emitted.name,/^zanim-typst-/);
assert.match(String(emitted.source),/^<svg/);
assert.match(loaded,/ROLLUP_FILE_URL_assetref/);

const vue=`<template><canvas/></template>\n<script setup lang="ts">\nimport { Math } from '@zanim/web'\nconst f=new Math('pi',{fontSize:24})\n</script>`;
const vueResult=plugin('serve').transform.call({},vue,join(root,'App.vue'));
assert.ok(vueResult.code.indexOf('import __zanim_typst_')>vueResult.code.indexOf('<script setup'));
assert.ok(vueResult.code.indexOf('import __zanim_typst_')<vueResult.code.indexOf("import { Math }"));

const dynamic=`import { Math } from '@zanim/web';\nexport function make(source){return new Math(source);}`;
assert.throws(()=>plugin('build').transform.call({},dynamic,join(root,'dynamic.js')),/must be build-time static/);

console.log('zanim-vite typst precompile test: ok');
