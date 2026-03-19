export interface CandidateRow {
  id: string
  processed_at: string
  source_filename: string
  source_format: string
  parse_quality: string
  recommendation: 'Invite' | 'Reject' | 'pending'
  confidence: number | null
  name: string | null
  email: string | null
  target_role: string | null
}

export interface CandidateDetail extends CandidateRow {
  cv_data: CVData
  missing_fields: string[]
}

export interface CVData {
  personal: { full_name: string | null; email: string | null; phone: string | null; address: string | null }
  target_role: string | null
  summary: string | null
  education: Education[]
  experience: Experience[]
  skills: { technical: string[]; methods: string[]; management: string[] }
  languages: { language: string; level: string | null; level_score: number }[]
  certifications: { name: string; year: number | null }[]
  parse_quality: string
  missing_fields: string[]
}

export interface Education {
  degree: string | null
  field: string | null
  institution: string | null
  year: number | null
  level_score: number
}

export interface Experience {
  title: string | null
  company: string | null
  start: string | null
  end: string | null
  duration_months: number | null
}

export interface ListResponse {
  total: number
  page: number
  page_size: number
  items: CandidateRow[]
}

export interface UploadResult {
  id: string
  name: string | null
  recommendation: 'Invite' | 'Reject' | 'pending'
  confidence: number | null
  parse_quality: string
  missing_fields: string[]
}
