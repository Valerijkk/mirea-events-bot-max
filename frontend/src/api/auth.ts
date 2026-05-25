import { useMutation } from '@tanstack/react-query'
import axios from 'axios'
import { api } from './client'
import type { LoginResponse, Organizer, TokenResponse } from '../types/api'
import { useAuthStore } from '../stores/authStore'

function decodeJwtSub(token: string): number | null {
  try {
    const payload = token.split('.')[1]
    if (!payload) return null
    const decoded = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/'))) as { sub?: string }
    if (!decoded.sub) return null
    return parseInt(decoded.sub, 10)
  } catch {
    return null
  }
}

async function resolveOrganizer(token: string, email: string): Promise<Organizer> {
  const id = decodeJwtSub(token)
  if (!id) {
    throw new Error('Не удалось прочитать токен')
  }

  try {
    const { data } = await api.get<Organizer[]>('/organizers', {
      headers: { Authorization: `Bearer ${token}` },
    })
    const found = data.find((o) => o.id === id)
    if (found) {
      return {
        id: found.id,
        name: found.name,
        email: found.email,
        role: found.role,
        department: found.department,
        created_at: found.created_at,
      }
    }
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.status === 403) {
      // обычный organizer, 403 ожидаем — падбэк к role: 'organizer'
    } else {
      throw err
    }
  }

  return {
    id,
    name: email,
    email,
    role: 'organizer',
  }
}

export async function loginRequest(email: string, password: string): Promise<LoginResponse> {
  const { data } = await api.post<TokenResponse>('/auth/login', { email, password })
  const organizer = await resolveOrganizer(data.access_token, email)
  return { ...data, organizer }
}

export function useLogin() {
  const login = useAuthStore((s) => s.login)

  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      loginRequest(email, password),
    onSuccess: (data) => {
      login(data.access_token, data.organizer)
    },
  })
}

export function useLogout() {
  const logout = useAuthStore((s) => s.logout)

  return useMutation({
    mutationFn: async () => {
      logout()
    },
  })
}
