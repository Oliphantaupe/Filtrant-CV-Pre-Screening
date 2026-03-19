import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { CandidateRow, CandidateDetail, CVData } from '../types/cv'

// ─── Feature derivation (mirrors backend features.py) ────────────────────────

function deriveFeatures(cv: CVData) {
  const totalMonths = cv.experience.reduce((s, e) => s + (e.duration_months ?? 0), 0)
  const numPositions = cv.experience.length
  const eduScore = cv.education.length ? Math.max(...cv.education.map(e => e.level_score)) : 0
  const sections = [
    !!(cv.personal.full_name || cv.personal.email),
    !!cv.summary,
    cv.education.length > 0,
    cv.experience.length > 0,
    cv.skills.technical.length > 0 || cv.skills.methods.length > 0,
    cv.languages.length > 0,
  ]
  return {
    yearsExp: Math.round((totalMonths / 12) * 10) / 10,
    numPositions,
    avgTenureMonths: numPositions ? Math.round(totalMonths / numPositions) : 0,
    eduScore,
    skillsCount: cv.skills.technical.length + cv.skills.methods.length + cv.skills.management.length,
    hasCerts: cv.certifications.length > 0,
    langCount: cv.languages.length,
    completeness: sections.filter(Boolean).length,
    totalSections: sections.length,
  }
}

const EDU_LABEL: Record<number, string> = {
  0: 'Unknown', 1: 'High school', 2: 'Associate degree',
  3: "Bachelor's degree", 4: "Master's degree", 5: 'PhD / Doctorate',
}

// ─── Shared badge ─────────────────────────────────────────────────────────────

function RecommendationBadge({ value, large }: { value: string; large?: boolean }) {
  const styles: Record<string, string> = {
    Invite: 'bg-green-100 text-green-800',
    Reject: 'bg-red-100 text-red-800',
    pending: 'bg-gray-100 text-gray-600',
  }
  const size = large ? 'px-4 py-1.5 text-sm' : 'px-2 py-0.5 text-xs'
  return (
    <span className={`${size} rounded-full font-semibold ${styles[value] ?? styles.pending}`}>
      {value}
    </span>
  )
}

// ─── Candidates page ──────────────────────────────────────────────────────────

export default function CandidatesPage() {
  const [items, setItems] = useState<CandidateRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState('')
  const [dateFilter, setDateFilter] = useState('')
  const [selected, setSelected] = useState<CandidateDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [view, setView] = useState<'simple' | 'advanced'>('simple')

  useEffect(() => {
    setLoading(true)
    api.listCandidates({ page, recommendation: filter || undefined, date: dateFilter || undefined })
      .then(res => { setItems(res.items); setTotal(res.total) })
      .finally(() => setLoading(false))
  }, [page, filter, dateFilter])

  const openDetail = async (id: string) => {
    const detail = await api.getCandidate(id)
    setSelected(detail)
  }

  const totalPages = Math.ceil(total / 20)

  return (
    <div>
      {/* Toolbar */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">
          Candidates <span className="text-gray-400 font-normal text-lg">({total})</span>
        </h1>
        <div className="flex items-center gap-3">
          {/* View toggle */}
          <div className="flex rounded-lg border border-gray-200 overflow-hidden text-sm">
            <button
              onClick={() => setView('simple')}
              className={`px-3 py-1.5 ${view === 'simple' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}
            >
              Simple
            </button>
            <button
              onClick={() => setView('advanced')}
              className={`px-3 py-1.5 border-l border-gray-200 ${view === 'advanced' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}
            >
              Advanced
            </button>
          </div>
          <button
            onClick={api.exportCsv}
            className="text-sm px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-700"
          >
            Export CSV
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-5">
        <select
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white"
          value={filter}
          onChange={e => { setFilter(e.target.value); setPage(1) }}
        >
          <option value="">All outcomes</option>
          <option value="Invite">Invite only</option>
          <option value="Reject">Reject only</option>
          <option value="pending">Pending</option>
        </select>
        <input
          type="date"
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white"
          value={dateFilter}
          onChange={e => { setDateFilter(e.target.value); setPage(1) }}
        />
      </div>

      {loading ? (
        <p className="text-gray-400 text-sm py-8 text-center">Loading candidates…</p>
      ) : view === 'simple' ? (
        <SimpleView items={items} onOpen={openDetail} />
      ) : (
        <AdvancedView items={items} onOpen={openDetail} />
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex gap-2 mt-5 justify-end">
          <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
            className="px-3 py-1 text-sm border rounded disabled:opacity-40">← Prev</button>
          <span className="px-3 py-1 text-sm text-gray-500">{page} / {totalPages}</span>
          <button disabled={page === totalPages} onClick={() => setPage(p => p + 1)}
            className="px-3 py-1 text-sm border rounded disabled:opacity-40">Next →</button>
        </div>
      )}

      {selected && <DetailPanel candidate={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

// ─── Simple view — card grid ──────────────────────────────────────────────────

function SimpleView({ items, onOpen }: { items: CandidateRow[]; onOpen: (id: string) => void }) {
  if (items.length === 0)
    return <p className="text-center text-gray-400 py-16">No candidates yet. Upload a CV to get started.</p>

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {items.map(c => (
        <button
          key={c.id}
          onClick={() => onOpen(c.id)}
          className="text-left bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md hover:border-blue-200 transition-all"
        >
          {/* Avatar + name */}
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-full bg-blue-100 text-blue-700 font-bold text-sm flex items-center justify-center shrink-0">
              {initials(c.name)}
            </div>
            <div className="min-w-0">
              <p className="font-semibold text-gray-900 truncate">{c.name ?? 'Unknown'}</p>
              <p className="text-xs text-blue-600 font-medium truncate">{c.target_role ?? <span className="text-gray-400 font-normal">No target role</span>}</p>
            </div>
          </div>

          {/* Recommendation + confidence */}
          <div className="flex items-center justify-between mb-3">
            <RecommendationBadge value={c.recommendation} />
            {c.confidence !== null && (
              <span className="text-sm font-semibold text-gray-700">
                {(c.confidence * 100).toFixed(0)}%
              </span>
            )}
          </div>

          {/* Confidence bar */}
          {c.confidence !== null && (
            <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden mb-3">
              <div
                className={`h-full rounded-full ${c.recommendation === 'Invite' ? 'bg-green-400' : c.recommendation === 'Reject' ? 'bg-red-400' : 'bg-gray-300'}`}
                style={{ width: `${(c.confidence * 100).toFixed(0)}%` }}
              />
            </div>
          )}

          {/* Date */}
          <p className="text-xs text-gray-400">{new Date(c.processed_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</p>
        </button>
      ))}
    </div>
  )
}

// ─── Advanced view — table ────────────────────────────────────────────────────

function AdvancedView({ items, onOpen }: { items: CandidateRow[]; onOpen: (id: string) => void }) {
  if (items.length === 0)
    return <p className="text-center text-gray-400 py-16">No candidates yet.</p>

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Candidate</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Outcome</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Confidence</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Parse quality</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Format</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Processed</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {items.map(c => (
            <tr key={c.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => onOpen(c.id)}>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-full bg-blue-100 text-blue-700 font-bold text-xs flex items-center justify-center shrink-0">
                    {initials(c.name)}
                  </div>
                  <div>
                    <p className="font-medium text-gray-800">{c.name ?? '—'}</p>
                    <p className="text-xs text-blue-600 font-medium">{c.target_role ?? <span className="text-gray-400 font-normal">—</span>}</p>
                    <p className="text-xs text-gray-400">{c.source_filename}</p>
                  </div>
                </div>
              </td>
              <td className="px-4 py-3"><RecommendationBadge value={c.recommendation} /></td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="w-20 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${c.recommendation === 'Invite' ? 'bg-green-400' : 'bg-red-400'}`}
                      style={{ width: c.confidence !== null ? `${(c.confidence * 100).toFixed(0)}%` : '0%' }}
                    />
                  </div>
                  <span className="text-gray-600 text-xs">
                    {c.confidence !== null ? `${(c.confidence * 100).toFixed(1)}%` : '—'}
                  </span>
                </div>
              </td>
              <td className="px-4 py-3">
                <ParseQualityBadge value={c.parse_quality} />
              </td>
              <td className="px-4 py-3 text-gray-500 uppercase text-xs">{c.source_format}</td>
              <td className="px-4 py-3 text-gray-400 text-xs">{new Date(c.processed_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Detail side panel ────────────────────────────────────────────────────────

function DetailPanel({ candidate, onClose }: { candidate: CandidateDetail; onClose: () => void }) {
  const cv = candidate.cv_data
  const f = deriveFeatures(cv)

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex" onClick={onClose}>
      <div
        className="ml-auto bg-white w-full max-w-4xl h-full overflow-hidden flex flex-col shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between z-10 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-blue-100 text-blue-700 font-bold flex items-center justify-center">
              {initials(cv.personal.full_name)}
            </div>
            <div>
              <h2 className="text-lg font-bold text-gray-900">{cv.personal.full_name ?? 'Unknown candidate'}</h2>
              <p className="text-sm text-gray-500">{cv.target_role ?? 'No target role specified'}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-2xl leading-none px-2">×</button>
        </div>

        {/* Body */}
        <div className="flex flex-1 overflow-hidden divide-x divide-gray-100">

          {/* LEFT — cleaned CV */}
          <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">

            {/* Contact */}
            <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-gray-600">
              {cv.personal.email    && <span>✉ {cv.personal.email}</span>}
              {cv.personal.phone    && <span>📞 {cv.personal.phone}</span>}
              {cv.personal.address  && <span>📍 {cv.personal.address}</span>}
            </div>

            {/* Parse warning */}
            {cv.parse_quality !== 'complete' && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-2.5 text-sm">
                <span className="font-semibold text-amber-800">
                  {cv.parse_quality === 'partial' ? 'Partially parsed CV' : 'Poorly parsed CV — low reliability'}
                </span>
                {cv.missing_fields.length > 0 && (
                  <p className="text-amber-600 mt-0.5 text-xs">
                    Missing or unclear: {cv.missing_fields.join(' · ')}
                  </p>
                )}
              </div>
            )}

            {/* Summary */}
            {cv.summary && (
              <CvSection title="Professional summary">
                <p className="text-sm text-gray-700 leading-relaxed">{cv.summary}</p>
              </CvSection>
            )}

            {/* Experience */}
            {cv.experience.length > 0 && (
              <CvSection title={`Work experience — ${f.yearsExp} years total across ${f.numPositions} position${f.numPositions !== 1 ? 's' : ''}`}>
                <div className="space-y-4">
                  {cv.experience.map((e, i) => (
                    <div key={i} className="border-l-2 border-blue-100 pl-4">
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-semibold text-sm text-gray-800">{e.title ?? 'Unknown role'}</span>
                        {e.duration_months != null && (
                          <span className="shrink-0 text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
                            {formatDuration(e.duration_months)}
                          </span>
                        )}
                      </div>
                      {e.company && <p className="text-xs font-medium text-blue-600 mt-0.5">{e.company}</p>}
                      {(e.start || e.end) && (
                        <p className="text-xs text-gray-400 mt-0.5">{e.start ?? '?'} → {e.end ?? 'present'}</p>
                      )}
                    </div>
                  ))}
                </div>
              </CvSection>
            )}

            {/* Education */}
            {cv.education.length > 0 && (
              <CvSection title="Education">
                <div className="space-y-2">
                  {cv.education.map((e, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <span className="shrink-0 text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full mt-0.5">
                        {EDU_LABEL[e.level_score] ?? `Level ${e.level_score}`}
                      </span>
                      <div>
                        <p className="text-sm font-medium text-gray-800">
                          {e.degree}{e.field ? ` in ${e.field}` : ''}
                        </p>
                        {e.institution && (
                          <p className="text-xs text-gray-500">{e.institution}{e.year ? `, ${e.year}` : ''}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CvSection>
            )}

            {/* Skills */}
            {(cv.skills.technical.length > 0 || cv.skills.methods.length > 0 || cv.skills.management.length > 0) && (
              <CvSection title={`Skills — ${f.skillsCount} identified`}>
                <div className="space-y-3">
                  {cv.skills.technical.length > 0 && (
                    <SkillGroup label="Technical" tags={cv.skills.technical} color="blue" />
                  )}
                  {cv.skills.methods.length > 0 && (
                    <SkillGroup label="Methods & practices" tags={cv.skills.methods} color="violet" />
                  )}
                  {cv.skills.management.length > 0 && (
                    <SkillGroup label="Management & soft skills" tags={cv.skills.management} color="emerald" />
                  )}
                </div>
              </CvSection>
            )}

            {/* Languages */}
            {cv.languages.length > 0 && (
              <CvSection title="Languages">
                <div className="flex flex-wrap gap-2">
                  {cv.languages.map((l, i) => (
                    <div key={i} className="flex items-center gap-1.5 bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5">
                      <span className="text-sm font-medium text-gray-800">{l.language}</span>
                      {l.level && (
                        <span className="text-xs text-gray-500 bg-white border border-gray-200 px-1.5 py-0.5 rounded">
                          {l.level}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </CvSection>
            )}

            {/* Certifications */}
            {cv.certifications.length > 0 && (
              <CvSection title="Certifications">
                <div className="space-y-1">
                  {cv.certifications.map((c, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      <span className="text-green-500">✓</span>
                      <span className="text-gray-700">{c.name}</span>
                      {c.year && <span className="text-gray-400 text-xs">({c.year})</span>}
                    </div>
                  ))}
                </div>
              </CvSection>
            )}
          </div>

          {/* RIGHT — assessment */}
          <div className="w-64 shrink-0 overflow-y-auto px-5 py-5 space-y-5 bg-gray-50">

            {/* Decision card */}
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm text-center">
              <p className="text-xs text-gray-400 uppercase tracking-wider mb-3">AI Recommendation</p>
              <RecommendationBadge value={candidate.recommendation} large />
              {candidate.confidence !== null && (
                <>
                  <p className="text-3xl font-bold text-gray-900 mt-3">
                    {(candidate.confidence * 100).toFixed(0)}
                    <span className="text-lg text-gray-400">%</span>
                  </p>
                  <p className="text-xs text-gray-400 mb-2">model confidence</p>
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${candidate.recommendation === 'Invite' ? 'bg-green-400' : 'bg-red-400'}`}
                      style={{ width: `${(candidate.confidence * 100).toFixed(0)}%` }}
                    />
                  </div>
                </>
              )}
            </div>

            {/* Scoring factors */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">What the model measured</p>
              <div className="space-y-3">
                <ScoreFactor
                  label="Years of experience"
                  display={`${f.yearsExp} yr`}
                  value={f.yearsExp} max={20}
                  hint="Max reference: 20 yr"
                />
                <ScoreFactor
                  label="Number of positions"
                  display={`${f.numPositions}`}
                  value={f.numPositions} max={6}
                  hint="More positions = broader track record"
                />
                <ScoreFactor
                  label="Average time per role"
                  display={formatDuration(f.avgTenureMonths)}
                  value={f.avgTenureMonths} max={60}
                  hint="Longer tenures indicate stability"
                />
                <ScoreFactor
                  label="Highest education"
                  display={EDU_LABEL[f.eduScore] ?? '—'}
                  value={f.eduScore} max={5}
                  hint="From high school (1) to PhD (5)"
                />
                <ScoreFactor
                  label="Total skills listed"
                  display={`${f.skillsCount}`}
                  value={f.skillsCount} max={20}
                  hint="Technical + methods + management"
                />
                <ScoreFactor
                  label="Certifications"
                  display={f.hasCerts ? 'Yes' : 'None'}
                  value={f.hasCerts ? 1 : 0} max={1}
                  hint="Any professional certification"
                />
                <ScoreFactor
                  label="Languages spoken"
                  display={`${f.langCount}`}
                  value={f.langCount} max={5}
                  hint="Number of languages declared"
                />
                <ScoreFactor
                  label="Profile completeness"
                  display={`${f.completeness} of ${f.totalSections} sections filled`}
                  value={f.completeness} max={f.totalSections}
                  hint="Personal · Summary · Education · Experience · Skills · Languages"
                />
              </div>
            </div>

            {/* Meta */}
            <div className="text-xs text-gray-400 space-y-1 pt-3 border-t border-gray-200">
              <p><span className="font-medium text-gray-500">File:</span> {candidate.source_filename}</p>
              <p><span className="font-medium text-gray-500">Format:</span> {candidate.source_format.toUpperCase()}</p>
              <p><span className="font-medium text-gray-500">Parsed:</span> {new Date(candidate.processed_at).toLocaleString()}</p>
              <p>
                <span className="font-medium text-gray-500">Parse quality: </span>
                <ParseQualityBadge value={candidate.parse_quality} />
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Small components ─────────────────────────────────────────────────────────

function CvSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2.5">{title}</h3>
      {children}
    </div>
  )
}

const SKILL_COLORS: Record<string, string> = {
  blue: 'bg-blue-50 text-blue-700',
  violet: 'bg-violet-50 text-violet-700',
  emerald: 'bg-emerald-50 text-emerald-700',
}

function SkillGroup({ label, tags, color }: { label: string; tags: string[]; color: string }) {
  return (
    <div>
      <p className="text-xs text-gray-400 mb-1.5">{label}</p>
      <div className="flex flex-wrap gap-1">
        {tags.map(t => (
          <span key={t} className={`${SKILL_COLORS[color]} px-2 py-0.5 rounded text-xs font-medium`}>{t}</span>
        ))}
      </div>
    </div>
  )
}

function ScoreFactor({ label, display, value, max, hint }: {
  label: string; display: string; value: number; max: number; hint: string
}) {
  const pct = Math.min(100, Math.round((value / max) * 100))
  return (
    <div title={hint}>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="font-semibold text-gray-800">{display}</span>
      </div>
      <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div className="h-full bg-blue-400 rounded-full" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function ParseQualityBadge({ value }: { value: string }) {
  const styles: Record<string, string> = {
    complete: 'bg-green-100 text-green-700',
    partial: 'bg-amber-100 text-amber-700',
    poor: 'bg-red-100 text-red-700',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[value] ?? 'bg-gray-100 text-gray-600'}`}>
      {value}
    </span>
  )
}

// ─── Utilities ────────────────────────────────────────────────────────────────

function initials(name: string | null): string {
  if (!name) return '?'
  return name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase()
}

function formatDuration(months: number): string {
  if (months === 0) return '—'
  const y = Math.floor(months / 12)
  const m = months % 12
  if (y === 0) return `${m}mo`
  if (m === 0) return `${y}yr`
  return `${y}yr ${m}mo`
}
