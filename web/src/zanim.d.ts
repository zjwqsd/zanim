export type Point2 = readonly [number, number];
export type EasingFunction = (t:number)=>number;
export type ScalarLike = number | ScalarValue | ((time:number)=>number);
export type TransformFrame = 'local'|'parent'|'world';
export interface TimeOptions { duration?:number; easing?:EasingFunction; at?:number }
export interface ObjectOptions { transform?:Transform2D; opacity?:number; zIndex?:number }
export interface StyleState { fill?:string|null; stroke?:string|null; width?:number|null; worldStroke?:boolean }

export const PI:number; export const TAU:number; export const DEGREES:number;
export const LOCAL:'local'; export const PARENT:'parent'; export const WORLD:'world';
export const ORIGIN:Point2; export const RIGHT:Point2; export const LEFT:Point2; export const UP:Point2; export const DOWN:Point2;
export const WHITE:string; export const MUTED:string; export const BLUE:string; export const GREEN:string;
export const RED:string; export const ORANGE:string; export const YELLOW:string; export const CYAN:string;
export const PINK:string; export const PURPLE:string; export const GRAY:string; export const BLACK:string;
export const Easing:Readonly<{LINEAR:EasingFunction;SMOOTHSTEP:EasingFunction;EASE_IN_OUT:EasingFunction}>;
export const DEFAULT_WASM_URL:URL;

export class Vec2 {
  x:number; y:number; constructor(x?:number,y?:number);
  add(v:Vec2):Vec2; sub(v:Vec2):Vec2; mul(k:number):Vec2; readonly length:number;
  static from(value:Vec2|Point2):Vec2;
}
export class Bounds2D {
  left:number; bottom:number; right:number; top:number;
  constructor(left:number,bottom:number,right:number,top:number);
  readonly width:number; readonly height:number; readonly center:Vec2;
  static union(...items:Bounds2D[]):Bounds2D;
}
export class Anchor { x:number; y:number; constructor(x?:number,y?:number); }
export const CENTER:Anchor; export const TOP:Anchor; export const BOTTOM:Anchor;
export const LEFT_CENTER:Anchor; export const RIGHT_CENTER:Anchor; export const TOP_LEFT:Anchor; export const TOP_RIGHT:Anchor;
export const BOTTOM_LEFT:Anchor; export const BOTTOM_RIGHT:Anchor;
export class Frame {
  xMin:number; yMin:number; xMax:number; yMax:number;
  constructor(xMin:number,yMin:number,xMax:number,yMax:number);
  static fromRenderer(renderer:CanvasRenderer):Frame;
  readonly width:number; readonly height:number; readonly center:Vec2; readonly top:Vec2; readonly bottom:Vec2; readonly left:Vec2; readonly right:Vec2;
  anchor(anchor:Anchor|Point2|Vec2):Vec2; inset(x:number,y?:number):Frame; topRegion(height:number):Frame; below(other:Frame,gap?:number):Frame;
}

export class Mat2 {
  xx:number; xy:number; yx:number; yy:number;
  constructor(xx?:number,xy?:number,yx?:number,yy?:number);
  static identity():Mat2; static rotation(radians:number):Mat2; static scaling(x:number,y?:number):Mat2; static shear(x?:number,y?:number):Mat2; static lerp(a:Mat2,b:Mat2,t:number):Mat2;
  mul(other:Mat2):Mat2; inverse():Mat2; apply(x:number,y:number):[number,number]; readonly determinant:number;
}
export class Transform2D {
  xx:number; xy:number; yx:number; yy:number; tx:number; ty:number;
  constructor(xx?:number,xy?:number,yx?:number,yy?:number,tx?:number,ty?:number);
  static identity():Transform2D; static translation(x:number,y:number):Transform2D; static scaling(x:number,y?:number):Transform2D; static rotation(radians:number):Transform2D; static shear(x?:number,y?:number):Transform2D;
  static fromMat2(m:Mat2):Transform2D; static affine(options?:{position?:Point2;rotation?:number;scale?:number|Point2;shear?:Point2}):Transform2D; static lerp(a:Transform2D,b:Transform2D,t:number):Transform2D;
  mul(other:Transform2D):Transform2D; inverse():Transform2D; apply(x:number,y:number):[number,number]; vector(x:number,y:number):[number,number]; readonly linear:Mat2; readonly determinant:number;
}
export const affine2d: typeof Transform2D.affine;

export class ScalarValue { readonly id:number; value:number; initial:number; constructor(value?:number); }
export function sampleValue(value:ScalarLike,time?:number):number;

export class ZanimWasm {
  readonly instance:WebAssembly.Instance; readonly exports:WebAssembly.Exports;
  constructor(instance:WebAssembly.Instance); static load(url:string|URL):Promise<ZanimWasm>;
  determinant(matrix:Mat2):number; resolveGrid(width:number,height:number,unitSize:number,step:number,matrix:Mat2):Float64Array;
  renderFractal(kind:1|2,width:number,height:number,centerRe:number,centerIm:number,worldPerPixel:number,maxIter?:number,juliaRe?:number,juliaIm?:number,colorShift?:number,colorScale?:number,inside?:readonly number[],palette?:readonly number[]):Uint8ClampedArray;
  renderComplexGrid(kind:1|2|3|4,width:number,height:number,centerRe:number,centerIm:number,worldPerPixel:number,stepX:number,stepY:number,progress:number,strokePx?:number,params?:readonly number[]):Uint8ClampedArray;
}

export class ZObject {
  readonly id:number; transform:Transform2D; opacity:number; zIndex:number; visible:boolean; birth:number; death:number;
  constructor(options?:ObjectOptions); draw(renderer:CanvasRenderer,parent?:Transform2D):void; world(parent?:Transform2D):Transform2D;
  bounds():Bounds2D; readonly center:Vec2; anchor(anchor?:Anchor|Point2|Vec2):Vec2; shift(x:number|Point2|Vec2,y?:number):this; place(options?:{anchor?:Anchor|Point2|Vec2;at?:Point2|Vec2}):this;
  fadeIn(options?:TimeOptions):this; fadeOut(options?:TimeOptions):this; opacityTo(to:number,options?:TimeOptions):this; styleTo(style:StyleState,options?:TimeOptions):this;
  transformFunction(provider:(alpha:number)=>Transform2D,options?:TimeOptions):this; affine(options?:TimeOptions&{position?:Point2;rotation?:number;scale?:number|Point2;shear?:Point2}):this;
  move(by:Point2|Vec2,options?:TimeOptions&{frame?:TransformFrame}):this; rotate(by:number,options?:TimeOptions&{frame?:TransformFrame;about?:Point2|Vec2|null}):this; scale(by:number,options?:TimeOptions&{frame?:TransformFrame;about?:Point2|Vec2|null}):this;
  create(options?:TimeOptions):this; trimTo(to:number,options?:TimeOptions):this; remove():this;
}
export class Camera2D extends ZObject { affine(options?:TimeOptions&{position?:Point2;rotation?:number;scale?:number|Point2;shear?:Point2}):this; pan(by:Point2|Vec2,options?:TimeOptions):this; }
export class CustomObject2D extends ZObject { constructor(draw:(context:{renderer:CanvasRenderer;ctx:CanvasRenderingContext2D;time:number;transform:Transform2D;object:CustomObject2D})=>void,options?:ObjectOptions); }

export class Line extends ZObject { constructor(start?:Point2,end?:Point2,options?:ObjectOptions&{stroke?:string;width?:number;strokeWidth?:number}); }
export class Polyline extends ZObject {
  points:readonly Point2[]; reveal:ScalarLike; trim:ScalarLike; worldStroke:boolean;
  constructor(points:readonly Point2[],options?:ObjectOptions&{stroke?:string|null;width?:number;strokeWidth?:number;closed?:boolean;fill?:string|null;reveal?:ScalarLike;trim?:ScalarLike}); invalidate():this;
}
export function resamplePolylineByArcLength(points:readonly Point2[],segmentCount:number):Point2[];
export class Polygon extends Polyline { constructor(points:readonly Point2[],options?:ConstructorParameters<typeof Polyline>[1]); }
export class Rectangle extends Polygon { readonly rectWidth:number; readonly rectHeight:number; constructor(width?:number,height?:number,options?:ConstructorParameters<typeof Polygon>[1]); }
export class Square extends Rectangle { constructor(side?:number,options?:ConstructorParameters<typeof Polygon>[1]); }
export class RegularPolygon extends Polygon { constructor(sides?:number,radius?:number,options?:ConstructorParameters<typeof Polygon>[1]&{phase?:number}); }
export class Circle extends ZObject { radius:number; reveal:ScalarLike; trim:ScalarLike; constructor(radius?:number,options?:ObjectOptions&{fill?:string|null;stroke?:string|null;width?:number;strokeWidth?:number;reveal?:ScalarLike;trim?:ScalarLike}); }
export class Dot extends Circle { constructor(point?:Point2,options?:ObjectOptions&{radius?:number;color?:string}); }
export class Arrow extends Line {}
export class Text extends ZObject { text:string|((time:number,object:Text)=>string); fontSize:number; color:string; fontFamily:string; constructor(text:string|((time:number,object:Text)=>string),options?:ObjectOptions&{fontSize?:number;color?:string;fontFamily?:string;align?:CanvasTextAlign;weight?:number}); }
export interface VectorDocumentData { width:number; height:number; group_count:number; paths:Array<{group:number;fill:string|null;stroke:{color:string;width:number}|null;contours:Array<{closed:boolean;segments:Array<[Point2,Point2,Point2,Point2]>}>}> }
export class VectorObject2D extends ZObject { document:VectorDocumentData; reveal:ScalarLike; constructor(document:VectorDocumentData,options?:ObjectOptions&{reveal?:ScalarLike}); invalidate():this; }
export class Group extends ZObject { readonly children:ZObject[]; constructor(children?:ZObject[],options?:ObjectOptions); add(...items:ZObject[]):this; }

export class InfiniteLine extends ZObject { constructor(point?:Point2,direction?:Point2,options?:ObjectOptions&{stroke?:string;width?:number;strokeWidth?:number}); }
export class InfiniteGrid extends ZObject { constructor(options?:ObjectOptions&{step?:number;stroke?:string;width?:number;strokeWidth?:number}); }
export class Axes extends ZObject { constructor(options?:ObjectOptions&{xColor?:string;yColor?:string;width?:number}); }

export type CircleItem = readonly [number,number,number,string?,string?,number?];
export type LineItem = readonly [number,number,number,number,string?,number?];
export type RectItem = readonly [number,number,number,number,string?,string?,number?];
export type TextItem = readonly [number,number,string|number,string?,number?,number?];
export class CircleSet extends ZObject { items:readonly CircleItem[]; constructor(items?:readonly CircleItem[],options?:ObjectOptions&{fill?:string;stroke?:string|null;width?:number;worldStroke?:boolean}); invalidate():this; batchTo(to:readonly CircleItem[]|CircleSet,options?:TimeOptions):this; }
export class LineSet extends ZObject { items:readonly LineItem[]; constructor(items?:readonly LineItem[],options?:ObjectOptions&{stroke?:string;width?:number;worldStroke?:boolean}); invalidate():this; batchTo(to:readonly LineItem[]|LineSet,options?:TimeOptions):this; }
export class RectSet extends ZObject { items:readonly RectItem[]; constructor(items?:readonly RectItem[],options?:ObjectOptions&{fill?:string;stroke?:string|null;width?:number;worldStroke?:boolean}); invalidate():this; batchTo(to:readonly RectItem[]|RectSet,options?:TimeOptions):this; }
export class TextSet extends ZObject { items:readonly TextItem[]; constructor(items?:readonly TextItem[],options?:ObjectOptions&{color?:string;fontSize?:number;fontFamily?:string;weight?:number;align?:CanvasTextAlign}); }
export class ScalarExpr {
  readonly op:string; readonly args:readonly unknown[];
  constructor(op:string,args?:readonly unknown[]);
  static constant(value:number):ScalarExpr; static variable(name:'x'|'time'):ScalarExpr; static fromData(value:unknown):ScalarExpr;
  toData():unknown[]; evaluate(values?:{x?:number;time?:number}):number;
  add(value:ScalarExpr|number):ScalarExpr; sub(value:ScalarExpr|number):ScalarExpr; mul(value:ScalarExpr|number):ScalarExpr; div(value:ScalarExpr|number):ScalarExpr; pow(value:ScalarExpr|number):ScalarExpr;
  neg():ScalarExpr; sin():ScalarExpr; cos():ScalarExpr; exp():ScalarExpr; log():ScalarExpr; abs():ScalarExpr;
}
export const X:ScalarExpr; export const TIME:ScalarExpr;
export class FunctionPlot extends Polyline {
  readonly expression:ScalarExpr; readonly xRange:number[]; readonly axesXRange:number[]; readonly axesYRange:number[]; readonly plotWidth:number; readonly plotHeight:number; readonly plotCenter:number[]; readonly samples:number;
  constructor(expression:ScalarExpr|number,options?:ConstructorParameters<typeof Polyline>[1]&{xRange?:Point2;axesXRange?:Point2;axesYRange?:Point2;width?:number;height?:number;center?:Point2;samples?:number});
  pointsAt(time:number):Point2[];
}
export class DynamicPolyline extends Polyline { constructor(provider:(time:number,object:DynamicPolyline)=>readonly Point2[],options?:ConstructorParameters<typeof Polyline>[1]); }
export class DynamicLineSet extends LineSet { constructor(provider:(time:number,object:DynamicLineSet)=>readonly LineItem[],options?:ConstructorParameters<typeof LineSet>[1]); }
export class DynamicCircleSet extends CircleSet { constructor(provider:(time:number,object:DynamicCircleSet)=>readonly CircleItem[],options?:ConstructorParameters<typeof CircleSet>[1]); }
export class DynamicRectSet extends RectSet { constructor(provider:(time:number,object:DynamicRectSet)=>readonly RectItem[],options?:ConstructorParameters<typeof RectSet>[1]); }
export interface FourierTerm2D { frequency:number; coefficient?:Point2; re?:number; im?:number; }
export class FourierEpicycles extends ZObject {
  readonly terms:Array<{frequency:number;re:number;im:number}>;
  readonly visualIndices:number[];
  readonly startTime:number; readonly drawDuration:number; readonly circleSamples:number; readonly traceSamples:number;
  constructor(terms:readonly (FourierTerm2D|readonly [number,number,number])[],options?:ObjectOptions&{startTime?:number;drawDuration?:number;circleSamples?:number;traceSamples?:number;visualIndices?:readonly number[];circleColor?:string;circleWidth?:number;arrowColor?:string;traceColor?:string;traceWidth?:number;tipColor?:string;tipRadius?:number;tipSides?:number});
  phaseAt(time:number):number;
}
export class DynamicTextSet extends TextSet { constructor(provider:(time:number,object:DynamicTextSet)=>readonly TextItem[],options?:ConstructorParameters<typeof TextSet>[1]); }
export class DynamicNumber extends Text { constructor(value:ScalarLike,options?:ObjectOptions&{digits?:number;prefix?:string;suffix?:string;format?:(value:number,time:number)=>string;fontSize?:number;color?:string;fontFamily?:string;align?:CanvasTextAlign;weight?:number}); }

export interface ProceduralQuality { resolution?:number; minWidth?:number; maxWidth?:number; maxHeight?:number }
export class FractalField extends ZObject {
  kind:number; viewportCenter:[ScalarLike,ScalarLike]; zoom:ScalarLike; maxIter:ScalarLike; juliaC:[ScalarLike,ScalarLike]; colorShift:ScalarLike; colorScale:ScalarLike; insideColor:string; paletteColor:string; viewport:'parameters'|'transform';
  resolution:number; minWidth:number; maxWidth:number; maxHeight:number;
  constructor(kind:1|2,options?:ObjectOptions&ProceduralQuality&{center?:readonly [ScalarLike,ScalarLike];zoom?:ScalarLike;maxIter?:ScalarLike;juliaC?:readonly [ScalarLike,ScalarLike];colorShift?:ScalarLike;colorScale?:ScalarLike;insideColor?:string;paletteColor?:string;viewport?:'parameters'|'transform'});
}
export class MandelbrotSet extends FractalField { constructor(options?:ConstructorParameters<typeof FractalField>[1]); }
export class JuliaSet extends FractalField { constructor(c?:Point2,options?:ConstructorParameters<typeof FractalField>[1]); }
export class ComplexMappedGrid extends ZObject {
  mapping:'square'|'exp'|'reciprocal'|'mobius'; progress:ScalarLike; span:ScalarLike; viewportCenter:[ScalarLike,ScalarLike]; viewport:'parameters'|'canvas';
  constructor(mapping:'square'|'exp'|'reciprocal'|'mobius',options?:ObjectOptions&ProceduralQuality&{step?:number|Point2;progress?:ScalarLike;center?:readonly [ScalarLike,ScalarLike];span?:ScalarLike;strokePx?:number;mapParams?:readonly number[];viewport?:'parameters'|'canvas';frame?:{center:Point2;size:Point2}|null});
}

export class CanvasRenderer {
  readonly canvas:HTMLCanvasElement; readonly ctx:CanvasRenderingContext2D; readonly wasm:ZanimWasm; baseUnitSize:number; unitSize:number; dpr:number; background:string; time:number;
  constructor(canvas:HTMLCanvasElement,wasm:ZanimWasm,options?:{unitSize?:number;background?:string}); resize():void; toDevice(x:number,y:number):[number,number]; clear():void;
}

export class Audio extends ZObject { url:string; duration:number|null; gain:number; readonly ready:Promise<this>; constructor(url:string|URL,options?:ObjectOptions&{gain?:number;duration?:number|null;crossOrigin?:string|null;preload?:string}); media(options?:MediaPlaybackOptions):this; destroy():void; }
export class MediaObject2D extends ZObject { url:string; width:number; height:number; sourceWidth:number; sourceHeight:number; duration:number|null; readonly ready:Promise<this>; media(options?:MediaPlaybackOptions):this; }
export class Image extends MediaObject2D { constructor(url:string|URL,options?:ObjectOptions&{width?:number|null;height?:number|null;sourceWidth?:number;sourceHeight?:number;crossOrigin?:string|null}); }
export class GIF extends MediaObject2D { constructor(url:string|URL,options?:ObjectOptions&{width?:number|null;height?:number|null;sourceWidth?:number;sourceHeight?:number;duration?:number|null;crossOrigin?:string|null}); }
export class Video extends MediaObject2D { constructor(url:string|URL,options?:ObjectOptions&{width?:number|null;height?:number|null;sourceWidth?:number;sourceHeight?:number;duration?:number|null;crossOrigin?:string|null;muted?:boolean;playsInline?:boolean;preload?:string}); destroy():void; }
export interface MediaPlaybackOptions { duration?:number|null; sourceStart?:number; speed?:number; loop?:boolean; sourceDuration?:number|null; at?:number }
export type TypstCompiler = (payload:{kind:'typst'|'math';source:string;font_size?:number;color?:string},context:{endpoint:string;object:Typst})=>Promise<VectorDocumentData|{document:VectorDocumentData}>;
export function configureTypstCompiler(compiler:TypstCompiler|null):void;
export class Typst extends VectorObject2D { source:string; endpoint:string; compiler:TypstCompiler; readonly ready:Promise<this>; constructor(source:string,options?:ObjectOptions&{reveal?:number;endpoint?:string;compiler?:TypstCompiler|null}); compile(source?:string):Promise<this>; }
export class Math extends Typst { fontSize:number; color:string; constructor(source:string,options?:ObjectOptions&{reveal?:number;endpoint?:string;compiler?:TypstCompiler|null;fontSize?:number;color?:string}); }

export interface AnimationOptions extends TimeOptions { transform?:Transform2D; opacity?:number; reveal?:number; style?:StyleState }
export interface ParallelAPI {
  animate(object:ZObject,options?:AnimationOptions):ZObject; animateValue(value:ScalarValue,options:{to:number}&TimeOptions):ScalarValue; transformFunction(object:ZObject,provider:(alpha:number)=>Transform2D,options?:TimeOptions):ZObject;
  fadeIn(object:ZObject,options?:TimeOptions):ZObject; fadeOut(object:ZObject,options?:TimeOptions):ZObject; create(object:ZObject,options?:TimeOptions):ZObject; style(object:ZObject,options:{to:StyleState}&TimeOptions):ZObject;
  batch(object:CircleSet|LineSet|RectSet,options:{to:readonly unknown[]|CircleSet|LineSet|RectSet}&TimeOptions):ZObject; media(object:MediaObject2D,options?:MediaPlaybackOptions):MediaObject2D;
  move(object:ZObject,by:Point2|Vec2,options?:TimeOptions&{frame?:TransformFrame}):ZObject; rotate(object:ZObject,by:number,options?:TimeOptions&{frame?:TransformFrame;about?:Point2|Vec2|null}):ZObject; scale(object:ZObject,by:number,options?:TimeOptions&{frame?:TransformFrame;about?:Point2|Vec2|null}):ZObject;
  affine(object:ZObject,options?:TimeOptions&{position?:Point2;rotation?:number;scale?:number|Point2;shear?:Point2}):ZObject; interpolate(source:ZObject,target:ZObject,options?:TimeOptions):ZObject;
}
export class Scene {
  readonly renderer:CanvasRenderer; readonly objects:ZObject[]; readonly camera:Camera2D; readonly frame:Frame; fps:number; cursor:number; duration:number; time:number; readonly stats:{renderMs:number;seekMs:number;frames:number};
  constructor(renderer:CanvasRenderer,options?:{fps?:number});
  static headless(options?:{width?:number;height?:number;unitSize?:number;fps?:number}):Scene;
  static create(canvas:HTMLCanvasElement|string,options?:{wasmURL?:string|URL;wasm?:ZanimWasm|null;renderer?:{unitSize?:number;background?:string};fps?:number;observeResize?:boolean}):Promise<Scene>;
  add<T extends ZObject>(object:T):T; add<T extends ZObject[]>(...objects:T):T; addLater<T extends ZObject>(object:T):T; addLater<T extends ZObject[]>(...objects:T):T; remove(...objects:ZObject[]):this; invalidateOrder():this;
  addValue<T extends ScalarValue>(value:T):T; addValue<T extends ScalarValue[]>(...values:T):T; animateValue(value:ScalarValue,options:{to:number}&TimeOptions):ScalarValue; valueAt(value:ScalarValue,time:number):number;
  wait(seconds?:number):this; at(seconds:number):this; animate(object:ZObject,options?:AnimationOptions):ZObject; transformFunction(object:ZObject,provider:(alpha:number)=>Transform2D,options?:TimeOptions):ZObject;
  fadeIn(object:ZObject,options?:TimeOptions):ZObject; fadeOut(object:ZObject,options?:TimeOptions):ZObject; style(object:ZObject,options:{to:StyleState}&TimeOptions):ZObject; trim(object:ZObject,options:{to:number}&TimeOptions):ZObject; create(object:ZObject,options?:TimeOptions):ZObject;
  batch(object:CircleSet|LineSet|RectSet,options:{to:readonly unknown[]|CircleSet|LineSet|RectSet}&TimeOptions):ZObject; media(object:MediaObject2D,options?:MediaPlaybackOptions):MediaObject2D; mediaPlaybackAt(object:MediaObject2D,time:number):unknown|null; mediaTimeAt(object:MediaObject2D,time:number):number|null; move(object:ZObject,by:Point2|Vec2,options?:TimeOptions&{frame?:TransformFrame}):ZObject; rotate(object:ZObject,by:number,options?:TimeOptions&{frame?:TransformFrame;about?:Point2|Vec2|null}):ZObject; scale(object:ZObject,by:number,options?:TimeOptions&{frame?:TransformFrame;about?:Point2|Vec2|null}):ZObject; affine(object:ZObject,options?:TimeOptions&{position?:Point2;rotation?:number;scale?:number|Point2;shear?:Point2}):ZObject;
  interpolate(source:ZObject,target:ZObject,options?:TimeOptions):ZObject; replace<T extends ZObject>(source:ZObject,target:T,options?:Omit<TimeOptions,'at'>):T;
  layout(...args:[...ZObject[],{to:Row|Column|Grid;duration?:number;easing?:EasingFunction;at?:number}]):ZObject[];
  parallel(callback:(api:ParallelAPI)=>void):this; parallel(duration:number,callback:(api:ParallelAPI)=>void):this;
  stateAt(object:ZObject,time:number):{transform:Transform2D;opacity:number;reveal:number|null;style:StyleState|null}; worldTransformAt(object:ZObject,time?:number):Transform2D; seek(time:number):this; render():void; play(options?:{loop?:boolean;from?:number}):this; pause():this; destroy():this; setMatrix(matrix:Mat2):void; animateTo(target:Mat2,duration?:number):void;
}

export class Row { constructor(options?:{gap?:number;anchor?:Anchor|Point2|Vec2;at?:Point2|Vec2;align?:Anchor|Point2|Vec2}); targets(...objects:ZObject[]):Transform2D[]; place<T extends ZObject[]>(...objects:T):T; }
export class Column { constructor(options?:{gap?:number;anchor?:Anchor|Point2|Vec2;at?:Point2|Vec2;align?:Anchor|Point2|Vec2}); targets(...objects:ZObject[]):Transform2D[]; place<T extends ZObject[]>(...objects:T):T; }
export class Grid { constructor(options?:{rows?:number|null;cols?:number|null;gap?:number|Point2|Vec2;anchor?:Anchor|Point2|Vec2;at?:Point2|Vec2}); targets(...objects:ZObject[]):Transform2D[]; place<T extends ZObject[]>(...objects:T):T; }
