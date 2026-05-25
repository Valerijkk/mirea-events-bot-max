export type EventType =
  | 'open_day'
  | 'masterclass'
  | 'olympiad'
  | 'tour'
  | 'consultation'
  | 'other'

export type EventStatus = 'draft' | 'published' | 'cancelled' | 'finished'

export type EventFormat = 'online' | 'onsite'

export type LateCancelPolicy = 'disallow' | 'allow_marked'

export interface Event {
  id: number
  title: string
  description: string | null
  event_type: EventType
  starts_at: string
  ends_at: string | null
  location: string | null
  cover_url: string | null
  capacity: number
  duration_minutes: number | null
  format: EventFormat
  requirements: string | null
  cancellation_terms: string | null
  meeting_url: string | null
  late_cancel_policy: LateCancelPolicy
  max_entries: number
  status: EventStatus
  organizer_id: number | null
  deeplink_payload: string
  free_slots: number
  confirmed_count: number
  waitlist_count: number
  registration_open: boolean
  created_at: string
  updated_at: string
}

export interface EventCreate {
  title: string
  description?: string | null
  event_type?: EventType
  starts_at: string
  ends_at?: string | null
  location?: string | null
  cover_url?: string | null
  capacity: number
  duration_minutes?: number | null
  format?: EventFormat
  requirements?: string | null
  cancellation_terms?: string | null
  meeting_url?: string | null
  late_cancel_policy?: LateCancelPolicy
  max_entries?: number
}

export interface EventUpdate {
  title?: string
  description?: string | null
  event_type?: EventType
  starts_at?: string
  ends_at?: string | null
  location?: string | null
  cover_url?: string | null
  capacity?: number
  duration_minutes?: number | null
  format?: EventFormat
  requirements?: string | null
  cancellation_terms?: string | null
  meeting_url?: string | null
  late_cancel_policy?: LateCancelPolicy
  registration_open?: boolean
  max_entries?: number
}

export interface EventStatusUpdate {
  status: EventStatus
}

export interface Slot {
  id: number
  event_id: number
  starts_at: string
  ends_at: string | null
  capacity: number
  label: string | null
  free_slots: number
  created_at: string
}

export interface SlotCreate {
  starts_at: string
  ends_at?: string | null
  capacity: number
  label?: string | null
}

export type RegistrationStatus =
  | 'confirmed'
  | 'waitlist'
  | 'cancelled'
  | 'late_cancelled'
  | 'cancelled_by_organizer'
  | 'attended'
  | 'no_show'

export interface User {
  max_user_id: number
  name: string | null
  notifications_enabled: boolean
  first_seen: string
  last_active: string
}

export interface Registration {
  id: number
  event_id: number
  user_id: number
  status: RegistrationStatus
  code: string
  waitlist_position: number | null
  registered_at: string
  cancelled_at: string | null
  attended_at: string | null
  user: User | null
}

export type OrganizerRole = 'admin' | 'organizer'

export interface Organizer {
  id: number
  name: string | null
  email: string
  role: OrganizerRole
  department?: string | null
  created_at?: string
}

export interface OrganizerCreate {
  name?: string | null
  email: string
  password: string
  role?: OrganizerRole
  department?: string | null
}

export interface OrganizerUpdate {
  name?: string | null
  email?: string
  password?: string
  role?: OrganizerRole
  department?: string | null
}

export interface AuditLog {
  id: number
  created_at: string
  actor_type: string
  organizer_id: number | null
  user_id: number | null
  actor_display: string | null
  event_type: string
  entity_type: string | null
  entity_id: number | null
  payload: Record<string, unknown> | null
  ip_address: string | null
  user_agent: string | null
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

export type AuditLogPage = Page<AuditLog>

export interface ScanResponse {
  ok: boolean
  status: 'ok' | 'already_attended' | 'cancelled' | 'not_found'
  user_name: string | null
  event_title: string | null
  attended_at: string | null
  error: string | null
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface LoginResponse extends TokenResponse {
  organizer: Organizer
}

export interface EventStats {
  event_id: number
  confirmed: number
  waitlist: number
  cancelled: number
  attended: number
  capacity: number
  fill_rate: number
  attendance_rate: number | null
}

export interface GlobalStats {
  total_users: number
  total_events: number
  published_events: number
  total_registrations: number
  active_registrations: number
  attended_total: number
}

export interface RegsByDay {
  date: string
  count: number
}

export interface MessageResponse {
  ok: boolean
  message: string | null
}

export interface EventFilters {
  status?: EventStatus
  type?: EventType
  format?: EventFormat
  only_upcoming?: boolean
}

export interface RegistrationFilters {
  status?: RegistrationStatus
}

export interface AuditFilters {
  page?: number
  per_page?: number
  event_type?: string
  entity_type?: string
  entity_id?: number
  /** Только клиентская фильтрация — backend не принимает actor_type. */
  actor_type?: string
  date_from?: string
  date_to?: string
}
