import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { api } from '../api/client'
import type { CandidateRow, CandidateDetail, CVData } from '../types/cv'
import SpotlightCard from '../components/SpotlightCard'
import CountUp from '../components/CountUp'
import RecommendationBadge from '../components/RecommendationBadge'

// ─── Feature derivation ───────────────────────────────────────────────────────

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
  0: 'Unknown', 1: 'High school', 2: 'Associate',
  3: "Bachelor's", 4: "Master's", 5: 'PhD',
}

// ─── Candidates page ──────────────────────────────────────────────────────────

type FilterValue = '' | 'Invite' | 'Reject' | 'pending'

const FILTER_OPTIONS: { label: string; value: FilterValue }[] = [
  { label: 'All', value: '' },
  { label: 'Invite', value: 'Invite' },
  { label: 'Reject', value: 'Reject' },
  { label: 'Pending', value: 'pending' },
]

export default function CandidatesPage() {
  const [items, setItems] = useState<CandidateRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState<FilterValue>('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [selected, setSelected] = useState<CandidateDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [view, setView] = useState<'simple' | 'advanced'>('simple')
  const [stats, setStats] = useState({ invited: 0, rejected: 0, total: 0 })

  // Fetch stats once on mount
  useEffect(() => {
    Promise.all([
      api.listCandidates({ page: 1, page_size: 1 }),
      api.listCandidates({ page: 1, page_size: 1, recommendation: 'Invite' }),
      api.listCandidates({ page: 1, page_size: 1, recommendation: 'Reject' }),
    ]).then(([all, inv, rej]) =>
      setStats({ total: all.total, invited: inv.total, rejected: rej.total })
    )
  }, [])

  useEffect(() => {
    setLoading(true)
    api.listCandidates({
      page,
      recommendation: filter || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    })
      .then(res => { setItems(res.items); setTotal(res.total) })
      .finally(() => setLoading(false))
  }, [page, filter, dateFrom, dateTo])

  const openDetail = async (id: string) => {
    const detail = await api.getCandidate(id)
    setSelected(detail)
  }

  const totalPages = Math.ceil(total / 20)

  return (
    <div>
      {/* Stats row */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <StatCard label="Total CVs" value={stats.total} color="blue" />
        <StatCard label="Invited" value={stats.invited} color="green" />
        <StatCard label="Rejected" value={stats.rejected} color="red" />
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-700">
          {filter ? `${filter} — ` : ''}{total} candidate{total !== 1 ? 's' : ''}
        </h2>
        <div className="flex items-center gap-2">
          {/* View toggle */}
          <div className="flex rounded-lg border border-gray-200 overflow-hidden text-sm">
            <button
              onClick={() => setView('simple')}
              className={`px-3 py-1.5 transition-colors ${view === 'simple' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}
            >
              Cards
            </button>
            <button
              onClick={() => setView('advanced')}
              className={`px-3 py-1.5 border-l border-gray-200 transition-colors ${view === 'advanced' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}
            >
              Table
            </button>
          </div>
          <button
            onClick={api.exportCsv}
            className="text-sm px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-700 transition-colors"
          >
            Export CSV
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        {/* Pill nav */}
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
          {FILTER_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => { setFilter(opt.value); setPage(1) }}
              className={`px-3 py-1 rounded-lg text-sm font-medium transition-all duration-150 ${
                filter === opt.value
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* Date range */}
        <div className="flex items-center gap-1.5 text-sm text-gray-500">
          <input
            type="date"
            className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm bg-white text-gray-700"
            value={dateFrom}
            onChange={e => { setDateFrom(e.target.value); setPage(1) }}
          />
          <span>→</span>
          <input
            type="date"
            className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm bg-white text-gray-700"
            value={dateTo}
            onChange={e => { setDateTo(e.target.value); setPage(1) }}
          />
          {(dateFrom || dateTo) && (
            <button
              onClick={() => { setDateFrom(''); setDateTo(''); setPage(1) }}
              className="text-gray-400 hover:text-gray-600 text-xs px-1"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : view === 'simple' ? (
        <SimpleView items={items} onOpen={openDetail} />
      ) : (
        <AdvancedView items={items} onOpen={openDetail} />
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex gap-2 mt-6 justify-end">
          <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
            className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-40 hover:bg-gray-50 transition-colors">
            ← Prev
          </button>
          <span className="px-3 py-1.5 text-sm text-gray-500">{page} / {totalPages}</span>
          <button disabled={page === totalPages} onClick={() => setPage(p => p + 1)}
            className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-40 hover:bg-gray-50 transition-colors">
            Next →
          </button>
        </div>
      )}

      {selected && <DetailPanel candidate={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

// ─── Stat card ────────────────────────────────────────────────────────────────

function StatCard({ label, value, color }: { label: string; value: number; color: 'blue' | 'green' | 'red' }) {
  const numColors = { blue: 'text-blue-600', green: 'text-green-600', red: 'text-red-500' }
  return (
    <div className="rounded-2xl border border-gray-200/70 bg-white/70 backdrop-blur-sm shadow-sm px-5 py-4">
      <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">{label}</p>
      <p className={`text-3xl font-black tabular-nums ${numColors[color]}`}>
        <CountUp to={value} duration={1.2} />
      </p>
    </div>
  )
}

// ─── Simple view — card grid ──────────────────────────────────────────────────

function SimpleView({ items, onOpen }: { items: CandidateRow[]; onOpen: (id: string) => void }) {
  if (items.length === 0)
    return (
      <div className="text-center py-20 text-gray-400">
        <div className="text-4xl mb-3">📭</div>
        <p className="font-medium">No candidates yet</p>
        <p className="text-sm mt-1">Upload a CV to get started</p>
      </div>
    )

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {items.map((c, i) => (
        <motion.div
          key={c.id}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.04, duration: 0.3 }}
        >
          <SpotlightCard
            className="bg-white/75 backdrop-blur-sm rounded-2xl border border-gray-200/70 p-5 cursor-pointer hover:shadow-md hover:border-blue-200/70 hover:bg-white/90 transition-all"
            onClick={() => onOpen(c.id)}
          >
            {/* Avatar + name */}
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-blue-100 text-blue-700 font-bold text-sm flex items-center justify-center shrink-0">
                {initials(c.name)}
              </div>
              <div className="min-w-0">
                <p className="font-semibold text-gray-900 truncate">{c.name ?? 'Unknown'}</p>
                <p className="text-xs text-blue-600 font-medium truncate">
                  {c.target_role ?? <span className="text-gray-400 font-normal">No target role</span>}
                </p>
              </div>
            </div>

            {/* Recommendation + confidence */}
            <div className="flex items-center justify-between mb-2">
              <RecommendationBadge value={c.recommendation} />
              {c.confidence !== null && (
                <span className="text-sm font-semibold text-gray-600 tabular-nums">
                  {(c.confidence * 100).toFixed(0)}%
                </span>
              )}
            </div>

            {/* Confidence bar */}
            {c.confidence !== null && (
              <div className="h-1 bg-gray-100 rounded-full overflow-hidden mb-3">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${(c.confidence * 100).toFixed(0)}%` }}
                  transition={{ delay: i * 0.04 + 0.2, duration: 0.6, ease: 'easeOut' }}
                  className={`h-full rounded-full ${
                    c.recommendation === 'Invite' ? 'bg-green-400' :
                    c.recommendation === 'Reject' ? 'bg-red-400' : 'bg-gray-300'
                  }`}
                />
              </div>
            )}

            <p className="text-xs text-gray-400">
              {new Date(c.processed_at).toLocaleDateString(undefined, {
                day: 'numeric', month: 'short', year: 'numeric',
              })}
            </p>
          </SpotlightCard>
        </motion.div>
      ))}
    </div>
  )
}

// ─── Advanced view — table ────────────────────────────────────────────────────

function AdvancedView({ items, onOpen }: { items: CandidateRow[]; onOpen: (id: string) => void }) {
  if (items.length === 0)
    return <p className="text-center text-gray-400 py-16">No candidates yet.</p>

  return (
    <div className="bg-white/75 backdrop-blur-sm rounded-2xl border border-gray-200/70 overflow-hidden shadow-sm">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            <th className="text-left px-4 py-3 font-medium text-gray-500">Candidate</th>
            <th className="text-left px-4 py-3 font-medium text-gray-500">Outcome</th>
            <th className="text-left px-4 py-3 font-medium text-gray-500">Confidence</th>
            <th className="text-left px-4 py-3 font-medium text-gray-500">Parse quality</th>
            <th className="text-left px-4 py-3 font-medium text-gray-500">Format</th>
            <th className="text-left px-4 py-3 font-medium text-gray-500">Processed</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {items.map((c, i) => (
            <motion.tr
              key={c.id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: i * 0.03 }}
              className="hover:bg-gray-50 cursor-pointer"
              onClick={() => onOpen(c.id)}
            >
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-full bg-blue-100 text-blue-700 font-bold text-xs flex items-center justify-center shrink-0">
                    {initials(c.name)}
                  </div>
                  <div>
                    <p className="font-medium text-gray-800">{c.name ?? '—'}</p>
                    <p className="text-xs text-blue-600 font-medium">{c.target_role ?? '—'}</p>
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
                  <span className="text-gray-500 text-xs tabular-nums">
                    {c.confidence !== null ? `${(c.confidence * 100).toFixed(1)}%` : '—'}
                  </span>
                </div>
              </td>
              <td className="px-4 py-3"><ParseQualityBadge value={c.parse_quality} /></td>
              <td className="px-4 py-3 text-gray-500 uppercase text-xs">{c.source_format}</td>
              <td className="px-4 py-3 text-gray-400 text-xs">{new Date(c.processed_at).toLocaleString()}</td>
            </motion.tr>
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
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/40 z-50 flex"
        onClick={onClose}
      >
        <motion.div
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          className="ml-auto bg-white/90 backdrop-blur-2xl w-full max-w-4xl h-full overflow-hidden flex flex-col shadow-2xl border-l border-gray-200/50"
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

            {/* LEFT — CV */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
              {/* Contact */}
              <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-gray-600">
                {cv.personal.email   && <span>✉ {cv.personal.email}</span>}
                {cv.personal.phone   && <span>📞 {cv.personal.phone}</span>}
                {cv.personal.address && <span>📍 {cv.personal.address}</span>}
              </div>

              {/* Parse warning */}
              {cv.parse_quality !== 'complete' && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-2.5 text-sm">
                  <span className="font-semibold text-amber-800">
                    {cv.parse_quality === 'partial' ? 'Partially parsed CV' : 'Poorly parsed CV — low reliability'}
                  </span>
                  {cv.missing_fields.length > 0 && (
                    <p className="text-amber-600 mt-0.5 text-xs">Missing: {cv.missing_fields.join(' · ')}</p>
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
                <CvSection title={`Work experience — ${f.yearsExp} yr across ${f.numPositions} position${f.numPositions !== 1 ? 's' : ''}`}>
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
                    {cv.skills.technical.length > 0 && <SkillGroup label="Technical" tags={cv.skills.technical} color="blue" />}
                    {cv.skills.methods.length > 0 && <SkillGroup label="Methods & practices" tags={cv.skills.methods} color="violet" />}
                    {cv.skills.management.length > 0 && <SkillGroup label="Management & soft skills" tags={cv.skills.management} color="emerald" />}
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
              <div className="bg-white/80 backdrop-blur-sm rounded-2xl border border-gray-200/70 p-4 shadow-sm text-center">
                <p className="text-xs text-gray-400 uppercase tracking-wider mb-3">AI Recommendation</p>
                <RecommendationBadge value={candidate.recommendation} large />
                {candidate.confidence !== null && (
                  <>
                    <p className="text-3xl font-bold text-gray-900 mt-3 tabular-nums">
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
                  <ScoreFactor label="Years of experience" display={`${f.yearsExp} yr`} value={f.yearsExp} max={20} hint="Max reference: 20 yr" />
                  <ScoreFactor label="Positions held" display={`${f.numPositions}`} value={f.numPositions} max={6} hint="More positions = broader track record" />
                  <ScoreFactor label="Avg. time per role" display={formatDuration(f.avgTenureMonths)} value={f.avgTenureMonths} max={60} hint="Longer tenures indicate stability" />
                  <ScoreFactor label="Highest education" display={EDU_LABEL[f.eduScore] ?? '—'} value={f.eduScore} max={5} hint="From high school (1) to PhD (5)" />
                  <ScoreFactor label="Total skills" display={`${f.skillsCount}`} value={f.skillsCount} max={20} hint="Technical + methods + management" />
                  <ScoreFactor label="Certifications" display={f.hasCerts ? 'Yes' : 'None'} value={f.hasCerts ? 1 : 0} max={1} hint="Any professional certification" />
                  <ScoreFactor label="Languages" display={`${f.langCount}`} value={f.langCount} max={5} hint="Number of languages declared" />
                  <ScoreFactor label="Profile completeness" display={`${f.completeness}/${f.totalSections}`} value={f.completeness} max={f.totalSections} hint="Personal · Summary · Education · Experience · Skills · Languages" />
                </div>
              </div>

              {/* Meta */}
              <div className="text-xs text-gray-400 space-y-1 pt-3 border-t border-gray-200">
                <p><span className="font-medium text-gray-500">File:</span> {candidate.source_filename}</p>
                <p><span className="font-medium text-gray-500">Format:</span> {candidate.source_format.toUpperCase()}</p>
                <p><span className="font-medium text-gray-500">Parsed:</span> {new Date(candidate.processed_at).toLocaleString()}</p>
                <p><span className="font-medium text-gray-500">Quality: </span><ParseQualityBadge value={candidate.parse_quality} /></p>
              </div>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
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
