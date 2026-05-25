import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { Organizer, OrganizerCreate, OrganizerUpdate } from '../types/api'

export const fetchOrganizers = () => api.get<Organizer[]>('/organizers').then((r) => r.data)

export function useOrganizers() {
  return useQuery({
    queryKey: ['organizers'],
    queryFn: fetchOrganizers,
  })
}

export function useCreateOrganizer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: OrganizerCreate) =>
      api.post<Organizer>('/organizers', data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['organizers'] }),
  })
}

export function useUpdateOrganizer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: OrganizerUpdate }) =>
      api.patch<Organizer>(`/organizers/${id}`, data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['organizers'] }),
  })
}

export function useDeleteOrganizer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/organizers/${id}`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['organizers'] }),
  })
}
