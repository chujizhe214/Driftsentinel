<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import Chart from 'chart.js/auto'
import type { ChartConfiguration } from 'chart.js'
const props = defineProps<{ config: ChartConfiguration; height?: number; label: string }>()
const canvas = ref<HTMLCanvasElement>()
let chart: Chart | undefined
function draw() {
  chart?.destroy()
  if (canvas.value) chart = new Chart(canvas.value, JSON.parse(JSON.stringify(props.config)))
}
onMounted(draw)
watch(() => props.config, draw, { deep: true })
onBeforeUnmount(() => chart?.destroy())
</script>
<template>
  <div class="chart-wrap" :style="{ height: (height || 260) + 'px' }">
    <canvas ref="canvas" role="img" :aria-label="label"></canvas>
  </div>
</template>
