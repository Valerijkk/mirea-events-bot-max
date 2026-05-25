import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  Event,
  EventCreate,
  EventFilters,
  EventStatusUpdate,
  EventUpdate,
} from '../types/api'

function buildEventParams(filters: EventFilters): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  if (filters.type) params.set('type', filters.type)
  if (filters.format) params.set('format', filters.format)
  if (filters.only_upcoming) params.set('only_upcoming', 'true')
  return params
}

export const fetchEvents = (filters: EventFilters = {}) =>
  api
    .get<Event[]>('/events', { params: buildEventParams(filters) })
    .then((r) => r.data)

export const fetchEvent = (id: number) =>
  api.get<Event>(`/events/${id}`).then((r) => r.data)

export function useEvents(filters: EventFilters = {}) {
  return useQuery({
    queryKey: ['events', filters],
    queryFn: () => fetchEvents(filters),
  })
}

export function useEvent(id: number | undefined) {
  return useQuery({
    queryKey: ['events', id],
    queryFn: () => fetchEvent(id!),
    enabled: id !== undefined,
  })
}

export function useCreateEvent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: EventCreate) => api.post<Event>('/events', data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['events'] }),
  })
}

export function useUpdateEvent(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: EventUpdate) =>
      api.patch<Event>(`/events/${id}`, data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['events'] })
      qc.invalidateQueries({ queryKey: ['events', id] })
    },
  })
}

export function useDeleteEvent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/events/${id}`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['events'] }),
  })
}

export function useEventStatus(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: EventStatusUpdate) =>
      api.post<Event>(`/events/${id}/status`, data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['events'] })
      qc.invalidateQueries({ queryKey: ['events', id] })
    },
  })
}
