import React, { useState } from 'react'
import { apiFetch, apiJson } from '../../utils/api'
import { useToast } from '../Toast'

function slugify(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 64)
}

export default function ScreenManager({ screens, activeScreenId, onSelectScreen, onRefresh }) {
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [newRows, setNewRows] = useState(6)
  const [newCols, setNewCols] = useState(22)
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')
  const [editRows, setEditRows] = useState(6)
  const [editCols, setEditCols] = useState(22)
  const [editSchedule, setEditSchedule] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const showToast = useToast()

  const DAY_LABELS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']  // Monday-first (backend weekday())

  const defaultSchedule = { enabled: false, off_time: '22:00', on_time: '08:00', days: [0, 1, 2, 3, 4, 5, 6] }

  const createScreen = async () => {
    if (!newName.trim()) return
    const id = slugify(newName) || `screen-${Date.now()}`
    try {
      await apiJson('/api/screens', 'POST',
                    { id, name: newName.trim(), rows: newRows, cols: newCols })
      setCreating(false)
      setNewName('')
      onRefresh()
      onSelectScreen(id)  // only navigate once the screen actually exists
    } catch (err) {
      showToast(`Could not create screen: ${err.message}`)
    }
  }

  const saveEdit = async (sid) => {
    try {
      await apiJson(`/api/screens/${sid}`, 'PUT',
                    { name: editName, rows: editRows, cols: editCols, schedule: editSchedule })
      setEditingId(null)
      onRefresh()
    } catch (err) {
      showToast(`Save failed: ${err.message}`)
    }
  }

  const setSched = (patch) => setEditSchedule(prev => ({ ...(prev || defaultSchedule), ...patch }))

  const toggleDay = (d) => setEditSchedule(prev => {
    const s = prev || defaultSchedule
    const days = s.days.includes(d) ? s.days.filter(x => x !== d) : [...s.days, d].sort()
    return { ...s, days }
  })

  const sleepNow = async (screen, sleeping, e) => {
    e.stopPropagation()
    try {
      await apiJson(`/api/screens/${screen.id}/sleep`, 'POST', { sleeping })
      onRefresh()
    } catch (err) {
      showToast(`${sleeping ? 'Sleep' : 'Wake'} failed: ${err.message}`)
    }
  }

  const deleteScreen = async (sid) => {
    try {
      await apiFetch(`/api/screens/${sid}`, { method: 'DELETE' })
      setConfirmDelete(null)
      if (activeScreenId === sid) onSelectScreen('main')
      onRefresh()
    } catch (err) {
      showToast(`Delete failed: ${err.message}`)
      setConfirmDelete(null)
    }
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-widest" style={{ color: 'var(--text-1)' }}>
          Screens
        </h2>
        <button
          onClick={() => setCreating(true)}
          className="fb-btn-primary text-[11px] px-3 py-1.5"
        >
          + New Screen
        </button>
      </div>

      <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>
        Open <code style={{ color: 'var(--text-2)' }}>/display?screen=ID</code> in any
        browser or cast tab. Each screen runs independently.
      </p>

      {/* Create form */}
      {creating && (
        <div
          className="rounded-xl p-4 space-y-3"
          style={{ background: 'var(--accent-dim)', border: '1px solid var(--accent-border)' }}
        >
          <p className="section-label" style={{ color: 'var(--accent)' }}>New Screen</p>
          <input
            autoFocus
            type="text"
            placeholder="Screen name (e.g. Living Room)"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && createScreen()}
            className="fb-input"
          />
          <p className="text-[10px] font-mono" style={{ color: 'var(--text-3)' }}>
            ID: <span style={{ color: 'var(--text-2)' }}>{slugify(newName) || '…'}</span>
          </p>
          <div className="flex gap-2">
            <div className="flex-1">
              <p className="section-label mb-1">Rows</p>
              <input type="number" min={1} max={20} value={newRows}
                onChange={e => setNewRows(Number(e.target.value))}
                className="fb-input" />
            </div>
            <div className="flex-1">
              <p className="section-label mb-1">Cols</p>
              <input type="number" min={1} max={60} value={newCols}
                onChange={e => setNewCols(Number(e.target.value))}
                className="fb-input" />
            </div>
          </div>
          <div className="flex gap-2 pt-1">
            <button onClick={createScreen} className="fb-btn-primary flex-1">Create</button>
            <button onClick={() => setCreating(false)} className="fb-btn-ghost flex-1">Cancel</button>
          </div>
        </div>
      )}

      {/* Screen list */}
      <div className="space-y-2">
        {screens.map(screen => (
          <div key={screen.id}>
            {editingId === screen.id ? (
              <div
                className="rounded-xl p-3 space-y-2"
                style={{ background: 'rgba(234,179,8,0.06)', border: '1px solid rgba(234,179,8,0.25)' }}
              >
                <input type="text" value={editName} onChange={e => setEditName(e.target.value)}
                  className="fb-input" />
                <div className="flex gap-2">
                  <input type="number" min={1} max={20} value={editRows}
                    onChange={e => setEditRows(Number(e.target.value))}
                    className="fb-input" placeholder="Rows" />
                  <input type="number" min={1} max={60} value={editCols}
                    onChange={e => setEditCols(Number(e.target.value))}
                    className="fb-input" placeholder="Cols" />
                </div>

                {/* Quiet hours */}
                <div className="rounded-lg p-2.5 space-y-2" style={{ border: '1px solid var(--border)' }}>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox"
                      checked={!!editSchedule?.enabled}
                      onChange={e => setSched({ enabled: e.target.checked })}
                      className="accent-blue-500" />
                    <span className="text-[11px] font-mono" style={{ color: 'var(--text-2)' }}>
                      Quiet hours — blank the display on a schedule
                    </span>
                  </label>
                  {editSchedule?.enabled && (
                    <>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono" style={{ color: 'var(--text-3)' }}>Off at</span>
                        <input type="time" value={editSchedule.off_time}
                          onChange={e => setSched({ off_time: e.target.value })}
                          className="fb-input py-1 text-[11px]" style={{ width: 92 }} />
                        <span className="text-[10px] font-mono" style={{ color: 'var(--text-3)' }}>on at</span>
                        <input type="time" value={editSchedule.on_time}
                          onChange={e => setSched({ on_time: e.target.value })}
                          className="fb-input py-1 text-[11px]" style={{ width: 92 }} />
                      </div>
                      <div className="flex gap-1">
                        {DAY_LABELS.map((label, d) => (
                          <button key={d} type="button" onClick={() => toggleDay(d)}
                            className="w-6 h-6 rounded text-[10px] font-mono transition-colors"
                            style={editSchedule.days.includes(d)
                              ? { background: 'var(--accent)', color: '#fff' }
                              : { background: 'var(--surface)', color: 'var(--text-3)', border: '1px solid var(--border)' }}>
                            {label}
                          </button>
                        ))}
                      </div>
                      <p className="text-[9px] font-mono" style={{ color: 'var(--text-3)' }}>
                        Days apply to the off time; overnight windows wake the next morning.
                      </p>
                    </>
                  )}
                </div>

                <div className="flex gap-2">
                  <button onClick={() => saveEdit(screen.id)}
                    className="flex-1 text-xs font-mono font-semibold uppercase tracking-wider rounded-lg py-1.5 transition-colors"
                    style={{ background: '#854d0e', color: '#fff' }}>
                    Save
                  </button>
                  <button onClick={() => setEditingId(null)} className="fb-btn-ghost flex-1 py-1.5">Cancel</button>
                </div>
              </div>
            ) : (
              <div
                className="flex items-center gap-3 rounded-xl px-4 py-3 cursor-pointer transition-all"
                style={{
                  background: activeScreenId === screen.id ? 'var(--accent-dim)' : 'var(--surface)',
                  border: `1px solid ${activeScreenId === screen.id ? 'var(--accent-border)' : 'var(--border)'}`,
                }}
                onClick={() => onSelectScreen(screen.id)}
              >
                {/* Status dot */}
                <span
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{
                    background: screen.online ? '#4ade80' : 'var(--text-3)',
                    boxShadow: screen.online ? '0 0 6px #4ade80' : 'none',
                  }}
                />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-semibold truncate" style={{ color: 'var(--text-1)' }}>
                      {screen.name}
                    </span>
                    {screen.id === 'main' && (
                      <span className="text-[10px] font-mono" style={{ color: 'var(--text-3)' }}>default</span>
                    )}
                    {activeScreenId === screen.id && (
                      <span className="text-[10px] font-mono" style={{ color: 'var(--accent)' }}>● active</span>
                    )}
                    {screen.sleeping && (
                      <span className="text-[10px] font-mono" style={{ color: '#a78bfa' }}>☾ sleeping</span>
                    )}
                  </div>
                  <div className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--text-3)' }}>
                    {screen.id} · {screen.rows}×{screen.cols} · {screen.mode?.toUpperCase()}
                  </div>
                </div>

                {/* Open display */}
                <a
                  href={`/display?screen=${screen.id}`}
                  target="_blank"
                  rel="noreferrer"
                  onClick={e => e.stopPropagation()}
                  className="text-[10px] font-mono px-2 py-1 rounded-lg transition-all flex-shrink-0"
                  style={{
                    color: 'var(--text-3)',
                    border: '1px solid var(--border)',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.color = 'var(--accent)'; e.currentTarget.style.borderColor = 'var(--accent-border)' }}
                  onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-3)'; e.currentTarget.style.borderColor = 'var(--border)' }}
                >
                  Open ↗
                </a>

                {/* Sleep / wake */}
                <button
                  onClick={e => sleepNow(screen, !screen.sleeping, e)}
                  className="transition-colors text-sm px-1 flex-shrink-0"
                  style={{ color: screen.sleeping ? '#a78bfa' : 'var(--text-3)' }}
                  title={screen.sleeping ? 'Wake display' : 'Sleep display'}
                >
                  {screen.sleeping ? '☀' : '☾'}
                </button>

                {/* Edit */}
                <button
                  onClick={e => {
                    e.stopPropagation()
                    setEditingId(screen.id)
                    setEditName(screen.name)
                    setEditRows(screen.rows)
                    setEditCols(screen.cols)
                    setEditSchedule(
                      screen.schedule && Object.keys(screen.schedule).length
                        ? { ...defaultSchedule, ...screen.schedule }
                        : { ...defaultSchedule })
                  }}
                  className="transition-colors text-sm px-1 flex-shrink-0"
                  style={{ color: 'var(--text-3)' }}
                  onMouseEnter={e => { e.currentTarget.style.color = '#eab308' }}
                  onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-3)' }}
                  title="Edit"
                >
                  ✎
                </button>

                {/* Delete */}
                {screen.id !== 'main' && (
                  confirmDelete === screen.id ? (
                    <div className="flex gap-1 flex-shrink-0" onClick={e => e.stopPropagation()}>
                      <button onClick={() => deleteScreen(screen.id)}
                        className="text-[10px] font-mono font-semibold rounded px-2 py-0.5 transition-colors"
                        style={{ background: '#dc2626', color: '#fff' }}>
                        Yes
                      </button>
                      <button onClick={() => setConfirmDelete(null)}
                        className="fb-btn-ghost text-[10px] px-2 py-0.5 rounded">
                        No
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={e => { e.stopPropagation(); setConfirmDelete(screen.id) }}
                      className="text-sm px-1 transition-colors flex-shrink-0"
                      style={{ color: 'var(--text-3)' }}
                      onMouseEnter={e => { e.currentTarget.style.color = '#ef4444' }}
                      onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-3)' }}
                      title="Delete"
                    >
                      ×
                    </button>
                  )
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Tips */}
      <div
        className="rounded-xl p-4 space-y-1.5"
        style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
      >
        <p className="section-label mb-2">Display Tips</p>
        <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>· F11 or ⊞ button for fullscreen</p>
        <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>· Chrome: ⋮ → Cast → Cast tab to Chromecast</p>
        <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>· Add <code style={{ color: 'var(--text-2)' }}>?kiosk=1</code> to hide all UI</p>
        <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>· Multiple screens can show different content simultaneously</p>
      </div>
    </div>
  )
}
