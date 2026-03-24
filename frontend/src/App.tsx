import { Outlet, NavLink } from 'react-router-dom'
import AnimatedBackground from './components/AnimatedBackground'

export default function App() {
  return (
    <div className="min-h-screen">
      <AnimatedBackground />

      {/* Frosted glass nav */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-white/90 border-b border-gray-200/60">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          {/* Logo */}
          <span className="text-base font-bold tracking-tight bg-gradient-to-r from-blue-600 to-violet-600 bg-clip-text text-transparent select-none">
            Filtrant
          </span>

          {/* Nav */}
          <nav className="flex items-center gap-1">
            <NavItem to="/candidates">Candidates</NavItem>
            <NavItem to="/upload">Upload CV</NavItem>
          </nav>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10">
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
        `px-4 py-1.5 rounded-full text-sm font-medium transition-all duration-150 ${
          isActive
            ? 'bg-gray-900 text-white'
            : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'
        }`
      }
    >
      {children}
    </NavLink>
  )
}
