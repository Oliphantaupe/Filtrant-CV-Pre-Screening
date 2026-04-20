const STYLES: Record<string, { bg: string; color: string; dot: string; symbol: string }> = {
  Invite: {
    bg: 'var(--teal-subtle)',
    color: 'var(--teal)',
    dot: 'var(--teal)',
    symbol: '●',
  },
  Reject: {
    bg: 'var(--glass-dim)',
    color: 'var(--text-muted)',
    dot: 'var(--text-faint)',
    symbol: '×',
  },
  pending: {
    bg: 'var(--glass-subtle)',
    color: 'var(--text-ghost)',
    dot: 'var(--text-4)',
    symbol: '○',
  },
}

export default function RecommendationBadge({ value, large }: { value: string; large?: boolean }) {
  const s = STYLES[value] ?? STYLES.pending
  const size = large ? 'px-4 py-1.5 text-sm gap-2' : 'px-2.5 py-1 text-xs gap-1.5'
  return (
    <span
      className={`inline-flex items-center ${size} rounded-full font-semibold tracking-wide`}
      style={{
        background: s.bg,
        color: s.color,
        border: '1px solid var(--border-dim)',
      }}
    >
      <span className="text-[9px] leading-none" style={{ color: s.dot }}>{s.symbol}</span>
      {value}
    </span>
  )
}
