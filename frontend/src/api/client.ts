/** 统一请求封装：拼后端地址、抛网络错误、给页脚留一句可读的说明。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  return fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}

/** 分页信封：后端所有列表接口统一返回 items/total/page/size。 */
export interface PageEnvelope<T> {
  items: T[]
  total: number
  page: number
  size: number
}

/** 统一的分页列表请求：拼过滤条件、解析分页信封，后端的报错说明原样抛给页面。 */
export async function fetchPage<T>(
  path: string,
  params: Record<string, string | number> = {},
): Promise<PageEnvelope<T>> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== '') {
      query.set(key, String(value))
    }
  }
  const qs = query.toString()
  const response = await request(qs ? `${path}?${qs}` : path)
  if (!response.ok) {
    let detail = ''
    try {
      const body = (await response.json()) as { detail?: unknown }
      detail = typeof body.detail === 'string' ? body.detail : ''
    } catch {
      // 错误体不是 JSON 时退化为状态码说明
    }
    throw new Error(detail || `接口返回 ${response.status}，列表读取失败`)
  }
  return (await response.json()) as PageEnvelope<T>
}
