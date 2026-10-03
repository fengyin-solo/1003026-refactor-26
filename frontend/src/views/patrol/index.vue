<template>
  <section class="page" data-module="patrol">
    <header class="page-head">
      <div>
        <h2>巡检作业管理</h2>
        <p class="page-desc">维护巡检任务，围绕任务编号、巡检站点、巡检人员、计划日期做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记巡检任务</button>
        <button class="btn" type="button" @click="exportRows">导出巡检作业清单</button>
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
          <td :colspan="columns.length + 1" class="empty-state">暂无巡检作业数据，可先登记巡检任务</td>
        </tr>
      </tbody>
    </table>

    <PageFooter :total="total" :page="page" :size="size" :error="errorMessage" label="巡检作业" @turn="turnPage" />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'
import PageFooter from '@/components/PageFooter.vue'
import { usePagedList } from '@/composables/usePagedList'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/patrol'
const columns = ["任务编号", "巡检站点", "巡检人员", "计划日期", "巡检路线", "发现问题", "处置措施", "任务状态"]
const actions = ["开始巡检", "提交巡检", "发起复查"]
const statuses = ["待巡检", "巡检中", "已巡检", "待复查"]
const stats = [{"label": "待巡检站点", "value": 0}, {"label": "已巡检站点", "value": 0}, {"label": "待复查站点", "value": 0}]

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
  errorMessage.value = '巡检任务登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('巡检作业动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡检作业操作失败'
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
