<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import Icon from './Icon.vue'
defineProps<{ title: string; wide?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLElement>()
let previous: Element | null
function keys(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
  if (e.key === 'Tab') {
    const els = dialog.value?.querySelectorAll<HTMLElement>(
      'button:not(:disabled),input,select,a[href],textarea',
    )
    if (!els?.length) return
    const first = els[0],
      last = els[els.length - 1]
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last?.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first?.focus()
    }
  }
}
onMounted(() => {
  previous = document.activeElement
  document.body.style.overflow = 'hidden'
  document.addEventListener('keydown', keys)
  dialog.value?.querySelector<HTMLElement>('button,input')?.focus()
})
onBeforeUnmount(() => {
  document.body.style.overflow = ''
  document.removeEventListener('keydown', keys)
  if (previous instanceof HTMLElement) previous.focus()
})
</script>
<template>
  <Teleport to="body">
    <div class="modal-backdrop" @click.self="emit('close')">
      <section
        ref="dialog"
        class="modal"
        :class="{ wide }"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
      >
        <header class="modal-head">
          <h2>{{ title }}</h2>
          <button class="icon-btn" aria-label="关闭对话框" @click="emit('close')">
            <Icon name="x" />
          </button>
        </header>
        <div class="modal-body"><slot /></div>
        <footer v-if="$slots.footer" class="modal-footer"><slot name="footer" /></footer>
      </section>
    </div>
  </Teleport>
</template>
