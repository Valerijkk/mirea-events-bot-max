import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useEventIdParam } from '../hooks/useEventIdParam'
import { useCreateSlot, useDeleteSlot, useSlots } from '../api/slots'
import { useEvent } from '../api/events'
import { getApiErrorMessage } from '../api/client'
import { formatDateTime, fromDatetimeLocalValue } from '../utils/format'

export function SlotsPage() {
  const eventId = useEventIdParam()

  const { data: event } = useEvent(eventId)
  const { data: slots = [], isLoading, error } = useSlots(eventId)
  const createMutation = useCreateSlot(eventId ?? 0)
  const deleteMutation = useDeleteSlot(eventId ?? 0)

  const [startsAt, setStartsAt] = useState('')
  const [endsAt, setEndsAt] = useState('')
  const [capacity, setCapacity] = useState('10')
  const [label, setLabel] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const handleAdd = async (e: FormEvent) => {
    e.preventDefault()
    setFormError(null)
    try {
      await createMutation.mutateAsync({
        starts_at: fromDatetimeLocalValue(startsAt),
        ends_at: endsAt ? fromDatetimeLocalValue(endsAt) : null,
        capacity: Number(capacity),
        label: label.trim() || null,
      })
      setStartsAt('')
      setEndsAt('')
      setLabel('')
    } catch (err) {
      setFormError(getApiErrorMessage(err, 'Не удалось добавить слот'))
    }
  }

  const handleDelete = async (slotId: number) => {
    if (!window.confirm('Удалить слот?')) return
    try {
      await deleteMutation.mutateAsync(slotId)
    } catch (err) {
      setFormError(getApiErrorMessage(err))
    }
  }

  return (
    <div>
      <Link to={`/events/${eventId}`} className="text-sm text-brand-600 hover:underline">
        ← {event?.title ?? 'Мероприятие'}
      </Link>
      <h1 className="mt-2 text-2xl font-bold">Слоты</h1>

      {isLoading && <p className="mt-4 text-slate-600">Загрузка…</p>}
      {error && <p className="mt-4 text-red-600">{getApiErrorMessage(error)}</p>}

      <ul className="mt-6 space-y-3" data-testid="slots-list">
        {slots.map((slot) => (
          <li
            key={slot.id}
            className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white p-4"
          >
            <div>
              <div className="font-medium">{slot.label ?? 'Слот'}</div>
              <div className="text-sm text-slate-600">
                {formatDateTime(slot.starts_at)}
                {slot.ends_at ? ` — ${formatDateTime(slot.ends_at)}` : ''}
              </div>
              <div className="text-sm text-slate-500">
                Свободно {slot.free_slots} / {slot.capacity}
              </div>
            </div>
            <button
              type="button"
              onClick={() => handleDelete(slot.id)}
              className="text-sm text-red-600 hover:underline"
              data-testid={`btn-delete-slot-${slot.id}`}
            >
              Удалить
            </button>
          </li>
        ))}
        {!isLoading && slots.length === 0 && (
          <li className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-slate-500">
            Слотов пока нет
          </li>
        )}
      </ul>

      <form onSubmit={handleAdd} className="mt-8 rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold">Добавить слот</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="slot-starts" className="mb-1 block text-sm font-medium">
              Начало
            </label>
            <input
              id="slot-starts"
              type="datetime-local"
              required
              value={startsAt}
              onChange={(e) => setStartsAt(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              data-testid="input-slot-starts"
            />
          </div>
          <div>
            <label htmlFor="slot-ends" className="mb-1 block text-sm font-medium">
              Окончание
            </label>
            <input
              id="slot-ends"
              type="datetime-local"
              value={endsAt}
              onChange={(e) => setEndsAt(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              data-testid="input-slot-ends"
            />
          </div>
          <div>
            <label htmlFor="slot-capacity" className="mb-1 block text-sm font-medium">
              Вместимость
            </label>
            <input
              id="slot-capacity"
              type="number"
              required
              min={1}
              value={capacity}
              onChange={(e) => setCapacity(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              data-testid="input-slot-capacity"
            />
          </div>
          <div>
            <label htmlFor="slot-label" className="mb-1 block text-sm font-medium">
              Метка
            </label>
            <input
              id="slot-label"
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              data-testid="input-slot-label"
            />
          </div>
        </div>
        {formError && <p className="mt-3 text-sm text-red-600">{formError}</p>}
        <button
          type="submit"
          disabled={createMutation.isPending}
          className="mt-4 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          data-testid="btn-add-slot"
        >
          Добавить
        </button>
      </form>
    </div>
  )
}
