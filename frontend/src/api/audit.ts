import { useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { AuditFilters, AuditLogPage } from '../types/api'

function buildAuditParams(filters: AuditFilters): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.page) params.set('page', String(filters.page))
  if (filters.per_page) params.set('per_page', String(filters.per_page))
  if (filters.event_type) params.set('event_type', filters.event_type)
  if (filters.entity_type) params.set('entity_type', filters.entity_type)
  if (filters.entity_id != null) params.set('entity_id', String(filters.entity_id))
  if (filters.date_from) params.set('date_from', filters.date_from)
  if (filters.date_to) params.set('date_to', filters.date_to)
  return params
}

export const fetchAuditLogs = (filters: AuditFilters = {}) =>
  api
    .get<AuditLogPage>('/audit-logs', { params: buildAuditParams(filters) })
    .then((r) => r.data)

export function useAuditLogs(filters: AuditFilters = {}) {
  return useQuery({
    queryKey: ['audit', filters],
    queryFn: () => fetchAuditLogs(filters),
  })
}
