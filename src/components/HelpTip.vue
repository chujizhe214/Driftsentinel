<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, useId } from 'vue'

defineProps<{ label: string; text: string }>()
const tipId = `help-tip-${useId()}`
const open = ref(false)
const trigger = ref<HTMLButtonElement>()
const tip = ref<HTMLElement>()
const position = ref({ left: '0px', top: '0px', visibility: 'hidden' as 'hidden' | 'visible' })

async function toggle() {
  open.value = !open.value
  if (!open.value) return
  position.value.visibility = 'hidden'
  await nextTick()
  updatePosition()
}

function updatePosition() {
  if (!open.value || !trigger.value || !tip.value) return
  const anchor = trigger.value.getBoundingClientRect()
  const bounds = tip.value.getBoundingClientRect()
  const margin = 12,
    gap = 8,
    width = document.documentElement.clientWidth,
    height = window.innerHeight
  if (anchor.bottom < 0 || anchor.top > height) {
    close()
    return
  }
  let left = anchor.right + gap
  let top = anchor.top + (anchor.height - bounds.height) / 2
  if (left + bounds.width > width - margin) {
    left = anchor.left - gap - bounds.width
    if (left < margin) {
      left = anchor.left
      top = anchor.bottom + gap
    }
  }
  position.value = {
    left: `${Math.max(margin, Math.min(left, width - bounds.width - margin))}px`,
    top: `${Math.max(margin, Math.min(top, height - bounds.height - margin))}px`,
    visibility: 'visible',
  }
}

function close() {
  open.value = false
}
function closeOutside(event: Event) {
  const target = event.target
  if (target instanceof Node && !trigger.value?.contains(target) && !tip.value?.contains(target))
    close()
}
function handleKey(event: KeyboardEvent) {
  if (event.key === 'Escape') close()
}
onMounted(() => {
  document.addEventListener('pointerdown', closeOutside)
  document.addEventListener('focusin', closeOutside)
  document.addEventListener('keydown', handleKey)
  window.addEventListener('resize', updatePosition)
  window.addEventListener('scroll', updatePosition, true)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', closeOutside)
  document.removeEventListener('focusin', closeOutside)
  document.removeEventListener('keydown', handleKey)
  window.removeEventListener('resize', updatePosition)
  window.removeEventListener('scroll', updatePosition, true)
})
</script>

<template>
  <span class="help-tip">
    <button
      ref="trigger"
      type="button"
      class="help-tip-trigger"
      :aria-label="`${label}说明`"
      :aria-expanded="open"
      :aria-controls="open ? tipId : undefined"
      :aria-describedby="open ? tipId : undefined"
      @click="toggle"
    >
      <span aria-hidden="true">?</span>
    </button>
    <Teleport to="body">
      <span
        v-if="open"
        :id="tipId"
        ref="tip"
        role="tooltip"
        class="help-tip-content"
        :style="position"
      >
        {{ text }}
      </span>
    </Teleport>
  </span>
</template>

<style scoped>
.help-tip {
  display: inline-flex;
  flex-shrink: 0;
  vertical-align: middle;
}
.help-tip-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--muted);
}
.help-tip-trigger > span {
  display: grid;
  place-items: center;
  width: 13px;
  height: 13px;
  border: 1px solid currentColor;
  border-radius: 50%;
  font-size: 9px;
  font-weight: 600;
  line-height: 1;
}
.help-tip-trigger:hover,
.help-tip-trigger[aria-expanded='true'] {
  color: var(--primary);
  background: var(--primary-soft);
}
.help-tip-content {
  position: fixed;
  z-index: 60;
  display: block;
  width: min(280px, calc(100vw - 24px));
  padding: 10px 12px;
  border: 1px solid var(--control-line);
  border-radius: 7px;
  background: var(--raised);
  box-shadow: var(--shadow);
  color: var(--ink);
  font-size: 12px;
  font-weight: 400;
  line-height: 1.8;
  white-space: normal;
  overflow-wrap: anywhere;
}
</style>
