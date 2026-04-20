import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { api } from '../api/client'
import type { UploadResult } from '../types/cv'
import BlurText from '../components/BlurText'
import CountUp from '../components/CountUp'

function ConfidenceArc({ value, color }: { value: number; color: string }) {
  const r = 40
  const circ = 2 * Math.PI * r
  return (
    <div className="relative flex items-center justify-center" style={{ width: 96, height: 96 }}>
      <svg width="96" height="96" style={{ transform: 'rotate(-90deg)', position: 'absolute' }}>
        <circle cx="48" cy="48" r={r} fill="none" stroke="var(--glass)" strokeWidth="5" />
        <motion.circle cx="48" cy="48" r={r} fill="none" stroke={color} strokeWidth="5" strokeLinecap="round"
          initial={{ strokeDasharray: circ, strokeDashoffset: circ }}
          animate={{ strokeDashoffset: circ * (1 - value / 100) }}
          transition={{ delay: 0.35, duration: 1.3, ease: 'easeOut' }}
          style={{ filter: `drop-shadow(0 0 6px ${color}80)` }}
        />
      </svg>
      <div className="relative z-10 text-center">
        <span className="font-jetbrains text-lg font-semibold" style={{ color: 'var(--text-heading)' }}>
          <CountUp to={value} duration={1.2} />
        </span>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>%</span>
      </div>
    </div>
  )
}

export default function UploadPage() {
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<UploadResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filename, setFilename] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = async (file: File) => {
    setLoading(true); setError(null); setResult(null); setFilename(file.name)
    try { setResult(await api.uploadCV(file)) }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Upload failed') }
    finally { setLoading(false) }
  }

  const reset = () => {
    setResult(null); setError(null); setFilename(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  const isInvite = result?.recommendation === 'Invite'
  const isReject = result?.recommendation === 'Reject'
  const resultColor = isInvite ? 'var(--teal)' : isReject ? 'var(--text-muted)' : 'var(--text-faint)'
  const resultGlowBg = isInvite ? 'var(--teal-dim)' : 'transparent'
  const resultBoxGlow = isInvite
    ? '0 0 60px var(--teal-subtle), var(--shadow-modal)'
    : 'var(--shadow-modal)'

  return (
    <div className="max-w-lg mx-auto">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 300, damping: 28 }}>
        <h1 className="font-bricolage text-3xl font-bold tracking-tight mb-1" style={{ color: 'var(--text-1)' }}>
          Upload CV
        </h1>
        <p className="text-sm mb-8" style={{ color: 'var(--text-muted)' }}>PDF, DOCX, or TXT — up to 5 MB</p>
      </motion.div>

      {/* Drop zone */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08, type: 'spring', stiffness: 280, damping: 26 }}
        className="relative rounded-3xl p-12 text-center cursor-pointer transition-all duration-300"
        style={{
          background: dragging ? 'var(--teal-dim)' : 'var(--glass-subtle)',
          backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
          border: dragging ? '1.5px dashed var(--teal-border)' : '1.5px dashed var(--glass-active)',
          boxShadow: dragging ? '0 0 40px var(--teal-subtle), inset 0 0 20px var(--teal-dim)' : 'none',
        }}
        onDragOver={e => { e.preventDefault(); if (!loading) setDragging(true) }}
        onDragLeave={() => setDragging(false)} onDrop={onDrop}
        onClick={() => { if (!loading) inputRef.current?.click() }}
      >
        <input ref={inputRef} type="file" className="hidden" accept=".pdf,.docx,.doc,.txt"
          onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }} />

        <AnimatePresence mode="wait">
          {loading ? (
            <motion.div key="loading" initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }} transition={{ type: 'spring', stiffness: 300, damping: 26 }}
              className="flex flex-col items-center gap-4">
              <div className="relative w-14 h-14">
                <div className="absolute inset-0 rounded-full" style={{ border: '2px solid var(--glass)' }} />
                <div className="absolute inset-0 rounded-full animate-spin"
                  style={{ border: '2px solid transparent', borderTopColor: 'var(--teal)', boxShadow: '0 0 18px var(--teal-glow)' }} />
              </div>
              <p className="text-sm" style={{ color: 'var(--text-2)' }}>AI is reading the CV…</p>
              {filename && (
                <span className="text-xs px-3 py-1 rounded-full font-jetbrains"
                  style={{ background: 'var(--glass-hover)', color: 'var(--text-muted)' }}>{filename}</span>
              )}
            </motion.div>
          ) : (
            <motion.div key="idle" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }} transition={{ type: 'spring', stiffness: 300, damping: 26 }}
              className="flex flex-col items-center gap-4">
              <motion.div animate={{ y: [0, -5, 0] }} transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                className="w-14 h-14 rounded-full flex items-center justify-center"
                style={{ background: 'var(--teal-dim)', boxShadow: '0 0 28px var(--teal-muted)' }}>
                <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="var(--teal)" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round"
                    d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                </svg>
              </motion.div>
              <div>
                <p className="text-sm font-medium" style={{ color: 'var(--text-body)' }}>Drop a file here</p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>or click to browse</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Error */}
      <AnimatePresence>
        {error && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="mt-4 p-4 rounded-2xl text-sm flex items-start gap-2"
            style={{ background: 'var(--reject-dim)', border: '1px solid var(--reject-border)', color: 'var(--reject)' }}>
            <span className="shrink-0 mt-0.5">✕</span>
            <span>{error}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Result */}
      <AnimatePresence>
        {result && (
          <motion.div initial={{ opacity: 0, y: 24, scale: 0.94 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -12, scale: 0.97 }} transition={{ type: 'spring', stiffness: 280, damping: 26 }}
            className="mt-6 rounded-3xl overflow-hidden relative"
            style={{ background: 'var(--glass)', backdropFilter: 'blur(28px)', WebkitBackdropFilter: 'blur(28px)',
              border: '1px solid var(--border)', borderTopColor: 'var(--border-top)', boxShadow: resultBoxGlow }}>
            <div className="absolute inset-0 pointer-events-none rounded-3xl"
              style={{ background: `radial-gradient(ellipse at 50% -10%, ${resultGlowBg} 0%, transparent 65%)` }} />

            <div className="px-6 pt-6 pb-5 relative z-10">
              <p className="text-xs font-medium uppercase tracking-widest mb-3" style={{ color: 'var(--text-faint)' }}>AI Recommendation</p>
              <div className="flex items-center justify-between">
                <div style={{ color: resultColor }}>
                  <BlurText text={result.recommendation} animateBy="letters" delay={60}
                    className="font-bricolage text-4xl font-bold tracking-tight" />
                </div>
                {result.confidence !== null && <ConfidenceArc value={Math.round(result.confidence * 100)} color={resultColor} />}
              </div>
            </div>

            <div className="px-6 py-4 space-y-3 relative z-10" style={{ borderTop: '1px solid var(--border-subtle)' }}>
              {result.name && (
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold font-jetbrains shrink-0"
                    style={{ background: isInvite ? 'var(--teal-muted)' : 'var(--glass-hover)', color: resultColor }}>
                    {result.name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase()}
                  </div>
                  <span className="font-semibold" style={{ color: 'var(--text-bright)' }}>{result.name}</span>
                </div>
              )}
              <div className="flex items-center gap-3 text-sm flex-wrap" style={{ color: 'var(--text-icon)' }}>
                <span>Parse quality:{' '}
                  <span className="font-medium" style={{
                    color: result.parse_quality === 'complete' ? 'var(--text-bright)' :
                           result.parse_quality === 'partial'  ? 'var(--text-2)' : 'var(--reject)' }}>
                    {result.parse_quality}
                  </span>
                </span>
                {filename && <span className="truncate max-w-[180px] font-jetbrains text-xs" style={{ color: 'var(--text-faint)' }}>{filename}</span>}
              </div>
              {result.missing_fields.length > 0 && (
                <p className="text-xs px-3 py-1.5 rounded-xl"
                  style={{ background: 'var(--gold-dim)', color: 'var(--gold-text)', border: '1px solid var(--gold-border)' }}>
                  Missing: {result.missing_fields.join(', ')}
                </p>
              )}
            </div>

            <div className="px-6 py-3.5 flex justify-end relative z-10" style={{ borderTop: '1px solid var(--glass)' }}>
              <button onClick={reset} className="text-xs transition-colors" style={{ color: 'var(--text-faint)' }}
                onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-body)')}
                onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-faint)')}>
                Upload another CV →
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
