import { useState, type FormEvent } from 'react'
import type { Event, EventCreate, EventFormat, EventType, EventUpdate } from '../types/api'
import { fromDatetimeLocalValue, toDatetimeLocalValue } from '../utils/format'
import { Select } from './Select'

interface EventFormProps {
  initial?: Event
  onSubmit: (data: EventCreate | EventUpdate) => Promise<void>
  onCancel: () => void
  submitLabel?: string
}

const defaultValues: EventCreate = {
  title: '',
  description: '',
  event_type: 'other',
  starts_at: new Date().toISOString(),
  capacity: 50,
  format: 'onsite',
  late_cancel_policy: 'disallow',
  max_entries: 1,
}

const fieldCls = 'w-full rounded-xl border border-slate-300 bg-white dark:bg-[#1a2238] dark:border-[#344063] text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 px-3 py-2.5 text-sm focus:outline-none focus:border-brand-500 dark:focus:border-brand-400 transition-colors'
const labelCls = 'mb-1.5 block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide'

export function EventForm({ initial, onSubmit, onCancel, submitLabel = 'Сохранить' }: EventFormProps) {
  const [title, setTitle] = useState(initial?.title ?? defaultValues.title)
  const [description, setDescription] = useState(initial?.description ?? '')
  const [eventType, setEventType] = useState<EventType>(initial?.event_type ?? 'other')
  const [startsAt, setStartsAt] = useState(
    toDatetimeLocalValue(initial?.starts_at ?? defaultValues.starts_at),
  )
  const [endsAt, setEndsAt] = useState(toDatetimeLocalValue(initial?.ends_at))
  const [location, setLocation] = useState(initial?.location ?? '')
  const [capacity, setCapacity] = useState(String(initial?.capacity ?? defaultValues.capacity))
  const [format, setFormat] = useState<EventFormat>(initial?.format ?? 'onsite')
  const [meetingUrl, setMeetingUrl] = useState(initial?.meeting_url ?? '')
  const [coverUrl, setCoverUrl] = useState(initial?.cover_url ?? '')
  const [requirements, setRequirements] = useState(initial?.requirements ?? '')
  const [cancellationTerms, setCancellationTerms] = useState(initial?.cancellation_terms ?? '')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    const cap = Number(capacity)
    if (!Number.isFinite(cap) || cap < 1) {
      setError('Вместимость должна быть положительным числом')
      return
    }
    setLoading(true)
    try {
      const payload: EventCreate | EventUpdate = {
        title: title.trim(),
        description: description.trim() || null,
        event_type: eventType,
        starts_at: fromDatetimeLocalValue(startsAt),
        ends_at: endsAt ? fromDatetimeLocalValue(endsAt) : null,
        location: location.trim() || null,
        capacity: cap,
        format,
        meeting_url: meetingUrl.trim() || null,
        cover_url: coverUrl.trim() || null,
        requirements: requirements.trim() || null,
        cancellation_terms: cancellationTerms.trim() || null,
      }
      await onSubmit(payload)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось сохранить')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
      <div>
        <label htmlFor="event-title" className={labelCls}>Название *</label>
        <input
          id="event-title"
          type="text"
          required
          minLength={3}
          placeholder="Например: День открытых дверей МИРЭА"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className={fieldCls}
          data-testid="input-event-title"
        />
      </div>

      <div>
        <label htmlFor="event-description" className={labelCls}>Описание</label>
        <textarea
          id="event-description"
          rows={3}
          placeholder="Краткое описание мероприятия для участников…"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className={fieldCls}
          data-testid="input-event-description"
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className={labelCls}>Тип</label>
          <Select
            value={eventType}
            onChange={(v) => setEventType(v as typeof eventType)}
            options={[
              { value: 'open_day',     label: 'День открытых дверей' },
              { value: 'masterclass',  label: 'Мастер-класс' },
              { value: 'olympiad',     label: 'Олимпиада' },
              { value: 'tour',         label: 'Экскурсия' },
              { value: 'consultation', label: 'Консультация' },
              { value: 'other',        label: 'Другое' },
            ]}
            data-testid="select-event-type"
          />
        </div>
        <div>
          <label className={labelCls}>Формат</label>
          <Select
            value={format}
            onChange={(v) => setFormat(v as typeof format)}
            options={[
              { value: 'onsite', label: '📍 Очно' },
              { value: 'online', label: '💻 Онлайн' },
            ]}
            data-testid="select-event-format"
          />
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="event-starts" className={labelCls}>Начало *</label>
          <input
            id="event-starts"
            type="datetime-local"
            required
            value={startsAt}
            onChange={(e) => setStartsAt(e.target.value)}
            className={fieldCls}
            data-testid="input-event-starts"
          />
        </div>
        <div>
          <label htmlFor="event-ends" className={labelCls}>Окончание</label>
          <input
            id="event-ends"
            type="datetime-local"
            value={endsAt}
            onChange={(e) => setEndsAt(e.target.value)}
            className={fieldCls}
            data-testid="input-event-ends"
          />
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="event-location" className={labelCls}>Место</label>
          <input
            id="event-location"
            type="text"
            placeholder="А-105, корпус МИРЭА"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className={fieldCls}
            data-testid="input-event-location"
          />
        </div>
        <div>
          <label htmlFor="event-capacity" className={labelCls}>Вместимость *</label>
          <input
            id="event-capacity"
            type="number"
            required
            min={1}
            value={capacity}
            onChange={(e) => setCapacity(e.target.value)}
            className={fieldCls}
            data-testid="input-event-capacity"
          />
        </div>
      </div>

      {format === 'online' && (
        <div>
          <label htmlFor="event-meeting-url" className={labelCls}>Ссылка на подключение</label>
          <input
            id="event-meeting-url"
            type="url"
            placeholder="https://zoom.us/j/..."
            value={meetingUrl}
            onChange={(e) => setMeetingUrl(e.target.value)}
            className={fieldCls}
            data-testid="input-event-meeting-url"
          />
        </div>
      )}

      <div>
        <label htmlFor="event-cover-url" className={labelCls}>
          Обложка (URL изображения или видео)
        </label>
        <input
          id="event-cover-url"
          type="url"
          placeholder="https://example.com/cover.jpg"
          value={coverUrl}
          onChange={(e) => setCoverUrl(e.target.value)}
          className={fieldCls}
          data-testid="input-event-cover-url"
        />
        {coverUrl && (
          <div className="mt-2 rounded-xl overflow-hidden border border-slate-200 dark:border-[#344063] max-h-32">
            <img
              src={coverUrl}
              alt="Обложка"
              className="w-full object-cover max-h-32"
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
            />
          </div>
        )}
        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
          Вставьте прямую ссылку на картинку (jpg, png, webp) или видео-превью
        </p>
      </div>

      <div>
        <label htmlFor="event-requirements" className={labelCls}>Требования к участникам</label>
        <textarea
          id="event-requirements"
          rows={2}
          placeholder="Студенческий билет, паспорт…"
          value={requirements}
          onChange={(e) => setRequirements(e.target.value)}
          className={fieldCls}
          data-testid="input-event-requirements"
        />
      </div>

      <div>
        <label htmlFor="event-cancellation-terms" className={labelCls}>Условия отмены записи</label>
        <textarea
          id="event-cancellation-terms"
          rows={2}
          placeholder="Отмена за 24 часа до начала…"
          value={cancellationTerms}
          onChange={(e) => setCancellationTerms(e.target.value)}
          className={fieldCls}
          data-testid="input-event-cancellation-terms"
        />
      </div>

      {error && (
        <p className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-[#2e0a0a] px-3 py-2 rounded-lg">
          {error}
        </p>
      )}

      <div className="flex justify-end gap-2 pt-2 border-t border-slate-100 dark:border-[#1e2740]">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-xl border border-slate-300 dark:border-[#344063] px-4 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-[#1a2238] transition-colors"
        >
          Отмена
        </button>
        <button
          type="submit"
          disabled={loading}
          className="rounded-xl bg-brand-600 hover:bg-brand-700 px-4 py-2 text-sm font-medium text-white shadow-[var(--shadow-glow)] disabled:opacity-50 transition-all"
          data-testid="btn-save-event"
        >
          {loading ? 'Сохранение…' : submitLabel}
        </button>
      </div>
    </form>
  )
}
