<template>
  <section class="page" data-module="vessel">
    <header class="page-head">
      <div>
        <h2>船舶档案管理</h2>
        <p class="page-desc">维护船舶，围绕船舶编号、船舶名称、船舶类型、载重吨位做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记船舶</button>
        <button class="btn" type="button" @click="exportRows">导出船舶档案清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label v-for="field in filterFields" :key="field.param" class="filter-item">
        <span>{{ field.label }}</span>
        <input v-model="filters[field.param]" :placeholder="`按${field.label}检索`" />
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
            <button class="link" type="button" @click="openDetail(row)">详情</button>
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
          <td :colspan="columns.length + 1" class="empty-state">暂无船舶档案数据，可先登记船舶</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条船舶档案记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onActivated, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

// KeepAlive 按名字缓存本页：从详情返回时筛选条件与滚动位置保持原样
defineOptions({ name: 'VesselList' })

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/vessel'
const columns = ["船舶编号", "船舶名称", "船舶类型", "船籍", "载重吨位", "船长", "船宽", "所属船公司", "船舶状态"]
const actions = ["登记船舶", "标记在港", "停用船舶"]
const statuses = ["待登记", "在册可用", "在港作业", "已停用"]
const stats = [{"label": "在册船舶", "value": 0}, {"label": "在港船舶", "value": 0}, {"label": "本月到港艘次", "value": 0}]

// 筛选框与接口参数的对应关系；筛选条件同时写进地址栏，刷新或返回后仍是同一组条件
const filterFields = [
  { label: '船舶编号', param: 'keyword' },
  { label: '船舶名称', param: 'name' },
  { label: '船舶类型', param: 'vessel_type' },
]

const route = useRoute()
const router = useRouter()

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})

function activeQuery(): Record<string, string> {
  return Object.fromEntries(
    Object.entries(filters.value).filter(([, value]) => value.trim().length > 0),
  )
}

function applyFilters() {
  void router.replace({ name: 'vessel', query: activeQuery() })
  void reload()
}

function resetFilters() {
  filters.value = {}
  void router.replace({ name: 'vessel', query: {} })
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '船舶登记入口尚未接入审批流'
}

function openDetail(row: Row) {
  void router.push({ name: 'vessel-detail', params: { id: row.id } })
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('船舶档案动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '船舶档案操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(activeQuery()).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('船舶列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '船舶档案列表读取失败'
  }
}

onMounted(() => {
  for (const field of filterFields) {
    const value = route.query[field.param]
    if (typeof value === 'string' && value) {
      filters.value[field.param] = value
    }
  }
})

// 首次进入与从详情返回时都会触发：保证列表与详情显示的是同一份最新数据
onActivated(reload)
</script>
