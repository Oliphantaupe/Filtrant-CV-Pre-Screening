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
    date_from?: string
    date_to?: string
    search?: string
    sort_by?: string
  }): Promise<ListResponse> => {
    const qs = new URLSearchParams()
    if (params.page) qs.set('page', String(params.page))
    if (params.page_size) qs.set('page_size', String(params.page_size))
    if (params.recommendation) qs.set('recommendation', params.recommendation)
    if (params.date_from) qs.set('date_from', params.date_from)
    if (params.date_to) qs.set('date_to', params.date_to)
    if (params.search) qs.set('search', params.search)
    if (params.sort_by) qs.set('sort_by', params.sort_by)
    return request(`/api/v1/candidates?${qs}`)
  },

  getCandidate: (id: string): Promise<CandidateDetail> =>
    request(`/api/v1/candidates/${id}`),

  exportCsv: () => {
    window.open(`${BASE}/api/v1/candidates/export.csv`, '_blank')
  },
}
