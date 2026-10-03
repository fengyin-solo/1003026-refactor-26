/** 列表分页的共用写法：所有模块共用这一份取页、翻页与总数逻辑。 */
import { ref } from 'vue'

import { request } from '@/api/client'

interface PagePayload<Row> {
  items: Row[]
  total: number
  page: number
  size: number
}

export function usePagedList<Row extends Record<string, unknown>>(endpoint: string, pageSize = 20) {
  const rows = ref<Row[]>([])
  const total = ref(0)
  const page = ref(1)
  const size = ref(pageSize)
  const errorMessage = ref('')

  /** 取一页：过滤条件原样带上；不传页码时停留在当前页。 */
  async function load(filters: Record<string, string> = {}, toPage: number = page.value) {
    errorMessage.value = ''
    const query = new URLSearchParams()
    for (const [field, value] of Object.entries(filters)) {
      if (value) {
        query.set(field, value)
      }
    }
    query.set('page', String(toPage))
    query.set('size', String(size.value))
    try {
      const response = await request(`${endpoint}?${query.toString()}`)
      const payload = (await response.json().catch(() => null)) as (PagePayload<Row> & { detail?: string }) | null
      if (!response.ok || !payload) {
        // 页大小越界时后端返回 400 和一句说明，原样展示给操作员
        throw new Error(payload?.detail ?? `接口返回 ${response.status}，列表读取失败`)
      }
      rows.value = payload.items ?? []
      total.value = typeof payload.total === 'number' ? payload.total : rows.value.length
      page.value = typeof payload.page === 'number' ? payload.page : toPage
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '列表读取失败'
    }
  }

  return { rows, total, page, size, errorMessage, load }
}
