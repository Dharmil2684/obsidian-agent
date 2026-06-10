const TABS = [
  { id: 'all', label: 'All' },
  { id: 'backend', label: '🖥️ BE' },
  { id: 'frontend', label: '🌐 FE' },
  { id: 'data_science', label: '📊 DS' },
]

export default function DomainTabs({ activeTab, onTabChange }) {
  return (
    <div style={S.bar}>
      {TABS.map((t) => (
        <button
          key={t.id}
          style={{ ...S.tab, ...(activeTab === t.id ? S.tabActive : {}) }}
          onClick={() => onTabChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}

const S = {
  bar: {
    display: 'flex',
    background: '#161b22',
    borderBottom: '1px solid #30363d',
    padding: '0 8px',
    flexShrink: 0,
  },
  tab: {
    padding: '7px 12px',
    background: 'none',
    border: 'none',
    borderBottom: '2px solid transparent',
    color: '#8b949e',
    fontSize: '12px',
    cursor: 'pointer',
    outline: 'none',
    fontWeight: 500,
    transition: 'color 0.15s',
  },
  tabActive: {
    color: '#58a6ff',
    borderBottomColor: '#58a6ff',
  },
}
