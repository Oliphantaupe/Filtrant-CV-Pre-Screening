export default function AnimatedBackground() {
  return (
    <div
      className="fixed inset-0 -z-10 overflow-hidden"
      style={{ background: 'linear-gradient(145deg, var(--bg) 0%, var(--bg2) 55%, var(--bg) 100%)' }}
    >
      <div className="bokeh-blob bokeh-1" />
      <div className="bokeh-blob bokeh-2" />
      <div className="bokeh-blob bokeh-3" />
      <div className="bokeh-blob bokeh-4" />
      <div className="bokeh-blob bokeh-5" />
      <div className="bokeh-blob bokeh-6" />
    </div>
  )
}
