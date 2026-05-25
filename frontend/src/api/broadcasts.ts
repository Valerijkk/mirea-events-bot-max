import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'

export type BroadcastSegment = 'all' | 'confirmed' | 'waitlist' | 'attended' | 'no_show'

export interface BroadcastRead {
  id: number
  event_id: number
  organizer_id: number | null
  segment: BroadcastSegment
  message_text: string
  sent_at: string | null
  delivered_count: number
  failed_count: number
  created_at: string
}

export interface BroadcastRequest {
  segment: BroadcastSegment
  message: string
}

export interface BroadcastResult {
  broadcast: BroadcastRead
}

export function useBroadcasts(eventId: number) {
  return useQuery<BroadcastRead[]>({
    queryKey: ['broadcasts', eventId],
    queryFn: () => api.get<BroadcastRead[]>(`/events/${eventId}/broadcasts`).then((r) => r.data),
    enabled: !!eventId,
  })
}

export function useSendBroadcast(eventId: number) {
  const qc = useQueryClient()
  return useMutation<BroadcastResult, Error, BroadcastRequest>({
    mutationFn: (payload) =>
      api.post<BroadcastResult>(`/events/${eventId}/broadcasts`, payload).then((r) => r.data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['broadcasts', eventId] })
    },
  })
}
