import { useEffect, useRef } from 'react'

const COMMANDS = [
  { cmd: '/task', hint: '/task [description] — add a task (suffix :be :fe :ds for domain)' },
  { cmd: '/blocker', hint: '/blocker [description] — log a blocker' },
  { cmd: '/done', hint: '/done [description] — complete task or resolve blocker' },
  { cmd: '/status', hint: '/status — show today\'s task counts' },
  { cmd: '/carry', hint: '/carry — move pending tasks to tomorrow' },
  { cmd: '/clear', hint: '/clear — remove all pending tasks from today' },
  { cmd: '/summary', hint: '/summary — generate EOD summary (Phase 3)' },
  { cmd: '/week', hint: '/week — generate weekly summary (Phase 3)' },
]

export default function SlashMenu({ onSelect, onClose }) {
  const ref = useRef(null)

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  return (
    <div ref={ref} style={S.menu}>
      {COMMANDS.map((c) => (
        <button
          key={c.cmd}
          style={S.item}
          onClick={() => onSelect(c.cmd)}
          onMouseEnter={(e) => (e.currentTarget.style.background = '#21262d')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <span style={S.cmd}>{c.cmd}</span>
          <span style={S.hint}>{c.hint.replace(c.cmd + ' ', '')}</span>
        </button>
      ))}
    </div>
  )
}

const S = {
  menu: {
    position: 'absolute',
    bottom: '56px',
    left: '12px',
    right: '12px',
    background: '#161b22',
    border: '1px solid #30363d',
    borderRadius: '8px',
    overflow: 'hidden',
    boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
    zIndex: 100,
  },
  item: {
    display: 'flex',
    alignItems: 'baseline',
    gap: '10px',
    width: '100%',
    padding: '8px 12px',
    background: 'transparent',
    border: 'none',
    cursor: 'pointer',
    textAlign: 'left',
    transition: 'background 0.1s',
    outline: 'none',
  },
  cmd: {
    color: '#58a6ff',
    fontFamily: "'Cascadia Code', 'Fira Code', monospace",
    fontSize: '12px',
    fontWeight: 600,
    minWidth: '70px',
  },
  hint: { color: '#8b949e', fontSize: '11px', lineHeight: 1.3 },
}
