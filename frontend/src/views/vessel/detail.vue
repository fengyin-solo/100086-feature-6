<template>
  <section class="page vessel-detail">
    <header class="page-head">
      <div>
        <h2>船舶档案详情</h2>
        <p class="page-desc">查看船舶最新档案信息，修改船舶类型、船籍等字段后自动留档，任何人打开都能看到改动内容与时间。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回船舶列表</button>
      </div>
    </header>

    <div v-if="loading" class="panel detail-panel">
      <p class="muted-text">档案加载中…</p>
    </div>

    <div v-else-if="!entry" class="panel detail-panel">
      <p class="error-text">{{ errorMessage || '船舶不存在或已归档' }}</p>
      <button class="btn" type="button" @click="goBack">返回船舶列表</button>
    </div>

    <template v-else>
      <article class="panel detail-panel">
        <h3 class="panel-title">基本信息</h3>
        <dl class="info-grid">
          <div v-for="field in readonlyFields" :key="field" class="info-item">
            <dt>{{ field }}</dt>
            <dd>{{ entry[field] || '—' }}</dd>
          </div>
        </dl>
      </article>

      <article class="panel detail-panel">
        <h3 class="panel-title">修改档案</h3>
        <form class="edit-grid" @submit.prevent="saveChanges">
          <label v-for="field in editableFields" :key="field" class="edit-item">
            <span>{{ field }}</span>
            <input v-model="form[field]" :placeholder="`请输入${field}`" />
          </label>
          <div class="edit-actions">
            <button class="btn primary" type="submit" :disabled="saving">
              {{ saving ? '提交中…' : '保存修改' }}
            </button>
            <button class="btn ghost" type="button" @click="resetForm">恢复为当前档案</button>
          </div>
        </form>
      </article>

      <article class="panel detail-panel">
        <h3 class="panel-title">变更记录 <span class="history-count">（共 {{ history.length }} 条）</span></h3>
        <div v-if="toast" class="toast" :class="toast.tone">{{ toast.text }}</div>
        <ul v-if="history.length" class="history-list">
          <li v-for="(record, index) in history" :key="`${record.time}-${index}`" class="history-item">
            <div class="history-meta">
              <strong>{{ record.operator || '值班管理员' }}</strong>
              <span>{{ record.time }}</span>
            </div>
            <ul class="change-list">
              <li v-for="change in record.changes" :key="change.field" class="change-item">
                <span class="change-field">{{ change.field }}</span>
                <span class="change-old">{{ change.old || '（空）' }}</span>
                <span class="change-arrow">→</span>
                <span class="change-new">{{ change.new || '（空）' }}</span>
              </li>
            </ul>
          </li>
        </ul>
        <p v-else class="empty-history">该船舶档案暂无修改记录，字段仍保持登记时的内容；保存修改后会在此显示变更内容与时间。</p>
      </article>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

interface ChangeRecord {
  field: string
  old: string
  new: string
}
interface HistoryRecord {
  time: string
  operator?: string
  changes: ChangeRecord[]
}
type Entry = Record<string, string | number | null>

const route = useRoute()
const router = useRouter()
const session = useSessionStore()

const ENDPOINT = '/api/vessel'
const readonlyFields = ['船舶编号', '船舶名称', '船舶类型', '船籍', '载重吨位', '船长', '船宽', '所属船公司', '船舶状态']
const editableFields = ['船舶名称', '船舶类型', '船籍', '载重吨位', '船长', '船宽', '所属船公司']

const entry = ref<Entry | null>(null)
const history = ref<HistoryRecord[]>([])
const loading = ref(true)
const saving = ref(false)
const errorMessage = ref('')
const toast = ref<{ text: string; tone: 'ok' | 'notice' } | null>(null)

const form = reactive<Record<string, string>>(Object.fromEntries(editableFields.map((f) => [f, ''])))

function fillForm() {
  if (!entry.value) return
  for (const field of editableFields) {
    form[field] = String(entry.value[field] ?? '')
  }
}

function resetForm() {
  fillForm()
  toast.value = null
}

async function loadEntry() {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${route.params.id}`)
    if (response.status === 404) {
      entry.value = null
      errorMessage.value = `船舶 ${route.params.id} 不存在或已归档`
      return
    }
    if (!response.ok) {
      throw new Error('船舶详情读取失败')
    }
    entry.value = await response.json()
    fillForm()
    await loadHistory()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '船舶详情读取失败'
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  try {
    const response = await request(`${ENDPOINT}/${route.params.id}/history`)
    if (response.ok) {
      const payload = await response.json()
      history.value = payload.items ?? []
    }
  } catch {
    // 留档区读取失败不阻断编辑，只保留空列表
    history.value = []
  }
}

async function saveChanges() {
  if (!entry.value) return
  saving.value = true
  toast.value = null
  try {
    const values: Record<string, string> = {}
    for (const field of editableFields) {
      values[field] = form[field].trim()
    }
    const response = await request(`${ENDPOINT}/${entry.value.id}`, {
      method: 'PUT',
      body: JSON.stringify({ values, operator: session.operator }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      throw new Error(payload?.detail ?? '船舶档案保存失败，请稍后重试')
    }
    // 以后端回写的档案为准，保证详情与列表同源一致
    entry.value = payload.entry
    fillForm()
    await loadHistory()
    toast.value = {
      text: payload.message ?? '船舶档案已更新',
      tone: payload.code === 'refreshed' || payload.code === 'unchanged' ? 'notice' : 'ok',
    }
  } catch (error) {
    toast.value = {
      text: error instanceof Error ? error.message : '船舶档案保存失败',
      tone: 'notice',
    }
  } finally {
    saving.value = false
  }
}

function goBack() {
  void router.push({ name: 'vessel' })
}

onMounted(loadEntry)
</script>
