import { useMemo, useState } from 'react'
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  Legend,
} from 'recharts'
import { useGlobalStats, useRegsByDay, useEventStats } from '../api/stats'
import { useEvents } from '../api/events'
import type { Event } from '../types/api'
import { EVENT_TYPE_LABELS } from '../utils/format'

const PIE_COLORS = ['#6366f1', '#8b5cf6', '#a78bfa', '#34d399', '#fbbf24', '#f87171']

const DAY_OPTIONS = [7, 14, 30] as const

function SectionHeading({ children }: { children: string }) {
  return (
    <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-200 mb-4">{children}</h2>
  )
}

function KpiCard({
  label,
  value,
  sub,
  color,
}: {
  label: string
  value: number | string
  sub?: string
  color: string
}) {
  return (
    <div className="bg-white dark:bg-[#131a2e] rounded-2xl border border-slate-200 dark:border-[#1e2740] p-5 flex flex-col gap-1">
      <div className={`text-3xl font-extrabold ${color}`}>{value}</div>
      <div className="text-sm font-medium text-slate-700 dark:text-slate-200">{label}</div>
      {sub && <div className="text-xs text-slate-400 dark:text-slate-500">{sub}</div>}
    </div>
  )
}

function DaysFilter({
  value,
  onChange,
}: {
  value: number
  onChange: (days: number) => void
}) {
  return (
    <div
      className="flex gap-2 mb-4"
      role="group"
      aria-label="Диапазон дней для графика"
    >
      {DAY_OPTIONS.map((d) => (
        <button
          key={d}
          type="button"
          onClick={() => onChange(d)}
          aria-pressed={value === d}
          className={`px-3 py-1 rounded-full text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 ${
            value === d
              ? 'bg-brand-600 text-white'
              : 'bg-slate-100 dark:bg-[#1a2238] text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-[#243049]'
          }`}
        >
          {d} дн.
        </button>
      ))}
    </div>
  )
}

function EventRow({ event }: { event: Event }) {
  const { data: stats } = useEventStats(event.id)
  const fill = stats ? Math.round(stats.fill_rate * 100) : null
  const att = stats?.attendance_rate != null ? Math.round(stats.attendance_rate * 100) : null

  return (
    <tr className="border-b border-slate-100 dark:border-[#1e2740] hover:bg-slate-50 dark:hover:bg-[#1a2238] transition-colors">
      <td className="py-3 pr-4 text-sm text-slate-800 dark:text-slate-200 max-w-xs truncate">
        {event.title}
      </td>
      <td className="py-3 px-2 text-sm text-slate-500 dark:text-slate-400 text-center">
        {event.capacity}
      </td>
      <td className="py-3 px-2 text-sm text-center">
        {stats ? (
          <span className="font-semibold text-brand-600 dark:text-brand-400">
            {stats.confirmed + stats.attended}
          </span>
        ) : (
          <span className="text-slate-300 dark:text-slate-600">—</span>
        )}
      </td>
      <td className="py-3 px-2 text-sm text-center">
        {stats ? (
          <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
            {stats.attended}
          </span>
        ) : (
          <span className="text-slate-300 dark:text-slate-600">—</span>
        )}
      </td>
      <td className="py-3 px-2 text-sm text-center">
        {fill !== null ? (
          <div className="flex items-center gap-2 justify-center">
            <div className="w-16 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
              <div
                className="h-full rounded-full bg-brand-500"
                style={{ width: `${fill}%` }}
              />
            </div>
            <span className="text-slate-600 dark:text-slate-300 text-xs">{fill}%</span>
          </div>
        ) : (
          <span className="text-slate-300 dark:text-slate-600">—</span>
        )}
      </td>
      <td className="py-3 pl-2 text-sm text-center">
        {att !== null ? (
          <span
            className={`font-semibold ${att >= 70 ? 'text-emerald-600 dark:text-emerald-400' : att >= 40 ? 'text-amber-600 dark:text-amber-400' : 'text-red-500 dark:text-red-400'}`}
          >
            {att}%
          </span>
        ) : (
          <span className="text-slate-300 dark:text-slate-600">—</span>
        )}
      </td>
    </tr>
  )
}

export function StatsPage() {
  const [days, setDays] = useState(30)
  const { data: global, isLoading: globalLoading } = useGlobalStats()
  const { data: regsByDay, isLoading: chartLoading } = useRegsByDay(days)
  const { data: publishedEvents = [] } = useEvents({ status: 'published' })

  const eventTypeData = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const e of publishedEvents) {
      counts[e.event_type] = (counts[e.event_type] ?? 0) + 1
    }
    return Object.entries(counts).map(([type, value]) => ({
      name: EVENT_TYPE_LABELS[type] ?? type,
      value,
    }))
  }, [publishedEvents])

  const placesData = useMemo(() => {
    const totals = publishedEvents.reduce(
      (acc, e) => ({
        confirmed: acc.confirmed + e.confirmed_count,
        waitlist: acc.waitlist + e.waitlist_count,
        capacity: acc.capacity + e.capacity,
      }),
      { confirmed: 0, waitlist: 0, capacity: 0 },
    )
    const free = Math.max(0, totals.capacity - totals.confirmed - totals.waitlist)
    return [{ name: 'Все', confirmed: totals.confirmed, waitlist: totals.waitlist, free }]
  }, [publishedEvents])

  const topEvents = useMemo(
    () => [...publishedEvents].sort((a, b) => b.confirmed_count - a.confirmed_count).slice(0, 5),
    [publishedEvents],
  )

  return (
    <div data-testid="stats-page">
      <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-6">Статистика</h1>

      {/* Обзор */}
      <section className="mb-8">
        <SectionHeading>Обзор</SectionHeading>
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          {globalLoading ? (
            Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="bg-white dark:bg-[#131a2e] rounded-2xl border border-slate-200 dark:border-[#1e2740] p-5 h-24 animate-pulse"
              />
            ))
          ) : global ? (
            <>
              <KpiCard
                label="Пользователей"
                value={global.total_users.toLocaleString()}
                sub="зарегистрировано в боте"
                color="text-brand-600 dark:text-brand-400"
              />
              <KpiCard
                label="Мероприятий"
                value={global.total_events}
                sub={`${global.published_events} опубликовано`}
                color="text-indigo-600 dark:text-indigo-400"
              />
              <KpiCard
                label="Регистраций"
                value={global.total_registrations.toLocaleString()}
                sub="за всё время"
                color="text-violet-600 dark:text-violet-400"
              />
              <KpiCard
                label="Активных записей"
                value={global.active_registrations}
                sub="confirmed + waitlist"
                color="text-sky-600 dark:text-sky-400"
              />
              <KpiCard
                label="Посещений"
                value={global.attended_total.toLocaleString()}
                sub="отсканированных QR"
                color="text-emerald-600 dark:text-emerald-400"
              />
              <KpiCard
                label="Явка"
                value={
                  global.attended_total > 0 && global.total_registrations > 0
                    ? `${Math.round((global.attended_total / global.total_registrations) * 100)}%`
                    : '—'
                }
                sub="attended / registrations"
                color="text-amber-600 dark:text-amber-400"
              />
            </>
          ) : null}
        </div>
      </section>

      {/* Динамика регистраций */}
      <section className="mb-8">
        <SectionHeading>Динамика регистраций</SectionHeading>
        <div className="bg-white dark:bg-[#131a2e] rounded-2xl border border-slate-200 dark:border-[#1e2740] p-5">
          <DaysFilter value={days} onChange={setDays} />
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200 mb-4">
            Регистрации по дням ({days} дней)
          </h3>
          {chartLoading ? (
            <div className="h-48 animate-pulse bg-slate-100 dark:bg-[#1a2238] rounded-xl" />
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={regsByDay ?? []} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorRegs" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" className="dark:stroke-[#1e2740]" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                  interval={days <= 7 ? 0 : days <= 14 ? 1 : 4}
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
                  labelFormatter={(l) => `Дата: ${l}`}
                  formatter={(v) => [Number(v), 'Регистраций']}
                />
                <Area
                  type="monotone"
                  dataKey="count"
                  stroke="#6366f1"
                  strokeWidth={2}
                  fill="url(#colorRegs)"
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </section>

      {/* Распределение */}
      <section className="mb-8">
        <SectionHeading>Распределение</SectionHeading>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {/* Pie chart — типы мероприятий */}
          <div className="bg-white dark:bg-[#131a2e] rounded-2xl border border-slate-200 dark:border-[#1e2740] p-5">
            <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200 mb-4">
              Мероприятия по типам
            </h3>
            {eventTypeData.length === 0 ? (
              <div className="h-48 flex items-center justify-center text-slate-400 text-sm">
                Нет опубликованных мероприятий
              </div>
            ) : (
              <div className="flex flex-col sm:flex-row items-center gap-4">
                <ResponsiveContainer width={200} height={200}>
                  <PieChart>
                    <Pie
                      data={eventTypeData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={88}
                      paddingAngle={2}
                    >
                      {eventTypeData.map((entry, i) => (
                        <Cell key={entry.name} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0', fontSize: 12 }}
                      formatter={(v, name) => [`${Number(v)} шт.`, String(name)]}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <ul className="flex flex-col gap-2 min-w-0">
                  {eventTypeData.map((entry, i) => (
                    <li key={entry.name} className="flex items-center gap-2 text-sm">
                      <span
                        className="w-3 h-3 rounded-full shrink-0"
                        style={{ background: PIE_COLORS[i % PIE_COLORS.length] }}
                      />
                      <span className="text-slate-700 dark:text-slate-300 truncate">{entry.name}</span>
                      <span className="ml-auto font-semibold text-slate-800 dark:text-slate-100 shrink-0">
                        {entry.value}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Bar chart — места по статусам */}
          <div className="bg-white dark:bg-[#131a2e] rounded-2xl border border-slate-200 dark:border-[#1e2740] p-5">
            <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200 mb-4">
              Распределение мест (все мероприятия)
            </h3>
            {publishedEvents.length === 0 ? (
              <div className="h-48 flex items-center justify-center text-slate-400 text-sm">
                Нет опубликованных мероприятий
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={placesData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" className="dark:stroke-[#1e2740]" />
                  <XAxis
                    dataKey="name"
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
                    contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0', fontSize: 12 }}
                    formatter={(v, name) => {
                      const labels: Record<string, string> = {
                        confirmed: 'Подтверждено',
                        waitlist: 'Лист ожидания',
                        free: 'Свободно',
                      }
                      return [Number(v), labels[String(name)] ?? String(name)]
                    }}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: 12 }}
                    formatter={(value) => {
                      const labels: Record<string, string> = {
                        confirmed: 'Подтверждено',
                        waitlist: 'Лист ожидания',
                        free: 'Свободно',
                      }
                      return (
                        <span className="text-slate-600 dark:text-slate-300">
                          {labels[String(value)] ?? value}
                        </span>
                      )
                    }}
                  />
                  <Bar dataKey="confirmed" stackId="a" fill="#6366f1" />
                  <Bar dataKey="waitlist" stackId="a" fill="#a78bfa" />
                  <Bar dataKey="free" stackId="a" fill="#34d399" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </section>

      {/* Мероприятия */}
      <section>
        <SectionHeading>Мероприятия</SectionHeading>
        <div className="bg-white dark:bg-[#131a2e] rounded-2xl border border-slate-200 dark:border-[#1e2740] p-5">
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200 mb-4">
            Топ-5 по записям
          </h3>
          {topEvents.length === 0 ? (
            <p className="text-sm text-slate-400 py-4 text-center">Нет опубликованных мероприятий</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-[#1e2740]">
                    {['Мероприятие', 'Вместимость', 'Записалось', 'Пришло', 'Заполнение', 'Явка'].map(
                      (h) => (
                        <th
                          key={h}
                          className="pb-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide pr-2 text-center first:text-left"
                        >
                          {h}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {topEvents.map((e) => (
                    <EventRow key={e.id} event={e} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
