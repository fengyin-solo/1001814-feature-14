/** 统一请求封装：拼后端地址、带操作身份、抛网络错误、给页脚留一句可读的说明。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

// 当前操作身份（角色 + 班组），由会话 store 在切换身份时同步过来
let identityHeaders: Record<string, string> = {}

export function setIdentity(role: string, team: string) {
  // 班组名是中文，直接放请求头会被按 latin-1 解码成乱码，先做百分号编码，后端再还原
  identityHeaders = { 'X-Operator-Role': role, 'X-Operator-Team': encodeURIComponent(team) }
}

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  return fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...identityHeaders, ...(init?.headers ?? {}) },
  }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

/** 读出后端返回的错误说明：越权拦截（403）等原因都在 detail 里。 */
export async function readError(response: Response, fallback: string): Promise<Error> {
  try {
    const payload = (await response.json()) as { detail?: string; message?: string }
    return new Error(payload.detail ?? payload.message ?? fallback)
  } catch {
    return new Error(fallback)
  }
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw await readError(response, `接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}
