<script setup>
import DemoCard from './components/DemoCard.vue'
import HeroScene from './components/HeroScene.vue'
import { lessons } from './lessons.js'

const features = [
  ['Random-access timeline', 'Evaluate exact scene state at any time. Preview seeking does not replay previous frames.'],
  ['Python + Web', 'Author with Python for rendering or JavaScript for interactive browser scenes.'],
  ['Explicit transforms', 'LOCAL, PARENT and WORLD make nested coordinate semantics visible in code.'],
  ['Native + WASM', 'The Zig renderer powers native Python wheels and the browser runtime through WebAssembly.'],
]

const learnMore = [
  ['Architecture', 'How Scene state, native rendering and Web rendering fit together.', 'https://github.com/zjwqsd/zanim/blob/main/docs/ARCHITECTURE.md'],
  ['Scene IR v1', 'The portable boundary shared by Python, Web and native rendering.', 'https://github.com/zjwqsd/zanim/blob/main/docs/scene-ir-v1.md'],
  ['Showcase', 'More complete scenes: math, fractals, 3D, kinematics and algorithms.', 'https://github.com/zjwqsd/zanim-showcase'],
  ['Zanim Slides', 'A Markdown-first presentation language built on the Zanim scene model.', 'https://github.com/zjwqsd/zanim-slide-lang'],
]
</script>

<template>
  <div class="site">
    <header class="site-header">
      <div class="container header-inner">
        <a class="site-brand" href="#top" aria-label="Zanim home">
          <span class="brand-mark">Z</span>
          <span>Zanim</span>
        </a>

        <nav class="site-nav">
          <a href="#install">Install</a>
          <a href="#examples">Examples</a>
          <a href="#about">About</a>
          <a href="https://github.com/zjwqsd/zanim" target="_blank" rel="noreferrer">GitHub</a>
        </nav>

        <a class="header-button" href="#examples">Getting Started</a>
      </div>
    </header>

    <main id="top">
      <section class="hero-section">
        <div class="container hero-inner">
          <div class="hero-copy">
            <p class="version">Zanim 0.7.0rc1 · pre-1.0</p>
            <h1>Zanim</h1>
            <p class="hero-tagline">A cross-platform animation engine for precise, seekable scenes.</p>
            <p class="hero-description">
              Create mathematical, technical and interactive animations with Python or JavaScript.
              One Scene model drives native video rendering and the browser runtime.
            </p>

            <div class="hero-buttons">
              <a class="button button-primary" href="https://github.com/zjwqsd/zanim" target="_blank" rel="noreferrer">Star on GitHub</a>
              <a class="button button-outline" href="#install">Getting Started</a>
            </div>

            <div class="hero-meta">
              <span>MIT licensed</span>
              <span>Python 3.12+</span>
              <span>WebAssembly</span>
            </div>
          </div>

          <HeroScene />
        </div>
      </section>

      <section id="install" class="section install-section">
        <div class="container">
          <div class="section-title centered">
            <h2>Install Zanim</h2>
            <p>Choose the authoring environment you need. Both use the same scene model.</p>
          </div>

          <div class="install-options">
            <article class="install-option">
              <div class="install-option-header">
                <strong>Python</strong>
                <span>PyPI</span>
              </div>
              <pre><code>pip install --pre zanim==0.7.0rc1</code></pre>
              <p>Native rendering, preview, video export, 3D and Scene IR.</p>
              <a href="https://pypi.org/project/zanim/" target="_blank" rel="noreferrer">View on PyPI →</a>
            </article>

            <article class="install-option">
              <div class="install-option-header">
                <strong>JavaScript</strong>
                <span>npm</span>
              </div>
              <pre><code>npm install @zanim/web@beta</code></pre>
              <p>Interactive browser scenes with Canvas2D and the Zig/WASM runtime.</p>
              <a href="https://www.npmjs.com/package/@zanim/web" target="_blank" rel="noreferrer">View on npm →</a>
            </article>
          </div>

          <p class="install-note">
            Published Python wheels include the native renderer. FFmpeg is only required for encoded video;
            Typst is required only when authoring Text or Math.
          </p>
        </div>
      </section>

      <section class="section features-section">
        <div class="container">
          <div class="section-title centered">
            <h2>Why Zanim?</h2>
            <p>The core ideas are intentionally small and explicit.</p>
          </div>

          <div class="feature-grid">
            <article v-for="[title, body] in features" :key="title">
              <h3>{{ title }}</h3>
              <p>{{ body }}</p>
            </article>
          </div>
        </div>
      </section>

      <section id="examples" class="section examples-section">
        <div class="container">
          <div class="section-title">
            <h2>Examples</h2>
            <p>
              Every example below is live Zanim running in your browser — not a video.
              Switch between Python and JavaScript, then scrub the timeline directly.
            </p>
          </div>

          <DemoCard v-for="lesson in lessons" :key="lesson.id" :lesson="lesson" />
        </div>
      </section>

      <section id="about" class="section open-source-section">
        <div class="container open-source-inner">
          <div>
            <h2>Free and open source</h2>
            <p>
              Zanim is released under the MIT license. The Python frontend, Zig renderer,
              Web runtime and scene format are developed in the open on GitHub.
            </p>
          </div>
          <div class="open-source-actions">
            <a class="button button-light" href="https://github.com/zjwqsd/zanim" target="_blank" rel="noreferrer">Contribute on GitHub</a>
            <a class="text-link light" href="https://github.com/zjwqsd/zanim/issues" target="_blank" rel="noreferrer">Report an issue →</a>
          </div>
        </div>
      </section>

      <section class="section learn-more-section">
        <div class="container">
          <div class="section-title centered">
            <h2>Learn more</h2>
            <p>Technical details and related projects.</p>
          </div>

          <div class="learn-grid">
            <a v-for="[title, body, url] in learnMore" :key="title" :href="url" target="_blank" rel="noreferrer">
              <h3>{{ title }}</h3>
              <p>{{ body }}</p>
              <span>Open →</span>
            </a>
          </div>
        </div>
      </section>
    </main>

    <footer class="site-footer">
      <div class="container footer-grid">
        <div>
          <a class="site-brand footer-brand" href="#top"><span class="brand-mark">Z</span><span>Zanim</span></a>
          <p>Cross-platform animation with Python, Zig and Web.</p>
        </div>

        <div>
          <strong>Project</strong>
          <a href="https://github.com/zjwqsd/zanim" target="_blank" rel="noreferrer">GitHub</a>
          <a href="https://pypi.org/project/zanim/" target="_blank" rel="noreferrer">PyPI</a>
          <a href="https://www.npmjs.com/package/@zanim/web" target="_blank" rel="noreferrer">npm</a>
        </div>

        <div>
          <strong>Learn</strong>
          <a href="#install">Install</a>
          <a href="#examples">Examples</a>
          <a href="https://github.com/zjwqsd/zanim/blob/main/docs/ARCHITECTURE.md" target="_blank" rel="noreferrer">Architecture</a>
        </div>

        <div>
          <strong>Community</strong>
          <a href="https://github.com/zjwqsd/zanim/issues" target="_blank" rel="noreferrer">Issues</a>
          <a href="https://github.com/zjwqsd/zanim-showcase" target="_blank" rel="noreferrer">Showcase</a>
          <a href="https://github.com/zjwqsd/zanim-slide-lang" target="_blank" rel="noreferrer">Zanim Slides</a>
        </div>
      </div>

      <div class="container footer-bottom">
        <span>MIT License</span>
        <span>Pre-1.0</span>
        <a href="#top">Back to top ↑</a>
      </div>
    </footer>
  </div>
</template>
