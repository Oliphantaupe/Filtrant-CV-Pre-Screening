import { useState, useEffect } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import AnimatedBackground from './components/AnimatedBackground'

type Theme = 'dark' | 'light'

function SunIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="7.5" cy="7.5" r="2.5" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M7.5 1v1.5M7.5 12.5V14M1 7.5h1.5M12.5 7.5H14M3.05 3.05l1.06 1.06M10.89 10.89l1.06 1.06M3.05 11.95l1.06-1.06M10.89 4.11l1.06-1.06"
        stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12.5 9A6 6 0 0 1 5 1.5a6 6 0 1 0 7.5 7.5z"
        stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

export default function App() {
  const [theme, setTheme] = useState<Theme>(() =>
    (localStorage.getItem('theme') as Theme) ?? 'dark'
  )

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('theme', theme)
  }, [theme])

  return (
    <div className="min-h-screen">
      <AnimatedBackground />

      {/* Floating glass pill nav */}
      <header className="fixed top-4 left-0 right-0 z-50 flex justify-center px-4 pointer-events-none">
        <nav className="glass-nav rounded-full px-2 py-2 flex items-center gap-0.5 pointer-events-auto">
          <span className="font-bricolage text-sm font-bold text-[--text-heading] px-4 py-1 tracking-tight select-none">
            Filtrant
          </span>
          <div className="w-px h-4 bg-[--glass-active] mx-1" />
          <NavItem to="/dashboard">Dashboard</NavItem>
          <NavItem to="/candidates">Candidates</NavItem>
          <NavItem to="/upload">Upload CV</NavItem>
          <div className="w-px h-4 bg-[--glass-active] mx-1" />
          <button
            onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
            className="w-8 h-8 rounded-full flex items-center justify-center transition-all duration-200"
            style={{ color: 'var(--text-icon)' }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'var(--glass-hover)'
              e.currentTarget.style.color = 'var(--text-body)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.color = 'var(--text-icon)'
            }}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          </button>
        </nav>
      </header>

      <main className="max-w-6xl mx-auto px-6 pt-24 pb-12">
        <Outlet />
      </main>
    </div>
  )
}

function NavItem({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `px-3.5 py-1.5 rounded-full text-sm font-medium transition-all duration-200 ${
          isActive
            ? 'bg-[--teal-subtle] text-[--teal]'
            : 'text-[--text-2] hover:text-[--text-bright] hover:bg-[--glass-hover]'
        }`
      }
    >
      {children}
    </NavLink>
  )
}
