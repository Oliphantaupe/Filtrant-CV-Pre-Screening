import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { api } from '../api/client'
import type { UploadResult } from '../types/cv'
import BlurText from '../components/BlurText'
import CountUp from '../components/CountUp'

export default function UploadPage() {
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<UploadResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filename, setFilename] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = async (file: File) => {
    setLoading(true)
    setError(null)
    setResult(null)
    setFilename(file.name)
    try {
      const res = await api.uploadCV(file)
      setResult(res)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  const reset = () => {
    setResult(null)
    setError(null)
    setFilename(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  const isInvite = result?.recommendation === 'Invite'
  const isReject = result?.recommendation === 'Reject'

  return (
    <div className="max-w-lg mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Upload CV</h1>
      <p className="text-sm text-gray-700 mb-6">PDF, DOCX, or TXT — up to 5 MB</p>

      {/* Drop zone */}
      <div
        className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all duration-200 ${
          dragging
            ? 'border-blue-400 bg-blue-50 scale-[1.01]'
            : loading
            ? 'border-gray-200 bg-white/80 cursor-default'
            : 'border-gray-300 bg-white/90 hover:border-blue-300 hover:bg-white'
        }`}
        onDragOver={e => { e.preventDefault(); if (!loading) setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => { if (!loading) inputRef.current?.click() }}
      >
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept=".pdf,.docx,.doc,.txt"
          onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
        />

        <AnimatePresence mode="wait">
          {loading ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="flex flex-col items-center gap-3"
            >
              <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-gray-500">Claude is reading the CV…</p>
              {filename && (
                <span className="text-xs bg-gray-100 text-gray-500 px-3 py-1 rounded-full">{filename}</span>
              )}
            </motion.div>
          ) : (
            <motion.div
              key="idle"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="flex flex-col items-center gap-3"
            >
              <div className="w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center">
                <svg className="w-6 h-6 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-700">Drop a file here</p>
                <p className="text-xs text-gray-400 mt-0.5">or click to browse</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Error */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-4 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-start gap-2"
          >
            <span className="shrink-0 mt-0.5">✕</span>
            <span>{error}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Result */}
      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ type: 'spring', stiffness: 300, damping: 28 }}
            className={`mt-6 rounded-2xl border overflow-hidden shadow-sm ${
              isInvite ? 'border-green-200 bg-white' : isReject ? 'border-red-200 bg-white' : 'border-gray-200 bg-white'
            }`}
          >
            {/* Verdict header */}
            <div className={`px-6 py-5 ${isInvite ? 'bg-green-50' : isReject ? 'bg-red-50' : 'bg-gray-50'}`}>
              <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">AI Recommendation</p>
              <div className="flex items-end justify-between">
                <BlurText
                  text={result.recommendation}
                  animateBy="letters"
                  delay={60}
                  className={`text-3xl font-black tracking-tight ${
                    isInvite ? 'text-green-700' : isReject ? 'text-red-700' : 'text-gray-600'
                  }`}
                />
                {result.confidence !== null && (
                  <span className="text-2xl font-bold text-gray-700 tabular-nums">
                    <CountUp to={Math.round(result.confidence * 100)} duration={1.2} />
                    <span className="text-base font-normal text-gray-400">%</span>
                  </span>
                )}
              </div>
              {result.confidence !== null && (
                <div className="mt-3 h-1.5 bg-white/60 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${(result.confidence * 100).toFixed(0)}%` }}
                    transition={{ delay: 0.4, duration: 0.8, ease: 'easeOut' }}
                    className={`h-full rounded-full ${isInvite ? 'bg-green-400' : isReject ? 'bg-red-400' : 'bg-gray-400'}`}
                  />
                </div>
              )}
            </div>

            {/* Details */}
            <div className="px-6 py-4 bg-white space-y-2">
              {result.name && (
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-full bg-blue-100 text-blue-700 font-bold text-xs flex items-center justify-center shrink-0">
                    {result.name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase()}
                  </div>
                  <span className="font-semibold text-gray-800">{result.name}</span>
                </div>
              )}
              <div className="flex items-center gap-3 text-sm text-gray-500 flex-wrap">
                <span>
                  Parse quality:{' '}
                  <span className={`font-medium ${
                    result.parse_quality === 'complete' ? 'text-green-600' :
                    result.parse_quality === 'partial' ? 'text-amber-600' : 'text-red-600'
                  }`}>{result.parse_quality}</span>
                </span>
                {filename && <span className="text-gray-400 truncate max-w-[180px]">{filename}</span>}
              </div>
              {result.missing_fields.length > 0 && (
                <p className="text-xs text-amber-600 bg-amber-50 px-3 py-1.5 rounded-lg">
                  Missing: {result.missing_fields.join(', ')}
                </p>
              )}
            </div>

            {/* Footer */}
            <div className="px-6 py-3 bg-gray-50 border-t border-gray-100 flex justify-end">
              <button
                onClick={reset}
                className="text-xs text-gray-400 hover:text-gray-700 transition-colors"
              >
                Upload another CV →
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
