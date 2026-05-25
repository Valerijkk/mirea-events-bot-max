import axios from 'axios'
import { useAuthStore } from '../stores/authStore'

export const api = axios.create({ baseURL: '/api/v1' })

api.interceptors.request.use((cfg) => {
  const token = useAuthStore.getState().token
  if (token) {
    cfg.headers.Authorization = `Bearer ${token}`
  }
  return cfg
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    // Не редиректим на /login если сам запрос логина вернул 401 (неверный пароль)
    const isLoginRequest = err.config?.url?.includes('/auth/login')
    if (err.response?.status === 401 && !isLoginRequest) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

export function getApiErrorMessage(err: unknown, fallback = 'Ошибка запроса'): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d: { msg?: string }) => d.msg ?? String(d)).join('; ')
  }
  return fallback
}
