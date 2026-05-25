import { useMutation } from '@tanstack/react-query'
import { api } from './client'
import type { ScanResponse } from '../types/api'

export const scanQr = (qrToken: string) =>
  api.post<ScanResponse>('/scan', { qr_token: qrToken }).then((r) => r.data)

export function useScan() {
  return useMutation({
    mutationFn: scanQr,
  })
}
