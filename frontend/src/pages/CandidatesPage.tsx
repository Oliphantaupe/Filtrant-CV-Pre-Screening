import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { api } from '../api/client'
import type { CandidateRow, CandidateDetail, CVData } from '../types/cv'
import SpotlightCard from '../components/SpotlightCard'
import CountUp from '../components/CountUp'
import RecommendationBadge from '../components/RecommendationBadge'
import DatePicker from '../components/DatePicker'
import ScrollArea from '../components/ScrollArea'
import { useModel } from '../context/ModelContext'

// ─── Feature derivation ───────────────────────────────────────────────────────

function deriveFeatures(cv: CVData) {
  const totalMonths = cv.experience.reduce((s, e) => s + (e.duration_months ?? 0), 0)
  const numPositions = cv.experience.length
  const eduScore = cv.education.length ? Math.max(...cv.education.map(e => e.level_score)) : 0
  const sectionFlags = [
    { label: 'Personal info', ok: !!(cv.personal.full_name || cv.personal.email) },
    { label: 'Summary',       ok: !!cv.summary },
    { label: 'Education',     ok: cv.education.length > 0 },
    { label: 'Experience',    ok: cv.experience.length > 0 },
    { label: 'Skills',        ok: cv.skills.technical.length > 0 || cv.skills.methods.length > 0 },
    { label: 'Languages',     ok: cv.languages.length > 0 },
  ]
  return {
    yearsExp: Math.round((totalMonths / 12) * 10) / 10,
    numPositions,
    avgTenureMonths: numPositions ? Math.round(totalMonths / numPositions) : 0,
    eduScore,
    skillsCount: cv.skills.technical.length + cv.skills.methods.length + cv.skills.management.length,
    hasCerts: cv.certifications.length > 0,
    langCount: cv.languages.length,
    completeness: sectionFlags.filter(s => s.ok).length,
    totalSections: sectionFlags.length,
    sectionFlags,
  }
}

const FIELD_LABELS: Record<string, string> = {
  'personal.full_name': 'Full name', 'personal.email': 'Email address',
  'personal.phone': 'Phone number', 'personal.address': 'Address',
  'target_role': 'Target role', 'summary': 'Professional summary',
  'education': 'Education', 'experience': 'Work experience',
  'skills': 'Skills', 'skills.technical': 'Technical skills',
  'skills.methods': 'Methods & practices', 'skills.management': 'Management skills',
  'languages': 'Languages', 'certifications': 'Certifications',
  'duration_months': 'Employment duration', 'company': 'Company name',
  'title': 'Job title', 'degree': 'Degree', 'institution': 'Institution',
}

function humanizeField(raw: string): string {
  if (FIELD_LABELS[raw]) return FIELD_LABELS[raw]
  const stripped = raw.replace(/\[\d+\]/g, '')
  if (FIELD_LABELS[stripped]) return FIELD_LABELS[stripped]
  const lastSegment = stripped.split('.').pop() ?? raw
  if (FIELD_LABELS[lastSegment]) return FIELD_LABELS[lastSegment]
  return lastSegment.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

function humanizeMissingFields(fields: string[]): string[] {
  return [...new Set(fields.map(humanizeField))]
}

const EDU_LABEL: Record<number, string> = {
  0: 'Unknown', 1: 'High school', 2: 'Associate',
  3: "Bachelor's", 4: "Master's", 5: 'PhD',
}

// ─── Types ────────────────────────────────────────────────────────────────────

type FilterValue = '' | 'Invite' | 'Reject' | 'pending'
type DatePreset = 'all' | 'today' | 'week' | 'month' | 'custom'

function computeDateRange(preset: DatePreset): { from: string; to: string } {
  const pad = (n: number) => String(n).padStart(2, '0')
  const fmtUTC = (d: Date) => `${d.getUTCFullYear()}-${pad(d.getUTCMonth()+1)}-${pad(d.getUTCDate())}`
  const now = new Date()
  if (preset === 'today') { const s = fmtUTC(now); return { from: s, to: s } }
  if (preset === 'week') {
    const day = now.getUTCDay()
    const monday = new Date(now)
    monday.setUTCDate(now.getUTCDate() + (day === 0 ? -6 : 1 - day))
    return { from: fmtUTC(monday), to: fmtUTC(now) }
  }
  if (preset === 'month') {
    return { from: `${now.getUTCFullYear()}-${pad(now.getUTCMonth()+1)}-01`, to: fmtUTC(now) }
  }
  return { from: '', to: '' }
}

const DATE_PRESET_LABELS: Record<DatePreset, string> = {
  all: 'All time', today: 'Today', week: 'This week', month: 'This month', custom: 'Custom',
}
const DATE_PRESET_OPTIONS: { label: string; value: DatePreset }[] = [
  { label: 'All time', value: 'all' },
  { label: 'Today', value: 'today' },
  { label: 'This week', value: 'week' },
  { label: 'This month', value: 'month' },
  { label: 'Custom range', value: 'custom' },
]
const FILTER_OPTIONS: { label: string; value: FilterValue; dot?: string }[] = [
  { label: 'All', value: '' },
  { label: 'Invite', value: 'Invite', dot: 'var(--invite)' },
  { label: 'Reject', value: 'Reject', dot: 'var(--reject)' },
  { label: 'Pending', value: 'pending', dot: 'var(--gold)' },
]

const SORT_OPTIONS: { label: string; value: string }[] = [
  { label: 'Date: Newest', value: 'date_desc' },
  { label: 'Date: Oldest', value: 'date_asc' },
  { label: 'Confidence: High to Low', value: 'confidence_desc' },
  { label: 'Confidence: Low to High', value: 'confidence_asc' },
]

const SORT_LABELS: Record<string, string> = {
  date_desc: 'Newest first',
  date_asc: 'Oldest first',
  confidence_desc: 'High confidence',
  confidence_asc: 'Low confidence',
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function CandidatesPage() {
  const [items, setItems] = useState<CandidateRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState<FilterValue>('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [datePreset, setDatePreset] = useState<DatePreset>('all')
  const [selected, setSelected] = useState<CandidateDetail | null>(null)
  const [quickLook, setQuickLook] = useState<CandidateRow | null>(null)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [sortBy, setSortBy] = useState('date_desc')
  const [sortOpen, setSortOpen] = useState(false)
  const [dateOpen, setDateOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState({ invited: 0, rejected: 0, total: 0 })
  const [view, setView] = useState<'simple' | 'advanced'>('simple')

  useEffect(() => {
    const handler = setTimeout(() => {
      if (debouncedSearch !== search) {
        setDebouncedSearch(search)
        setPage(1)
      }
    }, 400)
    return () => clearTimeout(handler)
  }, [search, debouncedSearch])

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
      search: debouncedSearch || undefined,
      sort_by: sortBy
    })
      .then(res => { setItems(res.items); setTotal(res.total) })
      .catch(() => { setItems([]); setTotal(0) })
      .finally(() => setLoading(false))
  }, [page, filter, dateFrom, dateTo, debouncedSearch, sortBy])

  const handleDatePreset = (preset: DatePreset) => {
    setDatePreset(preset); setPage(1)
    if (preset !== 'custom') {
      const { from, to } = computeDateRange(preset)
      setDateFrom(from); setDateTo(to)
    }
  }

  const openDetail = async (id: string) => {
    const detail = await api.getCandidate(id)
    setSelected(detail)
  }

  const totalPages = Math.ceil(total / 20)

  return (
    <div>
      {/* Stats row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <GlassStatCard label="Total CVs"  value={stats.total} />
        <GlassStatCard label="Invited"    value={stats.invited} />
        <GlassStatCard label="Rejected"   value={stats.rejected} />
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4 mb-5">
        {/* Left: count + search */}
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <h2 className="font-bricolage text-base font-semibold shrink-0 tabular-nums" style={{ color: 'var(--text-bright)' }}>
            {total} <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>candidate{total !== 1 ? 's' : ''}</span>
          </h2>
          <div className="relative flex-1 min-w-[140px] max-w-xs">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="var(--text-icon)" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M16.65 16.65A7.5 7.5 0 1110.5 3a7.5 7.5 0 016.15 13.65z" />
            </svg>
            <input
              type="text"
              placeholder="Search name or role…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-1.5 rounded-lg text-sm outline-none transition-all placeholder:text-gray-600"
              style={{ background: 'var(--glass-dim)', color: 'var(--text-bright)', border: '1px solid var(--border-subtle)' }}
              onFocus={e => (e.currentTarget.style.border = '1px solid var(--border-strong)')}
              onBlur={e => (e.currentTarget.style.border = '1px solid var(--border-subtle)')}
            />
          </div>
        </div>

        {/* Right: sort + view toggle + export */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Sort dropdown */}
          <div className="relative">
            {sortOpen && <div className="fixed inset-0 z-10" onClick={() => setSortOpen(false)} />}
            <button
              onClick={() => setSortOpen(o => !o)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors"
              style={{ background: 'var(--glass-dim)', color: 'var(--text-2)', border: '1px solid var(--border-subtle)' }}
              onMouseEnter={e => (e.currentTarget.style.background = 'var(--glass-hover)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'var(--glass-dim)')}
            >
              <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 7h18M6 12h12M9 17h6" />
              </svg>
              <span className="hidden sm:inline">{SORT_LABELS[sortBy]}</span>
              <svg className="w-3 h-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            <AnimatePresence>
              {sortOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -6, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -6, scale: 0.97 }}
                  transition={{ duration: 0.13 }}
                  className="absolute top-full mt-1.5 right-0 z-20 rounded-xl overflow-hidden min-w-[190px] glass-dropdown"
                >
                  {SORT_OPTIONS.map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => { setSortBy(opt.value); setSortOpen(false); setPage(1) }}
                      className="w-full text-left px-4 py-2.5 text-sm transition-colors flex items-center justify-between gap-3"
                      style={sortBy === opt.value
                        ? { background: 'var(--glass-hover)', color: 'var(--text-heading)', fontWeight: 500 }
                        : { color: 'var(--text-2)' }}
                      onMouseEnter={e => { if (sortBy !== opt.value) (e.currentTarget.style.background = 'var(--glass-dim)') }}
                      onMouseLeave={e => { if (sortBy !== opt.value) (e.currentTarget.style.background = 'transparent') }}
                    >
                      {opt.label}
                      {sortBy === opt.value && <span style={{ color: 'var(--teal)' }}>✓</span>}
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* View toggle */}
          <div className="glass-pill-group hidden md:flex">
            {(['simple', 'advanced'] as const).map(v => (
              <button key={v} onClick={() => setView(v)} className={`glass-pill-btn ${view === v ? 'active' : ''}`}>
                {v === 'simple' ? 'Cards' : 'Table'}
              </button>
            ))}
          </div>

          <button
            onClick={api.exportCsv}
            className="hidden sm:flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg transition-colors"
            style={{ background: 'var(--glass-dim)', color: 'var(--text-2)', border: '1px solid var(--border-subtle)' }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--glass-hover)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'var(--glass-dim)')}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export
          </button>
        </div>
      </div>

      {/* Unified filter bar */}
      <div className="flex flex-wrap items-center gap-2 mb-6 p-1.5 rounded-xl"
        style={{ background: 'var(--glass-subtle)', border: '1px solid var(--border-subtle)' }}>

        {/* Status filter pills */}
        <div className="flex items-center gap-1">
          {FILTER_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => { setFilter(opt.value); setPage(1) }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-150"
              style={filter === opt.value
                ? { background: 'var(--glass-active)', color: 'var(--text-heading)', boxShadow: '0 1px 0 var(--glass-dim) inset' }
                : { color: 'var(--text-3)' }}
              onMouseEnter={e => { if (filter !== opt.value) (e.currentTarget.style.color = 'var(--text-2)') }}
              onMouseLeave={e => { if (filter !== opt.value) (e.currentTarget.style.color = 'var(--text-3)') }}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* Separator */}
        <div className="w-px self-stretch mx-0.5" style={{ background: 'var(--border-subtle)' }} />

        {/* Date dropdown */}
        <div className="relative">
          {dateOpen && <div className="fixed inset-0 z-10" onClick={() => setDateOpen(false)} />}
          <button
            onClick={() => setDateOpen(o => !o)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-150"
            style={datePreset !== 'all'
              ? { background: 'var(--glass-active)', color: 'var(--text-heading)' }
              : { color: 'var(--text-3)' }}
            onMouseEnter={e => { if (datePreset === 'all') (e.currentTarget.style.color = 'var(--text-2)') }}
            onMouseLeave={e => { if (datePreset === 'all') (e.currentTarget.style.color = 'var(--text-3)') }}
          >
            <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            {DATE_PRESET_LABELS[datePreset]}
            <svg className="w-3 h-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          <AnimatePresence>
            {dateOpen && (
              <motion.div
                initial={{ opacity: 0, y: -6, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -6, scale: 0.97 }}
                transition={{ duration: 0.13 }}
                className="absolute top-full mt-1.5 left-0 z-20 rounded-xl overflow-hidden min-w-[160px] glass-dropdown"
              >
                {DATE_PRESET_OPTIONS.map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => { handleDatePreset(opt.value); setDateOpen(false) }}
                    className="w-full text-left px-4 py-2.5 text-sm transition-colors flex items-center justify-between gap-3"
                    style={datePreset === opt.value
                      ? { background: 'var(--glass-hover)', color: 'var(--text-heading)', fontWeight: 500 }
                      : { color: 'var(--text-2)' }}
                    onMouseEnter={e => { if (datePreset !== opt.value) (e.currentTarget.style.background = 'var(--glass-dim)') }}
                    onMouseLeave={e => { if (datePreset !== opt.value) (e.currentTarget.style.background = 'transparent') }}
                  >
                    {opt.label}
                    {datePreset === opt.value && <span style={{ color: 'var(--teal)' }}>✓</span>}
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Custom date pickers */}
        <AnimatePresence>
          {datePreset === 'custom' && (
            <motion.div key="custom-dates"
              initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }} transition={{ duration: 0.18, ease: 'easeOut' }}
              className="flex items-center gap-1.5"
            >
              <div className="w-px self-stretch" style={{ background: 'var(--border-subtle)' }} />
              <DatePicker value={dateFrom} onChange={v => { setDateFrom(v); setPage(1) }} placeholder="From" />
              <span className="text-xs" style={{ color: 'var(--text-ghost)' }}>→</span>
              <DatePicker value={dateTo} onChange={v => { setDateTo(v); setPage(1) }} placeholder="To" />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Active filter count badge */}
        {(filter !== '' || datePreset !== 'all') && (
          <button
            onClick={() => { setFilter(''); handleDatePreset('all'); }}
            className="ml-auto flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors"
            style={{ background: 'var(--glass-dim)', color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-body)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
            Clear filters
          </button>
        )}
      </div>

      {/* Content */}
      <div style={{ minHeight: '420px' }}
        className={`relative transition-opacity duration-150 ${loading ? 'opacity-40 pointer-events-none' : ''}`}>
        {loading && items.length === 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="glass-card h-36 animate-pulse" />
            ))}
          </div>
        )}
        {!loading && items.length === 0 && (
          <div className="text-center py-20">
            <p className="text-5xl mb-3 font-light" style={{ color: 'var(--text-dim)' }}>—</p>
            <p className="font-medium font-bricolage" style={{ color: 'var(--text-label)' }}>
              {datePreset !== 'all' || filter ? 'No candidates match this filter' : 'No candidates yet'}
            </p>
            <p className="text-sm mt-1" style={{ color: 'var(--text-faint)' }}>
              {datePreset !== 'all' || filter
                ? 'Try a different date range or recommendation filter'
                : 'Upload a CV to get started'}
            </p>
          </div>
        )}
        {items.length > 0 && (
          view === 'simple'
            ? <SimpleView items={items} onOpen={c => setQuickLook(c)} />
            : <AdvancedView items={items} onOpen={openDetail} />
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex gap-2 mt-6 justify-end">
          <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
            className="px-3 py-1.5 text-sm rounded-lg transition-colors disabled:opacity-30"
            style={{ border: '1px solid var(--border)', color: 'var(--text-2)' }}
            onMouseEnter={e => { if (page > 1) (e.currentTarget.style.background = 'var(--glass)') }}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
            ← Prev
          </button>
          <span className="px-3 py-1.5 text-sm font-jetbrains" style={{ color: 'var(--text-muted)' }}>
            {page} / {totalPages}
          </span>
          <button disabled={page === totalPages} onClick={() => setPage(p => p + 1)}
            className="px-3 py-1.5 text-sm rounded-lg transition-colors disabled:opacity-30"
            style={{ border: '1px solid var(--border)', color: 'var(--text-2)' }}
            onMouseEnter={e => { if (page < totalPages) (e.currentTarget.style.background = 'var(--glass)') }}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
            Next →
          </button>
        </div>
      )}

      <AnimatePresence>
        {quickLook && (
          <QuickLookModal
            candidate={quickLook}
            onClose={() => setQuickLook(null)}
            onOpenFull={() => { const id = quickLook.id; setQuickLook(null); openDetail(id) }}
          />
        )}
      </AnimatePresence>

      {selected && <DetailPanel candidate={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

// ─── Stat card ────────────────────────────────────────────────────────────────

const STAT_ACCENTS: Record<string, { dot: string; glow: string }> = {
  'Total CVs': { dot: 'var(--text-3)', glow: 'transparent' },
  'Invited':   { dot: 'var(--invite)', glow: 'transparent' },
  'Rejected':  { dot: 'var(--reject)', glow: 'transparent' },
}

function GlassStatCard({ label, value }: { label: string; value: number }) {
  const accent = STAT_ACCENTS[label] ?? { dot: 'var(--text-3)', glow: 'transparent' }
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 28 }}
      className="glass-card px-5 py-4 relative overflow-hidden"
      style={{ background: `linear-gradient(135deg, var(--glass) 60%, ${accent.glow})` }}
    >
      <p className="text-xs font-semibold uppercase tracking-wider mb-1.5 relative z-10" style={{ color: 'var(--text-muted)' }}>
        {label}
      </p>
      <p className="font-jetbrains text-3xl font-semibold tabular-nums relative z-10" style={{ color: 'var(--text-heading)' }}>
        <CountUp to={value} duration={1.2} />
      </p>
    </motion.div>
  )
}

// ─── Simple view — card grid ──────────────────────────────────────────────────

function SimpleView({ items, onOpen }: { items: CandidateRow[]; onOpen: (c: CandidateRow) => void }) {
  const { model } = useModel()
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {items.map((c, i) => {
        const rec  = (model === 'base' ? c.recommendation_base : c.recommendation) ?? c.recommendation
        const conf = model === 'base' ? c.confidence_base : c.confidence
        const inv = rec === 'Invite'
        const rej = rec === 'Reject'
        const barColor = inv ? 'var(--teal)' : rej ? 'var(--text-faint)' : 'var(--text-4)'
        return (
          <motion.div
            key={c.id}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04, type: 'spring', stiffness: 300, damping: 28 }}
          >
            <SpotlightCard
              spotlightColor="var(--glass)"
              className="glass-card cursor-pointer transition-all duration-200"
              onClick={() => onOpen(c)}
            >
              <div className="p-5">
                {/* Avatar + name */}
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full flex items-center justify-center shrink-0 text-sm font-bold font-jetbrains"
                    style={{ background: 'var(--glass-hover)', color: 'var(--text-body)' }}>
                    {initials(c.name)}
                  </div>
                  <div className="min-w-0">
                    <p className="font-semibold truncate" style={{ color: 'var(--text-bright)' }}>
                      {c.name ?? 'Unknown'}
                    </p>
                    <p className="text-xs font-medium truncate" style={{ color: 'var(--text-muted)' }}>
                      {c.target_role ?? <span style={{ color: 'var(--text-ghost)', fontWeight: 400 }}>No target role</span>}
                    </p>
                  </div>
                </div>

                {/* Recommendation + confidence */}
                <div className="flex items-center justify-between mb-2">
                  <div className="flex flex-col gap-0.5">
                    {c.hr_decision
                      ? <HROverrideBadge decision={c.hr_decision} />
                      : <RecommendationBadge value={rec as 'Invite' | 'Reject' | 'pending'} />
                    }
                    {c.hr_decision && (
                      <span className="text-[10px] pl-0.5" style={{ color: 'var(--text-faint)' }}>
                        AI: {rec}
                      </span>
                    )}
                  </div>
                  {conf !== null && (
                    <span className="text-sm font-semibold font-jetbrains tabular-nums"
                      style={{ color: 'var(--text-body)' }}>
                      {((conf ?? 0) * 100).toFixed(0)}%
                    </span>
                  )}
                </div>

                {/* Confidence bar */}
                {conf !== null && (
                  <div className="h-[3px] rounded-full overflow-hidden mb-3"
                    style={{ background: 'var(--glass)' }}>
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${((conf ?? 0) * 100).toFixed(0)}%` }}
                      transition={{ delay: i * 0.04 + 0.2, duration: 0.6, ease: 'easeOut' }}
                      className="h-full rounded-full"
                      style={{ background: barColor }}
                    />
                  </div>
                )}

                <p className="text-xs" style={{ color: 'var(--text-faint)' }}>
                  {new Date(c.processed_at).toLocaleDateString(undefined, {
                    day: 'numeric', month: 'short', year: 'numeric',
                  })}
                </p>
              </div>
            </SpotlightCard>
          </motion.div>
        )
      })}
    </div>
  )
}

// ─── Advanced view — table ────────────────────────────────────────────────────

function AdvancedView({ items, onOpen }: { items: CandidateRow[]; onOpen: (id: string) => void }) {
  const { model } = useModel()
  return (
    <div className="glass-card overflow-hidden overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead style={{ borderBottom: '1px solid var(--border-dim)' }}>
          <tr>
            {['Candidate', 'Outcome', 'RH Decision', 'Confidence', 'Parse quality', 'Format', 'Processed'].map(h => (
              <th key={h} className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider"
                style={{ color: 'var(--text-3)' }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((c, i) => {
            const rec  = (model === 'base' ? c.recommendation_base : c.recommendation) ?? c.recommendation
            const conf = model === 'base' ? c.confidence_base : c.confidence
            const inv = rec === 'Invite'
            const rej = rec === 'Reject'
            return (
              <motion.tr
                key={c.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.03 }}
                className="cursor-pointer transition-colors"
                style={{ borderBottom: '1px solid var(--glass-subtle)' }}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--glass-subtle)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                onClick={() => onOpen(c.id)}
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2.5">
                    <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold font-jetbrains shrink-0"
                      style={{ background: 'var(--glass-hover)', color: 'var(--text-body)' }}>
                      {initials(c.name)}
                    </div>
                    <div>
                      <p className="font-medium" style={{ color: 'var(--text-bright)' }}>{c.name ?? '—'}</p>
                      <p className="text-xs font-medium" style={{ color: 'var(--text-icon)' }}>{c.target_role ?? '—'}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3"><RecommendationBadge value={rec as 'Invite' | 'Reject' | 'pending'} /></td>
                <td className="px-4 py-3">
                  {c.hr_decision
                    ? <HROverrideBadge decision={c.hr_decision} />
                    : <span className="text-xs" style={{ color: 'var(--text-ghost)' }}>—</span>
                  }
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--glass-hover)' }}>
                      <div className="h-full rounded-full"
                        style={{
                          width: conf !== null ? `${((conf ?? 0) * 100).toFixed(0)}%` : '0%',
                          background: inv ? 'var(--teal)' : rej ? 'var(--text-ghost)' : 'var(--text-4)',
                        }} />
                    </div>
                    <span className="font-jetbrains text-xs" style={{ color: 'var(--text-body)' }}>
                      {conf !== null ? `${((conf ?? 0) * 100).toFixed(1)}%` : '—'}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3"><ParseQualityBadge value={c.parse_quality} /></td>
                <td className="px-4 py-3 font-jetbrains uppercase text-xs" style={{ color: 'var(--text-muted)' }}>{c.source_format}</td>
                <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-faint)' }}>
                  {new Date(c.processed_at).toLocaleString()}
                </td>
              </motion.tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ─── Quick-look modal ─────────────────────────────────────────────────────────

function QuickLookModal({ candidate, onClose, onOpenFull }: {
  candidate: CandidateRow; onClose: () => void; onOpenFull: () => void
}) {
  const { model } = useModel()
  const rec  = (model === 'base' ? candidate.recommendation_base : candidate.recommendation) ?? candidate.recommendation
  const conf = model === 'base' ? candidate.confidence_base : candidate.confidence
  const inv = rec === 'Invite'
  const rej = rec === 'Reject'
  const accentColor = inv ? 'var(--teal)' : rej ? 'var(--text-3)' : 'var(--text-muted)'

  return (
    <motion.div key="ql-backdrop"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'var(--backdrop-heavy)', backdropFilter: 'blur(6px)', WebkitBackdropFilter: 'blur(6px)' }}
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.90, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.90, y: 20 }}
        transition={{ type: 'spring', stiffness: 320, damping: 28 }}
        className="relative w-full max-w-sm rounded-3xl overflow-hidden"
        style={{
          background: 'var(--glass)',
          backdropFilter: 'blur(36px)',
          WebkitBackdropFilter: 'blur(36px)',
          border: '1px solid var(--glass-active)',
          borderTopColor: 'var(--border-top)',
          boxShadow: `0 0 60px ${inv ? 'var(--teal-subtle)' : 'transparent'}, var(--shadow-modal)`,
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Color tint */}
        <div className="absolute inset-0 pointer-events-none rounded-3xl"
          style={{ background: `radial-gradient(ellipse at 50% -15%, ${inv ? 'var(--teal-dim)' : 'transparent'} 0%, transparent 60%)` }} />

        <button onClick={onClose}
          className="absolute top-4 right-4 w-7 h-7 rounded-full flex items-center justify-center text-lg leading-none transition-colors z-20"
          style={{ color: 'var(--text-muted)', background: 'var(--glass-hover)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-bright)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}>
          ×
        </button>

        <div className="p-6 relative z-10">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-12 h-12 rounded-full flex items-center justify-center shrink-0 text-sm font-bold font-jetbrains"
              style={{ background: 'var(--glass-hover)', color: 'var(--text-body)' }}>
              {initials(candidate.name)}
            </div>
            <div className="min-w-0">
              <p className="font-bold text-base truncate" style={{ color: 'var(--text-heading)' }}>
                {candidate.name ?? 'Unknown'}
              </p>
              <p className="text-sm font-medium truncate" style={{ color: 'var(--text-label)' }}>
                {candidate.target_role ?? <span style={{ color: 'var(--text-faint)', fontWeight: 400 }}>No role</span>}
              </p>
            </div>
          </div>

          <div className="flex justify-center mb-5">
            <RecommendationBadge value={rec as 'Invite' | 'Reject' | 'pending'} large />
          </div>

          {conf !== null && (
            <div className="text-center mb-5">
              <p className="font-jetbrains text-4xl font-semibold tabular-nums" style={{ color: 'var(--text-heading)' }}>
                {((conf ?? 0) * 100).toFixed(0)}
                <span className="text-xl" style={{ color: 'var(--text-faint)' }}>%</span>
              </p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>model confidence</p>
              <div className="mt-3 h-1.5 rounded-full overflow-hidden mx-4"
                style={{ background: 'var(--glass)' }}>
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${((conf ?? 0) * 100).toFixed(0)}%` }}
                  transition={{ duration: 0.65, ease: 'easeOut' }}
                  className="h-full rounded-full"
                  style={{
                    background: inv ? 'var(--teal)' : rej ? 'var(--text-faint)' : 'var(--text-4)',
                  }}
                />
              </div>
            </div>
          )}

          {candidate.email && (
            <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl mb-4 min-w-0"
              style={{ background: 'var(--glass)', border: '1px solid var(--border-dim)' }}>
              <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="var(--text-muted)" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round"
                  d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
              </svg>
              <span className="text-sm truncate" style={{ color: 'var(--text-body)' }}>{candidate.email}</span>
            </div>
          )}

          <div className="flex items-center justify-between mb-5">
            <span className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Parse quality</span>
            <ParseQualityBadge value={candidate.parse_quality} />
          </div>

          <button onClick={onOpenFull}
            className="w-full py-2.5 rounded-2xl text-sm font-semibold flex items-center justify-center gap-2 transition-colors"
            style={{ background: 'var(--border)', color: 'var(--text-heading)', border: '1px solid var(--border-strong)' }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--glass-active)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'var(--border)')}>
            Full profile
            <span style={{ color: 'var(--text-icon)' }}>→</span>
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}

// ─── Detail side panel ────────────────────────────────────────────────────────

function DetailPanel({ candidate: initialCandidate, onClose }: { candidate: CandidateDetail; onClose: () => void }) {
  const [candidate, setCandidate] = useState(initialCandidate)
  const { model } = useModel()
  const [overrideOpen, setOverrideOpen] = useState(false)
  const [overrideDecision, setOverrideDecision] = useState<'Invite' | 'Reject'>(
    initialCandidate.hr_decision ?? 'Invite'
  )
  const [overrideReason, setOverrideReason] = useState(initialCandidate.override_reason ?? '')
  const [overrideLoading, setOverrideLoading] = useState(false)
  const [overrideError, setOverrideError] = useState<string | null>(null)

  async function handleOverride() {
    if (!overrideReason.trim()) { setOverrideError('A reason is required.'); return }
    setOverrideLoading(true); setOverrideError(null)
    try {
      await api.overrideDecision(candidate.id, { hr_decision: overrideDecision, override_reason: overrideReason.trim() })
      setCandidate(prev => ({
        ...prev,
        hr_decision: overrideDecision,
        override_reason: overrideReason.trim(),
        overridden_at: new Date().toISOString(),
      }))
      setOverrideOpen(false)
    } catch (e: unknown) {
      setOverrideError(e instanceof Error ? e.message : 'Override failed')
    } finally {
      setOverrideLoading(false)
    }
  }

  const cv = candidate.cv_data
  const f = deriveFeatures(cv)
  const activeRec  = (model === 'base' ? candidate.recommendation_base : candidate.recommendation) ?? candidate.recommendation
  const activeConf = model === 'base' ? candidate.confidence_base : candidate.confidence
  const activeExpl = model === 'base' ? candidate.explanation_base : candidate.explanation
  const inv = activeRec === 'Invite'
  const rej = activeRec === 'Reject'
  const statusColor = inv ? 'var(--teal)' : rej ? 'var(--text-muted)' : 'var(--text-faint)'

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex"
        style={{ background: 'var(--backdrop-overlay)', backdropFilter: 'blur(4px)', WebkitBackdropFilter: 'blur(4px)' }}
        onClick={onClose}
      >
        <motion.div
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          className="ml-auto w-full max-w-4xl h-full overflow-hidden flex flex-col"
          style={{
            background: 'var(--glass-panel)',
            backdropFilter: 'blur(40px)',
            WebkitBackdropFilter: 'blur(40px)',
            borderLeft: '1px solid var(--glass-hover)',
            borderTop: '1px solid var(--glass)',
            boxShadow: 'var(--shadow-side)',
          }}
          onClick={e => e.stopPropagation()}
        >
          {/* Header */}
          <div className="sticky top-0 px-6 py-4 flex items-center justify-between z-10 shrink-0"
            style={{
              background: 'transparent',
              borderBottom: '1px solid var(--border-subtle)',
            }}>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full flex items-center justify-center font-bold font-jetbrains"
                style={{ background: 'var(--glass-hover)', color: 'var(--text-body)' }}>
                {initials(cv.personal.full_name)}
              </div>
              <div>
                <h2 className="font-bricolage text-lg font-bold" style={{ color: 'var(--text-heading)' }}>
                  {cv.personal.full_name ?? 'Unknown candidate'}
                </h2>
                <p className="text-sm" style={{ color: 'var(--text-icon)' }}>
                  {cv.target_role ?? 'No target role specified'}
                </p>
              </div>
            </div>
            <button onClick={onClose}
              className="w-8 h-8 rounded-full flex items-center justify-center text-xl leading-none transition-colors"
              style={{ color: 'var(--text-muted)', background: 'var(--glass)' }}
              onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-bright)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}>
              ×
            </button>
          </div>

          {/* Body */}
          <div className="flex flex-col md:flex-row flex-1 overflow-hidden">

            {/* LEFT — CV content */}
            <ScrollArea className="flex-1">
              <div className="px-6 py-5 space-y-6">
                {/* Contact */}
                <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm" style={{ color: 'var(--text-2)' }}>
                  {cv.personal.email   && <span>✉ {cv.personal.email}</span>}
                  {cv.personal.phone   && <span>📞 {cv.personal.phone}</span>}
                  {cv.personal.address && <span>📍 {cv.personal.address}</span>}
                </div>

                {/* Parse warning */}
                {cv.parse_quality !== 'complete' && (
                  <div className="rounded-xl px-4 py-2.5 text-sm"
                    style={{ background: 'var(--glass-dim)', border: '1px solid var(--glass-hover)' }}>
                    <span className="font-semibold" style={{ color: 'var(--text-body)' }}>
                      {cv.parse_quality === 'partial' ? 'Partially parsed CV' : 'Poorly parsed CV — low reliability'}
                    </span>
                    {cv.missing_fields.length > 0 && (
                      <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                        Missing: {humanizeMissingFields(cv.missing_fields).join(' · ')}
                      </p>
                    )}
                  </div>
                )}

                {/* Summary */}
                {cv.summary && (
                  <CvSection title="Professional summary">
                    <p className="text-sm leading-relaxed" style={{ color: 'var(--text-body)' }}>{cv.summary}</p>
                  </CvSection>
                )}

                {/* Experience */}
                {cv.experience.length > 0 && (
                  <CvSection title={`Work experience — ${f.yearsExp} yr across ${f.numPositions} position${f.numPositions !== 1 ? 's' : ''}`}>
                    <div className="space-y-4">
                      {cv.experience.map((e, i) => (
                        <div key={i} className="pl-4" style={{ borderLeft: '2px solid var(--teal-border)' }}>
                          <div className="flex items-start justify-between gap-2">
                            <span className="font-semibold text-sm" style={{ color: 'var(--text-bright)' }}>
                              {e.title ?? 'Unknown role'}
                            </span>
                            {e.duration_months != null && (
                              <span className="shrink-0 text-xs px-2 py-0.5 rounded-full font-jetbrains"
                                style={{ background: 'var(--glass-hover)', color: 'var(--text-icon)' }}>
                                {formatDuration(e.duration_months)}
                              </span>
                            )}
                          </div>
                          {e.company && (
                            <p className="text-xs font-medium mt-0.5" style={{ color: 'var(--teal-bright)' }}>{e.company}</p>
                          )}
                          {(e.start || e.end) && (
                            <p className="text-xs mt-0.5" style={{ color: 'var(--text-faint)' }}>
                              {e.start ?? '?'} → {e.end ?? 'present'}
                            </p>
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
                          <span className="shrink-0 text-xs px-2 py-0.5 rounded-full mt-0.5"
                            style={{ background: 'var(--teal-subtle)', color: 'var(--teal)' }}>
                            {EDU_LABEL[e.level_score] ?? `Level ${e.level_score}`}
                          </span>
                          <div>
                            <p className="text-sm font-medium" style={{ color: 'var(--text-bright)' }}>
                              {e.degree}{e.field ? ` in ${e.field}` : ''}
                            </p>
                            {e.institution && (
                              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                                {e.institution}{e.year ? `, ${e.year}` : ''}
                              </p>
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
                        <SkillGroup label="Technical" tags={cv.skills.technical} color="var(--teal)" />
                      )}
                      {cv.skills.methods.length > 0 && (
                        <SkillGroup label="Methods & practices" tags={cv.skills.methods} color="var(--teal-bright)" />
                      )}
                      {cv.skills.management.length > 0 && (
                        <SkillGroup label="Management & soft skills" tags={cv.skills.management} color="var(--teal-bright)" />
                      )}
                    </div>
                  </CvSection>
                )}

                {/* Languages */}
                {cv.languages.length > 0 && (
                  <CvSection title="Languages">
                    <div className="flex flex-wrap gap-2">
                      {cv.languages.map((l, i) => (
                        <div key={i} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg"
                          style={{ background: 'var(--glass)', border: '1px solid var(--glass-hover)' }}>
                          <span className="text-sm font-medium" style={{ color: 'var(--text-bright)' }}>{l.language}</span>
                          {l.level && (
                            <span className="text-xs px-1.5 py-0.5 rounded"
                              style={{ background: 'var(--glass-hover)', color: 'var(--text-label)' }}>
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
                          <span style={{ color: 'var(--text-2)' }}>✓</span>
                          <span style={{ color: 'var(--text-body)' }}>{c.name}</span>
                          {c.year && (
                            <span className="text-xs font-jetbrains" style={{ color: 'var(--text-faint)' }}>
                              ({c.year})
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </CvSection>
                )}
              </div>
            </ScrollArea>

            {/* RIGHT — assessment panel */}
            <div className="w-full md:w-64 shrink-0 overflow-hidden flex flex-col"
              style={{ borderLeft: '1px solid var(--border-subtle)', background: 'var(--glass-subtle)' }}>
            <ScrollArea className="flex-1">
              <div className="px-5 py-5 space-y-5">

                {/* Decision card */}
                <div className="rounded-2xl p-4 text-center relative overflow-hidden"
                  style={{
                    background: 'var(--glass-dim)',
                    border: '1px solid var(--border)',
                    borderTopColor: 'var(--text-4)',
                  }}>
                  <div className="absolute inset-0 pointer-events-none rounded-2xl"
                    style={{ background: `radial-gradient(ellipse at 50% -10%, ${inv ? 'var(--teal-dim)' : 'transparent'} 0%, transparent 60%)` }} />
                  <p className="text-xs uppercase tracking-wider mb-3 relative z-10" style={{ color: 'var(--text-faint)' }}>
                    AI Recommendation
                  </p>
                  <div className="flex justify-center mb-3 relative z-10">
                    <RecommendationBadge value={activeRec as 'Invite' | 'Reject' | 'pending'} large />
                  </div>
                  {activeConf !== null && (
                    <>
                      <p className="font-jetbrains text-3xl font-semibold mt-3 tabular-nums relative z-10" style={{ color: 'var(--text-heading)' }}>
                        {((activeConf ?? 0) * 100).toFixed(0)}
                        <span className="text-lg" style={{ color: 'var(--text-faint)' }}>%</span>
                      </p>
                      <p className="text-xs mb-2 relative z-10" style={{ color: 'var(--text-faint)' }}>model confidence</p>
                      <div className="h-2 rounded-full overflow-hidden relative z-10" style={{ background: 'var(--glass-hover)' }}>
                        <div className="h-full rounded-full transition-all"
                          style={{
                            width: `${((activeConf ?? 0) * 100).toFixed(0)}%`,
                            background: inv ? 'var(--teal)' : rej ? 'var(--text-ghost)' : 'var(--text-4)',
                          }} />
                      </div>
                    </>
                  )}
                </div>

                {/* Scoring factors */}
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-faint)' }}>
                    What the model measured
                  </p>
                  <div className="space-y-3">
                    <ScoreFactor label="Years of experience" display={`${f.yearsExp} yr`} value={f.yearsExp} max={20} hint="Max reference: 20 yr" />
                    <ScoreFactor label="Positions held" display={`${f.numPositions}`} value={f.numPositions} max={6} hint="More positions = broader track record" />
                    <ScoreFactor label="Avg. time per role" display={formatDuration(f.avgTenureMonths)} value={f.avgTenureMonths} max={60} hint="Longer tenures indicate stability" />
                    <ScoreFactor label="Highest education" display={EDU_LABEL[f.eduScore] ?? '—'} value={f.eduScore} max={5} hint="From high school (1) to PhD (5)" />
                    <ScoreFactor label="Total skills" display={`${f.skillsCount}`} value={f.skillsCount} max={20} hint="Technical + methods + management" />
                    <ScoreFactor label="Certifications" display={f.hasCerts ? 'Yes' : 'None'} value={f.hasCerts ? 1 : 0} max={1} hint="Any professional certification" />
                    <ScoreFactor label="Languages" display={`${f.langCount}`} value={f.langCount} max={5} hint="Number of languages declared" />
                    <div className="pt-1">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium" style={{ color: 'var(--text-2)' }}>Profile completeness</span>
                        <span className="text-xs font-semibold font-jetbrains" style={{ color: 'var(--text-bright)' }}>
                          {f.completeness}/{f.totalSections}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {f.sectionFlags.map(({ label, ok }) => (
                          <span key={label} className="text-xs px-2 py-0.5 rounded-full font-medium"
                            style={ok
                              ? { background: 'var(--teal-subtle)', color: 'var(--teal)' }
                              : { background: 'var(--glass-dim)', color: 'var(--text-faint)', textDecoration: 'line-through' }}>
                            {label}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                {/* SHAP Explanation */}
                {activeExpl && (
                  <div className="pt-4" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                    <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-faint)' }}>
                      Why this decision
                    </p>
                    <div className="space-y-2">
                      {activeExpl.positive.map(c => (
                        <div key={c.feature}>
                          <div className="flex justify-between text-xs mb-0.5">
                            <span style={{ color: 'var(--teal)' }}>+ {c.label}</span>
                            <span className="font-jetbrains" style={{ color: 'var(--teal)' }}>+{c.contribution.toFixed(3)}</span>
                          </div>
                          <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--glass-hover)' }}>
                            <div className="h-full rounded-full" style={{ width: `${Math.min(100, Math.abs(c.contribution) * 400)}%`, background: 'var(--teal)' }} />
                          </div>
                        </div>
                      ))}
                      {activeExpl.negative.map(c => (
                        <div key={c.feature}>
                          <div className="flex justify-between text-xs mb-0.5">
                            <span style={{ color: 'var(--text-muted)' }}>− {c.label}</span>
                            <span className="font-jetbrains" style={{ color: 'var(--text-muted)' }}>{c.contribution.toFixed(3)}</span>
                          </div>
                          <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--glass-hover)' }}>
                            <div className="h-full rounded-full" style={{ width: `${Math.min(100, Math.abs(c.contribution) * 400)}%`, background: 'var(--text-ghost)' }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* HR Override */}
                <div className="pt-4" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                  <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-faint)' }}>
                    HR Decision
                  </p>
                  {candidate.hr_decision && !overrideOpen && (
                    <div className="mb-3 p-3 rounded-xl" style={{ background: 'var(--glass-dim)', border: '1px solid var(--border)' }}>
                      <div className="flex items-center gap-2 mb-1.5">
                        <RecommendationBadge value={candidate.hr_decision} />
                        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>overrides AI</span>
                      </div>
                      {candidate.override_reason && (
                        <p className="text-xs italic mb-1" style={{ color: 'var(--text-2)' }}>"{candidate.override_reason}"</p>
                      )}
                      {candidate.overridden_at && (
                        <p className="text-xs" style={{ color: 'var(--text-faint)' }}>
                          {new Date(candidate.overridden_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  )}
                  {!overrideOpen && (
                    <button onClick={() => {
                      setOverrideDecision(candidate.hr_decision ?? 'Invite')
                      setOverrideReason(candidate.override_reason ?? '')
                      setOverrideOpen(true)
                    }}
                      className="w-full py-2 rounded-xl text-xs font-semibold transition-colors"
                      style={{ background: 'var(--glass)', border: '1px solid var(--border)', color: 'var(--text-body)' }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'var(--glass-hover)')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'var(--glass)')}>
                      {candidate.hr_decision ? 'Change override' : 'Override decision'}
                    </button>
                  )}
                  {overrideOpen && (
                    <div className="space-y-3">
                      <div className="flex gap-2">
                        {(['Invite', 'Reject'] as const).map(d => (
                          <button key={d} onClick={() => setOverrideDecision(d)}
                            className="flex-1 py-1.5 rounded-lg text-xs font-semibold transition-colors"
                            style={overrideDecision === d
                              ? { background: d === 'Invite' ? 'var(--teal)' : 'var(--reject)', color: 'white' }
                              : { background: 'var(--glass)', color: 'var(--text-body)', border: '1px solid var(--border)' }}>
                            {d}
                          </button>
                        ))}
                      </div>
                      <textarea
                        value={overrideReason}
                        onChange={e => setOverrideReason(e.target.value)}
                        placeholder="Reason for override (required)"
                        rows={2}
                        className="w-full text-xs rounded-lg px-3 py-2 resize-none"
                        style={{ background: 'var(--glass)', border: '1px solid var(--border)', color: 'var(--text-body)', outline: 'none' }}
                      />
                      {overrideError && (
                        <p className="text-xs" style={{ color: 'var(--reject)' }}>{overrideError}</p>
                      )}
                      <div className="flex gap-2">
                        <button onClick={() => { setOverrideOpen(false); setOverrideError(null) }}
                          className="flex-1 py-1.5 rounded-lg text-xs font-medium"
                          style={{ background: 'var(--glass)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
                          Cancel
                        </button>
                        <button onClick={handleOverride} disabled={overrideLoading}
                          className="flex-1 py-1.5 rounded-lg text-xs font-semibold transition-opacity"
                          style={{ background: 'var(--teal)', color: 'white', opacity: overrideLoading ? 0.6 : 1 }}>
                          {overrideLoading ? 'Saving…' : 'Confirm'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* Meta */}
                <div className="space-y-1 pt-3 text-xs" style={{ borderTop: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                  <p><span className="font-medium" style={{ color: 'var(--text-label)' }}>File:</span>{' '}{candidate.source_filename}</p>
                  <p><span className="font-medium" style={{ color: 'var(--text-label)' }}>Format:</span>{' '}{candidate.source_format.toUpperCase()}</p>
                  <p><span className="font-medium" style={{ color: 'var(--text-label)' }}>Parsed:</span>{' '}{new Date(candidate.processed_at).toLocaleString()}</p>
                  <p className="flex items-center gap-1.5">
                    <span className="font-medium" style={{ color: 'var(--text-label)' }}>Quality:</span>
                    <ParseQualityBadge value={candidate.parse_quality} />
                  </p>
                </div>
              </div>
            </ScrollArea>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

// ─── Small reusable components ────────────────────────────────────────────────

function CvSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wider mb-2.5"
        style={{ color: 'var(--text-faint)' }}>
        {title}
      </h3>
      {children}
    </div>
  )
}

function SkillGroup({ label, tags, color }: { label: string; tags: string[]; color: string }) {
  return (
    <div>
      <p className="text-xs mb-1.5" style={{ color: 'var(--text-muted)' }}>{label}</p>
      <div className="flex flex-wrap gap-1">
        {tags.map(t => (
          <span key={t} className="px-2 py-0.5 rounded text-xs font-medium"
            style={{ background: `${color}12`, color }}>
            {t}
          </span>
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
        <span style={{ color: 'var(--text-2)' }}>{label}</span>
        <span className="font-semibold font-jetbrains" style={{ color: 'var(--text-body)' }}>{display}</span>
      </div>
      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--glass-hover)' }}>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: 'var(--teal)', boxShadow: '0 0 5px var(--teal-glow)' }} />
      </div>
    </div>
  )
}

function ParseQualityBadge({ value }: { value: string }) {
  const styles: Record<string, { bg: string; color: string }> = {
    complete: { bg: 'var(--teal-subtle)',  color: 'var(--teal)' },
    partial:  { bg: 'var(--glass-hover)', color: 'var(--text-2)' },
    poor:     { bg: 'var(--glass-dim)', color: 'var(--text-3)' },
  }
  const s = styles[value] ?? { bg: 'var(--glass-hover)', color: 'var(--text-label)' }
  return (
    <span className="px-2 py-0.5 rounded text-xs font-medium"
      style={{ background: s.bg, color: s.color }}>
      {value}
    </span>
  )
}


function HROverrideBadge({ decision }: { decision: 'Invite' | 'Reject' }) {
  const inv = decision === 'Invite'
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold tracking-wide"
      style={{
        background: inv ? 'var(--teal-subtle)' : 'var(--glass-dim)',
        color: inv ? 'var(--teal)' : 'var(--text-muted)',
        border: '1px solid var(--border-dim)',
      }}>
      <svg className="w-2.5 h-2.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
      </svg>
      {decision}
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
