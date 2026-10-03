<template>
  <footer class="page-foot">
    <span>共 {{ total }} 条{{ label }}记录</span>
    <span class="page-turn">
      <button class="btn ghost" type="button" :disabled="page <= 1" @click="turn(page - 1)">上一页</button>
      <span>第 {{ page }} / {{ pageCount }} 页</span>
      <button class="btn ghost" type="button" :disabled="page >= pageCount" @click="turn(page + 1)">下一页</button>
    </span>
    <span v-if="error" class="error-text">{{ error }}</span>
  </footer>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  total: number
  page: number
  size: number
  label: string
  error?: string
}>()

const emit = defineEmits<{
  turn: [page: number]
}>()

const pageCount = computed(() => Math.max(1, Math.ceil(props.total / Math.max(props.size, 1))))

function turn(next: number) {
  if (next >= 1 && next <= pageCount.value && next !== props.page) {
    emit('turn', next)
  }
}
</script>
