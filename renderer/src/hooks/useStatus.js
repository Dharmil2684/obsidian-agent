import { useState, useEffect, useCallback } from 'react'

const API_BASE = 'http://localhost:8000'
const POLL_MS = 10_000

export function useStatus() {
  const [stats, setStats] = useState({ tasks: 0, completed: 0, blockers: 0 })
  const [connected, setConnected] = useState(false)

  const fetch_status = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/status`, { signal: AbortSignal.timeout(3000) })
      if (res.ok) {
        const data = await res.json()
        setStats(data.stats ?? { tasks: 0, completed: 0, blockers: 0 })
        setConnected(true)
      } else {
        setConnected(false)
      }
    } catch {
      setConnected(false)
    }
  }, [])

  useEffect(() => {
    fetch_status()
    const id = setInterval(fetch_status, POLL_MS)
    return () => clearInterval(id)
  }, [fetch_status])

  return { stats, connected, refresh: fetch_status }
}
