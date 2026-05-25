import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useAuditLogs } from '../api/audit'
import { getApiErrorMessage } from '../api/client'
import { Pagination } from '../components/Pagination'
import { Select } from '../components/Select'
import type { AuditLog } from '../types/api'
import { formatDateTime } from '../utils/format'

const EVENT_TYPE_OPTIONS = [
  { value: '', label: 'Все события' },
  { value: 'event.created',  label: 'event.created' },
  { value: 'event.updated',  label: 'event.updated' },
  { value: 'event.published', label: 'event.published' },
  { value: 'event.cancelled', label: 'event.cancelled' },
  { value: 'event.finished',  label: 'event.finished' },
  { value: 'event.deleted',   label: 'event.deleted' },
  { value: 'slot.created',    label: 'slot.created' },
  { value: 'slot.deleted',    label: 'slot.deleted' },
  { value: 'registration.attended',  label: 'registration.attended' },
  { value: 'registration.cancelled', label: 'registration.cancelled' },
  { value: 'organizer.created', label: 'organizer.created' },
  { value: 'organizer.updated', label: 'organizer.updated' },
  { value: 'organizer.deleted', label: 'organizer.deleted' },
  { value: 'admin.login',       label: 'admin.login' },
  { value: 'admin.login_failed', label: 'admin.login_failed' },
  { value: 'broadcast.sent',    label: 'broadcast.sent' },
]
const ENTITY_TYPE_OPTIONS = [
  { value: '', label: 'Все объекты' },
  { value: 'event',        label: 'event' },
  { value: 'slot',         label: 'slot' },
  { value: 'registration', label: 'registration' },
  { value: 'organizer',    label: 'organizer' },
  { value: 'broadcast',    label: 'broadcast' },
]
const ACTOR_TYPE_OPTIONS = [
  { value: '', label: 'Все' },
  { value: 'organizer', label: 'organizer' },
  { value: 'user', label: 'user' },
  { value: 'system', label: 'system' },
]
const PER_PAGE_OPTIONS = [
  { value: '25', label: '25 записей' },
  { value: '50', label: '50 записей' },
  { value: '100', label: '100 записей' },
]

type AuditTab = 'all' | 'events' | 'registrations' | 'auth'

const AUDIT_TABS: { id: AuditTab; label: string }[] = [
  { id: 'all', label: 'Все' },
  { id: 'events', label: 'Мероприятия' },
  { id: 'registrations', label: 'Регистрации' },
  { id: 'auth', label: 'Аутентификация' },
]

const EVENT_TYPE_BADGE: Record<string, string> = {
  'event.created':        'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
  'event.published':      'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
  'event.updated':        'bg-brand-50 text-brand-700 dark:bg-brand-950/40 dark:text-brand-300',
  'event.cancelled':      'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300',
  'event.deleted':        'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300',
  'event.finished':       'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
  'slot.created':         'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
  'slot.deleted':         'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300',
  'registration.attended':'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
  'registration.cancelled':'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300',
  'organizer.created':    'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
  'organizer.deleted':    'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300',
  'admin.login':          'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
  'admin.login_failed':   'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300',
}

const inputCls =
  'w-full rounded-xl border border-slate-300 dark:border-[#344063] bg-white dark:bg-[#131a2e] text-slate-900 dark:text-slate-100 px-3 py-2 text-sm focus:outline-none focus:border-brand-500 transition-colors'

function matchesTab(eventType: string, tab: AuditTab): boolean {
  if (tab === 'all') return true
  if (tab === 'events') {
    return eventType.startsWith('event.') || eventType.startsWith('slot.')
  }
  if (tab === 'registrations') {
    return eventType.startsWith('registration.') || eventType.startsWith('waitlist.')
  }
  if (tab === 'auth') {
    return eventType === 'admin.login' || eventType === 'admin.login_failed'
  }
  return true
}

function buildActivityChart(items: AuditLog[]): { date: string; label: string; count: number }[] {
  const buckets = new Map<string, number>()
  const labels = new Map<string, string>()

  for (let i = 6; i >= 0; i -= 1) {
    const day = new Date()
    day.setHours(0, 0, 0, 0)
    day.setDate(day.getDate() - i)
    const key = day.toISOString().slice(0, 10)
    buckets.set(key, 0)
    labels.set(key, day.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }))
  }

  for (const row of items) {
    const key = row.created_at.slice(0, 10)
    if (buckets.has(key)) {
      buckets.set(key, (buckets.get(key) ?? 0) + 1)
    }
  }

  return Array.from(buckets.entries()).map(([date, count]) => ({
    date,
    label: labels.get(date) ?? date,
    count,
  }))
}

export function AuditPage() {
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(50)
  const [activeTab, setActiveTab] = useState<AuditTab>('all')
  const [eventType, setEventType] = useState('')
  const [entityType, setEntityType] = useState('')
  const [entityIdInput, setEntityIdInput] = useState('')
  const [actorType, setActorType] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const entityId = useMemo(() => {
    const trimmed = entityIdInput.trim()
    if (!trimmed) return undefined
    const parsed = Number(trimmed)
    return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined
  }, [entityIdInput])

  const isoDateFrom = useMemo(
    () => (dateFrom ? new Date(dateFrom).toISOString() : undefined),
    [dateFrom],
  )
  const isoDateTo = useMemo(
    () => (dateTo ? new Date(dateTo).toISOString() : undefined),
    [dateTo],
  )

  const chartDateFrom = useMemo(() => {
    const day = new Date()
    day.setHours(0, 0, 0, 0)
    day.setDate(day.getDate() - 6)
    return day.toISOString()
  }, [])

  const serverFilters = useMemo(
    () => ({
      page,
      per_page: perPage,
      event_type: eventType || undefined,
      entity_type: entityType || undefined,
      entity_id: entityId,
      date_from: isoDateFrom,
      date_to: isoDateTo,
    }),
    [page, perPage, eventType, entityType, entityId, isoDateFrom, isoDateTo],
  )

  const { data, isLoading, error } = useAuditLogs(serverFilters)

  const { data: chartSource, isLoading: chartLoading } = useAuditLogs({
    page: 1,
    per_page: 200,
    entity_type: entityType || undefined,
    entity_id: entityId,
    date_from: chartDateFrom,
    date_to: isoDateTo,
  })

  const activityChart = useMemo(
    () => buildActivityChart(chartSource?.items ?? []),
    [chartSource?.items],
  )

  const filteredItems = useMemo(() => {
    const items = data?.items ?? []
    return items.filter((row) => {
      if (actorType && row.actor_type !== actorType) return false
      if (!matchesTab(row.event_type, activeTab)) return false
      return true
    })
  }, [data?.items, actorType, activeTab])

  const handleReset = () => {
    setPage(1)
    setPerPage(50)
    setActiveTab('all')
    setEventType('')
    setEntityType('')
    setEntityIdInput('')
    setActorType('')
    setDateFrom('')
    setDateTo('')
  }

  const hasFilters =
    activeTab !== 'all'
    || eventType
    || entityType
    || entityIdInput
    || actorType
    || dateFrom
    || dateTo
    || perPage !== 50

  const handleTabChange = (tab: AuditTab) => {
    setPage(1)
    setActiveTab(tab)
    setEventType('')
  }

  const handleEventTypeChange = (value: string) => {
    setPage(1)
    setEventType(value)
    setActiveTab('all')
  }

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
            Журнал аудита
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Все действия организаторов с временными метками и IP.
          </p>
        </div>
      </div>

      <div className="bg-white dark:bg-[#131a2e] rounded-2xl border border-slate-200 dark:border-[#1e2740] p-5 mb-6 shadow-[var(--shadow-soft)]">
        <h2 className="text-base font-semibold text-slate-800 dark:text-slate-200 mb-4">
          Активность за 7 дней
        </h2>
        {chartLoading ? (
          <div className="h-[200px] animate-pulse bg-slate-100 dark:bg-[#1a2238] rounded-xl" />
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={activityChart} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" className="dark:stroke-[#1e2740]" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: '12px',
                  border: '1px solid #e2e8f0',
                  fontSize: 12,
                }}
                labelFormatter={(_, payload) => {
                  const point = payload?.[0]?.payload as { date?: string } | undefined
                  return point?.date ? `Дата: ${point.date}` : ''
                }}
                formatter={(value) => [Number(value), 'Событий']}
              />
              <Bar dataKey="count" fill="#6366f1" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="bg-white dark:bg-[#131a2e] rounded-2xl border border-slate-200 dark:border-[#1e2740] p-4 mb-6 shadow-[var(--shadow-soft)]">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
          <div>
            <label
              htmlFor="filter-audit-event-type"
              className="mb-1.5 block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide"
            >
              Тип события
            </label>
            <Select
              id="filter-audit-event-type"
              value={eventType}
              onChange={handleEventTypeChange}
              options={EVENT_TYPE_OPTIONS}
              data-testid="filter-audit-event-type"
            />
          </div>
          <div>
            <label
              htmlFor="filter-audit-entity-type"
              className="mb-1.5 block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide"
            >
              Тип объекта
            </label>
            <Select
              id="filter-audit-entity-type"
              value={entityType}
              onChange={(v) => { setPage(1); setEntityType(v) }}
              options={ENTITY_TYPE_OPTIONS}
              data-testid="filter-audit-entity-type"
            />
          </div>
          <div>
            <label
              htmlFor="filter-audit-actor-type"
              className="mb-1.5 block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide"
            >
              Актор
            </label>
            <Select
              id="filter-audit-actor-type"
              value={actorType}
              onChange={(v) => { setPage(1); setActorType(v) }}
              options={ACTOR_TYPE_OPTIONS}
              data-testid="filter-audit-actor-type"
            />
          </div>
          <div>
            <label
              htmlFor="filter-audit-entity-id"
              className="mb-1.5 block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide"
            >
              ID объекта
            </label>
            <input
              id="filter-audit-entity-id"
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              value={entityIdInput}
              onChange={(e) => { setPage(1); setEntityIdInput(e.target.value.replace(/\D/g, '')) }}
              placeholder="Например, 42"
              className={inputCls}
              data-testid="filter-audit-entity-id"
            />
          </div>
          <div>
            <label
              htmlFor="filter-audit-per-page"
              className="mb-1.5 block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide"
            >
              На странице
            </label>
            <Select
              id="filter-audit-per-page"
              value={String(perPage)}
              onChange={(v) => { setPage(1); setPerPage(Number(v)) }}
              options={PER_PAGE_OPTIONS}
              data-testid="filter-audit-per-page"
            />
          </div>
          <div>
            <label
              htmlFor="audit-date-from"
              className="mb-1.5 block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide"
            >
              С даты
            </label>
            <input
              id="audit-date-from"
              type="datetime-local"
              value={dateFrom}
              onChange={(e) => { setPage(1); setDateFrom(e.target.value) }}
              className={inputCls}
              data-testid="filter-audit-date-from"
            />
          </div>
          <div>
            <label
              htmlFor="audit-date-to"
              className="mb-1.5 block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide"
            >
              По дату
            </label>
            <input
              id="audit-date-to"
              type="datetime-local"
              value={dateTo}
              onChange={(e) => { setPage(1); setDateTo(e.target.value) }}
              className={inputCls}
              data-testid="filter-audit-date-to"
            />
          </div>
        </div>
        {hasFilters && (
          <button
            type="button"
            onClick={handleReset}
            className="mt-3 text-xs text-brand-600 dark:text-brand-400 hover:underline"
          >
            × Сбросить фильтры
          </button>
        )}
      </div>

      <div
        className="flex flex-wrap gap-2 mb-4"
        role="tablist"
        aria-label="Группы событий аудита"
      >
        {AUDIT_TABS.map((tab) => {
          const selected = activeTab === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => handleTabChange(tab.id)}
              className={[
                'px-4 py-2 rounded-xl text-sm font-medium transition-colors',
                selected
                  ? 'bg-brand-600 text-white shadow-sm'
                  : 'bg-white dark:bg-[#131a2e] text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-[#1e2740] hover:border-brand-300 dark:hover:border-brand-700',
              ].join(' ')}
              data-testid={`audit-tab-${tab.id}`}
            >
              {tab.label}
            </button>
          )
        })}
      </div>

      {isLoading && <p className="text-slate-500 dark:text-slate-400">Загрузка…</p>}
      {error && <p className="text-red-600 dark:text-red-400">{getApiErrorMessage(error)}</p>}

      <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-[#1e2740] bg-white dark:bg-[#131a2e] shadow-[var(--shadow-soft)]">
        <table className="min-w-full text-sm" data-testid="audit-table">
          <thead>
            <tr className="border-b border-slate-100 dark:border-[#1e2740] text-left">
              <th className="px-4 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide whitespace-nowrap">
                Время
              </th>
              <th className="px-4 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                Актор
              </th>
              <th className="px-4 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                Событие
              </th>
              <th className="px-4 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                Объект
              </th>
              <th className="px-4 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                IP
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-[#1e2740]">
            {filteredItems.map((row) => {
              const badgeCls = EVENT_TYPE_BADGE[row.event_type] ?? 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
              return (
                <tr key={row.id} className="hover:bg-slate-50 dark:hover:bg-[#1a2238] transition-colors">
                  <td className="px-4 py-3 text-slate-500 dark:text-slate-400 whitespace-nowrap font-mono text-xs">
                    {formatDateTime(row.created_at)}
                  </td>
                  <td className="px-4 py-3 text-slate-700 dark:text-slate-200 max-w-xs truncate">
                    {row.actor_display ?? row.actor_type}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${badgeCls}`}>
                      {row.event_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500 dark:text-slate-400">
                    {row.entity_type
                      ? `${row.entity_type}${row.entity_id != null ? `#${row.entity_id}` : ''}`
                      : '—'}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500 dark:text-slate-400">
                    {row.ip_address ?? '—'}
                  </td>
                </tr>
              )
            })}
            {data && filteredItems.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center text-slate-500 dark:text-slate-400">
                  Записей нет
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {data && (
        <div className="mt-4">
          <Pagination page={data.page} pages={data.pages} onPageChange={setPage} />
        </div>
      )}
    </div>
  )
}
