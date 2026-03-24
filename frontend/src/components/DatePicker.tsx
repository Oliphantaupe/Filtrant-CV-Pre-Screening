import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'motion/react'

interface DatePickerProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
}

const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December']
const DAYS = ['Mo','Tu','We','Th','Fr','Sa','Su']

import { pad } from '../utils/date'

function toISO(y: number, m: number, d: number) { return `${y}-${pad(m + 1)}-${pad(d)}` }
function todayISO() {
  const n = new Date()
  return toISO(n.getUTCFullYear(), n.getUTCMonth(), n.getUTCDate())
}

export default function DatePicker({ value, onChange, placeholder = 'Pick a date' }: DatePickerProps) {
  const [open, setOpen] = useState(false)
  const [view, setView] = useState<{ year: number; month: number }>(() => {
    if (value) {
      const [y, m] = value.split('-').map(Number)
      return { year: y, month: m - 1 }
    }
    const n = new Date()
    return { year: n.getUTCFullYear(), month: n.getUTCMonth() }
  })

  useEffect(() => {
    if (value) {
      const [y, m] = value.split('-').map(Number)
      setView({ year: y, month: m - 1 })
    }
  }, [value])

  const { year, month } = view
  const firstDayOfWeek = (new Date(year, month, 1).getDay() + 6) % 7 // 0 = Monday
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const today = todayISO()

  const cells: (number | null)[] = [
    ...Array(firstDayOfWeek).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]

  const label = value
    ? new Date(value + 'T00:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
    : placeholder

  return (
    <div className="relative">
      {open && <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />}

      <button
        onClick={() => setOpen(o => !o)}
        className={`px-3 py-1 rounded-lg text-sm font-medium transition-all duration-150 whitespace-nowrap ${
          value ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
        }`}
      >
        {label}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ duration: 0.12 }}
            className="absolute top-full mt-1 z-20 bg-white rounded-2xl border border-gray-200 shadow-xl p-4 w-64"
          >
            {/* Month nav */}
            <div className="flex items-center justify-between mb-3">
              <button
                onClick={() => setView(v => {
                  const d = new Date(v.year, v.month - 1, 1)
                  return { year: d.getFullYear(), month: d.getMonth() }
                })}
                className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors text-base"
              >‹</button>
              <span className="text-sm font-semibold text-gray-900">{MONTHS[month]} {year}</span>
              <button
                onClick={() => setView(v => {
                  const d = new Date(v.year, v.month + 1, 1)
                  return { year: d.getFullYear(), month: d.getMonth() }
                })}
                className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors text-base"
              >›</button>
            </div>

            {/* Day headers */}
            <div className="grid grid-cols-7 mb-1">
              {DAYS.map(d => (
                <div key={d} className="text-center text-xs font-medium text-gray-400 py-1">{d}</div>
              ))}
            </div>

            {/* Day cells */}
            <div className="grid grid-cols-7 gap-0.5">
              {cells.map((day, i) => {
                if (!day) return <div key={i} />
                const iso = toISO(year, month, day)
                const isSelected = iso === value
                const isToday = iso === today
                return (
                  <button
                    key={i}
                    onClick={() => { onChange(iso); setOpen(false) }}
                    className={`w-full aspect-square rounded-lg text-xs flex items-center justify-center transition-colors font-medium ${
                      isSelected
                        ? 'bg-blue-500 text-white'
                        : isToday
                        ? 'bg-blue-50 text-blue-600'
                        : 'text-gray-700 hover:bg-gray-100'
                    }`}
                  >
                    {day}
                  </button>
                )
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}