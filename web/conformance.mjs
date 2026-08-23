import {
  Group, Line, LOCAL, PARENT, RIGHT, ScalarValue, Scene, Transform2D, WORLD,
} from './src/zanim.js';

const matrix = m => [m.xx,m.xy,m.yx,m.yy,m.tx,m.ty];
const samples = (scene, object, times) => times.map(t => matrix(scene.worldTransformAt(object,t)));

function worldScenario(){
  const scene=Scene.headless();
  const child=new Line([0,0],[1,0],{transform:Transform2D.translation(1,0)});
  const parent=new Group([child],{transform:Transform2D.translation(2,1).mul(Transform2D.rotation(Math.PI/2))});
  scene.add(parent);
  scene.move(child,RIGHT,{frame:WORLD,duration:2});
  return samples(scene,child,[0,1,2]);
}

function framedScenario(frame){
  const scene=Scene.headless();
  const line=new Line([0,0],[1,0],{transform:Transform2D.rotation(Math.PI/2)});
  scene.add(line);
  scene.move(line,RIGHT,{frame,duration:2});
  return samples(scene,line,[0,1,2]);
}

function valueScenario(){
  const scene=Scene.headless();
  const value=scene.addValue(new ScalarValue(2));
  scene.animateValue(value,{to:6,duration:2});
  return [0,1,2].map(t=>scene.valueAt(value,t));
}

function relativeAtScenario(){
  const scene=Scene.headless();
  const line=new Line();
  scene.add(line);
  scene.move(line,RIGHT,{frame:PARENT,duration:1});
  scene.move(line,[0,1],{frame:PARENT,duration:1,at:.5});
  return {duration:scene.duration, samples:samples(scene,line,[0,1,1.5,2,2.5])};
}

function rejectsTransformOverlap(){
  const scene=Scene.headless();
  const line=new Line();
  scene.add(line);
  try{scene.parallel(api=>{api.move(line,RIGHT,{frame:PARENT,duration:1});api.rotate(line,.5,{frame:PARENT,duration:1});});return false;}catch{return true;}
}

function allowsIndependentChannels(){
  const scene=Scene.headless();
  const line=new Line({opacity:1});
  scene.add(line);
  try{scene.parallel(api=>{api.move(line,RIGHT,{frame:PARENT,duration:1});api.fadeOut(line,{duration:1});});return true;}catch{return false;}
}

function rejectsParentFirst(){
  const scene=Scene.headless();
  const child=new Line();
  const parent=new Group([child]);
  scene.add(parent);
  try{scene.parallel(api=>{api.move(parent,RIGHT,{frame:LOCAL,duration:1});api.move(child,RIGHT,{frame:WORLD,duration:1});});return false;}catch{return true;}
}

function rejectsChildFirst(){
  const scene=Scene.headless();
  const child=new Line();
  const parent=new Group([child]);
  scene.add(parent);
  try{scene.parallel(api=>{api.move(child,RIGHT,{frame:WORLD,duration:1});api.move(parent,RIGHT,{frame:LOCAL,duration:1});});return false;}catch{return true;}
}

console.log(JSON.stringify({
  world:worldScenario(),
  local:framedScenario(LOCAL),
  parent:framedScenario(PARENT),
  value:valueScenario(),
  relative_at:relativeAtScenario(),
  rejects_transform_overlap:rejectsTransformOverlap(),
  allows_independent_channels:allowsIndependentChannels(),
  rejects_parent_first:rejectsParentFirst(),
  rejects_child_first:rejectsChildFirst(),
}));
