import React, { useState, useEffect, useRef, useCallback } from 'react'
import { apiFetch, apiJson } from '../../utils/api'
import { useToast } from '../Toast'
import ConfigField from './ConfigField'

/** One-line summary of a mode item's config for the row label. */
function configSummary(config) {
  if (!config) return ''
  const parts = []
  for (const v of Object.values(config)) {
    if (Array.isArray(v) && v.length) parts.push(v.join(','))
    else if (typeof v === 'string' && v.trim()) parts.push(v.trim())
    if (parts.length >= 2) break
  }
  const s = parts.join(' · ')
  return s.length > 28 ? s.slice(0, 28) + '…' : s
}

const DAY_LABELS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']  // Monday-first
const DEFAULT_WINDOW = { enabled: false, start_time: '11:00', end_time: '22:00', days: [0, 1, 2, 3, 4, 5, 6] }

function windowBadge(w) {
  if (!w?.enabled) return null
  const days = (w.days?.length === 7) ? '' : ' ' + (w.days || []).map(d => DAY_LABELS[d]).join('')
  return `⏱ ${w.start_time}–${w.end_time}${days}`
}

/** Compact time-window editor: start/end times + day picker. */
function WindowEditor({ value, onChange }) {
  const w = value || DEFAULT_WINDOW
  const toggleDay = (d) => {
    const days = w.days.includes(d) ? w.days.filter(x => x !== d) : [...w.days, d].sort()
    onChange({ ...w, days })
  }
  return (
    <div className="rounded-lg p-2 space-y-1.5" style={{ border: '1px solid var(--border)' }}>
      <label className="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={!!w.enabled}
          onChange={e => onChange({ ...w, enabled: e.target.checked })}
          className="accent-blue-500" />
        <span className="text-[10px] font-mono" style={{ color: 'var(--text-2)' }}>
          Only show during a time window
        </span>
      </label>
      {w.enabled && (
        <>
          <div className="flex items-center gap-1.5">
            <input type="time" value={w.start_time}
              onChange={e => onChange({ ...w, start_time: e.target.value })}
              className="fb-input py-0.5 text-[10px]" style={{ width: 86 }} />
            <span className="text-[10px] font-mono" style={{ color: 'var(--text-3)' }}>to</span>
            <input type="time" value={w.end_time}
              onChange={e => onChange({ ...w, end_time: e.target.value })}
              className="fb-input py-0.5 text-[10px]" style={{ width: 86 }} />
            <div className="flex gap-0.5 ml-1">
              {DAY_LABELS.map((label, d) => (
                <button key={d} type="button" onClick={() => toggleDay(d)}
                  className="w-5 h-5 rounded text-[9px] font-mono transition-colors"
                  style={w.days.includes(d)
                    ? { background: 'var(--accent)', color: '#fff' }
                    : { background: 'var(--surface)', color: 'var(--text-3)', border: '1px solid var(--border)' }}>
                  {label}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default function UniversalPlaylist({ rows, cols, screenId = 'main' }) {
  const [items, setItems] = useState([])
  const [availableModes, setAvailableModes] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [addType, setAddType] = useState('mode')
  const [addMode, setAddMode] = useState('clock')
  const [addConfig, setAddConfig] = useState({})      // per-item mode config draft (new item)
  const [editingConfig, setEditingConfig] = useState(null)  // item id with config editor open
  const [configDraft, setConfigDraft] = useState({})  // config draft for the item being edited
  const [addText, setAddText] = useState('')
  const [addPhoto, setAddPhoto] = useState(null)
  const [addHomeName, setAddHomeName] = useState('')
  const [addAwayName, setAddAwayName] = useState('')
  const [addMenuTitle, setAddMenuTitle] = useState('')
  const [addMenuEntries, setAddMenuEntries] = useState([{ name: '', price: '' }])
  const [addWindow, setAddWindow] = useState(null)
  const [addDuration, setAddDuration] = useState(30)
  const [editingWindow, setEditingWindow] = useState(null)  // item id with window editor open
  const [saving, setSaving] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [editingDuration, setEditingDuration] = useState(null)
  const [dragIdx, setDragIdx] = useState(null)
  const [dragOverIdx, setDragOverIdx] = useState(null)
  const photoRef = useRef(null)
  const rowRefs = useRef([])
  const showToast = useToast()

  const modeById = Object.fromEntries(availableModes.map(m => [m.id, m]))

  const itemIcon  = (item) =>
    item.type === 'text' ? '📝'
    : item.type === 'photo' ? '🖼️'
    : item.type === 'scoreboard' ? '🆚'
    : item.type === 'menu' ? '🧾'
    : modeById[item.content?.mode]?.icon ?? '⬡'
  const itemLabel = (item) => {
    if (item.type === 'text') { const t = item.content?.text ?? ''; return `"${t.length > 40 ? t.slice(0, 40) + '…' : t}"` }
    if (item.type === 'photo') return item.content?.url?.split('/').pop() ?? 'Photo'
    if (item.type === 'scoreboard') {
      const c = item.content ?? {}
      return `${c.home_name ?? 'HOME'} ${c.home_score ?? 0} — ${c.away_score ?? 0} ${c.away_name ?? 'AWAY'}`
    }
    if (item.type === 'menu') {
      const c = item.content ?? {}
      return `${c.title || 'Menu'} (${(c.entries || []).length} items)`
    }
    const label = modeById[item.content?.mode]?.label ?? item.content?.mode ?? 'Mode'
    const summary = configSummary(item.content?.config)
    return summary ? `${label} · ${summary}` : label
  }

  const qs = `?screen=${encodeURIComponent(screenId)}`

  useEffect(() => {
    fetch('/api/modes/available').then(r => r.json()).then(list => {
      setAvailableModes(list)
      if (list.length > 0 && !list.find(m => m.id === addMode)) setAddMode(list[0].id)
    }).catch(() => {})
  }, [])

  const load = useCallback(async () => {
    const res = await fetch(`/api/playlist${qs}`)
    if (res.ok) setItems(await res.json())
  }, [qs])

  useEffect(() => { load() }, [load])

  const addItem = async () => {
    setSaving(true)
    try {
      let content = {}
      if (addType === 'photo') {
        if (!addPhoto) return
        const fd = new FormData()
        fd.append('file', addPhoto)
        const { url } = await apiFetch('/api/upload', { method: 'POST', body: fd })
        content = { url }
      } else if (addType === 'text') {
        content = { text: addText }
      } else if (addType === 'scoreboard') {
        content = {
          home_name: addHomeName.trim().toUpperCase(),
          away_name: addAwayName.trim().toUpperCase(),
          home_score: 0,
          away_score: 0,
        }
      } else if (addType === 'menu') {
        content = {
          title: addMenuTitle.trim(),
          entries: addMenuEntries.filter(e => e.name.trim() || e.price.trim()),
        }
      } else {
        content = { mode: addMode, config: addConfig }
      }
      await apiJson(`/api/playlist${qs}`, 'POST',
                    { type: addType, content, duration: addDuration, window: addWindow })
      await load()
      setShowAdd(false)
      setAddText('')
      setAddConfig({})
      setAddPhoto(null)
      setAddHomeName('')
      setAddAwayName('')
      setAddMenuTitle('')
      setAddMenuEntries([{ name: '', price: '' }])
      setAddWindow(null)
    } catch (err) {
      showToast(`Could not add item: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  const bumpScore = async (item, side, delta) => {
    const next = Math.max(0, (item.content?.[side] ?? 0) + delta)
    try {
      await apiJson(`/api/playlist/${item.id}${qs}`, 'PUT', {
        type: 'scoreboard',
        content: { ...item.content, [side]: next },
        duration: item.duration,
      })
    } catch (err) {
      showToast(`Score update failed: ${err.message}`)
    }
    await load()
  }

  const remove = async (id) => {
    try {
      await apiFetch(`/api/playlist/${id}${qs}`, { method: 'DELETE' })
    } catch (err) {
      showToast(`Remove failed: ${err.message}`)
    }
    await load()
  }

  const clear = async () => {
    if (!window.confirm(`Remove all ${items.length} item${items.length !== 1 ? 's' : ''}?`)) return
    try {
      await apiFetch(`/api/playlist/clear${qs}`, { method: 'POST' })
      setItems([])
    } catch (err) {
      showToast(`Clear failed: ${err.message}`)
      await load()  // resync — the optimistic empty list would be a lie
    }
  }

  const move = async (idx, dir) => {
    const newItems = [...items]
    const swapIdx = idx + dir
    if (swapIdx < 0 || swapIdx >= newItems.length) return
    ;[newItems[idx], newItems[swapIdx]] = [newItems[swapIdx], newItems[idx]]
    setItems(newItems)  // optimistic
    try {
      await apiJson(`/api/playlist/reorder${qs}`, 'POST',
                    { ids: newItems.map(i => i.id) })
    } catch (err) {
      showToast(`Reorder failed: ${err.message}`)
      await load()  // rollback to server order
    }
  }

  // ── Drag to reorder (pointer-based — works with touch and mouse) ────────────

  const commitOrder = async (newItems) => {
    setItems(newItems)  // optimistic
    try {
      await apiJson(`/api/playlist/reorder${qs}`, 'POST',
                    { ids: newItems.map(i => i.id) })
    } catch (err) {
      showToast(`Reorder failed: ${err.message}`)
      await load()
    }
  }

  const dragStateRef = useRef({ from: null, over: null })

  const startDrag = (e, idx) => {
    e.preventDefault()
    dragStateRef.current = { from: idx, over: idx }
    setDragIdx(idx)
    setDragOverIdx(idx)

    const onMove = (ev) => {
      const y = ev.clientY ?? ev.touches?.[0]?.clientY
      if (y == null) return
      rowRefs.current.forEach((el, i) => {
        if (!el) return
        const rect = el.getBoundingClientRect()
        if (y >= rect.top && y <= rect.bottom) {
          dragStateRef.current.over = i
          setDragOverIdx(i)
        }
      })
    }

    const onUp = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      const { from, over } = dragStateRef.current
      dragStateRef.current = { from: null, over: null }
      setDragIdx(null)
      setDragOverIdx(null)
      if (from !== null && over !== null && from !== over) {
        const next = [...items]
        const [moved] = next.splice(from, 1)
        next.splice(over, 0, moved)
        commitOrder(next)
      }
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  const saveWindow = async (item, window) => {
    try {
      await apiJson(`/api/playlist/${item.id}${qs}`, 'PUT',
                    { type: item.type, content: item.content, duration: item.duration, window })
    } catch (err) {
      showToast(`Schedule update failed: ${err.message}`)
    }
    await load()
  }

  const saveConfig = async (item, config) => {
    try {
      await apiJson(`/api/playlist/${item.id}${qs}`, 'PUT',
                    { type: item.type, content: { ...item.content, config },
                      duration: item.duration, window: item.window })
    } catch (err) {
      showToast(`Config update failed: ${err.message}`)
    }
    setEditingConfig(null)
    await load()
  }

  const saveDuration = async (item, newDuration) => {
    const dur = Math.max(5, parseInt(newDuration, 10) || 30)
    try {
      await apiJson(`/api/playlist/${item.id}${qs}`, 'PUT',
                    { type: item.type, content: item.content, duration: dur })
    } catch (err) {
      showToast(`Duration update failed: ${err.message}`)
    }
    setEditingDuration(null)
    await load()
  }

  const playNow = async () => {
    try {
      await apiFetch(`/api/playlist/play${qs}`, { method: 'POST' })
      setPlaying(true)
      setTimeout(() => setPlaying(false), 2000)
    } catch (err) {
      showToast(`Play failed: ${err.message}`)
    }
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-widest" style={{ color: 'var(--text-1)' }}>
            Playlist
          </h2>
          <p className="text-[11px] font-mono mt-1" style={{ color: 'var(--text-3)' }}>
            {items.length > 0
              ? 'Active — overrides Modes rotation while items exist.'
              : 'Add items to create a custom looping sequence.'}
          </p>
        </div>
        {items.length > 0 && (
          <button onClick={clear} className="text-[11px] font-mono transition-colors mt-1 flex-shrink-0"
            style={{ color: 'var(--text-3)' }}
            onMouseEnter={e => { e.currentTarget.style.color = '#ef4444' }}
            onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-3)' }}>
            Clear All
          </button>
        )}
      </div>

      {/* Item list */}
      {items.length > 0 && (
        <div className="space-y-1.5">
          {items.map((item, idx) => (
            <div
              key={item.id}
              ref={el => { rowRefs.current[idx] = el }}
              className="flex items-center gap-2 rounded-xl px-3 py-2.5 transition-colors"
              style={{
                background: dragOverIdx === idx && dragIdx !== null && dragIdx !== idx
                  ? 'var(--accent-dim)' : 'var(--surface)',
                border: `1px solid ${dragOverIdx === idx && dragIdx !== null && dragIdx !== idx
                  ? 'var(--accent-border)' : 'var(--border)'}`,
                opacity: dragIdx === idx ? 0.5 : 1,
              }}
            >
              <span
                onPointerDown={e => startDrag(e, idx)}
                className="w-5 text-center text-sm flex-shrink-0 cursor-grab active:cursor-grabbing select-none"
                style={{ color: 'var(--text-3)', touchAction: 'none' }}
                title="Drag to reorder"
              >
                ⠿
              </span>
              <span className="text-sm flex-shrink-0">{itemIcon(item)}</span>
              <div className="flex-1 min-w-0">
                {item.type === 'photo' ? (
                  <div className="flex items-center gap-2">
                    <img src={item.content?.url} alt="" className="h-5 w-8 object-cover rounded" style={{ border: '1px solid var(--border)' }} />
                    <span className="text-[11px] font-mono truncate" style={{ color: 'var(--text-2)' }}>{itemLabel(item)}</span>
                  </div>
                ) : item.type === 'scoreboard' ? (
                  <div className="space-y-1">
                    <span className="text-[11px] font-mono truncate block" style={{ color: 'var(--text-2)' }}>{itemLabel(item)}</span>
                    <div className="flex items-center gap-1">
                      {[['home_score', item.content?.home_name ?? 'HOME'], ['away_score', item.content?.away_name ?? 'AWAY']].map(([side, label]) => (
                        <div key={side} className="flex items-center gap-0.5 rounded px-1 py-0.5"
                          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)' }}>
                          <span className="text-[9px] font-mono px-0.5 max-w-[52px] truncate" style={{ color: 'var(--text-3)' }}>{label}</span>
                          <button onClick={() => bumpScore(item, side, -1)}
                            className="w-4 h-4 flex items-center justify-center text-[11px] rounded transition-colors"
                            style={{ color: 'var(--text-2)' }}>−</button>
                          <span className="text-[11px] font-mono w-5 text-center" style={{ color: 'var(--text-1)' }}>
                            {item.content?.[side] ?? 0}
                          </span>
                          <button onClick={() => bumpScore(item, side, 1)}
                            className="w-4 h-4 flex items-center justify-center text-[11px] rounded transition-colors"
                            style={{ color: 'var(--accent)' }}>+</button>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <span className="text-[11px] font-mono truncate block" style={{ color: 'var(--text-2)' }}>{itemLabel(item)}</span>
                )}
                {windowBadge(item.window) && (
                  <span className="text-[9px] font-mono block mt-0.5" style={{ color: 'var(--accent)' }}>
                    {windowBadge(item.window)}
                  </span>
                )}
              </div>

              {/* Per-item mode config (only when the mode has settings) */}
              {item.type === 'mode' && Object.keys(modeById[item.content?.mode]?.config_schema || {}).length > 0 && (
                <button
                  onClick={() => {
                    setConfigDraft({ ...(item.content?.config || {}) })
                    setEditingConfig(editingConfig === item.id ? null : item.id)
                  }}
                  className="w-5 h-5 flex items-center justify-center text-xs flex-shrink-0 transition-colors"
                  style={{ color: configSummary(item.content?.config) ? 'var(--accent)' : 'var(--text-3)' }}
                  title="Configure this item"
                >
                  ⚙
                </button>
              )}

              {/* Time window */}
              <button
                onClick={() => setEditingWindow(editingWindow === item.id ? null : item.id)}
                className="w-5 h-5 flex items-center justify-center text-xs flex-shrink-0 transition-colors"
                style={{ color: item.window?.enabled ? 'var(--accent)' : 'var(--text-3)' }}
                title="Time window (dayparting)"
              >
                ⏱
              </button>

              {/* Duration */}
              {editingDuration === item.id ? (
                <input
                  type="number" defaultValue={item.duration} min={5} max={3600} autoFocus
                  className="w-14 text-center text-xs font-mono rounded px-1.5 py-0.5"
                  style={{ background: 'var(--accent-dim)', border: '1px solid var(--accent-border)', color: 'var(--text-1)' }}
                  onBlur={e => saveDuration(item, e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') saveDuration(item, e.target.value); if (e.key === 'Escape') setEditingDuration(null) }}
                />
              ) : (
                <button
                  onClick={() => setEditingDuration(item.id)}
                  className="text-[10px] font-mono rounded px-2 py-0.5 transition-colors flex-shrink-0"
                  style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-3)' }}
                  title="Click to edit"
                >
                  {item.duration}s
                </button>
              )}

              {/* Reorder */}
              <div className="flex gap-0.5 flex-shrink-0">
                {[[-1, '↑'], [1, '↓']].map(([dir, label]) => (
                  <button key={label} onClick={() => move(idx, dir)}
                    disabled={(dir === -1 && idx === 0) || (dir === 1 && idx === items.length - 1)}
                    className="w-5 h-5 flex items-center justify-center text-xs disabled:opacity-20 transition-colors"
                    style={{ color: 'var(--text-3)' }}>
                    {label}
                  </button>
                ))}
              </div>

              <button onClick={() => remove(item.id)}
                className="w-5 h-5 flex items-center justify-center text-base flex-shrink-0 transition-colors"
                style={{ color: 'var(--text-3)' }}
                onMouseEnter={e => { e.currentTarget.style.color = '#ef4444' }}
                onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-3)' }}>
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Per-item mode config editor (below the list) */}
      {editingConfig !== null && (() => {
        const item = items.find(i => i.id === editingConfig)
        const schema = item && modeById[item.content?.mode]?.config_schema
        if (!item || !schema) return null
        return (
          <div className="rounded-xl p-3 space-y-3"
            style={{ background: 'rgba(234,179,8,0.05)', border: '1px solid rgba(234,179,8,0.25)' }}>
            <p className="section-label" style={{ color: '#eab308' }}>
              {modeById[item.content?.mode]?.label} settings — {itemLabel(item)}
            </p>
            {Object.entries(schema).map(([key, s]) => (
              <ConfigField key={key} schema={s} value={configDraft[key]}
                onChange={val => setConfigDraft(prev => ({ ...prev, [key]: val }))} />
            ))}
            <div className="flex gap-2">
              <button onClick={() => saveConfig(item, configDraft)}
                className="fb-btn-primary flex-1 py-1.5 text-[11px]"
                style={{ background: '#854d0e', borderColor: 'rgba(234,179,8,0.3)' }}>
                Save
              </button>
              <button onClick={() => setEditingConfig(null)} className="fb-btn-ghost px-4 py-1.5 text-[11px]">
                Cancel
              </button>
            </div>
          </div>
        )
      })()}

      {/* Per-item window editor (below the list to avoid drag interference) */}
      {editingWindow !== null && (() => {
        const item = items.find(i => i.id === editingWindow)
        if (!item) return null
        return (
          <div className="rounded-xl p-3 space-y-2"
            style={{ background: 'var(--accent-dim)', border: '1px solid var(--accent-border)' }}>
            <p className="section-label" style={{ color: 'var(--accent)' }}>
              Schedule — {itemLabel(item)}
            </p>
            <WindowEditor
              value={item.window?.enabled != null && Object.keys(item.window).length
                ? { ...DEFAULT_WINDOW, ...item.window } : null}
              onChange={w => saveWindow(item, w)}
            />
            <button onClick={() => setEditingWindow(null)} className="fb-btn-ghost w-full py-1.5 text-[11px]">
              Done
            </button>
          </div>
        )
      })()}

      {items.length === 0 && !showAdd && (
        <div className="text-center py-8 text-[11px] font-mono rounded-xl"
          style={{ color: 'var(--text-3)', border: '1px dashed var(--border)' }}>
          No items yet
        </div>
      )}

      {/* Add form */}
      {showAdd ? (
        <div className="rounded-xl p-4 space-y-3"
          style={{ background: 'var(--surface)', border: '1px solid var(--border-bright)' }}>
          <p className="section-label">Add Item</p>

          {/* Type tabs */}
          <div className="flex gap-1">
            {['mode', 'text', 'photo', 'scoreboard', 'menu'].map(t => (
              <button key={t} onClick={() => setAddType(t)}
                className="flex-1 py-1.5 rounded-lg text-xs font-mono font-semibold tracking-wider transition-colors uppercase"
                style={addType === t
                  ? { background: 'var(--accent)', color: '#fff' }
                  : { background: 'var(--surface)', color: 'var(--text-3)', border: '1px solid var(--border)' }}>
                {t === 'mode' ? 'Mode' : t === 'text' ? 'Text' : t === 'photo' ? 'Photo'
                  : t === 'scoreboard' ? 'Score' : 'Menu'}
              </button>
            ))}
          </div>

          {addType === 'mode' && (
            <>
              <div className="grid grid-cols-2 gap-1.5">
                {availableModes.map(m => (
                  <button key={m.id} onClick={() => { setAddMode(m.id); setAddConfig({}) }}
                    className="flex items-center gap-2 rounded-lg px-3 py-2 text-left transition-colors"
                    style={addMode === m.id
                      ? { background: 'var(--accent-dim)', border: '1px solid var(--accent-border)', color: 'var(--text-1)' }
                      : { background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-3)' }}>
                    <span>{m.icon}</span>
                    <span className="font-mono text-xs">{m.label}</span>
                  </button>
                ))}
              </div>
              {/* Per-item config for the selected mode */}
              {Object.keys(modeById[addMode]?.config_schema || {}).length > 0 && (
                <div className="rounded-lg p-3 space-y-3 mt-1"
                  style={{ background: 'rgba(234,179,8,0.05)', border: '1px solid rgba(234,179,8,0.25)' }}>
                  <p className="section-label" style={{ color: '#eab308' }}>
                    {modeById[addMode].label} settings for this item
                  </p>
                  {Object.entries(modeById[addMode].config_schema).map(([key, schema]) => (
                    <ConfigField key={key} schema={schema} value={addConfig[key]}
                      onChange={val => setAddConfig(prev => ({ ...prev, [key]: val }))} />
                  ))}
                </div>
              )}
            </>
          )}

          {addType === 'text' && (
            <textarea value={addText} onChange={e => setAddText(e.target.value)}
              placeholder="Enter message text…" rows={3}
              className="fb-input resize-none" />
          )}

          {addType === 'scoreboard' && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm flex-shrink-0" style={{ background: '#2a9d8f' }} />
                <input type="text" value={addHomeName} onChange={e => setAddHomeName(e.target.value)}
                  placeholder="Home team name…" maxLength={16} className="fb-input flex-1" />
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm flex-shrink-0" style={{ background: '#e63946' }} />
                <input type="text" value={addAwayName} onChange={e => setAddAwayName(e.target.value)}
                  placeholder="Away team name…" maxLength={16} className="fb-input flex-1" />
              </div>
              <p className="text-[10px] font-mono" style={{ color: 'var(--text-3)' }}>
                Scores start at 0 — bump them live from the playlist row, the API, or MQTT.
                Only the changed digits flip.
              </p>
            </div>
          )}

          {addType === 'menu' && (
            <div className="space-y-2">
              <input type="text" value={addMenuTitle} onChange={e => setAddMenuTitle(e.target.value)}
                placeholder="Menu title (e.g. HAPPY HOUR) — optional" className="fb-input w-full" />
              {addMenuEntries.map((entry, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <input type="text" value={entry.name}
                    onChange={e => setAddMenuEntries(prev => prev.map((x, j) => j === i ? { ...x, name: e.target.value } : x))}
                    placeholder="Item name" className="fb-input flex-1" />
                  <input type="text" value={entry.price}
                    onChange={e => setAddMenuEntries(prev => prev.map((x, j) => j === i ? { ...x, price: e.target.value } : x))}
                    placeholder="6.50" className="fb-input" style={{ width: 72 }} />
                  <button type="button"
                    onClick={() => setAddMenuEntries(prev => prev.length > 1 ? prev.filter((_, j) => j !== i) : prev)}
                    className="text-sm px-1" style={{ color: 'var(--text-3)' }}>×</button>
                </div>
              ))}
              <button type="button"
                onClick={() => setAddMenuEntries(prev => [...prev, { name: '', price: '' }])}
                className="fb-btn-ghost text-[10px] px-3 py-1">
                + Row
              </button>
              <p className="text-[10px] font-mono" style={{ color: 'var(--text-3)' }}>
                Renders as NAME····PRICE with dot leaders. Long menus paginate each rotation.
              </p>
            </div>
          )}

          {addType === 'photo' && (
            <div onClick={() => photoRef.current?.click()}
              className="rounded-xl p-4 text-center cursor-pointer transition-all"
              style={{ border: '1px dashed var(--border)' }}>
              <input ref={photoRef} type="file" accept="image/*" className="hidden"
                onChange={e => setAddPhoto(e.target.files[0])} />
              {addPhoto ? (
                <div className="space-y-1">
                  <img src={URL.createObjectURL(addPhoto)} alt="" className="mx-auto h-14 object-contain rounded" />
                  <div className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>{addPhoto.name}</div>
                </div>
              ) : (
                <>
                  <div className="text-2xl mb-1 opacity-60">🖼️</div>
                  <div className="text-xs font-mono" style={{ color: 'var(--text-3)' }}>Click to select photo</div>
                </>
              )}
            </div>
          )}

          {/* Duration */}
          <div className="flex items-center gap-3">
            <span className="section-label">Duration</span>
            <input type="number" value={addDuration} min={5} max={3600}
              onChange={e => setAddDuration(parseInt(e.target.value, 10) || 30)}
              className="w-20 text-center fb-input py-1" />
            <span className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>seconds</span>
          </div>

          {/* Time window (dayparting) */}
          <WindowEditor value={addWindow} onChange={setAddWindow} />

          <div className="flex gap-2 pt-1">
            <button onClick={addItem}
              disabled={saving || (addType === 'text' && !addText.trim()) || (addType === 'photo' && !addPhoto)
                || (addType === 'scoreboard' && (!addHomeName.trim() || !addAwayName.trim()))
                || (addType === 'menu' && !addMenuEntries.some(e => e.name.trim()))}
              className="fb-btn-primary flex-1">
              {saving ? 'Adding…' : 'Add to Playlist'}
            </button>
            <button onClick={() => { setShowAdd(false); setAddPhoto(null); setAddText('') }}
              className="fb-btn-ghost px-4">
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button onClick={() => setShowAdd(true)}
          className="w-full rounded-xl py-3 text-xs font-mono font-medium transition-all"
          style={{
            border: '1px dashed var(--border)',
            color: 'var(--text-3)',
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--border-bright)'; e.currentTarget.style.color = 'var(--text-2)' }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-3)' }}>
          + Add Item
        </button>
      )}

      {/* Play now */}
      {items.length > 0 && (
        <button onClick={playNow}
          className="fb-btn-primary w-full py-3"
          style={playing ? { background: '#16a34a' } : {}}>
          {playing ? '▶ Playing' : '▶ Play Now'}
        </button>
      )}

      {/* Tips */}
      <div className="rounded-xl p-4 space-y-1.5"
        style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
        <p className="section-label mb-2">How it works</p>
        <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>· Each item plays for its own duration, then auto-advances</p>
        <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>· Loops forever — playlist overrides the Modes tab rotation</p>
        <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>· Mix modes, text, and photos in any order</p>
        <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>· Remove all items to return to Modes rotation</p>
        <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>· Click a duration badge to edit it inline</p>
      </div>
    </div>
  )
}
