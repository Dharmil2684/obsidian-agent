import { useState, useEffect } from 'react'

const API = 'http://localhost:8000'

export default function SettingsPanel({ onClose }) {
  const [settings, setSettings]   = useState(null)
  const [vaultPath, setVaultPath] = useState('')
  const [model, setModel]         = useState('')
  const [backups, setBackups]     = useState(3)
  const [saving, setSaving]       = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [msg, setMsg]             = useState(null)   // { text, ok }

  // Load settings on mount
  useEffect(() => {
    fetch(`${API}/settings`)
      .then(r => r.json())
      .then(d => {
        setSettings(d)
        setVaultPath(d.vault_path)
        setModel(d.local_model)
        setBackups(d.max_backups)
      })
      .catch(() => setMsg({ text: 'Could not reach backend.', ok: false }))
  }, [])

  const flash = (text, ok = true) => {
    setMsg({ text, ok })
    setTimeout(() => setMsg(null), 3500)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const res = await fetch(`${API}/settings`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          vault_path:  vaultPath  !== settings.vault_path  ? vaultPath  : null,
          local_model: model      !== settings.local_model ? model      : null,
          max_backups: backups    !== settings.max_backups ? backups    : null,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Save failed')
      flash(`Saved: ${data.updated.join(', ')}`)
      setSettings(s => ({ ...s, vault_path: vaultPath, local_model: model, max_backups: backups }))
    } catch (e) {
      flash(e.message, false)
    } finally {
      setSaving(false)
    }
  }

  const handleRefreshContext = async () => {
    setRefreshing(true)
    try {
      const res  = await fetch(`${API}/refresh-context`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Refresh failed')
      flash(data.message)
    } catch (e) {
      flash(e.message, false)
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div style={S.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={S.panel}>

        {/* Header */}
        <div style={S.header}>
          <span style={S.title}>⚙ Settings</span>
          <button style={S.closeBtn} onClick={onClose}>✕</button>
        </div>

        {!settings ? (
          <p style={S.loading}>Loading…</p>
        ) : (
          <>
            {/* Vault path */}
            <label style={S.label}>Vault Path</label>
            <input
              style={S.input}
              value={vaultPath}
              onChange={e => setVaultPath(e.target.value)}
              spellCheck={false}
            />

            {/* Local model */}
            <label style={S.label}>Local Model (Ollama)</label>
            <input
              style={S.input}
              value={model}
              onChange={e => setModel(e.target.value)}
              placeholder="hermes3"
            />

            {/* Max backups */}
            <label style={S.label}>Backup Copies per File</label>
            <input
              style={{ ...S.input, width: '60px' }}
              type="number"
              min={1}
              max={10}
              value={backups}
              onChange={e => setBackups(Number(e.target.value))}
            />

            {/* Read-only info */}
            <div style={S.infoGrid}>
              <span style={S.infoLabel}>Groq Model</span>
              <span style={S.infoValue}>{settings.groq_model}</span>

              <span style={S.infoLabel}>Groq Key</span>
              <span style={{
                ...S.infoValue,
                color: settings.groq_key_set ? '#3fb950' : '#f85149',
              }}>
                {settings.groq_key_set ? '● set' : '○ missing'}
              </span>

              <span style={S.infoLabel}>API Port</span>
              <span style={S.infoValue}>{settings.api_port}</span>

              <span style={S.infoLabel}>Ollama URL</span>
              <span style={S.infoValue}>{settings.ollama_base_url}</span>
            </div>

            {/* Actions */}
            <div style={S.actions}>
              <button
                style={{ ...S.btn, ...S.btnPrimary }}
                disabled={saving}
                onClick={handleSave}
              >
                {saving ? 'Saving…' : 'Save Changes'}
              </button>

              <button
                style={{ ...S.btn, ...S.btnSecondary }}
                disabled={refreshing}
                onClick={handleRefreshContext}
                title="Re-scan vault to update Agent/context.md"
              >
                {refreshing ? 'Scanning…' : '↻ Refresh Context'}
              </button>
            </div>

            {/* Feedback message */}
            {msg && (
              <div style={{ ...S.msg, background: msg.ok ? '#0f2a0f' : '#2a0f0f', borderColor: msg.ok ? '#1f4a1f' : '#5a1f1f', color: msg.ok ? '#3fb950' : '#f85149' }}>
                {msg.text}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const S = {
  overlay: {
    position:        'fixed',
    inset:           0,
    background:      'rgba(0,0,0,0.55)',
    display:         'flex',
    alignItems:      'center',
    justifyContent:  'center',
    zIndex:          1000,
  },
  panel: {
    background:   '#161b22',
    border:       '1px solid #30363d',
    borderRadius: '10px',
    padding:      '20px',
    width:        '320px',
    maxHeight:    '90vh',
    overflowY:    'auto',
    display:      'flex',
    flexDirection:'column',
    gap:          '10px',
    boxShadow:    '0 8px 32px rgba(0,0,0,0.5)',
  },
  header: {
    display:        'flex',
    justifyContent: 'space-between',
    alignItems:     'center',
    marginBottom:   '4px',
  },
  title: {
    color:      '#e6edf3',
    fontSize:   '15px',
    fontWeight: 600,
  },
  closeBtn: {
    background:  'transparent',
    border:      'none',
    color:       '#8b949e',
    fontSize:    '14px',
    cursor:      'pointer',
    padding:     '2px 6px',
    borderRadius:'4px',
    outline:     'none',
  },
  loading: {
    color: '#8b949e',
    textAlign: 'center',
    padding: '20px 0',
  },
  label: {
    color:      '#8b949e',
    fontSize:   '11px',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: '-4px',
  },
  input: {
    background:   '#0d1117',
    border:       '1px solid #30363d',
    borderRadius: '6px',
    color:        '#e6edf3',
    fontSize:     '13px',
    padding:      '7px 10px',
    outline:      'none',
    width:        '100%',
    boxSizing:    'border-box',
    fontFamily:   'monospace',
  },
  infoGrid: {
    display:             'grid',
    gridTemplateColumns: '1fr 1fr',
    gap:                 '4px 8px',
    background:          '#0d1117',
    border:              '1px solid #21262d',
    borderRadius:        '6px',
    padding:             '10px 12px',
    marginTop:           '4px',
  },
  infoLabel: {
    color:    '#8b949e',
    fontSize: '11px',
  },
  infoValue: {
    color:      '#e6edf3',
    fontSize:   '11px',
    fontFamily: 'monospace',
    textAlign:  'right',
  },
  actions: {
    display:  'flex',
    gap:      '8px',
    marginTop:'4px',
  },
  btn: {
    flex:         1,
    padding:      '8px',
    borderRadius: '6px',
    border:       'none',
    fontSize:     '13px',
    fontWeight:   500,
    cursor:       'pointer',
    outline:      'none',
    transition:   'opacity 0.15s',
  },
  btnPrimary: {
    background: '#238636',
    color:      '#fff',
  },
  btnSecondary: {
    background: '#21262d',
    color:      '#e6edf3',
    border:     '1px solid #30363d',
  },
  msg: {
    padding:      '8px 12px',
    borderRadius: '6px',
    border:       '1px solid',
    fontSize:     '12px',
  },
}
