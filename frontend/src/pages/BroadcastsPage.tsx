import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useEventIdParam } from '../hooks/useEventIdParam'
import { useBroadcasts, useSendBroadcast, type BroadcastSegment } from '../api/broadcasts'
import { useEvent } from '../api/events'
import { getApiErrorMessage } from '../api/client'
import { Select } from '../components/Select'
import { formatDateTime } from '../utils/format'

const SEGMENT_LABELS: Record<BroadcastSegment, string> = {
  all:       'Все (подтверждённые + очередь)',
  confirmed: 'Подтверждённые',
  waitlist:  'Лист ожидания',
  attended:  'Пришедшие',
  no_show:   'Не явившиеся',
}

const SEGMENT_BADGE: Record<BroadcastSegment, string> = {
  all:       'bg-brand-50 text-brand-700 dark:bg-[#1a1f3a] dark:text-brand-300',
  confirmed: 'bg-emerald-50 text-emerald-700',
  waitlist:  'bg-amber-50 text-amber-700',
  attended:  'bg-slate-100 text-slate-600',
  no_show:   'bg-red-50 text-red-700',
}

const TEMPLATES = [
  { label: 'Перенос аудитории', text: 'Внимание! Аудитория мероприятия переносится. Уточните актуальное место на сайте.' },
  { label: 'Изменение времени', text: 'Внимание! Время начала мероприятия изменено. Следите за актуальной информацией.' },
  { label: 'Ссылка на трансляцию', text: 'Ссылка для подключения к онлайн-трансляции: ' },
  { label: 'Напоминание за час', text: 'Напоминаем: мероприятие начнётся через 1 час. Ждём вас!' },
  { label: 'Напоминание за день', text: 'Напоминаем: мероприятие пройдёт завтра. Не забудьте взять документы.' },
]

export function BroadcastsPage() {
  const eventId = useEventIdParam()
  const { data: event } = useEvent(eventId)
  const { data: broadcasts = [], isLoading } = useBroadcasts(eventId ?? 0)
  const sendMutation = useSendBroadcast(eventId ?? 0)

  const [segment, setSegment] = useState<BroadcastSegment>('confirmed')
  const [message, setMessage] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<{ delivered: number; failed: number } | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!message.trim()) return
    setError(null)
    setLastResult(null)
    try {
      const result = await sendMutation.mutateAsync({ segment, message: message.trim() })
      setLastResult({
        delivered: result.broadcast.delivered_count,
        failed: result.broadcast.failed_count,
      })
      setMessage('')
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось отправить рассылку'))
    }
  }

  return (
    <div>
      <div className="mb-8">
        <Link to={`/events/${eventId}`} className="text-sm text-brand-600 hover:underline">
          ← {event?.title ?? 'Мероприятие'}
        </Link>
        <h1 className="mt-2 text-3xl font-bold text-slate-900 tracking-tight">Рассылки</h1>
        <p className="text-slate-500 mt-1">Отправьте сообщение участникам сегментированно.</p>
      </div>

      <div className="grid gap-8 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-[var(--shadow-soft)]">
            <h2 className="text-lg font-semibold text-slate-900 mb-5">Новая рассылка</h2>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Получатели
                </label>
                <Select
                  value={segment}
                  onChange={(v) => setSegment(v as BroadcastSegment)}
                  options={Object.entries(SEGMENT_LABELS).map(([value, label]) => ({ value, label }))}
                  data-testid="select-broadcast-segment"
                />
              </div>

              <div>
                <p className="mb-2 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Шаблоны
                </p>
                <div className="flex flex-wrap gap-2">
                  {TEMPLATES.map((t) => (
                    <button
                      key={t.label}
                      type="button"
                      onClick={() => setMessage(t.text)}
                      className="px-3 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-[#344063] text-slate-600 dark:text-slate-300 hover:bg-brand-50 dark:hover:bg-[#1a1f3a] hover:border-brand-300 hover:text-brand-700 transition-colors"
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label htmlFor="broadcast-message" className="mb-1.5 block text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Текст сообщения
                </label>
                <textarea
                  id="broadcast-message"
                  rows={6}
                  required
                  maxLength={4000}
                  placeholder="Введите текст рассылки…"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 dark:border-[#344063] bg-white dark:bg-[#1a2238] text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 px-4 py-3 text-sm focus:outline-none focus:border-brand-500 transition-colors resize-none"
                  data-testid="input-broadcast-message"
                />
                <div className="mt-1 flex justify-between text-xs text-slate-400">
                  <span>Поддерживается базовый Markdown</span>
                  <span className={message.length > 3800 ? 'text-amber-600' : ''}>{message.length} / 4000</span>
                </div>
              </div>

              {error && (
                <p className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-[#2e0a0a] px-4 py-3 rounded-xl">
                  {error}
                </p>
              )}

              {lastResult && (
                <div className="bg-emerald-50 dark:bg-[#062e1f] border border-emerald-200 dark:border-[#14532d] rounded-xl px-4 py-3">
                  <p className="text-sm font-semibold text-emerald-700 dark:text-emerald-400 mb-1">
                    ✅ Рассылка отправлена
                  </p>
                  <p className="text-xs text-emerald-600 dark:text-emerald-500">
                    Доставлено: {lastResult.delivered} · Ошибок: {lastResult.failed}
                  </p>
                </div>
              )}

              <button
                type="submit"
                disabled={sendMutation.isPending || !message.trim()}
                className="w-full rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-semibold py-3 text-sm shadow-[var(--shadow-glow)] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="btn-send-broadcast"
              >
                {sendMutation.isPending
                  ? 'Отправка…'
                  : `Отправить → ${SEGMENT_LABELS[segment]}`}
              </button>
            </form>
          </div>
        </div>

        <div className="lg:col-span-2">
          <div className="rounded-2xl border border-slate-200 bg-white shadow-[var(--shadow-soft)] overflow-hidden dark:border-slate-700 dark:bg-slate-900">
            <div className="border-b border-slate-100 px-5 py-4 dark:border-slate-700">
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">История</h2>
            </div>
            {isLoading && <p className="px-5 py-6 text-sm text-slate-500 dark:text-slate-400">Загрузка…</p>}
            {!isLoading && broadcasts.length === 0 && (
              <p className="px-5 py-8 text-center text-sm text-slate-400 dark:text-slate-500">
                Рассылок ещё не было
              </p>
            )}
            <ul className="divide-y divide-slate-100 dark:divide-slate-700">
              {broadcasts.map((bc) => (
                <li key={bc.id} className="px-5 py-4">
                  <div className="mb-2 flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SEGMENT_BADGE[bc.segment]}`}>
                      {SEGMENT_LABELS[bc.segment]}
                    </span>
                    <span className="ml-auto text-xs text-slate-400 whitespace-nowrap dark:text-slate-500">
                      {formatDateTime(bc.created_at)}
                    </span>
                  </div>
                  <p className="mb-2 line-clamp-2 text-sm text-slate-700 dark:text-slate-300">
                    {bc.message_text}
                  </p>
                  <div className="flex gap-3 text-xs text-slate-500 dark:text-slate-400">
                    <span className="text-emerald-600 dark:text-emerald-400">
                      ✓ {bc.delivered_count} доставлено
                    </span>
                    {bc.failed_count > 0 && (
                      <span className="text-red-500 dark:text-red-400">✗ {bc.failed_count} ошибок</span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
