import { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { api } from '../api/client'
import type { CandidateRow } from '../types/cv'
import CountUp from '../components/CountUp'
import RecommendationBadge from '../components/RecommendationBadge'

function pad(n: number) { return String(n).padStart(2, '0') }
function fmtUTC(d: Date) { return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}` }

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

  useEffect(() => {
    api.listCandidates({ page: 1, page_size: 100 })
      .then(res => { setItems(res.items); setTotal(res.total) })
      .finally(() => setLoading(false))
  }, [])

  const invited  = items.filter(c => c.recommendation === 'Invite').length
  const rejected = items.filter(c => c.recommendation === 'Reject').length
  const pending  = items.filter(c => c.recommendation === 'pending').length

  const confs   = items.filter(c => c.confidence !== null).map(c => c.confidence!)
  const avgConf = confs.length ? Math.round(confs.reduce((a, b) => a + b, 0) / confs.length * 100) : 0

  const complete    = items.filter(c => c.parse_quality === 'complete').length
  const inviteRate  = total > 0 ? Math.round((invited / total) * 100) : 0
  const parsedRate  = total > 0 ? Math.round((complete / total) * 100) : 0

  // 14-day trend
  const days = lastNDays(14)
  const byDay: Record<string, number> = {}
  items.forEach(c => { const d = c.processed_at.slice(0, 10); byDay[d] = (byDay[d] || 0) + 1 })
  const maxDay = Math.max(1, ...days.map(d => byDay[d] || 0))
  const today = fmtUTC(new Date())

  // Format breakdown
  const byFormat: Record<string, number> = {}
  items.forEach(c => {
    const f = (c.source_format ?? 'other').toUpperCase()
    byFormat[f] = (byFormat[f] || 0) + 1
  })

  const recent = items.slice(0, 6)

  const stats = [
    { label: 'Total screened',  value: total,       suffix: '',  color: 'text-gray-900'    },
    { label: 'Invite rate',     value: inviteRate,   suffix: '%', color: 'text-green-600'   },
    { label: 'Avg confidence',  value: avgConf,      suffix: '%', color: 'text-blue-600'    },
    { label: 'Fully parsed',    value: parsedRate,   suffix: '%', color: 'text-violet-600'  },
  ]

  const outcomes = [
    { label: 'Invite',  count: invited,  color: 'bg-green-400' },
    { label: 'Reject',  count: rejected, color: 'bg-red-400'   },
    { label: 'Pending', count: pending,  color: 'bg-gray-300'  },
  ].filter(o => o.count > 0)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-700 mt-0.5">Overview of all screened candidates</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s, i) => (
          <motion.div key={s.label}
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
            className="bg-white rounded-2xl border border-gray-200 p-5 shadow-sm"
          >
            <p className="text-xs font-medium text-gray-500 mb-1">{s.label}</p>
            <p className={`text-3xl font-bold tabular-nums ${s.color}`}>
              {loading ? '—' : <><CountUp to={s.value} duration={1} />{s.suffix}</>}
            </p>
          </motion.div>
        ))}
      </div>

      {/* Trend + breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* 14-day activity */}
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="lg:col-span-2 bg-white rounded-2xl border border-gray-200 p-5 shadow-sm"
        >
          <p className="text-sm font-semibold text-gray-900 mb-5">Activity — last 14 days</p>
          <div className="flex items-end gap-1.5" style={{ height: '96px' }}>
            {days.map(day => {
              const count  = byDay[day] || 0
              const isToday = day === today
              const heightPct = count === 0 ? 3 : Math.max(8, (count / maxDay) * 100)
              return (
                <div key={day} className="flex-1 flex flex-col items-center gap-1 group relative">
                  {count > 0 && (
                    <span className="absolute -top-5 left-1/2 -translate-x-1/2 text-xs font-semibold text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                      {count}
                    </span>
                  )}
                  <div className="w-full flex items-end" style={{ height: '88px' }}>
                    <motion.div
                      initial={{ height: 0 }} animate={{ height: `${heightPct}%` }}
                      transition={{ delay: 0.3 + days.indexOf(day) * 0.02, duration: 0.4, ease: 'easeOut' }}
                      className={`w-full rounded-t-md ${count === 0 ? 'bg-gray-100' : isToday ? 'bg-blue-400' : 'bg-blue-200'}`}
                    />
                  </div>
                </div>
              )
            })}
          </div>
          <div className="flex justify-between mt-1 text-xs text-gray-400">
            <span>{new Date(days[0] + 'T00:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span>
            <span>Today</span>
          </div>
        </motion.div>

        {/* Outcome split + formats */}
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-white rounded-2xl border border-gray-200 p-5 shadow-sm space-y-5"
        >
          <div>
            <p className="text-sm font-semibold text-gray-900 mb-3">Outcome split</p>
            {total > 0 ? (
              <>
                <div className="flex h-2.5 rounded-full overflow-hidden mb-3 bg-gray-100">
                  {outcomes.map(o => (
                    <motion.div key={o.label}
                      initial={{ width: 0 }}
                      animate={{ width: `${(o.count / total) * 100}%` }}
                      transition={{ delay: 0.4, duration: 0.6, ease: 'easeOut' }}
                      className={o.color}
                    />
                  ))}
                </div>
                <div className="space-y-2">
                  {outcomes.map(o => (
                    <div key={o.label} className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-1.5">
                        <div className={`w-2 h-2 rounded-full ${o.color}`} />
                        <span className="text-gray-600">{o.label}</span>
                      </div>
                      <span className="font-semibold text-gray-900">
                        {o.count} <span className="text-gray-400 font-normal">({Math.round(o.count / total * 100)}%)</span>
                      </span>
                    </div>
                  ))}
                </div>
              </>
            ) : <p className="text-xs text-gray-400">No data yet</p>}
          </div>

          <div className="border-t border-gray-100 pt-4">
            <p className="text-sm font-semibold text-gray-900 mb-3">File formats</p>
            <div className="space-y-2">
              {Object.entries(byFormat).sort((a, b) => b[1] - a[1]).map(([fmt, count]) => (
                <div key={fmt} className="flex items-center justify-between text-xs">
                  <span className="text-gray-500 font-medium">{fmt}</span>
                  <span className="font-semibold text-gray-900">{count}</span>
                </div>
              ))}
              {Object.keys(byFormat).length === 0 && <p className="text-xs text-gray-400">No data yet</p>}
            </div>
          </div>
        </motion.div>
      </div>

      {/* Recent uploads */}
      <motion.div
        initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
        className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden"
      >
        <div className="px-5 py-4 border-b border-gray-100">
          <p className="text-sm font-semibold text-gray-900">Recent uploads</p>
        </div>
        <div className="divide-y divide-gray-50">
          {recent.map(c => (
            <div key={c.id} className="px-5 py-3 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-7 h-7 rounded-full bg-blue-100 text-blue-700 font-bold text-xs flex items-center justify-center shrink-0">
                  {(c.name ?? '').split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase() || '?'}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">{c.name ?? 'Unknown'}</p>
                  <p className="text-xs text-gray-400 truncate">{c.target_role ?? '—'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <RecommendationBadge value={c.recommendation} />
                <span className="text-xs text-gray-400 hidden sm:block">
                  {new Date(c.processed_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}
                </span>
              </div>
            </div>
          ))}
          {recent.length === 0 && !loading && (
            <p className="px-5 py-10 text-center text-sm text-gray-400">No candidates yet — upload a CV to get started</p>
          )}
        </div>
      </motion.div>
    </div>
  )
}
