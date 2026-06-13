import { useState, useCallback } from 'react'

const API_BASE = 'http://localhost:8000'

const WELCOME = {
  id: 0,
  role: 'agent',
  content:
    "👋 Hey! I'm your **Obsidian Agent**.\n\nTell me what you're working on, or try:\n- `/status` — see today's tasks\n- `/task:be Auth API refactor` — add a backend task\n- `/blocker CORS issue on /auth` — log a blocker",
  action: null,
  timestamp: new Date(),
}

export function useChat() {
  const [messages, setMessages] = useState([WELCOME])
  const [isLoading, setIsLoading] = useState(false)

  const sendMessage = useCallback(
    async (text) => {
      if (!text.trim() || isLoading) return

      const userMsg = {
        id: Date.now(),
        role: 'user',
        content: text,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, userMsg])
      setIsLoading(true)

      try {
        const res = await fetch(`${API_BASE}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text }),
        })

        if (!res.ok) {
          const err = await res.json().catch(() => ({}))
          throw new Error(err.detail || `Server error ${res.status}`)
        }

        const data = await res.json()
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            role: 'agent',
            content: data.response,
            action: data.action,
            intent: data.intent,
            domain: data.domain,
            success: data.success,
            timestamp: new Date(),
          },
        ])
      } catch (err) {
        const isOffline = err.message.toLowerCase().includes('fetch') ||
          err.message.toLowerCase().includes('network')
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            role: 'error',
            content: isOffline
              ? '⚠️ Cannot connect to backend. Make sure the Python server is running (`dev.bat`).'
              : `⚠️ ${err.message}`,
            timestamp: new Date(),
          },
        ])
      } finally {
        setIsLoading(false)
      }
    },
    [isLoading],
  )

  // Inject a synthetic agent message (used for onboarding welcome etc.)
  const injectMessage = useCallback((content, role = 'agent') => {
    setMessages(prev => [
      ...prev,
      { id: Date.now(), role, content, action: null, timestamp: new Date() },
    ])
  }, [])

  return { messages, isLoading, sendMessage, injectMessage }
}
