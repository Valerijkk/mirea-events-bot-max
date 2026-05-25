import { useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { EventStats, GlobalStats, RegsByDay } from '../types/api'

export const fetchEventStats = (eventId: number) =>
  api.get<EventStats>(`/events/${eventId}/stats`).then((r) => r.data)

export function useEventStats(eventId: number | undefined, refetchInterval?: number) {
  return useQuery({
    queryKey: ['event-stats', eventId],
    queryFn: () => fetchEventStats(eventId!),
    enabled: eventId !== undefined,
    refetchInterval,
  })
}

export const fetchGlobalStats = () =>
  api.get<GlobalStats>('/stats').then((r) => r.data)

export function useGlobalStats() {
  return useQuery({
    queryKey: ['global-stats'],
    queryFn: fetchGlobalStats,
    refetchInterval: 30_000,
  })
}

export const fetchRegsByDay = (days = 30) =>
  api.get<RegsByDay[]>('/stats/registrations-by-day', { params: { days } }).then((r) => r.data)

export function useRegsByDay(days = 30) {
  return useQuery({
    queryKey: ['regs-by-day', days],
    queryFn: () => fetchRegsByDay(days),
    refetchInterval: 60_000,
  })
}
