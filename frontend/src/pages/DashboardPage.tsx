import { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { api } from '../api/client'
import type { CandidateRow } from '../types/cv'
import CountUp from '../components/CountUp'
import RecommendationBadge from '../components/RecommendationBadge'
import { fmtUTC } from '../utils/date'

interface ByGroupRaw { selection_rate: Record<string, number>; tpr: Record<string, number> }
interface AttributeMetricsRaw {
  equal_opportunity_diff: number
  demographic_parity_diff: number
  by_group: ByGroupRaw
}
interface FairnessReportRaw {
  model: string
  auc: number
  baseline: { auc: number; metrics: Record<string, AttributeMetricsRaw> }
  fair: { auc: number; metrics: Record<string, AttributeMetricsRaw> }
}
interface GroupMetric { selection_rate: number; tpr: number }
interface AttributeMetrics {
  eod: number
  dp_diff: number
  by_group: Record<string, GroupMetric>
}
interface FairnessMetrics {
  model_name: string
  fairness_mitigated: boolean
  auc: number
  baseline_auc: number
  metrics: Record<string, AttributeMetrics>
}

function parseFairnessReport(raw: FairnessReportRaw): FairnessMetrics {
  const metrics: Record<string, AttributeMetrics> = {}
  const src = raw.fair?.metrics ?? {}
  for (const [attr, m] of Object.entries(src)) {
    const byGroup: Record<string, GroupMetric> = {}
    for (const grp of Object.keys(m.by_group.selection_rate ?? {})) {
      byGroup[grp] = {
        selection_rate: m.by_group.selection_rate[grp] ?? 0,
        tpr: m.by_group.tpr?.[grp] ?? 0,
      }
    }
    metrics[attr] = {
      eod: m.equal_opportunity_diff ?? 0,
      dp_diff: m.demographic_parity_diff ?? 0,
      by_group: byGroup,
    }
  }
  return {
    model_name: raw.model ?? 'Unknown',
    fairness_mitigated: true,
    auc: raw.fair?.auc ?? 0,
    baseline_auc: raw.baseline?.auc ?? 0,
    metrics,
  }
}


function lastNDays(n: number): string[] {
  const days: string[] = []
  const now = new Date()
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(now)
    d.setUTCDate(now.getUTCDate() - i)
    days.push(fmtUTC(d))
  }
  return days
}

export default function DashboardPage() {
  const [items, setItems] = useState<CandidateRow[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [fairness, setFairness] = useState<FairnessMetrics | null>(null)

  useEffect(() => {
    api.listCandidates({ page: 1, page_size: 100 })
      .then(res => { setItems(res.items); setTotal(res.total) })
      .finally(() => setLoading(false))
    api.getFairnessMetrics()
      .then(data => setFairness(parseFairnessReport(data as unknown as FairnessReportRaw)))
      .catch(() => {})
  }, [])

  const invited  = items.filter(c => c.recommendation === 'Invite').length
  const rejected = items.filter(c => c.recommendation === 'Reject').length
  const pending  = items.filter(c => c.recommendation === 'pending').length

  const confs    = items.filter(c => c.confidence !== null).map(c => c.confidence!)
  const avgConf  = confs.length ? Math.round(confs.reduce((a, b) => a + b, 0) / confs.length * 100) : 0

  const complete   = items.filter(c => c.parse_quality === 'complete').length
  const inviteRate = total > 0 ? Math.round((invited / total) * 100) : 0
  const parsedRate = total > 0 ? Math.round((complete / total) * 100) : 0

  const days = lastNDays(14)
  const byDay: Record<string, number> = {}
  items.forEach(c => { const d = c.processed_at.slice(0, 10); byDay[d] = (byDay[d] || 0) + 1 })
  const maxDay = Math.max(1, ...days.map(d => byDay[d] || 0))
  const today = fmtUTC(new Date())

  const byFormat: Record<string, number> = {}
  items.forEach(c => {
    const f = (c.source_format ?? 'other').toUpperCase()
    byFormat[f] = (byFormat[f] || 0) + 1
  })

  const recent = items.slice(0, 6)

  const stats = [
    { label: 'Total screened', value: total,      suffix: '',  accent: 'var(--accent)' },
    { label: 'Invite rate',    value: inviteRate,  suffix: '%', accent: 'var(--invite)' },
    { label: 'Avg confidence', value: avgConf,     suffix: '%', accent: 'var(--accent)' },
    { label: 'Fully parsed',   value: parsedRate,  suffix: '%', accent: 'var(--purple)' },
  ]

  const outcomes = [
    { label: 'Invite',  count: invited,  color: 'var(--teal)', glow: 'var(--teal-glow)' },
    { label: 'Reject',  count: rejected, color: 'var(--text-ghost)', glow: 'transparent' },
    { label: 'Pending', count: pending,  color: 'var(--text-dim)', glow: 'transparent' },
  ].filter(o => o.count > 0)

  return (
    <div className="space-y-5">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 300, damping: 28 }}>
        <h1 className="font-bricolage text-3xl font-bold tracking-tight" style={{ color: 'var(--text-1)' }}>Dashboard</h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>Overview of all screened candidates</p>
      </motion.div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s, i) => (
          <motion.div key={s.label} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.07, type: 'spring', stiffness: 300, damping: 28 }}
            className="glass-card p-5 relative overflow-hidden">
            <p className="text-xs font-medium uppercase tracking-wider mb-2 relative z-10" style={{ color: 'var(--text-muted)' }}>{s.label}</p>
            <p className="font-jetbrains text-3xl font-semibold tabular-nums relative z-10" style={{ color: 'var(--text-heading)' }}>
              {loading ? '—' : <><CountUp to={s.value} duration={1} />{s.suffix}</>}
            </p>
          </motion.div>
        ))}
      </div>

      {/* Trend + breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* 14-day activity */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.28, type: 'spring', stiffness: 280, damping: 28 }}
          className="glass-card lg:col-span-2 p-5">
          <p className="font-bricolage text-sm font-semibold mb-5" style={{ color: 'var(--text-body)' }}>Activity — last 14 days</p>
          <div className="flex items-end gap-1.5" style={{ height: '96px' }}>
            {days.map((day, idx) => {
              const count   = byDay[day] || 0
              const isToday = day === today
              const heightPct = count === 0 ? 3 : Math.max(8, (count / maxDay) * 100)
              return (
                <div key={day} className="flex-1 flex flex-col items-center group relative">
                  {count > 0 && (
                    <span className="absolute -top-5 left-1/2 -translate-x-1/2 text-xs font-jetbrains font-medium opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap"
                      style={{ color: 'var(--text-2)' }}>{count}</span>
                  )}
                  <div className="w-full flex items-end" style={{ height: '88px' }}>
                    <motion.div initial={{ height: 0 }} animate={{ height: `${heightPct}%` }}
                      transition={{ delay: 0.3 + idx * 0.02, duration: 0.5, ease: 'easeOut' }}
                      className="w-full rounded-t-md relative overflow-hidden"
                      style={{
                        background: count === 0
                          ? 'var(--glass-subtle)'
                          : isToday
                          ? 'linear-gradient(to top, var(--teal-muted), var(--teal-bright))'
                          : 'linear-gradient(to top, var(--teal-dim), var(--teal-muted))',
                        boxShadow: isToday && count > 0 ? '0 -3px 10px var(--teal-glow)' : 'none',
                      }}>
                      {count > 0 && (
                        <div className="absolute top-0 left-0 right-0 h-px rounded-full"
                          style={{ background: isToday ? 'var(--teal)' : 'var(--teal-border)' }} />
                      )}
                    </motion.div>
                  </div>
                </div>
              )
            })}
          </div>
          <div className="flex justify-between mt-2 text-xs" style={{ color: 'var(--text-faint)' }}>
            <span>{new Date(days[0] + 'T00:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span>
            <span>Today</span>
          </div>
        </motion.div>

        {/* Outcome split + formats */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.33, type: 'spring', stiffness: 280, damping: 28 }}
          className="glass-card p-5 space-y-5">
          <div>
            <p className="font-bricolage text-sm font-semibold mb-3" style={{ color: 'var(--text-body)' }}>Outcome split</p>
            {total > 0 ? (
              <>
                <div className="flex h-2 rounded-full overflow-hidden mb-3 gap-px" style={{ background: 'var(--glass-dim)' }}>
                  {outcomes.map(o => (
                    <motion.div key={o.label} initial={{ width: 0 }}
                      animate={{ width: `${(o.count / total) * 100}%` }}
                      transition={{ delay: 0.45, duration: 0.7, ease: 'easeOut' }}
                      className="rounded-full" style={{ background: o.color, boxShadow: `0 0 6px ${o.glow}` }} />
                  ))}
                </div>
                <div className="space-y-2">
                  {outcomes.map(o => (
                    <div key={o.label} className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full" style={{ background: o.color }} />
                        <span style={{ color: 'var(--text-label)' }}>{o.label}</span>
                      </div>
                      <span className="font-jetbrains font-medium" style={{ color: 'var(--text-body)' }}>
                        {o.count}{' '}<span style={{ color: 'var(--text-faint)' }}>({Math.round(o.count / total * 100)}%)</span>
                      </span>
                    </div>
                  ))}
                </div>
              </>
            ) : <p className="text-xs" style={{ color: 'var(--text-ghost)' }}>No data yet</p>}
          </div>

          <div className="pt-4" style={{ borderTop: '1px solid var(--border-subtle)' }}>
            <p className="font-bricolage text-sm font-semibold mb-3" style={{ color: 'var(--text-body)' }}>File formats</p>
            <div className="space-y-2">
              {Object.entries(byFormat).sort((a, b) => b[1] - a[1]).map(([fmt, count]) => (
                <div key={fmt} className="flex items-center justify-between text-xs">
                  <span className="font-medium tracking-widest" style={{ color: 'var(--text-muted)' }}>{fmt}</span>
                  <span className="font-jetbrains font-medium" style={{ color: 'var(--text-body)' }}>{count}</span>
                </div>
              ))}
              {Object.keys(byFormat).length === 0 && (
                <p className="text-xs" style={{ color: 'var(--text-ghost)' }}>No data yet</p>
              )}
            </div>
          </div>
        </motion.div>
      </div>

      {/* Fairness metrics */}
      {fairness && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.36, type: 'spring', stiffness: 280, damping: 28 }}
          className="glass-card overflow-hidden">

          {/* Header */}
          <div className="px-5 py-4 flex items-center justify-between"
            style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <div>
              <div className="flex items-center gap-2 mb-0.5">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="var(--teal)" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1M4.22 4.22l.7.7m13.86 13.86.7.7M1 12h1m20 0h1M4.22 19.78l.7-.7M18.64 5.36l.7-.7" />
                  <circle cx="12" cy="12" r="4" />
                </svg>
                <p className="font-bricolage text-sm font-semibold" style={{ color: 'var(--text-body)' }}>
                  Fairness Audit
                </p>
                <span className="text-xs font-medium px-1.5 py-0.5 rounded" style={{ background: 'var(--glass-hover)', color: 'var(--text-muted)' }}>
                  {fairness.model_name}
                </span>
              </div>
              <p className="text-xs" style={{ color: 'var(--text-faint)' }}>
                Equal Opportunity &amp; Demographic Parity by protected attribute
              </p>
            </div>
            <div className="flex items-center gap-3">
              {/* AUC comparison */}
              <div className="hidden sm:flex items-center gap-2 text-xs">
                <span style={{ color: 'var(--text-faint)' }}>Baseline</span>
                <span className="font-jetbrains font-semibold" style={{ color: 'var(--text-muted)' }}>
                  {fairness.baseline_auc.toFixed(3)}
                </span>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="var(--text-faint)" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                </svg>
                <span className="font-jetbrains font-semibold" style={{ color: 'var(--teal)' }}>
                  {fairness.auc.toFixed(3)}
                </span>
                <span style={{ color: 'var(--text-faint)' }}>Fair AUC</span>
              </div>
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full flex items-center gap-1.5"
                style={{
                  background: 'var(--teal-dim)',
                  color: 'var(--teal)',
                  border: '1px solid var(--teal-border)',
                }}>
                <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: 'var(--teal)' }} />
                Fair Model v2
              </span>
            </div>
          </div>

          {/* Attribute cards */}
          <div className="p-5 grid grid-cols-1 sm:grid-cols-3 gap-4">
            {Object.entries(fairness.metrics).map(([attr, m]) => {
              const eodBad = Math.abs(m.eod) > 0.1
              const dpBad  = Math.abs(m.dp_diff) > 0.1
              const attrLabel: Record<string, string> = {
                gender: 'Gender',
                age_cohort: 'Age cohort',
                is_multilingual: 'Multilingual',
              }
              return (
                <div key={attr} className="rounded-2xl overflow-hidden"
                  style={{ background: 'var(--glass-subtle)', border: '1px solid var(--border-subtle)' }}>

                  {/* Attribute header */}
                  <div className="px-4 py-2.5 flex items-center justify-between"
                    style={{ borderBottom: '1px solid var(--border-subtle)', background: 'var(--glass-dim)' }}>
                    <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                      {attrLabel[attr] ?? attr.replace(/_/g, ' ')}
                    </p>
                    <div className="flex items-center gap-1">
                      {(eodBad || dpBad) && (
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="var(--reject)" strokeWidth={2.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                        </svg>
                      )}
                      <span className="text-xs" style={{ color: (eodBad || dpBad) ? 'var(--reject)' : 'var(--teal)' }}>
                        {(eodBad || dpBad) ? 'Review' : 'OK'}
                      </span>
                    </div>
                  </div>

                  <div className="p-4 space-y-4">
                    {/* EOD + DP scores */}
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        { label: 'EOD', value: m.eod, bad: eodBad },
                        { label: 'DP diff', value: m.dp_diff, bad: dpBad },
                      ].map(({ label, value, bad }) => (
                        <div key={label} className="rounded-xl p-3 text-center"
                          style={{
                            background: bad ? 'rgba(239,68,68,0.06)' : 'var(--teal-dim)',
                            border: `1px solid ${bad ? 'rgba(239,68,68,0.2)' : 'var(--teal-border)'}`,
                          }}>
                          <p className="font-jetbrains text-xl font-bold leading-none mb-1"
                            style={{ color: bad ? 'var(--reject)' : 'var(--teal)' }}>
                            {Math.abs(value).toFixed(2)}
                          </p>
                          <p className="text-xs font-medium" style={{ color: bad ? 'var(--reject)' : 'var(--teal)', opacity: 0.7 }}>
                            {label}
                          </p>
                        </div>
                      ))}
                    </div>

                    {/* Per-group bars */}
                    <div className="space-y-2.5">
                      {Object.entries(m.by_group).map(([grp, g]) => (
                        <div key={grp}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium" style={{ color: 'var(--text-label)' }}>{grp}</span>
                            <span className="text-xs font-jetbrains" style={{ color: 'var(--text-faint)' }}>
                              {(g.selection_rate * 100).toFixed(0)}% sel · {(g.tpr * 100).toFixed(0)}% tpr
                            </span>
                          </div>
                          <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--glass-active)' }}>
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${Math.min(100, g.selection_rate * 100)}%` }}
                              transition={{ duration: 0.6, ease: 'easeOut' }}
                              className="h-full rounded-full"
                              style={{ background: 'linear-gradient(to right, var(--teal-muted), var(--teal))' }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Footer legend */}
          <div className="px-5 pb-4 flex flex-wrap gap-x-5 gap-y-1">
            {[
              { dot: 'var(--teal)', text: 'EOD ≤ 0.10 — acceptable gap' },
              { dot: 'var(--reject)', text: 'EOD / DP > 0.10 — warrants review' },
              { dot: 'var(--text-faint)', text: 'sel = selection rate · tpr = true positive rate' },
            ].map(({ dot, text }) => (
              <div key={text} className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--text-faint)' }}>
                <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: dot }} />
                {text}
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Recent uploads */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.38, type: 'spring', stiffness: 280, damping: 28 }}
        className="glass-card overflow-hidden">
        <div className="px-5 py-4" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
          <p className="font-bricolage text-sm font-semibold" style={{ color: 'var(--text-body)' }}>Recent uploads</p>
        </div>
        <div>
          {recent.map(c => (
            <div key={c.id} className="px-5 py-3 flex items-center justify-between gap-4 transition-colors"
              style={{ borderBottom: '1px solid var(--glass-subtle)' }}
              onMouseEnter={e => (e.currentTarget.style.background = 'var(--glass-subtle)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-bold font-jetbrains"
                  style={{ background: 'var(--glass-hover)', color: 'var(--text-body)' }}>
                  {(c.name ?? '').split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase() || '?'}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate" style={{ color: 'var(--text-bright)' }}>{c.name ?? 'Unknown'}</p>
                  <p className="text-xs truncate" style={{ color: 'var(--text-3)' }}>{c.target_role ?? '—'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <RecommendationBadge value={c.recommendation} />
                <span className="text-xs hidden sm:block" style={{ color: 'var(--text-faint)' }}>
                  {new Date(c.processed_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}
                </span>
              </div>
            </div>
          ))}
          {recent.length === 0 && !loading && (
            <p className="px-5 py-12 text-center text-sm" style={{ color: 'var(--text-faint)' }}>
              No candidates yet — upload a CV to get started
            </p>
          )}
        </div>
      </motion.div>

    </div>
  )
}
