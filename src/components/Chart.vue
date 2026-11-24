<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import Chart from 'chart.js/auto'
import type { ChartConfiguration, Plugin } from 'chart.js'
const props = defineProps<{ config: ChartConfiguration; height?: number; label: string }>()
const canvas = ref<HTMLCanvasElement>()
let chart: Chart | undefined
let observer: IntersectionObserver | undefined
let frame: number | undefined
let progress = 1

const lineReveal: Plugin = {
  id: 'lineReveal',
  beforeDatasetsDraw({ ctx, chartArea, height }) {
    if (progress === 0) return false
    if (progress === 1) return

    const easedProgress = progress * (2 - progress)
    const markerPadding = 8
    const edge =
      chartArea.left - markerPadding + (chartArea.width + 2 * markerPadding) * easedProgress
    ctx.save()
    ctx.beginPath()
    ctx.rect(0, 0, edge, height)
    ctx.clip()
  },
  afterDatasetsDraw({ ctx }) {
    if (progress > 0 && progress < 1) ctx.restore()
  },
}

function clearChart() {
  observer?.disconnect()
  observer = undefined
  if (frame !== undefined) cancelAnimationFrame(frame)
  frame = undefined
  chart?.destroy()
}

function draw() {
  clearChart()
  if (!canvas.value) return

  const config: ChartConfiguration = JSON.parse(JSON.stringify(props.config))
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
  const reveal = config.type === 'line' && !motion.matches
  progress = reveal ? 0 : 1
  if (reveal) config.plugins = [...(config.plugins ?? []), lineReveal]
  chart = new Chart(canvas.value, config)
  if (!reveal) return

  observer = new IntersectionObserver(
    ([entry], visibilityObserver) => {
      if (observer !== visibilityObserver || !entry || entry.intersectionRatio < 0.1) return
      visibilityObserver.disconnect()
      let startedAt: number | undefined
      function revealFrame(now: number) {
        startedAt ??= now
        progress = motion.matches ? 1 : Math.min((now - startedAt) / 900, 1)
        chart?.draw()
        frame = progress < 1 ? requestAnimationFrame(revealFrame) : undefined
      }
      frame = requestAnimationFrame(revealFrame)
    },
    { threshold: 0.1 },
  )
  observer.observe(canvas.value)
}

onMounted(draw)
watch(() => props.config, draw, { deep: true })
onBeforeUnmount(clearChart)
</script>
<template>
  <div class="chart-wrap" :style="{ height: (height || 260) + 'px' }">
    <canvas ref="canvas" role="img" :aria-label="label"></canvas>
  </div>
</template>
