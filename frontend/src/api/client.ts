/** 统一请求封装：拼后端地址、附带当前操作人、抛网络错误、给页脚留一句可读的说明。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const SESSION_KEY = 'pipeline-session'

type SessionPayload = { role?: string; team?: string }

function sessionHeaders(): HeadersInit {
  try {
    const saved = JSON.parse(localStorage.getItem(SESSION_KEY) ?? '{}') as SessionPayload
    return {
      'X-Operator-Role': saved.role === 'crew' || saved.role === 'admin' ? saved.role : 'viewer',
      'X-Operator-Team': saved.team ?? '',
    }
  } catch {
    return { 'X-Operator-Role': 'viewer', 'X-Operator-Team': '' }
  }
}

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  return fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...sessionHeaders(),
      ...(init?.headers ?? {}),
    },
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

export async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string | { field?: string; message?: string } }
    if (typeof payload.detail === 'object' && payload.detail?.message) {
      return payload.detail.message
    }
    if (typeof payload.detail === 'string') return payload.detail
  } catch {
    // 非 JSON 错误使用调用方的兜底文案。
  }
  return fallback
}
