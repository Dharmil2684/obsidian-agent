import { useState, useEffect } from 'react'

const API = 'http://localhost:8000'

export function useFirstRun() {
  const [isFirstRun, setIsFirstRun] = useState(false)
  const [checked, setChecked]       = useState(false)

  useEffect(() => {
    fetch(`${API}/first-run`)
      .then(r => r.json())
      .then(d => {
        setIsFirstRun(d.is_first_run)
        setChecked(true)
      })
      .catch(() => setChecked(true))  // silently skip if backend not ready
  }, [])

  return { isFirstRun, checked }
}
