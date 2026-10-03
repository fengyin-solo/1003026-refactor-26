<template>
  <section class="page" data-module="tower">
    <header class="page-head">
      <div>
        <h2>铁塔管理管理</h2>
        <p class="page-desc">维护铁塔，围绕铁塔编号、铁塔类型、设计高度、平台数量做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记铁塔</button>
        <button class="btn" type="button" @click="exportRows">导出铁塔管理清单</button>
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
          <td :colspan="columns.length + 1" class="empty-state">暂无铁塔管理数据，可先登记铁塔</td>
        </tr>
      </tbody>
    </table>

    <PageFooter :total="total" :page="page" :size="size" :error="errorMessage" label="铁塔管理" @turn="turnPage" />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'
import PageFooter from '@/components/PageFooter.vue'
import { usePagedList } from '@/composables/usePagedList'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/tower'
const columns = ["铁塔编号", "铁塔类型", "设计高度", "平台数量", "所属站点", "建成年份", "上次检测", "铁塔状态"]
const actions = ["登记倾斜", "防腐处理", "拆塔完成"]
const statuses = ["正常", "倾斜超标", "锈蚀", "已拆除"]
const stats = [{"label": "正常铁塔", "value": 0}, {"label": "倾斜铁塔", "value": 0}, {"label": "锈蚀铁塔", "value": 0}]

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
  errorMessage.value = '铁塔登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('铁塔管理动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '铁塔管理操作失败'
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
