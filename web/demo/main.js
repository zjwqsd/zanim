import { Axes, InfiniteGrid, Mat2, Polygon, Scene } from "../src/zanim.js";

const canvas = document.querySelector("#scene");
const scene = await Scene.create(canvas);
const wasm = scene.renderer.wasm;

scene.add(
  new InfiniteGrid({ step: 0.5 }),
  new Axes(),
  new Polygon([
    [-1.25, -0.9], [0.15, -0.9], [0.15, -0.25], [1.15, -0.25],
    [1.15, 0.85], [0.45, 0.85], [0.45, 0.3], [-1.25, 0.3],
  ]),
);

const fields = ["xx", "xy", "yx", "yy"];
const controls = Object.fromEntries(fields.map(name => [name, document.querySelector(`#${name}`)]));
const outputs = Object.fromEntries(fields.map(name => [name, document.querySelector(`[data-value=${name}]`)]));
const det = document.querySelector("#det");

function matrixFromControls() {
  return new Mat2(...fields.map(name => Number(controls[name].value)));
}
function syncControls(matrix) {
  for (const name of fields) {
    controls[name].value = matrix[name];
    outputs[name].textContent = Number(matrix[name]).toFixed(2);
  }
  updateReadout(matrix);
}
function updateReadout(matrix) {
  const value = wasm.determinant(matrix);
  det.textContent = value.toFixed(3);
  det.classList.toggle("singular", Math.abs(value) < 0.02);
}
for (const name of fields) {
  controls[name].addEventListener("input", () => {
    const matrix = matrixFromControls();
    outputs[name].textContent = Number(controls[name].value).toFixed(2);
    updateReadout(matrix);
    scene.setMatrix(matrix);
  });
}

const presets = {
  identity: Mat2.identity(),
  rotation: Mat2.rotation(Math.PI * 0.31),
  stretch: Mat2.scaling(1.8, 0.55),
  shear: Mat2.shear(1.15, 0),
  projection: new Mat2(1, 0.65, 0, 0),
  general: new Mat2(1.15, 0.75, -0.45, 1.05),
};
for (const button of document.querySelectorAll("[data-preset]")) {
  button.addEventListener("click", () => {
    const target = presets[button.dataset.preset];
    scene.animateTo(target, 850);
    syncControls(target);
  });
}

const requestedPreset = new URLSearchParams(location.search).get("preset");
const initial = presets[requestedPreset] ?? Mat2.identity();
syncControls(initial);
scene.setMatrix(initial);
