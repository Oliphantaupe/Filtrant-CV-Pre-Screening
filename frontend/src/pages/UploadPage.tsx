import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { api } from '../api/client'
import type { UploadResult } from '../types/cv'

type ItemStatus = 'queued' | 'processing' | 'done' | 'error' | 'duplicate'

interface FileItem {
  id: string
  file: File
  status: ItemStatus
  result?: UploadResult
  error?: string
}

const CONCURRENCY = 3

function StatusIcon({ status }: { status: ItemStatus }) {
  if (status === 'processing') return (
    <div className="w-5 h-5 relative shrink-0">
      <div className="absolute inset-0 rounded-full" style={{ border: '1.5px solid var(--glass-active)' }} />
      <div className="absolute inset-0 rounded-full animate-spin"
        style={{ border: '1.5px solid transparent', borderTopColor: 'var(--teal)' }} />
    </div>
  )
  if (status === 'done') return (
    <div className="w-5 h-5 rounded-full flex items-center justify-center shrink-0"
      style={{ background: 'var(--teal-dim)' }}>
      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="var(--teal)" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
      </svg>
    </div>
  )
  if (status === 'duplicate') return (
    <div className="w-5 h-5 rounded-full flex items-center justify-center shrink-0"
      style={{ background: 'var(--glass-hover)' }}>
      <span className="text-xs" style={{ color: 'var(--text-faint)' }}>~</span>
    </div>
  )
  if (status === 'error') return (
    <div className="w-5 h-5 rounded-full flex items-center justify-center shrink-0"
      style={{ background: 'var(--reject-dim)' }}>
      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="var(--reject)" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </div>
  )
  return (
    <div className="w-5 h-5 rounded-full shrink-0"
      style={{ border: '1.5px solid var(--glass-active)' }} />
  )
}

function ResultRow({ item }: { item: FileItem }) {
  const rec = item.result?.recommendation
  const isInvite = rec === 'Invite'
  const recColor = isInvite ? 'var(--teal)' : rec ? 'var(--text-muted)' : undefined

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      className="flex items-center gap-3 px-4 py-3 rounded-2xl"
      style={{ background: 'var(--glass-subtle)', border: '1px solid var(--border-subtle)' }}
    >
      <StatusIcon status={item.status} />

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate" style={{ color: 'var(--text-body)' }}>
          {item.result?.name ?? item.file.name}
        </p>
        {item.status === 'duplicate' && (
          <p className="text-xs" style={{ color: 'var(--text-faint)' }}>Already processed</p>
        )}
        {item.status === 'error' && (
          <p className="text-xs truncate" style={{ color: 'var(--reject)' }}>{item.error}</p>
        )}
        {item.status === 'queued' && (
          <p className="text-xs" style={{ color: 'var(--text-faint)' }}>Queued…</p>
        )}
        {item.status === 'processing' && (
          <p className="text-xs" style={{ color: 'var(--text-faint)' }}>Reading CV…</p>
        )}
      </div>

      {rec && (
        <div className="flex items-center gap-2 shrink-0">
          {item.result?.fairness_mitigated && (
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
              style={{ background: 'var(--teal-dim)', color: 'var(--teal)', border: '1px solid var(--teal-border)' }}>
              Fair v2
            </span>
          )}
          {item.result?.confidence != null && (
            <span className="text-xs font-jetbrains" style={{ color: 'var(--text-faint)' }}>
              {Math.round(item.result.confidence * 100)}%
            </span>
          )}
          <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full"
            style={{
              background: isInvite ? 'var(--teal-dim)' : 'var(--glass-hover)',
              color: recColor,
              border: `1px solid ${isInvite ? 'var(--teal-border)' : 'var(--border-subtle)'}`,
            }}>
            {rec}
          </span>
        </div>
      )}
    </motion.div>
  )
}

export default function UploadPage() {
  const [dragging, setDragging] = useState(false)
  const [items, setItems] = useState<FileItem[]>([])
  const [processing, setProcessing] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const updateItem = (id: string, patch: Partial<FileItem>) =>
    setItems(prev => prev.map(it => it.id === id ? { ...it, ...patch } : it))

  const handleFiles = async (files: File[]) => {
    if (!files.length) return
    const newItems: FileItem[] = files.map(f => ({
      id: Math.random().toString(36).slice(2),
      file: f,
      status: 'queued',
    }))
    setItems(prev => [...prev, ...newItems])
    setProcessing(true)

    let cursor = 0
    const workers = Array.from({ length: Math.min(CONCURRENCY, newItems.length) }, async () => {
      while (true) {
        const i = cursor++
        if (i >= newItems.length) break
        const item = newItems[i]
        updateItem(item.id, { status: 'processing' })
        try {
          const result = await api.uploadCV(item.file)
          updateItem(item.id, { status: 'done', result })
        } catch (e) {
          const msg = e instanceof Error ? e.message : 'Upload failed'
          const isDuplicate = msg.toLowerCase().includes('already been processed')
          updateItem(item.id, { status: isDuplicate ? 'duplicate' : 'error', error: msg })
        }
      }
    })
    await Promise.all(workers)
    setProcessing(false)
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragging(false)
    if (!processing) handleFiles(Array.from(e.dataTransfer.files))
  }

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(Array.from(e.target.files ?? []))
    if (inputRef.current) inputRef.current.value = ''
  }

  const inviteCount = items.filter(i => i.result?.recommendation === 'Invite').length
  const rejectCount = items.filter(i => i.result?.recommendation === 'Reject').length
  const remaining = items.filter(i => i.status === 'queued' || i.status === 'processing').length

  return (
    <div className="max-w-lg mx-auto">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 300, damping: 28 }}>
        <h1 className="font-bricolage text-3xl font-bold tracking-tight mb-1" style={{ color: 'var(--text-1)' }}>
          Upload CVs
        </h1>
        <p className="text-sm mb-8" style={{ color: 'var(--text-muted)' }}>
          PDF, DOCX, or TXT — up to 5 MB · drag multiple files at once
        </p>
      </motion.div>

      {/* Drop zone */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08, type: 'spring', stiffness: 280, damping: 26 }}
        className="relative rounded-3xl p-10 text-center cursor-pointer transition-all duration-300"
        style={{
          background: dragging ? 'var(--teal-dim)' : 'var(--glass-subtle)',
          backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
          border: dragging ? '1.5px dashed var(--teal-border)' : '1.5px dashed var(--glass-active)',
          boxShadow: dragging ? '0 0 40px var(--teal-subtle), inset 0 0 20px var(--teal-dim)' : 'none',
          opacity: processing ? 0.6 : 1,
          pointerEvents: processing ? 'none' : 'auto',
        }}
        onDragOver={e => { e.preventDefault(); if (!processing) setDragging(true) }}
        onDragLeave={() => setDragging(false)} onDrop={onDrop}
        onClick={() => { if (!processing) inputRef.current?.click() }}
      >
        <input ref={inputRef} type="file" multiple className="hidden"
          accept=".pdf,.docx,.doc,.txt" onChange={onInputChange} />

        <div className="flex flex-col items-center gap-3">
          <motion.div animate={{ y: [0, -5, 0] }} transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
            className="w-12 h-12 rounded-full flex items-center justify-center"
            style={{ background: 'var(--teal-dim)', boxShadow: '0 0 28px var(--teal-muted)' }}>
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="var(--teal)" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
            </svg>
          </motion.div>
          <div>
            <p className="text-sm font-medium" style={{ color: 'var(--text-body)' }}>
              Drop files here
            </p>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>or click to browse — select multiple</p>
          </div>
        </div>
      </motion.div>

      {/* Status bar */}
      <AnimatePresence>
        {items.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="mt-4 flex items-center justify-between px-1">
            <div className="flex items-center gap-3 text-sm" style={{ color: 'var(--text-muted)' }}>
              {processing ? (
                <span>{remaining} remaining…</span>
              ) : (
                <>
                  {inviteCount > 0 && <span style={{ color: 'var(--teal)' }}>{inviteCount} Invite</span>}
                  {rejectCount > 0 && <span>{rejectCount} Reject</span>}
                </>
              )}
            </div>
            {!processing && (
              <button className="text-xs transition-colors" style={{ color: 'var(--text-faint)' }}
                onClick={() => setItems([])}
                onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-body)')}
                onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-faint)')}>
                Clear all
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results list */}
      <div className="mt-3 flex flex-col gap-2">
        <AnimatePresence>
          {items.map(item => <ResultRow key={item.id} item={item} />)}
        </AnimatePresence>
      </div>
    </div>
  )
}
