const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { headers: { 'Content-Type': 'application/json' }, ...options })
  const payload = await response.json()
  if (!response.ok) throw new Error(payload?.detail?.message || 'Request failed')
  return payload as T
}
