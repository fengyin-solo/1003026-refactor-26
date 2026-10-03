<template>
  <section class="page" data-module="feeder">
    <header class="page-head">
      <div>
        <h2>馈线巡检管理</h2>
        <p class="page-desc">维护馈线，围绕馈线编号、所属站点、馈线长度、接头数量做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记馈线</button>
        <button class="btn" type="button" @click="exportRows">导出馈线巡检清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="search">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无馈线巡检数据，可先登记馈线</td>
        </tr>
      </tbody>
    </table>

    <PageFooter :total="total" :page="page" :size="size" :error="errorMessage" label="馈线巡检" @turn="turnPage" />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'
import PageFooter from '@/components/PageFooter.vue'
import { usePagedList } from '@/composables/usePagedList'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/feeder'
const columns = ["馈线编号", "所属站点", "馈线长度", "接头数量", "防水情况", "接地电阻", "巡检日期", "馈线状态"]
const actions = ["登记失效", "登记超标", "安排修复"]
const statuses = ["正常", "防水失效", "接地超标", "已修复"]
const stats = [{"label": "正常馈线", "value": 0}, {"label": "失效馈线", "value": 0}, {"label": "超标馈线", "value": 0}]

const { rows, total, page, size, errorMessage, load } = usePagedList<Row>(ENDPOINT)
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

function resetFilters() {
  filters.value = {}
  void load({}, 1)
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '馈线登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('馈线巡检动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '馈线巡检操作失败'
  }
}

function search() {
  return load(filters.value, 1)
}

function reload() {
  return load(filters.value)
}

function turnPage(next: number) {
  return load(filters.value, next)
}

onMounted(reload)
</script>
