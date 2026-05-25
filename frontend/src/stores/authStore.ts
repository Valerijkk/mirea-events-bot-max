import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Organizer } from '../types/api'

interface AuthState {
  token: string | null
  organizer: Organizer | null
  login: (token: string, organizer: Organizer) => void
  logout: () => void
  isAdmin: () => boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      organizer: null,
      login: (token, organizer) => set({ token, organizer }),
      logout: () => set({ token: null, organizer: null }),
      isAdmin: () => get().organizer?.role === 'admin',
    }),
    { name: 'mirea-auth' },
  ),
)
