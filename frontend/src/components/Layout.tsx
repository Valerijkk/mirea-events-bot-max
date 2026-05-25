import { useState, useEffect } from 'react'
import { NavLink, useNavigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { useLogout } from '../api/auth'

/* ---------- theme toggle ---------- */
function useTheme() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))

  const toggle = () => {
    const next = !dark
    setDark(next)
    if (next) {
      document.documentElement.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }

  return { dark, toggle }
}

/* ---------- nav item ---------- */
function NavItem({ to, icon, label }: { to: string; icon: React.ReactNode; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        [
          'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors',
          isActive
            ? 'bg-brand-50 text-brand-700 dark:bg-[#1a1f3a] dark:text-brand-300'
            : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-[#1a2238] hover:text-slate-900 dark:hover:text-slate-100',
        ].join(' ')
      }
    >
      <span className="w-5 h-5 shrink-0">{icon}</span>
      {label}
    </NavLink>
  )
}

/* ---------- SVG icons ---------- */
const IconEvents = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
    <line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
  </svg>
)
const IconAudit = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
    <line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
  </svg>
)
const IconSwagger = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
    <circle cx="10" cy="13" r="2"/><path d="M14 13h2"/><path d="M14 17h2"/><path d="M10 17h0"/>
  </svg>
)
const IconOrganizers = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="9" cy="7" r="4"/>
    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
  </svg>
)
const IconLogout = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
    <polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
  </svg>
)
const IconMoon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  </svg>
)
const IconSun = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
    <circle cx="12" cy="12" r="5"/>
    <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
    <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
  </svg>
)
const IconStats = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
    <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
  </svg>
)
const IconMenu = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
    <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
  </svg>
)

/* ---------- Sidebar ---------- */
function Sidebar({ onClose }: { onClose?: () => void }) {
  const organizer = useAuthStore((s) => s.organizer)
  const isAdmin = useAuthStore((s) => s.isAdmin())
  const logoutMutation = useLogout()
  const navigate = useNavigate()
  const { dark, toggle } = useTheme()

  const handleLogout = async () => {
    await logoutMutation.mutateAsync()
    navigate('/login')
  }

  return (
    <div className="flex flex-col w-64 bg-white dark:bg-[#131a2e] border-r border-slate-200 dark:border-[#1e2740] h-full">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-slate-100 dark:border-[#1e2740]">
        <NavLink to="/events" className="flex items-center gap-3 group" onClick={onClose}>
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 grid place-items-center shadow-[var(--shadow-glow)] group-hover:scale-105 transition-transform shrink-0">
            <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 4H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z"/>
              <line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>
              <line x1="3" y1="10" x2="21" y2="10"/>
            </svg>
          </div>
          <div>
            <div className="font-bold text-slate-900 dark:text-slate-100 leading-tight">mirea-events-bot</div>
            <div className="text-xs text-slate-500 dark:text-slate-400">РТУ МИРЭА · МАКС</div>
          </div>
        </NavLink>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto scrollbar-hide">
        <NavItem to="/events" icon={IconEvents} label="Мероприятия" />
        {isAdmin && (
          <>
            <NavItem to="/organizers" icon={IconOrganizers} label="Организаторы" />
            <NavItem to="/stats" icon={IconStats} label="Статистика" />
            <NavItem to="/audit" icon={IconAudit} label="Audit-log" />
          </>
        )}
        <a
          href="/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-[#1a2238] hover:text-slate-900 dark:hover:text-slate-100"
        >
          <span className="w-5 h-5 shrink-0">{IconSwagger}</span>
          Swagger API
        </a>
      </nav>

      {/* Bottom */}
      <div className="px-3 py-4 border-t border-slate-100 dark:border-[#1e2740] space-y-1">
        {/* Theme toggle */}
        <button
          type="button"
          onClick={toggle}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-[#1a2238] hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
          aria-label="Переключить тему"
        >
          <span className="w-5 h-5 shrink-0">{dark ? IconSun : IconMoon}</span>
          {dark ? 'Светлая тема' : 'Тёмная тема'}
        </button>

        {/* User + logout */}
        {organizer && (
          <div className="px-3 py-2.5 rounded-xl">
            <div className="text-xs text-slate-500 dark:text-slate-400 truncate">{organizer.name || organizer.email}</div>
            <div className="text-[11px] text-slate-400 dark:text-slate-500 capitalize">{organizer.role}</div>
          </div>
        )}
        <button
          type="button"
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-red-50 dark:hover:bg-[#2e0a0a] hover:text-red-700 dark:hover:text-red-400 transition-colors"
          data-testid="btn-logout"
        >
          <span className="w-5 h-5 shrink-0">{IconLogout}</span>
          Выйти
        </button>
      </div>
    </div>
  )
}

/* ---------- Layout ---------- */
export function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  useEffect(() => { setMobileOpen(false) }, [location])

  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-[#0b1020]">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex flex-col w-64 sticky top-0 h-screen shrink-0">
        <Sidebar />
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          <div className="absolute left-0 top-0 h-full w-64 z-50">
            <Sidebar onClose={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top bar */}
        <header className="lg:hidden flex items-center gap-3 px-4 py-3 bg-white dark:bg-[#131a2e] border-b border-slate-200 dark:border-[#1e2740] sticky top-0 z-30">
          <button
            type="button"
            className="w-8 h-8 text-slate-600 dark:text-slate-400"
            onClick={() => setMobileOpen(true)}
            aria-label="Открыть меню"
          >
            <span className="w-6 h-6 block">{IconMenu}</span>
          </button>
          <div className="font-bold text-slate-900 dark:text-slate-100">mirea-events-bot</div>
        </header>

        <main className="flex-1 px-4 sm:px-8 py-8 max-w-7xl w-full mx-auto animate-fade-in">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
