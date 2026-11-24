<script setup lang="ts">
import { onMounted, onUnmounted, ref, useId } from 'vue'

defineProps<{ active: boolean }>()
const gradientId = `workflow-flow-${useId()}`
const paths = [
  'M 0 48 C 224 48 256 134 480 134',
  'M 0 162 C 154 162 176 184 262 176 C 343 168 382 162 480 162',
  'M 0 276 C 224 276 256 190 480 190',
]
const pathWidth = 480
const glowWidth = 192
const glowStart = `${-glowWidth} 0`
const glowEnd = `${pathWidth} 0`
const motion = ref(false)
let preference: MediaQueryList | undefined

function syncMotion() {
  motion.value = preference?.matches ?? false
}

onMounted(() => {
  preference = matchMedia('(prefers-reduced-motion: no-preference)')
  syncMotion()
  preference.addEventListener('change', syncMotion)
})
onUnmounted(() => preference?.removeEventListener('change', syncMotion))
</script>

<template>
  <svg class="workflow-links" viewBox="0 0 480 324" preserveAspectRatio="none" aria-hidden="true">
    <defs v-if="motion && active">
      <linearGradient
        :id="gradientId"
        gradientUnits="userSpaceOnUse"
        x1="0"
        :x2="glowWidth"
        :gradientTransform="`translate(${glowStart})`"
      >
        <stop offset="0" stop-color="#424249" />
        <stop offset=".25" stop-color="#4c4c53" />
        <stop offset=".48" stop-color="#717178" />
        <stop offset=".66" stop-color="#b3b3ba" />
        <stop offset=".8" stop-color="#f4f4f6" />
        <stop offset=".88" stop-color="#c3c3ca" />
        <stop offset="1" stop-color="#424249" />
        <animateTransform
          attributeName="gradientTransform"
          type="translate"
          :from="glowStart"
          :to="glowEnd"
          dur="2.8s"
          repeatCount="indefinite"
        />
      </linearGradient>
    </defs>
    <g :stroke="motion && active ? `url(#${gradientId})` : '#424249'" fill="none">
      <path v-for="path in paths" :key="path" :d="path" />
    </g>
  </svg>
</template>

<style scoped>
.workflow-links {
  display: block;
  width: 100%;
  height: 324px;
  pointer-events: none;
}
.workflow-links path {
  stroke-width: 1.5;
  vector-effect: non-scaling-stroke;
}
</style>
