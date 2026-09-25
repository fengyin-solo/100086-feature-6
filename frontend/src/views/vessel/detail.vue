<template>
  <section class="page" data-module="vessel-detail">
    <header class="page-head">
      <div>
        <h2>船舶详情</h2>
        <p class="page-desc">查看船舶档案，维护船舶类型与船籍；每次改动都会留档，谁都能看到这里改过什么、什么时候改的。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回列表</button>
      </div>
    </header>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
    <p v-else-if="!entry" class="empty-state">船舶档案加载中…</p>

    <template v-else>
      <div class="detail-grid">
        <div v-for="field in readonlyFields" :key="field" class="detail-item">
          <span class="detail-label">{{ field }}</span>
          <strong>{{ entry[field] ?? '—' }}</strong>
        </div>
      </div>

      <form class="edit-panel" @submit.prevent="save">
        <h3>档案维护</h3>
        <div class="filter-bar">
          <label class="filter-item">
            <span>船舶类型</span>
            <input v-model="form.船舶类型" list="vessel-type-options" placeholder="选择或输入船舶类型" />
            <datalist id="vessel-type-options">
              <option v-for="option in typeOptions" :key="option" :value="option" />
            </datalist>
          </label>
          <label class="filter-item">
            <span>船籍</span>
            <input v-model="form.船籍" placeholder="例：中国上海 / 巴拿马" />
          </label>
          <label class="filter-item">
            <span>备注（选填）</span>
            <input v-model="remark" placeholder="本次改动说明" />
          </label>
          <button class="btn primary" type="submit" :disabled="saving">
            {{ saving ? '保存中…' : '保存改动' }}
          </button>
        </div>
        <p v-if="saveMessage" :class="saveOk ? 'success-text' : 'error-text'">{{ saveMessage }}</p>
      </form>

      <section class="history-panel">
        <h3>改动留档</h3>
        <p v-if="!history.length" class="empty-state">
          暂无改动记录：这艘船的船舶类型与船籍自登记以来还没有被修改过。
        </p>
        <table v-else class="data-table">
          <thead>
            <tr>
              <th>改动时间</th>
              <th>操作人</th>
              <th>改动内容</th>
              <th>备注</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in history" :key="record.id">
              <td>{{ record.时间 }}</td>
              <td>{{ record.操作人 }}</td>
              <td>
                <div v-for="change in record.改动" :key="change.字段">
                  {{ change.字段 }}：{{ change.旧值 || '—' }} → {{ change.新值 || '—' }}
                </div>
              </td>
              <td>{{ record.备注 || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

defineOptions({ name: 'VesselDetail' })

interface ChangeItem {
  字段: string
  旧值: string
  新值: string
}

interface ChangeRecord {
  id: number
  时间: string
  操作人: string
  改动: ChangeItem[]
  备注: string
}

type VesselEntry = Record<string, string | number | null>

const ENDPOINT = '/api/vessel'
const readonlyFields = ["船舶编号", "船舶名称", "载重吨位", "船长", "船宽", "所属船公司", "船舶状态"]
const typeOptions = ["集装箱船", "散货船", "杂货船", "滚装船", "油船", "冷藏船", "多用途船"]

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const entryId = Number(route.params.id)

const entry = ref<VesselEntry | null>(null)
const history = ref<ChangeRecord[]>([])
const form = ref({ 船舶类型: '', 船籍: '' })
const remark = ref('')
const saving = ref(false)
const saveMessage = ref('')
const saveOk = ref(true)
const errorMessage = ref('')

function goBack() {
  // 从列表点进来就原路返回（保留筛选与滚动位置）；直接打开的详情则回列表首页
  if (window.history.state?.back) {
    router.back()
  } else {
    void router.push({ name: 'vessel' })
  }
}

async function load() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${entryId}`)
    const payload = (await response.json().catch(() => null)) as
      | { entry?: VesselEntry; history?: ChangeRecord[]; detail?: string }
      | null
    if (!response.ok) {
      throw new Error(payload?.detail ?? '船舶详情读取失败')
    }
    entry.value = payload?.entry ?? null
    history.value = payload?.history ?? []
    form.value = {
      船舶类型: String(entry.value?.船舶类型 ?? ''),
      船籍: String(entry.value?.船籍 ?? ''),
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '船舶详情读取失败'
  }
}

async function save() {
  saveMessage.value = ''
  errorMessage.value = ''
  saving.value = true
  try {
    const response = await request(`${ENDPOINT}/${entryId}`, {
      method: 'PUT',
      body: JSON.stringify({
        values: { 船舶类型: form.value.船舶类型, 船籍: form.value.船籍 },
        remark: remark.value,
        operator: session.operator,
      }),
    })
    const payload = (await response.json().catch(() => null)) as
      | { ok?: boolean; message?: string; detail?: string }
      | null
    if (!response.ok) {
      throw new Error(payload?.detail ?? '船舶档案保存失败，请稍后重试')
    }
    saveOk.value = payload?.ok !== false
    saveMessage.value = payload?.message ?? '船舶档案已保存'
    if (saveOk.value) {
      remark.value = ''
      await load()
    }
  } catch (error) {
    saveOk.value = false
    saveMessage.value = error instanceof Error ? error.message : '船舶档案保存失败，请稍后重试'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
