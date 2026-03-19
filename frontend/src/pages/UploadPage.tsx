import { useState, useRef } from 'react'
import { api } from '../api/client'
import type { UploadResult } from '../types/cv'

export default function UploadPage() {
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<UploadResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = async (file: File) => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.uploadCV(file)
      setResult(res)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  return (
    <div className="max-w-xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Upload CV</h1>

      <div
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
          dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400'
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept=".pdf,.docx,.doc,.txt"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
        />
        <p className="text-gray-500 text-sm">
          {loading ? 'Processing…' : 'Drop a PDF, DOCX, or TXT file here, or click to browse'}
        </p>
      </div>

      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-6 p-6 bg-white rounded-xl border border-gray-200 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-gray-800">{result.name ?? 'Unknown candidate'}</span>
            <RecommendationBadge value={result.recommendation} />
          </div>
          {result.confidence !== null && (
            <p className="text-sm text-gray-500">Confidence: {(result.confidence * 100).toFixed(1)}%</p>
          )}
          <p className="text-sm text-gray-500">Parse quality: <span className="font-medium">{result.parse_quality}</span></p>
          {result.missing_fields.length > 0 && (
            <p className="text-sm text-amber-600">Missing: {result.missing_fields.join(', ')}</p>
          )}
        </div>
      )}
    </div>
  )
}

function RecommendationBadge({ value }: { value: string }) {
  const styles: Record<string, string> = {
    Invite: 'bg-green-100 text-green-800',
    Reject: 'bg-red-100 text-red-800',
    pending: 'bg-gray-100 text-gray-600',
  }
  return (
    <span className={`px-3 py-1 rounded-full text-xs font-semibold ${styles[value] ?? styles.pending}`}>
      {value}
    </span>
  )
}
