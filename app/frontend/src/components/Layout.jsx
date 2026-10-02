import { NavLink, Outlet } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/vault', label: 'Resume Vault' },
  { to: '/tailor', label: 'Tailor Resume' },
  { to: '/history', label: 'History' },
  { to: '/profile', label: 'Profile' },
]

export function Layout() {
  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      <aside className="flex h-full w-60 shrink-0 flex-col border-r border-gray-200 bg-white">
        <div className="flex items-center gap-2 px-5 py-5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gray-900 text-sm font-semibold text-white">
            R
          </div>
          <span className="text-[15px] font-semibold text-gray-900">ResumeAI</span>
        </div>
        <nav className="flex flex-col gap-0.5 px-3">
          {NAV_ITEMS.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive ? 'bg-gray-100 text-gray-900' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto px-5 py-4 text-xs text-gray-400">
          Local-first &middot; runs entirely on this machine
        </div>
      </aside>
      <main className="h-full min-w-0 flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
