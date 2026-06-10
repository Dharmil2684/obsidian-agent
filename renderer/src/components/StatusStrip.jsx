export default function StatusStrip({ stats }) {
  const { tasks = 0, completed = 0, blockers = 0 } = stats

  return (
    <div style={S.strip}>
      <Item icon="📋" value={tasks} label="pending" color="#58a6ff" />
      <Divider />
      <Item icon="✅" value={completed} label="done" color="#3fb950" />
      <Divider />
      <Item icon="🚧" value={blockers} label="blockers" color={blockers > 0 ? '#f85149' : '#8b949e'} />
    </div>
  )
}

function Item({ icon, value, label, color }) {
  return (
    <div style={S.item}>
      <span style={S.icon}>{icon}</span>
      <span style={{ ...S.value, color }}>{value}</span>
      <span style={S.label}>{label}</span>
    </div>
  )
}

function Divider() {
  return <div style={S.divider} />
}

const S = {
  strip: {
    display: 'flex',
    alignItems: 'center',
    padding: '5px 14px',
    background: '#0d1117',
    borderBottom: '1px solid #21262d',
    flexShrink: 0,
    gap: '4px',
  },
  item: { display: 'flex', alignItems: 'center', gap: '4px' },
  icon: { fontSize: '12px' },
  value: { fontSize: '12px', fontWeight: 700 },
  label: { fontSize: '11px', color: '#484f58' },
  divider: { width: '1px', height: '12px', background: '#21262d', margin: '0 8px' },
}
