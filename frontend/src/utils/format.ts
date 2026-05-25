export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleTimeString('ru-RU')
}

export function toDatetimeLocalValue(value: string | null | undefined): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function fromDatetimeLocalValue(value: string): string {
  return new Date(value).toISOString()
}

export const EVENT_STATUS_LABELS: Record<string, string> = {
  draft: 'Черновик',
  published: 'Опубликовано',
  cancelled: 'Отменено',
  finished: 'Завершено',
}

export const REG_STATUS_LABELS: Record<string, string> = {
  confirmed: 'Подтверждена',
  waitlist: 'Очередь',
  cancelled: 'Отменена',
  late_cancelled: 'Поздняя отмена',
  cancelled_by_organizer: 'Отменена организатором',
  attended: 'Пришёл',
  no_show: 'Не пришёл',
}

export const EVENT_TYPE_LABELS: Record<string, string> = {
  open_day: 'День открытых дверей',
  masterclass: 'Мастер-класс',
  olympiad: 'Олимпиада',
  tour: 'Экскурсия',
  consultation: 'Консультация',
  other: 'Другое',
}
