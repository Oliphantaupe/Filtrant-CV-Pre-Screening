export default function RecommendationBadge({ value, large }: { value: string; large?: boolean }) {
  const styles: Record<string, string> = {
    Invite: 'bg-green-100 text-green-800',
    Reject: 'bg-red-100 text-red-800',
    pending: 'bg-gray-100 text-gray-600',
  }
  const size = large ? 'px-4 py-1.5 text-sm' : 'px-2.5 py-0.5 text-xs'
  return (
    <span className={`${size} rounded-full font-semibold ${styles[value] ?? styles.pending}`}>
      {value}
    </span>
  )
}
