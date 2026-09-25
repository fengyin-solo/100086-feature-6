import { defineStore } from 'pinia'

/**
 * 船舶档案列表的视图状态：筛选条件、页码与滚动位置。
 * 存 sessionStorage 而不是 localStorage：关页签即清，只服务“列表→详情→返回”这一趟。
 */
const STORAGE_KEY = 'vessel-list-view-state'

interface VesselListViewState {
  filters: {
    keyword: string
    status: string
    vesselType: string
    registry: string
  }
  page: number
  size: number
  scrollTop: number
}

const DEFAULT_STATE: VesselListViewState = {
  filters: { keyword: '', status: '', vesselType: '', registry: '' },
  page: 1,
  size: 10,
  scrollTop: 0,
}

function loadState(): VesselListViewState {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_STATE, filters: { ...DEFAULT_STATE.filters } }
    const parsed = JSON.parse(raw) as Partial<VesselListViewState>
    return {
      ...DEFAULT_STATE,
      ...parsed,
      filters: { ...DEFAULT_STATE.filters, ...(parsed.filters ?? {}) },
    }
  } catch {
    return { ...DEFAULT_STATE, filters: { ...DEFAULT_STATE.filters } }
  }
}

export const useVesselViewStore = defineStore('vessel-view', {
  state: (): VesselListViewState => loadState(),
  actions: {
    persist() {
      try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(this.$state))
      } catch {
        // sessionStorage 不可用时退回纯内存，功能降级但不阻断操作
      }
    },
    setFilters(filters: VesselListViewState['filters']) {
      this.filters = { ...filters }
      this.page = 1
      this.persist()
    },
    setPage(page: number) {
      this.page = page
      this.persist()
    },
    setScrollTop(scrollTop: number) {
      this.scrollTop = scrollTop
      this.persist()
    },
    reset() {
      this.$patch({ ...DEFAULT_STATE, filters: { ...DEFAULT_STATE.filters } })
      this.persist()
    },
  },
})
