import { useState, useRef, useEffect } from 'react'
import { useChat } from './hooks/useChat'
import { useStatus } from './hooks/useStatus'
import ChatWindow from './components/ChatWindow'
import StatusStrip from './components/StatusStrip'
import DomainTabs from './components/DomainTabs'
import SlashMenu from './components/SlashMenu'

const HINT_CMDS = ['/task', '/blocker', '/done', '/status', '/carry', '/clear', '/summary', '/week']

export default function App() {
  const [input, setInput] = useState('')
  const [showSlashMenu, setShowSlashMenu] = useState(false)
  const [activeTab, setActiveTab] = useState('all')
  const inputRef = useRef(null)

  // Detect if running inside Electron
  const isElectron = typeof window !== 'undefined' && !!window.electronAPI

  const handleHide = () => window.electronAPI?.hideWindow()
  const handleQuit = () => window.electronAPI?.quitApp()

  const { messages, isLoading, sendMessage } = useChat()
  const { stats, connected } = useStatus()

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed || isLoading) return
    sendMessage(trimmed)
    setInput('')
    setShowSlashMenu(false)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
    if (e.key === 'Escape') setShowSlashMenu(false)
  }

  const handleChange = (e) => {
    const val = e.target.value
    setInput(val)
    setShowSlashMenu(val === '/')
  }

  const handleSlashSelect = (cmd) => {
    setInput(cmd + ' ')
    setShowSlashMenu(false)
    inputRef.current?.focus()
  }

  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })

  return (
    <div style={S.app}>
      {/* Header */}
      <div style={S.header}>
        <div style={S.headerLeft}>
          <span style={S.icon}>🧠</span>
          <span style={S.title}>Obsidian Agent</span>
        </div>
        <div style={S.headerRight}>
          <span style={S.date}>{today}</span>
          <span
            style={{
              ...S.badge,
              background: connected ? '#0f2a0f' : '#2a0f0f',
              color: connected ? '#3fb950' : '#f85149',
              borderColor: connected ? '#1f4a1f' : '#5a1f1f',
            }}
          >
            {connected ? '● local' : '○ offline'}
          </span>
          {isElectron && (
            <div style={S.winControls}>
              <button style={S.winBtn} title="Hide (Ctrl+Shift+Space to reopen)" onClick={handleHide}>─</button>
              <button style={{ ...S.winBtn, ...S.winBtnClose }} title="Quit" onClick={handleQuit}>✕</button>
            </div>
          )}
        </div>
      </div>

      {/* Domain Tabs */}
      <DomainTabs activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Status Strip */}
      <StatusStrip stats={stats} />

      {/* Chat */}
      <ChatWindow messages={messages} isLoading={isLoading} activeTab={activeTab} />

      {/* Slash hint chips */}
      <div style={S.hintBar}>
        {HINT_CMDS.map((cmd) => (
          <button
            key={cmd}
            style={S.chip}
            onClick={() => sendMessage(cmd)}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = '#58a6ff'
              e.currentTarget.style.borderColor = '#2d5a8e'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = '#8b949e'
              e.currentTarget.style.borderColor = '#30363d'
            }}
          >
            {cmd}
          </button>
        ))}
      </div>

      {/* Slash autocomplete menu */}
      {showSlashMenu && (
        <SlashMenu onSelect={handleSlashSelect} onClose={() => setShowSlashMenu(false)} />
      )}

      {/* Input row */}
      <div style={S.inputRow}>
        <input
          ref={inputRef}
          style={S.input}
          value={input}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Type or use / commands..."
          disabled={isLoading}
          autoFocus
          onFocus={(e) => (e.currentTarget.style.borderColor = '#58a6ff')}
          onBlur={(e) => (e.currentTarget.style.borderColor = '#30363d')}
        />
        <button
          style={{ ...S.sendBtn, opacity: isLoading || !input.trim() ? 0.35 : 1 }}
          onClick={handleSend}
          disabled={isLoading || !input.trim()}
        >
          {isLoading ? '···' : '➤'}
        </button>
      </div>
    </div>
  )
}

const S = {
  app: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    background: '#0d1117',
    color: '#e6edf3',
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    fontSize: '13px',
    overflow: 'hidden',
    position: 'relative',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 14px',
    borderBottom: '1px solid #30363d',
    background: '#161b22',
    flexShrink: 0,
    WebkitAppRegion: 'drag',
  },
  headerLeft: { display: 'flex', alignItems: 'center', gap: '8px' },
  icon: { fontSize: '16px' },
  title: { fontWeight: 600, fontSize: '14px' },
  headerRight: { display: 'flex', alignItems: 'center', gap: '8px' },
  date: { color: '#8b949e', fontSize: '12px' },
  badge: {
    padding: '2px 8px',
    borderRadius: '10px',
    fontSize: '11px',
    fontWeight: 500,
    border: '1px solid',
  },
  winControls: {
    display: 'flex',
    gap: '2px',
    marginLeft: '4px',
    WebkitAppRegion: 'no-drag',
  },
  winBtn: {
    width: '22px',
    height: '22px',
    background: 'transparent',
    border: 'none',
    borderRadius: '4px',
    color: '#8b949e',
    fontSize: '11px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    outline: 'none',
    transition: 'background 0.1s, color 0.1s',
    padding: 0,
  },
  winBtnClose: {},
  hintBar: {
    display: 'flex',
    gap: '4px',
    padding: '5px 10px',
    overflowX: 'auto',
    borderTop: '1px solid #21262d',
    background: '#0d1117',
    flexShrink: 0,
    scrollbarWidth: 'none',
  },
  chip: {
    padding: '3px 9px',
    background: '#21262d',
    border: '1px solid #30363d',
    borderRadius: '4px',
    color: '#8b949e',
    fontSize: '11px',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
    fontFamily: "'Cascadia Code', 'Fira Code', monospace",
    outline: 'none',
    transition: 'color 0.1s, border-color 0.1s',
  },
  inputRow: {
    display: 'flex',
    gap: '8px',
    padding: '8px 12px',
    borderTop: '1px solid #30363d',
    background: '#161b22',
    flexShrink: 0,
  },
  input: {
    flex: 1,
    padding: '8px 12px',
    background: '#0d1117',
    border: '1px solid #30363d',
    borderRadius: '6px',
    color: '#e6edf3',
    fontSize: '13px',
    outline: 'none',
    fontFamily: 'inherit',
    transition: 'border-color 0.15s',
  },
  sendBtn: {
    padding: '8px 14px',
    background: '#1f6feb',
    border: 'none',
    borderRadius: '6px',
    color: '#fff',
    fontSize: '14px',
    cursor: 'pointer',
    fontWeight: 600,
    outline: 'none',
    transition: 'opacity 0.15s',
    flexShrink: 0,
  },
}
