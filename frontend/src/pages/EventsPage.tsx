import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useCreateEvent, useEvents } from '../api/events'
import { getApiErrorMessage } from '../api/client'
import { EventForm } from '../components/EventForm'
import { Modal } from '../components/Modal'
import { Select } from '../components/Select'
import type { EventCreate, EventStatus, EventUpdate } from '../types/api'
import { EVENT_STATUS_LABELS } from '../utils/format'

const STATUS_BADGE: Record<string, string> = {
  draft:     'bg-slate-100 dark:bg-[#1a2238] text-slate-600 dark:text-slate-400',
  published: 'bg-emerald-50 dark:bg-[#062e1f] text-emerald-700 dark:text-emerald-400',
  cancelled: 'bg-red-50 dark:bg-[#2e0a0a] text-red-700 dark:text-red-400',
  finished:  'bg-slate-100 dark:bg-[#1a2238] text-slate-500 dark:text-slate-500',
}
const RU_MONTHS = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']

function EventCoverImage({ src, alt }: { src: string; alt: string }) {
  const [imgError, setImgError] = useState(false)
  if (imgError) return null
  return (
    <div className="h-28 overflow-hidden shrink-0">
      <img
        src={src}
        alt={alt}
        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
        onError={() => setImgError(true)}
      />
    </div>
  )
}

export function EventsPage() {
  const [statusFilter, setStatusFilter] = useState<EventStatus | ''>('')
  const [search, setSearch] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const { data: events = [], isLoading, error } = useEvents(
    statusFilter ? { status: statusFilter } : {},
  )
  const createMutation = useCreateEvent()

  const q = search.trim().toLowerCase()
  const filtered = !q
    ? events
    : events.filter((e) => e.title.toLowerCase().includes(q))

  const handleCreate = async (data: EventCreate | EventUpdate) => {
    setCreateError(null)
    try {
      await createMutation.mutateAsync(data as EventCreate)
      setCreateOpen(false)
    } catch (err) {
      setCreateError(getApiErrorMessage(err, 'Не удалось создать мероприятие'))
      throw err
    }
  }

  return (
    <div data-testid="events-page">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">Мероприятия</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">Создавайте, публикуйте и управляйте — всё в одном месте.</p>
        </div>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-medium text-sm shadow-[var(--shadow-glow)] transition-all"
          data-testid="btn-create-event"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          Создать
        </button>
      </div>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap gap-3">
        <div className="w-44">
          <Select
            value={statusFilter}
            onChange={(v) => setStatusFilter(v as EventStatus | '')}
            options={[
              { value: '',          label: 'Все статусы' },
              { value: 'draft',     label: 'Черновик' },
              { value: 'published', label: 'Опубликовано' },
              { value: 'cancelled', label: 'Отменено' },
              { value: 'finished',  label: 'Завершено' },
            ]}
            data-testid="filter-status"
          />
        </div>
        <div className="flex-1 min-w-[200px]">
          <label htmlFor="filter-search" className="sr-only">Поиск по названию</label>
          <input
            id="filter-search"
            type="search"
            placeholder="Поиск по названию…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-xl border border-slate-300 dark:border-[#344063] bg-white dark:bg-[#131a2e] text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 transition"
            data-testid="filter-search"
          />
        </div>
      </div>

      {isLoading && <p className="text-slate-500 dark:text-slate-400">Загрузка…</p>}
      {error && <p className="text-red-600 dark:text-red-400">{getApiErrorMessage(error)}</p>}

      {/* Empty state */}
      {!isLoading && filtered.length === 0 && (
        <div className="bg-white dark:bg-[#131a2e] rounded-2xl border border-slate-200 dark:border-[#1e2740] p-16 text-center shadow-[var(--shadow-soft)]">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-50 to-brand-100 dark:from-[#1a1f3a] dark:to-[#1a2238] grid place-items-center mx-auto mb-5">
            <svg className="w-8 h-8 text-brand-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-1">Пока пусто</h3>
          <p className="text-slate-500 dark:text-slate-400 mb-5">Создайте первое мероприятие — оно появится в боте после публикации.</p>
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium transition-colors"
            data-testid="btn-create-event-empty"
          >
            Создать мероприятие
          </button>
        </div>
      )}

      {/* Cards grid */}
      {filtered.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5" data-testid="events-grid">
          {filtered.map((event) => {
            const d = new Date(event.starts_at)
            const mon = RU_MONTHS[d.getMonth()]
            const day = String(d.getDate()).padStart(2, '0')
            const time = d.toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' })
            const pct = event.capacity ? Math.min(100, Math.round(100 * event.confirmed_count / event.capacity)) : 0
            const barColor = pct >= 100
              ? 'from-red-400 to-red-600'
              : pct >= 75
                ? 'from-amber-400 to-orange-500'
                : 'from-emerald-400 to-emerald-600'
            const badge = STATUS_BADGE[event.status] ?? STATUS_BADGE.draft

            return (
              <Link
                key={event.id}
                to={`/events/${event.id}`}
                className="group bg-white dark:bg-[#131a2e] rounded-2xl border border-slate-200 dark:border-[#1e2740] shadow-[var(--shadow-soft)] hover:shadow-[var(--shadow-glow)] hover:border-brand-300 dark:hover:border-brand-700 transition-all flex flex-col overflow-hidden"
                data-testid={`event-link-${event.id}`}
              >
                {event.cover_url && (
                  <EventCoverImage src={event.cover_url} alt={event.title} />
                )}
                <div className="p-5 flex flex-col flex-1">
                <div className="flex items-start justify-between mb-3 gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    {/* Date badge */}
                    <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white grid place-items-center shrink-0">
                      <div className="text-center leading-tight">
                        <div className="text-[10px] uppercase opacity-80">{mon}</div>
                        <div className="text-base font-bold">{day}</div>
                      </div>
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs text-slate-500 dark:text-slate-400 mb-0.5">{time}</div>
                      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${badge}`}>
                        ● {EVENT_STATUS_LABELS[event.status] ?? event.status}
                      </span>
                    </div>
                  </div>
                  <svg className="w-4 h-4 text-slate-300 dark:text-slate-600 group-hover:text-brand-600 transition-colors shrink-0 mt-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                    <line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/>
                  </svg>
                </div>

                <h3 className="font-semibold text-slate-900 dark:text-slate-100 mb-1 line-clamp-2 group-hover:text-brand-700 dark:group-hover:text-brand-400 transition-colors">
                  {event.title}
                </h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 truncate mb-4">
                  {event.format === 'online' ? '💻 Онлайн' : `📍 ${event.location || 'место не указано'}`}
                </p>

                {/* Capacity bar */}
                <div className="mt-auto">
                  <div className="flex justify-between text-xs text-slate-500 dark:text-slate-400 mb-1.5">
                    <span className="font-medium text-slate-700 dark:text-slate-300 tabular-nums">
                      {event.confirmed_count} / {event.capacity}
                    </span>
                    <span className="tabular-nums">
                      {pct}%
                      {event.waitlist_count > 0 && (
                        <span className="text-amber-600 dark:text-amber-400"> · +{event.waitlist_count} в очереди</span>
                      )}
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-100 dark:bg-[#1a2238] overflow-hidden">
                    <div
                      className={`h-full bg-gradient-to-r ${barColor} transition-all`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
                </div>{/* /p-5 */}
              </Link>
            )
          })}
        </div>
      )}

      <Modal open={createOpen} title="Новое мероприятие" onClose={() => setCreateOpen(false)}>
        {createError && <p className="mb-3 text-sm text-red-600 dark:text-red-400">{createError}</p>}
        <EventForm
          onSubmit={handleCreate}
          onCancel={() => setCreateOpen(false)}
          submitLabel="Создать"
        />
      </Modal>
    </div>
  )
}
