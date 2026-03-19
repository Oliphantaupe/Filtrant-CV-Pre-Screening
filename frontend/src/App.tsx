import { Outlet, NavLink } from 'react-router-dom'

export default function App() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-4 py-2 rounded text-sm font-medium transition-colors ${
      isActive ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'
    }`

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-6">
        <span className="text-lg font-bold text-blue-700 tracking-tight">Filtrant</span>
        <nav className="flex gap-2">
          <NavLink to="/candidates" className={linkClass}>Candidates</NavLink>
          <NavLink to="/upload" className={linkClass}>Upload CV</NavLink>
        </nav>
      </header>
      <main className="max-w-6xl mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
