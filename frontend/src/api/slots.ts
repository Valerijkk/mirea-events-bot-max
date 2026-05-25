import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { Slot, SlotCreate } from '../types/api'

export const fetchSlots = (eventId: number) =>
  api.get<Slot[]>(`/events/${eventId}/slots`).then((r) => r.data)

export function useSlots(eventId: number | undefined) {
  return useQuery({
    queryKey: ['slots', eventId],
    queryFn: () => fetchSlots(eventId!),
    enabled: eventId !== undefined,
  })
}

export function useCreateSlot(eventId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: SlotCreate) =>
      api.post<Slot>(`/events/${eventId}/slots`, data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['slots', eventId] }),
  })
}

export function useDeleteSlot(eventId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (slotId: number) =>
      api.delete(`/events/${eventId}/slots/${slotId}`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['slots', eventId] }),
  })
}
