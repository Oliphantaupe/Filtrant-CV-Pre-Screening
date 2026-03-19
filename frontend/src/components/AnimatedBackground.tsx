export default function AnimatedBackground() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden bg-white">
      {/* Orb 1 — blue, top-left */}
      <div
        className="absolute -top-40 -left-40 w-[700px] h-[700px] rounded-full bg-blue-200/40 blur-[120px]"
        style={{ animation: 'orb-drift-1 28s ease-in-out infinite' }}
      />
      {/* Orb 2 — violet, top-right */}
      <div
        className="absolute -top-20 -right-40 w-[550px] h-[550px] rounded-full bg-violet-200/35 blur-[120px]"
        style={{ animation: 'orb-drift-2 36s ease-in-out infinite' }}
      />
      {/* Orb 3 — sky, bottom-center */}
      <div
        className="absolute -bottom-32 left-1/3 w-[500px] h-[500px] rounded-full bg-sky-200/30 blur-[100px]"
        style={{ animation: 'orb-drift-3 22s ease-in-out infinite' }}
      />
    </div>
  )
}
