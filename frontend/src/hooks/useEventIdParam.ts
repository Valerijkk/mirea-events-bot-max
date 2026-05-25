import { useParams } from 'react-router-dom'

export function useEventIdParam(): number | undefined {
  const { id } = useParams()
  const n = Number(id)
  return Number.isFinite(n) && n > 0 ? n : undefined
}
