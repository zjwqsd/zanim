import type { CanvasRenderer, Scene, ScalarValue, Transform2D, ZanimWasm } from './zanim.js';

export const SCENE_IR_FORMAT:'zanim.scene';
export const SCENE_IR_VERSION:1;
export class SceneIRUnsupported extends Error {}

export type RGBA = [number,number,number,number];
export type IRTransform = [number,number,number,number,number,number];
export interface SceneIR {
  format:'zanim.scene';
  version:1;
  canvas:{width:number;height:number;unit_size:number};
  fps:number;
  duration:number;
  objects:Array<Record<string,unknown>>;
  values:Array<Record<string,unknown>>;
  resources:Array<Record<string,unknown>>;
  clips:Array<Record<string,unknown>>;
  meta?:Record<string,unknown>;
}
export function validateSceneIR(value:unknown):SceneIR;
export function sceneFromIR(ir:SceneIR,renderer:CanvasRenderer,options?:{proceduralQuality?:{resolution?:number;minWidth?:number;maxWidth?:number;maxHeight?:number}}):Scene;
export function createSceneFromIR(canvas:HTMLCanvasElement|string,ir:SceneIR,options?:{wasmURL?:string|URL;wasm?:ZanimWasm|null;renderer?:{unitSize?:number;background?:string};observeResize?:boolean;proceduralQuality?:{resolution?:number;minWidth?:number;maxWidth?:number;maxHeight?:number}}):Promise<Scene>;
export function sceneToIR(scene:Scene,options?:{sampleTransformFunctions?:boolean;sampleDynamicProviders?:boolean;sampleFps?:number}):SceneIR;
export function stringifySceneIR(ir:SceneIR,space?:number):string;
export function parseSceneIR(text:string):SceneIR;
