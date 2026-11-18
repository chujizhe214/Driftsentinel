export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch('/api' + path, {
    ...options,
    headers:
      options.body instanceof FormData
        ? options.headers
        : { 'Content-Type': 'application/json', ...options.headers },
  })
  if (!response.ok) {
    let message = `请求失败 (${response.status})`
    try {
      const payload = await response.json()
      message = Array.isArray(payload.detail)
        ? payload.detail.map((d: { msg: string }) => d.msg).join('；')
        : payload.detail || message
    } catch {
      /* HTTP status remains actionable when a proxy returns HTML. */
    }
    throw new Error(message)
  }
  return response.json()
}

export const post = <T>(path: string, body: unknown = {}) =>
  api<T>(path, { method: 'POST', body: JSON.stringify(body) })

export function download(url: string) {
  const link = document.createElement('a')
  link.href = url
  link.download = ''
  document.body.append(link)
  link.click()
  link.remove()
}

export function number(value: number | null | undefined, digits = 3) {
  return value == null
    ? '—'
    : value.toLocaleString('en-US', {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      })
}
export function percent(value: number | null | undefined, digits = 1) {
  return value == null ? '—' : `${(value * 100).toFixed(digits)}%`
}
export function date(value: string) {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}
