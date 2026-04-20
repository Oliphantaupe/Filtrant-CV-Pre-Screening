import { Outlet, NavLink } from 'react-router-dom'
import AnimatedBackground from './components/AnimatedBackground'

export default function App() {
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
