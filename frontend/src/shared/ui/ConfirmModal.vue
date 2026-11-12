<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useUi } from '@/shared/state/ui'

const ui = useUi()
const value = ref('')
const okBtn = ref<HTMLButtonElement | null>(null)

watch(
  () => ui.confirmOpts,
  async (o) => {
    value.value = ''
    if (o) {
      await nextTick()
      const input = document.querySelector<HTMLInputElement>('.ov input')
      if (input) input.focus()
      else okBtn.value?.focus()
    }
  },
)
const close = (ok: boolean) => ui.answer(ok, value.value)
</script>

<template>
  <div v-if="ui.confirmOpts" class="ov" @mousedown.self="close(false)" @keydown.esc="close(false)">
    <div class="md" role="dialog" aria-modal="true" :aria-label="ui.confirmOpts.title">
      <h2>{{ ui.confirmOpts.title }}</h2>
      <p v-if="ui.confirmOpts.body" style="margin-top: 10px; color: #334155">{{ ui.confirmOpts.body }}</p>
      <div v-if="ui.confirmOpts.input" style="margin-top: 14px">
        <label class="f" for="cm-in">{{ ui.confirmOpts.input.label }}</label>
        <input id="cm-in" v-model="value" class="in" :type="ui.confirmOpts.input.type || 'text'" @keydown.enter="close(true)" />
      </div>
      <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 22px; flex-wrap: wrap">
        <button class="btn btn-g" @click="close(false)">취소</button>
        <button ref="okBtn" class="btn" :class="ui.confirmOpts.danger ? 'btn-danger' : 'btn-p'" @click="close(true)">
          {{ ui.confirmOpts.okLabel || '확인' }}
        </button>
      </div>
    </div>
  </div>
</template>
