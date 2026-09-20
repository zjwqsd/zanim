<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { heroBuilder } from '../lessons.js'

const canvas = ref(null)
let scene = null
let observer = null

onMounted(async () => {
  scene = await heroBuilder(canvas.value)
  scene.seek(0)
  scene.play({ loop: true })
  observer = new IntersectionObserver(([entry]) => {
    if (!scene) return
    if (entry.isIntersecting) scene.play({ loop: true, from: scene.time })
    else scene.pause()
  }, { threshold: 0.05 })
  observer.observe(canvas.value)
})

onBeforeUnmount(() => {
  observer?.disconnect()
  scene?.destroy()
})
</script>

<template>
  <div class="hero-stage">
    <canvas ref="canvas"></canvas>
    <div class="hero-stage-label">
      <span class="live-dot"></span>
      live @zanim/web
    </div>
  </div>
</template>
