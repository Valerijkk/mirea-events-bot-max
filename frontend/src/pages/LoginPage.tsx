import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLogin } from '../api/auth'
import { getApiErrorMessage } from '../api/client'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const loginMutation = useLogin()
  const navigate = useNavigate()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await loginMutation.mutateAsync({ email, password })
      navigate('/events')
    } catch (err) {
      setError(getApiErrorMessage(err, 'Неверный email или пароль'))
    }
  }

  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-[#0b1020]">
      {/* Left brand panel — desktop only */}
      <div className="hidden lg:flex w-1/2 bg-gradient-to-br from-brand-700 via-brand-600 to-brand-900 text-white relative overflow-hidden">
        <div
          className="absolute inset-0 opacity-30"
          style={{
            backgroundImage:
              'radial-gradient(circle at 20% 20%, rgba(255,255,255,0.25) 0%, transparent 40%), radial-gradient(circle at 80% 70%, rgba(255,255,255,0.15) 0%, transparent 40%)',
          }}
        />
        <div className="relative flex flex-col justify-between p-12 z-10">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-white/20 backdrop-blur grid place-items-center">
              <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 4H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z"/>
                <line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>
                <line x1="3" y1="10" x2="21" y2="10"/>
              </svg>
            </div>
            <div>
              <div className="font-bold text-lg">mirea-events-bot</div>
              <div className="text-xs text-white/70">РТУ МИРЭА × VK · трек МАКС</div>
            </div>
          </div>

          {/* Hero */}
          <div>
            <h1 className="text-4xl font-bold leading-tight mb-4">
              Запись на мероприятия<br />в МАКС — за 4 тапа.
            </h1>
            <p className="text-white/80 text-lg leading-relaxed max-w-md">
              Управляйте мероприятиями, делайте сегментированные рассылки и сканируйте QR-пропуска — всё в одной админке.
            </p>
            <div className="mt-10 grid grid-cols-3 gap-4 max-w-md">
              {[['< 2 сек', 'до подтверждения'], ['5', 'сегментов рассылок'], ['24ч / 1ч', 'напоминания']].map(([val, label]) => (
                <div key={label}>
                  <div className="text-2xl font-bold">{val}</div>
                  <div className="text-xs text-white/70 mt-1">{label}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="text-xs text-white/50">
            Хакатон «Весенний код» · кейс №2 «Запись абитуриента на мероприятие университета»
          </div>
        </div>
      </div>

      {/* Right form panel */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm animate-slide-up">
          {/* Mobile logo */}
          <div className="lg:hidden mb-8 flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 grid place-items-center text-white">
              <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 4H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z"/>
                <line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>
                <line x1="3" y1="10" x2="21" y2="10"/>
              </svg>
            </div>
            <div>
              <div className="font-bold text-slate-900 dark:text-slate-100">mirea-events-bot</div>
              <div className="text-xs text-slate-500 dark:text-slate-400">РТУ МИРЭА · МАКС</div>
            </div>
          </div>

          <h2 className="text-3xl font-bold text-slate-900 dark:text-slate-100 mb-2">С возвращением</h2>
          <p className="text-slate-500 dark:text-slate-400 mb-8">Войдите в админку для организаторов.</p>

          {error && (
            <div data-testid="login-error" className="mb-5 px-4 py-3 rounded-xl bg-red-50 dark:bg-[#2e0a0a] border border-red-200 dark:border-[#4c1212] text-red-700 dark:text-red-400 text-sm flex items-start gap-2">
              <svg className="w-5 h-5 shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="login-email" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                Email
              </label>
              <input
                id="login-email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-xl border border-slate-300 dark:border-[#344063] bg-white dark:bg-[#131a2e] text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition"
                placeholder="admin@mirea.ru"
                data-testid="input-email"
              />
            </div>
            <div>
              <label htmlFor="login-password" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                Пароль
              </label>
              <input
                id="login-password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-xl border border-slate-300 dark:border-[#344063] bg-white dark:bg-[#131a2e] text-slate-900 dark:text-slate-100 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition"
                data-testid="input-password"
              />
            </div>

            <button
              type="submit"
              disabled={loginMutation.isPending}
              className="w-full rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-semibold py-3 text-sm shadow-[var(--shadow-glow)] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              data-testid="btn-login"
            >
              {loginMutation.isPending ? 'Вход…' : 'Войти'}
            </button>
          </form>

          <p className="mt-8 text-xs text-slate-400 dark:text-slate-500 text-center">
            Сервис разработан командой хакатона и не является официальной функцией платформы МАКС.
          </p>
        </div>
      </div>
    </div>
  )
}
