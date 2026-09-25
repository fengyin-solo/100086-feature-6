<template>
  <section class="page" data-module="vessel">
    <header class="page-head">
      <div>
        <h2>船舶档案管理</h2>
        <p class="page-desc">维护船舶，围绕船舶编号、船舶类型、船籍做筛选、档案修改留档与状态流转。</p>
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
      <label class="filter-item">
        <span>船舶编号</span>
        <input v-model="draftFilters.keyword" placeholder="按船舶编号检索" />
      </label>
      <label class="filter-item">
        <span>船舶类型</span>
        <input v-model="draftFilters.vesselType" placeholder="按船舶类型检索" />
      </label>
      <label class="filter-item">
        <span>船籍</span>
        <input v-model="draftFilters.registry" placeholder="按船籍检索" />
      </label>
      <label class="filter-item">
        <span>船舶状态</span>
        <select v-model="draftFilters.status">
          <option value="">全部状态</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
        </select>
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
        <tr
          v-for="row in rows"
          :key="String(row.id)"
          class="data-row"
          @click="openDetail(row)"
        >
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click.stop="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!loading && !rows.length">
          <td :colspan="columns.length + 1" class="empty-state">
            暂无符合条件的船舶档案，可调整筛选条件或先登记船舶
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条船舶档案记录</span>
      <span class="pager">
        <button class="btn" type="button" :disabled="view.page <= 1" @click="goPage(view.page - 1)">上一页</button>
        <span>第 {{ view.page }} / {{ totalPages }} 页</span>
        <button class="btn" type="button" :disabled="view.page >= totalPages" @click="goPage(view.page + 1)">下一页</button>
      </span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onActivated, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'

import { request } from '@/api/client'
import { useVesselViewStore } from '@/stores/vesselView'
import { useSessionStore } from '@/stores/session'

defineOptions({ name: 'VesselList' })

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/vessel'
const columns = ['船舶编号', '船舶名称', '船舶类型', '船籍', '载重吨位', '船长', '船宽', '所属船公司', '船舶状态']
const actions = ['登记船舶', '标记在港', '停用船舶']
const statuses = ['待登记', '在册可用', '在港作业', '已停用']
const stats = [{ label: '在册船舶', value: 0 }, { label: '在港船舶', value: 0 }, { label: '本月到港艘次', value: 0 }]

const router = useRouter()
const view = useVesselViewStore()
const session = useSessionStore()

const rows = ref<Row[]>([])
const total = ref(0)
const loading = ref(false)
const errorMessage = ref('')
// 输入草稿与已生效筛选分开：只有点“查询”才覆盖存档，返回列表时回填的是已生效那份
const draftFilters = ref({ ...view.filters })

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / view.size)))

function applyFilters() {
  view.setFilters({ ...draftFilters.value })
  void reload(true)
}

function resetFilters() {
  draftFilters.value = { keyword: '', status: '', vesselType: '', registry: '' }
  view.setFilters({ ...draftFilters.value })
  void reload(true)
}

function goPage(page: number) {
  view.setPage(page)
  void reload(true)
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '船舶登记入口尚未接入审批流'
}

function openDetail(row: Row) {
  saveScroll()
  void router.push({ name: 'vessel-detail', params: { id: String(row.id) } })
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action }, operator: session.operator }),
    })
    if (!response.ok) {
      throw new Error('船舶档案动作未生效，请稍后重试')
    }
    await reload(false)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '船舶档案操作失败'
  }
}

function buildQuery() {
  const params = new URLSearchParams()
  const f = view.filters
  if (f.keyword.trim()) params.set('keyword', f.keyword.trim())
  if (f.status) params.set('status', f.status)
  if (f.vesselType.trim()) params.set('vessel_type', f.vesselType.trim())
  if (f.registry.trim()) params.set('registry', f.registry.trim())
  params.set('page', String(view.page))
  params.set('size', String(view.size))
  return params.toString()
}

async function reload(resetScroll: boolean) {
  errorMessage.value = ''
  loading.value = true
  try {
    const response = await request(`${ENDPOINT}?${buildQuery()}`)
    if (!response.ok) {
      throw new Error('船舶列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    // 越界页（例如删数据后）兜底回最后一页
    if (!rows.value.length && total.value > 0 && view.page > 1) {
      view.setPage(Math.max(1, Math.ceil(total.value / view.size)))
      await reload(false)
      return
    }
    if (resetScroll) {
      window.scrollTo({ top: 0 })
      view.setScrollTop(0)
    } else {
      await restoreScroll()
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '船舶档案列表读取失败'
  } finally {
    loading.value = false
  }
}

async function restoreScroll() {
  // 等表格渲染完再滚，否则长列表高度没撑开，位置恢复不到位
  await new Promise((resolve) => requestAnimationFrame(() => resolve(null)))
  window.scrollTo({ top: view.scrollTop })
}

function saveScroll() {
  view.setScrollTop(window.scrollY)
}

// KeepAlive 下从详情返回：数据重拉（保证看到的与详情一致），位置与筛选沿用存档
let firstEnter = true
onMounted(() => {
  draftFilters.value = { ...view.filters }
  void reload(false)
})
onActivated(() => {
  if (firstEnter) {
    firstEnter = false
    return
  }
  draftFilters.value = { ...view.filters }
  void reload(false)
})
onBeforeRouteLeave(() => {
  saveScroll()
})
</script>
