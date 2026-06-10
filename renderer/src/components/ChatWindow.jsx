import { useEffect, useRef } from 'react'

// Very lightweight markdown → JSX without a library
function InlineMarkdown({ text }) {
  // Split on **bold**, *italic*, `code`, and newlines
  const parts = []
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g
  let last = 0
  let m
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) parts.push({ type: 'text', val: text.slice(last, m.index) })
    const raw = m[0]
    if (raw.startsWith('**')) parts.push({ type: 'bold', val: raw.slice(2, -2) })
    else if (raw.startsWith('*')) parts.push({ type: 'italic', val: raw.slice(1, -1) })
    else parts.push({ type: 'code', val: raw.slice(1, -1) })
    last = m.index + raw.length
  }
  if (last < text.length) parts.push({ type: 'text', val: text.slice(last) })

  return (
    <>
      {parts.map((p, i) => {
        if (p.type === 'bold') return <strong key={i}>{p.val}</strong>
        if (p.type === 'italic') return <em key={i}>{p.val}</em>
        if (p.type === 'code') return <code key={i} style={S.inlineCode}>{p.val}</code>
        return <span key={i}>{p.val}</span>
      })}
    </>
  )
}

function MessageContent({ text }) {
  const lines = text.split('\n')
  return (
    <div>
      {lines.map((line, i) => {
        if (line.startsWith('- ')) {
          return (
            <div key={i} style={S.listItem}>
              <span style={S.bullet}>•</span>
              <InlineMarkdown text={line.slice(2)} />
            </div>
          )
        }
        if (line.trim() === '') return <div key={i} style={{ height: '6px' }} />
        return (
          <div key={i}>
            <InlineMarkdown text={line} />
          </div>
        )
      })}
    </div>
  )
}

const DOMAIN_FILTER = { all: null, backend: 'backend', frontend: 'frontend', data_science: 'data_science' }

export default function ChatWindow({ messages, isLoading, activeTab }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const filtered = messages.filter((msg) => {
    if (activeTab === 'all') return true
    if (msg.role === 'user' || msg.role === 'error') return true
    const target = DOMAIN_FILTER[activeTab]
    return !target || msg.domain === target || !msg.domain
  })

  return (
    <div style={S.window}>
      {filtered.map((msg) => (
        <div key={msg.id} style={S.msgWrapper}>
          {msg.role === 'user' && (
            <div style={S.userRow}>
              <div style={S.userBubble}>
                <MessageContent text={msg.content} />
              </div>
              <span style={S.time}>{fmt(msg.timestamp)}</span>
            </div>
          )}

          {msg.role === 'error' && (
            <div style={S.errorRow}>
              <div style={S.errorBubble}>
                <MessageContent text={msg.content} />
              </div>
            </div>
          )}

          {msg.role === 'agent' && (
            <div style={S.agentRow}>
              <span style={S.avatar}>🧠</span>
              <div style={S.agentContent}>
                <div style={S.agentBubble}>
                  <MessageContent text={msg.content} />
                </div>
                {msg.action && (
                  <div style={S.actionConfirm}>
                    <span style={S.checkMark}>✓</span>
                    <span style={S.actionText}>{msg.action}</span>
                  </div>
                )}
                <span style={S.time}>{fmt(msg.timestamp)}</span>
              </div>
            </div>
          )}
        </div>
      ))}

      {isLoading && (
        <div style={S.agentRow}>
          <span style={S.avatar}>🧠</span>
          <div style={S.typingBubble}>
            <span style={{ ...S.dot, animationDelay: '0ms' }} />
            <span style={{ ...S.dot, animationDelay: '200ms' }} />
            <span style={{ ...S.dot, animationDelay: '400ms' }} />
          </div>
        </div>
      )}

      <div ref={bottomRef} />

      <style>{`
        @keyframes blink {
          0%, 80%, 100% { opacity: 0.2; transform: scale(0.8); }
          40% { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  )
}

function fmt(d) {
  return d instanceof Date
    ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : ''
}

const S = {
  window: {
    flex: 1,
    overflowY: 'auto',
    padding: '12px 12px 4px',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    scrollbarWidth: 'thin',
    scrollbarColor: '#30363d transparent',
  },
  msgWrapper: { display: 'flex', flexDirection: 'column' },
  userRow: { display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' },
  agentRow: { display: 'flex', alignItems: 'flex-start', gap: '8px' },
  errorRow: { display: 'flex' },
  avatar: { fontSize: '16px', marginTop: '2px', flexShrink: 0 },
  agentContent: { display: 'flex', flexDirection: 'column', gap: '4px', maxWidth: '88%' },
  userBubble: {
    background: '#1f3a5f',
    border: '1px solid #2d5a8e',
    borderRadius: '12px 12px 2px 12px',
    padding: '8px 12px',
    color: '#c9d9f0',
    fontSize: '13px',
    lineHeight: 1.5,
    maxWidth: '88%',
    wordBreak: 'break-word',
  },
  agentBubble: {
    background: '#161b22',
    border: '1px solid #30363d',
    borderRadius: '2px 12px 12px 12px',
    padding: '8px 12px',
    color: '#e6edf3',
    fontSize: '13px',
    lineHeight: 1.6,
    wordBreak: 'break-word',
  },
  errorBubble: {
    background: '#2a0f0f',
    border: '1px solid #5a1f1f',
    borderRadius: '8px',
    padding: '8px 12px',
    color: '#f08080',
    fontSize: '12px',
    lineHeight: 1.5,
    width: '100%',
  },
  actionConfirm: {
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
    padding: '3px 8px',
    background: '#0f2a0f',
    border: '1px solid #1f4a1f',
    borderRadius: '4px',
    width: 'fit-content',
  },
  checkMark: { color: '#3fb950', fontSize: '11px', fontWeight: 700 },
  actionText: { color: '#7ee787', fontSize: '11px' },
  time: { color: '#484f58', fontSize: '10px', alignSelf: 'flex-end' },
  listItem: { display: 'flex', gap: '6px', marginTop: '2px' },
  bullet: { color: '#58a6ff', flexShrink: 0 },
  inlineCode: {
    background: '#21262d',
    padding: '1px 5px',
    borderRadius: '3px',
    fontFamily: "'Cascadia Code', 'Fira Code', monospace",
    fontSize: '12px',
    color: '#79c0ff',
  },
  typingBubble: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    background: '#161b22',
    border: '1px solid #30363d',
    borderRadius: '2px 12px 12px 12px',
    padding: '10px 14px',
  },
  dot: {
    display: 'inline-block',
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    background: '#58a6ff',
    animation: 'blink 1.2s infinite',
  },
}
