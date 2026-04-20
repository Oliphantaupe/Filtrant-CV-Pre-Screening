import { useRef, useState, useCallback, useEffect } from 'react'

interface ScrollAreaProps {
  children: React.ReactNode
  className?: string
}

export default function ScrollArea({ children, className = '' }: ScrollAreaProps) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const [thumb, setThumb] = useState({ top: 0, height: 0, visible: false })
  const dragging = useRef(false)
  const dragStart = useRef({ y: 0, scrollTop: 0 })

  const updateThumb = useCallback(() => {
    const el = viewportRef.current
    if (!el) return
    const { scrollTop, scrollHeight, clientHeight } = el
    if (scrollHeight <= clientHeight) { setThumb(t => ({ ...t, visible: false })); return }
    const thumbHeight = Math.max(28, (clientHeight / scrollHeight) * clientHeight)
    const thumbTop = (scrollTop / (scrollHeight - clientHeight)) * (clientHeight - thumbHeight)
    setThumb({ top: thumbTop, height: thumbHeight, visible: true })
  }, [])

  useEffect(() => {
    updateThumb()
    const el = viewportRef.current
    if (!el) return
    const ro = new ResizeObserver(updateThumb)
    ro.observe(el)
    return () => ro.disconnect()
  }, [updateThumb])

  const onMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    const el = viewportRef.current
    if (!el) return
    dragging.current = true
    dragStart.current = { y: e.clientY, scrollTop: el.scrollTop }

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return
      const { scrollHeight, clientHeight } = el
      const thumbHeight = Math.max(28, (clientHeight / scrollHeight) * clientHeight)
      const ratio = (ev.clientY - dragStart.current.y) / (clientHeight - thumbHeight)
      el.scrollTop = dragStart.current.scrollTop + ratio * (scrollHeight - clientHeight)
    }
    const onUp = () => {
      dragging.current = false
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  return (
    <div className={`relative overflow-hidden ${className}`}>
      <div
        ref={viewportRef}
        onScroll={updateThumb}
        className="h-full w-full overflow-y-scroll"
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' } as React.CSSProperties}
      >
        {children}
      </div>

      {thumb.visible && (
        <div className="absolute right-1.5 top-2 bottom-2 w-[3px] rounded-full pointer-events-none">
          <div
            className="absolute w-full rounded-full cursor-pointer pointer-events-auto transition-colors"
            style={{
              top: thumb.top,
              height: thumb.height,
              background: 'var(--text-ghost)',
            }}
            onMouseDown={onMouseDown}
          />
        </div>
      )}
    </div>
  )
}
