import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useEventIdParam } from '../hooks/useEventIdParam'
import jsQR from 'jsqr'
import { useScan } from '../api/scan'
import { useEvent } from '../api/events'
import { getApiErrorMessage } from '../api/client'
import type { ScanResponse } from '../types/api'
import { formatDateTime } from '../utils/format'

function resultClasses(status: string): string {
  switch (status) {
    case 'ok':
      return 'border-emerald-300 bg-emerald-50 text-emerald-900'
    case 'already_attended':
      return 'border-amber-300 bg-amber-50 text-amber-900'
    default:
      return 'border-red-300 bg-red-50 text-red-900'
  }
}

export function ScannerPage() {
  const eventId = useEventIdParam()
  const { data: event } = useEvent(eventId)
  const scanMutation = useScan()

  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const scanningRef = useRef(false)
  const unlockTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [manualCode, setManualCode] = useState('')
  const [result, setResult] = useState<ScanResponse | null>(null)
  const [cameraError, setCameraError] = useState<string | null>(null)

  const processScan = useCallback(
    async (token: string) => {
      if (!token.trim() || scanningRef.current) return
      scanningRef.current = true
      try {
        const data = await scanMutation.mutateAsync(token.trim())
        setResult(data)
      } catch (err) {
        setResult({
          ok: false,
          status: 'not_found',
          user_name: null,
          event_title: null,
          attended_at: null,
          error: getApiErrorMessage(err),
        })
      } finally {
        if (unlockTimeoutRef.current) clearTimeout(unlockTimeoutRef.current)
        unlockTimeoutRef.current = setTimeout(() => {
          scanningRef.current = false
        }, 1500)
      }
    },
    [scanMutation],
  )

  useEffect(() => {
    let frameId = 0
    let active = true

    const startCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment' },
        })
        if (!active) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          await videoRef.current.play()
        }
      } catch {
        setCameraError('Камера недоступна — используйте ручной ввод кода')
      }
    }

    let lastTick = 0
    const TICK_INTERVAL = 100 // 10 fps — достаточно для QR, не нагружает CPU

    const tick = (now: number) => {
      frameId = requestAnimationFrame(tick)
      if (now - lastTick < TICK_INTERVAL) return
      lastTick = now

      const video = videoRef.current
      const canvas = canvasRef.current
      if (video && canvas && video.readyState === video.HAVE_ENOUGH_DATA) {
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        const ctx = canvas.getContext('2d')
        if (ctx) {
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
          const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
          const code = jsQR(imageData.data, imageData.width, imageData.height)
          if (code?.data) {
            void processScan(code.data)
          }
        }
      }
    }

    void startCamera()
    frameId = requestAnimationFrame(tick as FrameRequestCallback)

    return () => {
      active = false
      cancelAnimationFrame(frameId)
      streamRef.current?.getTracks().forEach((t) => t.stop())
      if (unlockTimeoutRef.current) clearTimeout(unlockTimeoutRef.current)
    }
  }, [processScan])

  const handleManual = (e: FormEvent) => {
    e.preventDefault()
    void processScan(manualCode)
  }

  return (
    <div>
      <Link to={`/events/${eventId}`} className="text-sm text-brand-600 hover:underline">
        ← {event?.title ?? 'Мероприятие'}
      </Link>
      <h1 className="mt-2 text-2xl font-bold">Сканер QR</h1>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div>
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-black">
            <video ref={videoRef} className="aspect-video w-full object-cover" muted playsInline />
          </div>
          <canvas ref={canvasRef} className="hidden" />
          {cameraError && <p className="mt-2 text-sm text-amber-700">{cameraError}</p>}
        </div>

        <div>
          <form onSubmit={handleManual} className="rounded-xl border border-slate-200 bg-white p-4">
            <label htmlFor="manual-code" className="mb-1 block text-sm font-medium">
              Код записи или QR-токен
            </label>
            <input
              id="manual-code"
              type="text"
              placeholder="RG-XXXXXX"
              value={manualCode}
              onChange={(e) => setManualCode(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono"
              data-testid="input-manual-code"
            />
            <button
              type="submit"
              className="mt-3 rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700"
              data-testid="btn-manual-scan"
            >
              Проверить
            </button>
          </form>

          {result && (
            <div
              className={`mt-4 rounded-xl border p-4 ${resultClasses(result.status)}`}
              data-testid="scanner-result"
            >
              <div className="text-lg font-semibold">
                {result.status === 'ok' && '✅ Пропуск принят'}
                {result.status === 'already_attended' && '⚠️ Уже отмечен'}
                {result.status === 'cancelled' && '🚫 Запись отменена'}
                {result.status === 'not_found' && '❌ Не найдено'}
              </div>
              {result.user_name && <p className="mt-2">{result.user_name}</p>}
              {result.event_title && <p className="text-sm opacity-80">{result.event_title}</p>}
              {result.attended_at && (
                <p className="mt-1 text-sm opacity-80">Первый проход: {formatDateTime(result.attended_at)}</p>
              )}
              {result.error && <p className="mt-2 text-sm">{result.error}</p>}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
