import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { Registration, RegistrationFilters } from '../types/api'

function buildRegParams(filters: RegistrationFilters): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  return params
}

export const fetchRegistrations = (eventId: number, filters: RegistrationFilters = {}) =>
  api
    .get<Registration[]>(`/events/${eventId}/registrations`, {
      params: buildRegParams(filters),
    })
    .then((r) => r.data)

export function useRegistrations(
  eventId: number | undefined,
  filters: RegistrationFilters = {},
  refetchInterval?: number,
) {
  return useQuery({
    queryKey: ['registrations', eventId, filters],
    queryFn: () => fetchRegistrations(eventId!, filters),
    enabled: eventId !== undefined,
    refetchInterval,
  })
}

export function useCancelRegistration(eventId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (regId: number) =>
      api.post(`/events/${eventId}/registrations/${regId}/cancel`).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['registrations', eventId] })
      qc.invalidateQueries({ queryKey: ['event-stats', eventId] })
      qc.invalidateQueries({ queryKey: ['events', eventId] })
    },
  })
}
