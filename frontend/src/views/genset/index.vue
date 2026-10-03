<template>
  <section class="page" data-module="genset">
    <header class="page-head">
      <div>
        <h2>发电机组管理</h2>
        <p class="page-desc">维护发电机组，围绕机组编号、机组型号、额定功率、所属站点做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记发电机组</button>
        <button class="btn" type="button" @click="exportRows">导出发电机组清单</button>
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
          <td :colspan="columns.length + 1" class="empty-state">暂无发电机组数据，可先登记发电机组</td>
        </tr>
      </tbody>
    </table>

    <PageFooter :total="total" :page="page" :size="size" :error="errorMessage" label="发电机组" @turn="turnPage" />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'
import PageFooter from '@/components/PageFooter.vue'
import { usePagedList } from '@/composables/usePagedList'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/genset'
const columns = ["机组编号", "机组型号", "额定功率", "所属站点", "上次试机", "油量储备", "启动状态", "机组状态"]
const actions = ["启动发电", "关闭机组", "登记故障"]
const statuses = ["待命", "发电中", "故障", "维修中"]
const stats = [{"label": "待命机组", "value": 0}, {"label": "发电机组", "value": 0}, {"label": "故障机组", "value": 0}]

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
  errorMessage.value = '发电机组登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('发电机组动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '发电机组操作失败'
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
