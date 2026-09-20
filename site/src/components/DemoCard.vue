<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({ lesson: { type: Object, required: true } })

const root = ref(null)
const canvas = ref(null)
const activeCode = ref('python')
const loading = ref(false)
const error = ref('')
const playing = ref(false)
const copied = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const visible = ref(false)

let scene = null
let raf = 0
let observer = null

const code = computed(() => activeCode.value === 'python' ? props.lesson.python : props.lesson.js)
const progress = computed(() => duration.value > 0 ? currentTime.value / duration.value : 0)

async function build() {
  if (scene || loading.value || !canvas.value) return
  loading.value = true
  error.value = ''
  try {
    await nextTick()
    scene = await props.lesson.builder(canvas.value)
    duration.value = scene.duration
    scene.seek(0)
    if (visible.value) {
      scene.play({ loop: true, from: 0 })
      playing.value = true
    }
  } catch (err) {
    console.error(err)
    error.value = err?.stack || String(err)
  } finally {
    loading.value = false
  }
}

function toggle() {
  if (!scene || loading.value) return
  if (playing.value) {
    scene.pause()
    playing.value = false
  } else {
    if (scene.time >= scene.duration - 1e-4) scene.seek(0)
    scene.play({ loop: true, from: scene.time })
    playing.value = true
  }
}

function restart() {
  if (!scene) return
  scene.pause()
  scene.seek(0)
  currentTime.value = 0
  if (visible.value) {
    scene.play({ loop: true, from: 0 })
    playing.value = true
  } else {
    playing.value = false
  }
}

function seek(event) {
  if (!scene) return
  const value = Number(event.target.value)
  scene.pause()
  scene.seek(value)
  currentTime.value = value
  playing.value = false
}

async function copyCode() {
  await navigator.clipboard.writeText(code.value)
  copied.value = true
  setTimeout(() => { copied.value = false }, 1200)
}

function tick() {
  if (scene) currentTime.value = scene.time
  raf = requestAnimationFrame(tick)
}

onMounted(() => {
  observer = new IntersectionObserver(async ([entry]) => {
    visible.value = entry.isIntersecting
    if (entry.isIntersecting) {
      await build()
      if (scene && !playing.value) {
        scene.play({ loop: true, from: scene.time })
        playing.value = true
      }
    } else if (scene && playing.value) {
      scene.pause()
      playing.value = false
    }
  }, { rootMargin: '180px 0px', threshold: 0.08 })
  observer.observe(root.value)
  tick()
})

onBeforeUnmount(() => {
  observer?.disconnect()
  cancelAnimationFrame(raf)
  scene?.destroy()
})
</script>

<template>
  <article :id="lesson.id" ref="root" class="lesson">
    <header class="lesson-copy">
      <div class="lesson-kicker"><span>{{ lesson.index }}</span>{{ lesson.eyebrow }}</div>
      <h2>{{ lesson.title }}</h2>
      <p>{{ lesson.summary }}</p>
      <ul>
        <li v-for="point in lesson.points" :key="point">{{ point }}</li>
      </ul>
    </header>

    <div class="demo-shell">
      <div class="stage">
        <canvas ref="canvas"></canvas>
        <div v-if="!scene && !error" class="stage-idle">
          <span v-if="loading" class="spinner"></span>
          <span>{{ loading ? 'building scene' : 'scroll to run' }}</span>
        </div>
        <div v-if="error" class="stage-error">
          <strong>Scene failed</strong>
          <pre>{{ error }}</pre>
        </div>
        <div v-if="lesson.id === 'frames'" class="frame-labels" aria-hidden="true">
          <span>LOCAL</span><span>PARENT</span><span>WORLD</span>
        </div>
      </div>

      <div class="transport">
        <button class="play-button" :disabled="!scene || !!error" @click="toggle">
          <span>{{ playing ? 'Ⅱ' : '▶' }}</span>{{ playing ? 'Pause' : 'Play' }}
        </button>
        <button class="ghost-button" :disabled="!scene || !!error" @click="restart">↺</button>
        <input
          type="range"
          min="0"
          :max="Math.max(duration, .001)"
          step=".001"
          :value="currentTime"
          :disabled="!scene || !!error"
          @input="seek"
        />
        <span class="time">{{ currentTime.toFixed(2) }} / {{ duration.toFixed(2) }}s</span>
      </div>
      <div class="transport-progress"><i :style="{ width: `${progress * 100}%` }"></i></div>

      <div class="code-panel">
        <div class="code-toolbar">
          <div class="code-tabs">
            <button :class="{ active: activeCode === 'python' }" @click="activeCode = 'python'">Python</button>
            <button :class="{ active: activeCode === 'js' }" @click="activeCode = 'js'">JavaScript</button>
          </div>
          <button class="copy-button" @click="copyCode">{{ copied ? 'Copied' : 'Copy' }}</button>
        </div>
        <pre><code>{{ code }}</code></pre>
      </div>
    </div>
  </article>
</template>
