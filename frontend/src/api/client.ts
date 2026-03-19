import type { ListResponse, CandidateDetail, UploadResult } from '../types/cv'

const BASE = import.meta.env.VITE_API_BASE_URL || ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Request failed')
  }
  return res.json()
}

export const api = {
  uploadCV: (file: File): Promise<UploadResult> => {
    const form = new FormData()
    form.append('file', file)
    return request('/api/v1/upload', { method: 'POST', body: form })
  },

  listCandidates: (params: {
    page?: number
    page_size?: number
    recommendation?: string
    date?: string
  }): Promise<ListResponse> => {
    const qs = new URLSearchParams()
    if (params.page) qs.set('page', String(params.page))
    if (params.page_size) qs.set('page_size', String(params.page_size))
    if (params.recommendation) qs.set('recommendation', params.recommendation)
    if (params.date) qs.set('date', params.date)
    return request(`/api/v1/candidates?${qs}`)
  },

  getCandidate: (id: string): Promise<CandidateDetail> =>
    request(`/api/v1/candidates/${id}`),

  exportCsv: () => {
    window.open(`${BASE}/api/v1/candidates/export.csv`, '_blank')
  },
}
