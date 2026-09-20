<script setup>
import DemoCard from './components/DemoCard.vue'
import HeroScene from './components/HeroScene.vue'
import { lessons } from './lessons.js'

const principles = [
  ['01', 'Absolute time', 'Ask for state at t. Seeking never replays earlier frames.'],
  ['02', 'Explicit state', 'Scene owns authored state after add(); no hidden visual copies.'],
  ['03', 'Named frames', 'LOCAL / PARENT / WORLD make relative transforms unambiguous.'],
  ['04', 'Two frontends', 'Python and Web share the same scene model and Scene IR boundary.'],
]

const reference = [
  ['Objects', 'Circle · Square · Rectangle · Polygon · Line · Arrow · Group'],
  ['Time', 'move · rotate · scale · affine · fade · create · parallel · wait'],
  ['Layout', 'Row · Column · Grid · Frame · anchors'],
  ['Math', 'Axes · FunctionPlot · DynamicNumber · FormulaTemplate · Text · Math'],
  ['Space', 'LOCAL · PARENT · WORLD · Transform2D · SE2 · Transform3D · SO3 · SE3'],
  ['Media', 'Image · GIF · Video · Audio'],
  ['Procedural', 'InfiniteGrid · VectorField · Fourier · Mandelbrot · Julia · Simulation'],
  ['3D', 'Camera3D · Cube3D · Box3D · Surface3D'],
]
</script>

<template>
  <div class="site-shell">
    <header class="top-nav">
      <a class="brand" href="#top" aria-label="Zanim home">
        <span class="brand-mark">Z</span>
        <span>Zanim</span>
      </a>
      <nav class="nav-links">
        <a href="#learn">Learn</a>
        <a href="#reference">Reference</a>
        <a href="https://github.com/zjwqsd/zanim" target="_blank" rel="noreferrer">GitHub ↗</a>
      </nav>
      <a class="nav-cta" href="#quickstart">Get started</a>
    </header>

    <main id="top">
      <section class="hero">
        <div class="hero-copy">
          <div class="release-pill"><span></span> v0.7.0rc1 · pre-1.0</div>
          <h1>Animation as <em>state</em>,<br />not frame history.</h1>
          <p class="hero-lede">
            A random-access animation engine with Python authoring, a Zig renderer,
            and a browser runtime built on the same Scene model.
          </p>

          <div class="hero-actions">
            <a class="primary-button" href="#quickstart">Start in 60 seconds</a>
            <a class="secondary-button" href="https://github.com/zjwqsd/zanim" target="_blank" rel="noreferrer">View source</a>
          </div>

          <div class="hero-facts">
            <div><strong>Python 3.12+</strong><span>native wheels</span></div>
            <div><strong>@zanim/web</strong><span>Canvas + WASM</span></div>
            <div><strong>Scene IR</strong><span>portable boundary</span></div>
          </div>
        </div>

        <HeroScene />
      </section>

      <section id="quickstart" class="quickstart">
        <div class="section-heading compact">
          <span>Quick start</span>
          <h2>One model. Two authoring surfaces.</h2>
          <p>Use Python for authored scenes and rendering; use JavaScript for interactive browser scenes.</p>
        </div>

        <div class="install-grid">
          <article class="install-card">
            <header><span class="lang-dot python"></span><strong>Python</strong><small>PyPI</small></header>
            <pre><code>pip install --pre zanim==0.7.0rc1</code></pre>
            <div class="mini-code">
              <code><b>from</b> zanim <b>import</b> BLUE, Circle, Scene</code>
              <code>scene = Scene()</code>
              <code>circle = scene.add(Circle(1, fill=BLUE))</code>
              <code>circle.move(by=(2, 0), duration=2)</code>
            </div>
            <footer><code>zanim preview scene.py</code></footer>
          </article>

          <article class="install-card">
            <header><span class="lang-dot js"></span><strong>JavaScript</strong><small>npm</small></header>
            <pre><code>npm install @zanim/web@beta</code></pre>
            <div class="mini-code">
              <code><b>import</b> { Circle, Scene } <b>from</b> '@zanim/web'</code>
              <code>const scene = await Scene.create('#canvas')</code>
              <code>const circle = scene.add(new Circle(1))</code>
              <code>circle.move([2, 0], { duration: 2 })</code>
            </div>
            <footer><code>scene.play({ loop: true })</code></footer>
          </article>
        </div>
        <p class="tool-note">
          Release wheels bundle the Zig native renderer and Web/WASM preview runtime.
          FFmpeg is only needed for encoded video; Typst is only needed when authoring Text / Math.
        </p>
      </section>

      <section class="principles">
        <div v-for="[index, title, body] in principles" :key="title" class="principle">
          <span>{{ index }}</span>
          <h3>{{ title }}</h3>
          <p>{{ body }}</p>
        </div>
      </section>

      <section id="learn" class="learn">
        <div class="learn-intro">
          <div class="section-heading">
            <span>Learn by running it</span>
            <h2>The shortest path through Zanim.</h2>
            <p>
              Eight examples cover the core mental model. Every canvas below is live Zanim,
              not a recording. Drag any timeline to inspect arbitrary time directly.
            </p>
          </div>

          <aside class="toc">
            <span>Path</span>
            <a v-for="lesson in lessons" :key="lesson.id" :href="'#' + lesson.id">
              <i>{{ lesson.index }}</i>{{ lesson.title }}
            </a>
          </aside>
        </div>

        <DemoCard v-for="lesson in lessons" :key="lesson.id" :lesson="lesson" />
      </section>

      <section class="model-section">
        <div class="section-heading">
          <span>The model</span>
          <h2>Declare → add → author time → evaluate.</h2>
          <p>Most Zanim code becomes simple once these four stages stay separate.</p>
        </div>

        <div class="model-flow">
          <article>
            <b>1</b><strong>Declare</strong>
            <p>Create geometry, style, resources and one-time layout as ordinary values.</p>
          </article>
          <i>→</i>
          <article>
            <b>2</b><strong>Scene.add()</strong>
            <p>Capture initial state and cross the explicit Scene ownership boundary.</p>
          </article>
          <i>→</i>
          <article>
            <b>3</b><strong>Author</strong>
            <p>Schedule channels on absolute time; the authored head advances explicitly.</p>
          </article>
          <i>→</i>
          <article>
            <b>4</b><strong>Evaluate(t)</strong>
            <p>Reconstruct exact state at any time for preview, frames, video or Web.</p>
          </article>
        </div>
      </section>

      <section id="reference" class="reference-section">
        <div class="section-heading">
          <span>Compact reference</span>
          <h2>Enough surface area for real scenes.</h2>
          <p>These are the concepts worth remembering; details belong in autocomplete and source docs.</p>
        </div>

        <div class="reference-grid">
          <article v-for="[title, items] in reference" :key="title">
            <strong>{{ title }}</strong>
            <p>{{ items }}</p>
          </article>
        </div>
      </section>

      <section class="deep-dive">
        <article>
          <span>Text + Math</span>
          <h3>Typst once. Vector graphics afterwards.</h3>
          <p>
            Python Text / Math compile to immutable vector documents and cache by content.
            The Vite plugin precompiles static Web Math during development/build, so production browsers
            never ship a Typst compiler.
          </p>
          <code>ZANIM_TYPST=/path/to/typst</code>
        </article>
        <article>
          <span>Python CLI</span>
          <h3>Preview, render, inspect.</h3>
          <pre><code>zanim preview scene.py
zanim render scene.py -o scene.mp4
zanim render scene.py --time 1.25 -o frame.png
zanim export-ir scene.py -o scene.zanim.json
zanim info</code></pre>
        </article>
        <article>
          <span>Design rule</span>
          <h3>Unsupported portability fails loudly.</h3>
          <p>
            Scene IR carries portable semantics. Runtime callbacks are intentionally not guessed or
            cosmetically approximated; use explicit sampling when behavior must cross runtimes.
          </p>
          <a href="https://github.com/zjwqsd/zanim/blob/main/docs/scene-ir-v1.md" target="_blank" rel="noreferrer">Scene IR v1 ↗</a>
        </article>
      </section>

      <section class="final-cta">
        <div>
          <span>Build the scene you actually mean.</span>
          <h2>Explicit state. Seekable time. One scene model.</h2>
        </div>
        <div>
          <a class="primary-button" href="https://github.com/zjwqsd/zanim" target="_blank" rel="noreferrer">GitHub</a>
          <a class="secondary-button" href="https://pypi.org/project/zanim/" target="_blank" rel="noreferrer">PyPI</a>
          <a class="secondary-button" href="https://www.npmjs.com/package/@zanim/web" target="_blank" rel="noreferrer">npm</a>
        </div>
      </section>
    </main>

    <footer class="footer">
      <div class="brand"><span class="brand-mark">Z</span><span>Zanim</span></div>
      <p>MIT · Python + Zig + Web · pre-1.0</p>
      <a href="#top">Back to top ↑</a>
    </footer>
  </div>
</template>
