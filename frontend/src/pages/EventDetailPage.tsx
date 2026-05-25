import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useEventIdParam } from '../hooks/useEventIdParam'
import { Select } from '../components/Select'
import {
  useDeleteEvent,
  useEvent,
  useEventStatus,
  useUpdateEvent,
} from '../api/events'
import { useCancelRegistration, useRegistrations } from '../api/registrations'
import { getApiErrorMessage } from '../api/client'
import { EventForm } from '../components/EventForm'
import { Modal } from '../components/Modal'
import type { EventStatus, EventUpdate, RegistrationStatus } from '../types/api'
import { EVENT_STATUS_LABELS, formatDateTime, REG_STATUS_LABELS } from '../utils/format'

export function EventDetailPage() {
  const eventId = useEventIdParam()
  const navigate = useNavigate()

  const [editOpen, setEditOpen] = useState(false)
  const [statusFilter, setStatusFilter] = useState<RegistrationStatus | ''>('')
  const [codeSearch, setCodeSearch] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)

  const { data: event, isLoading, error } = useEvent(eventId)
  const { data: registrations = [] } = useRegistrations(
    eventId,
    statusFilter ? { status: statusFilter } : {},
  )

  const updateMutation = useUpdateEvent(eventId ?? 0)
  const statusMutation = useEventStatus(eventId ?? 0)
  const deleteMutation = useDeleteEvent()
  const cancelMutation = useCancelRegistration(eventId ?? 0)

  const filteredRegs = useMemo(() => {
    const q = codeSearch.trim().toUpperCase()
    if (!q) return registrations
    return registrations.filter((r) => r.code.toUpperCase().includes(q))
  }, [registrations, codeSearch])

  const handleUpdate = async (data: EventUpdate) => {
    await updateMutation.mutateAsync(data)
    setEditOpen(false)
  }

  const handleStatus = async (status: EventStatus) => {
    setActionError(null)
    try {
      await statusMutation.mutateAsync({ status })
    } catch (err) {
      setActionError(getApiErrorMessage(err))
    }
  }

  const handleDelete = async () => {
    if (!eventId || !window.confirm('Удалить мероприятие без возможности восстановления?')) return
    setActionError(null)
    try {
      await deleteMutation.mutateAsync(eventId)
      navigate('/events')
    } catch (err) {
      setActionError(getApiErrorMessage(err))
    }
  }

  const handleCancelReg = async (regId: number) => {
    if (!window.confirm('Отменить запись участника?')) return
    setActionError(null)
    try {
      await cancelMutation.mutateAsync(regId)
    } catch (err) {
      setActionError(getApiErrorMessage(err))
    }
  }

  if (isLoading) return <p className="text-slate-600">Загрузка…</p>
  if (error || !event) {
    return <p className="text-red-600">{getApiErrorMessage(error, 'Мероприятие не найдено')}</p>
  }

  return (
    <div data-testid="event-detail">
      {/* Cover image */}
      {event.cover_url && (
        <div className="mb-6 rounded-2xl overflow-hidden max-h-56 border border-slate-200">
          <img
            src={event.cover_url}
            alt={event.title}
            className="w-full object-cover max-h-56"
          />
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link to="/events" className="text-sm text-brand-600 hover:underline">
            ← К списку
          </Link>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">{event.title}</h1>
          <p className="mt-1 text-slate-600">{formatDateTime(event.starts_at)}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-800">
              {EVENT_STATUS_LABELS[event.status]}
            </span>
            {!event.registration_open && (
              <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800">
                🚫 Регистрация закрыта
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setEditOpen(true)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
            data-testid="btn-edit-event"
          >
            Редактировать
          </button>
          {event.status === 'draft' && (
            <button
              type="button"
              onClick={() => handleStatus('published')}
              className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm text-white hover:bg-emerald-700"
              data-testid="btn-publish"
            >
              Опубликовать
            </button>
          )}
          {event.status === 'published' && (
            <button
              type="button"
              onClick={() => handleStatus('cancelled')}
              className="rounded-lg bg-amber-600 px-3 py-1.5 text-sm text-white hover:bg-amber-700"
              data-testid="btn-cancel-event"
            >
              Отменить
            </button>
          )}
          <button
            type="button"
            onClick={handleDelete}
            className="rounded-lg bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700"
            data-testid="btn-delete-event"
          >
            Удалить
          </button>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
          <div className="text-xs text-slate-500">Подтверждено</div>
          <div className="text-2xl font-bold tabular-nums">{event.confirmed_count}</div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
          <div className="text-xs text-slate-500">Очередь</div>
          <div className="text-2xl font-bold tabular-nums">{event.waitlist_count}</div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
          <div className="text-xs text-slate-500">Свободно</div>
          <div className="text-2xl font-bold tabular-nums">{event.free_slots}</div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
          <div className="text-xs text-slate-500">Вместимость</div>
          <div className="text-2xl font-bold tabular-nums">{event.capacity}</div>
        </div>
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        <Link
          to={`/events/${event.id}/slots`}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
        >
          Слоты
        </Link>
        <Link
          to={`/events/${event.id}/scanner`}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
        >
          Сканер
        </Link>
        <Link
          to={`/events/${event.id}/broadcasts`}
          className="rounded-lg border border-brand-300 dark:border-brand-700 bg-brand-50 dark:bg-[#1a1f3a] px-3 py-1.5 text-sm text-brand-700 dark:text-brand-300 hover:bg-brand-100 dark:hover:bg-[#1e2b4a]"
        >
          📢 Рассылки
        </Link>
      </div>

      {actionError && <p className="mb-4 text-sm text-red-600">{actionError}</p>}

      <section>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Участники</h2>
          <div className="flex flex-wrap gap-2">
            <div className="w-40">
              <Select
                value={statusFilter}
                onChange={(v) => setStatusFilter(v as RegistrationStatus | '')}
                options={[
                  { value: '',          label: 'Все' },
                  { value: 'confirmed', label: 'Подтверждена' },
                  { value: 'waitlist',  label: 'Очередь' },
                  { value: 'attended',  label: 'Пришёл' },
                ]}
                data-testid="filter-reg-status"
              />
            </div>
            <label htmlFor="input-reg-code" className="sr-only">
              Код записи
            </label>
            <input
              id="input-reg-code"
              type="search"
              placeholder="RG-XXXXXX"
              value={codeSearch}
              onChange={(e) => setCodeSearch(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
              data-testid="input-reg-code-search"
            />
          </div>
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full text-sm" data-testid="participants-table">
            <thead className="bg-slate-50 text-left text-slate-600">
              <tr>
                <th className="px-4 py-3">Код</th>
                <th className="px-4 py-3">Имя</th>
                <th className="px-4 py-3">Статус</th>
                <th className="px-4 py-3">Записан</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {filteredRegs.map((reg) => (
                <tr
                  key={reg.id}
                  className="even:bg-slate-50/50 hover:bg-slate-50"
                >
                  <td className="px-4 py-3 font-mono">{reg.code}</td>
                  <td className="px-4 py-3">{reg.user?.name ?? '—'}</td>
                  <td className="px-4 py-3">{REG_STATUS_LABELS[reg.status] ?? reg.status}</td>
                  <td className="px-4 py-3 text-slate-600">{formatDateTime(reg.registered_at)}</td>
                  <td className="px-4 py-3">
                    {(reg.status === 'confirmed' || reg.status === 'waitlist') && (
                      <button
                        type="button"
                        onClick={() => handleCancelReg(reg.id)}
                        className="text-sm text-red-600 hover:underline"
                        data-testid={`btn-cancel-reg-${reg.id}`}
                      >
                        Отменить
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {filteredRegs.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                    Участников нет
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <Modal open={editOpen} title="Редактировать мероприятие" onClose={() => setEditOpen(false)}>
        <EventForm
          initial={event}
          onSubmit={handleUpdate}
          onCancel={() => setEditOpen(false)}
        />
      </Modal>
    </div>
  )
}
