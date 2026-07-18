import React, { useState, useEffect, useRef, useCallback } from 'react'
import { apiFetch, apiJson } from '../../utils/api'
import { useToast } from '../Toast'

export default function UniversalPlaylist({ rows, cols, screenId = 'main' }) {
  const [items, setItems] = useState([])
  const [availableModes, setAvailableModes] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [addType, setAddType] = useState('mode')
  const [addMode, setAddMode] = useState('clock')
  const [addText, setAddText] = useState('')
  const [addPhoto, setAddPhoto] = useState(null)
  const [addHomeName, setAddHomeName] = useState('')
  const [addAwayName, setAddAwayName] = useState('')
  const [addDuration, setAddDuration] = useState(30)
  const [saving, setSaving] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [editingDuration, setEditingDuration] = useState(null)
  const photoRef = useRef(null)
  const showToast = useToast()

  const modeById = Object.fromEntries(availableModes.map(m => [m.id, m]))

  const itemIcon  = (item) =>
    item.type === 'text' ? '📝'
    : item.type === 'photo' ? '🖼️'
    : item.type === 'scoreboard' ? '🆚'
    : modeById[item.content?.mode]?.icon ?? '⬡'
  const itemLabel = (item) => {
    if (item.type === 'text') { const t = item.content?.text ?? ''; return `"${t.length > 40 ? t.slice(0, 40) + '…' : t}"` }
    if (item.type === 'photo') return item.content?.url?.split('/').pop() ?? 'Photo'
    if (item.type === 'scoreboard') {
      const c = item.content ?? {}
      return `${c.home_name ?? 'HOME'} ${c.home_score ?? 0} — ${c.away_score ?? 0} ${c.away_name ?? 'AWAY'}`
    }
    return modeById[item.content?.mode]?.label ?? item.content?.mode ?? 'Mode'
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
      } else {
        content = { mode: addMode }
      }
      await apiJson(`/api/playlist${qs}`, 'POST',
                    { type: addType, content, duration: addDuration })
      await load()
      setShowAdd(false)
      setAddText('')
      setAddPhoto(null)
      setAddHomeName('')
      setAddAwayName('')
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
              className="flex items-center gap-2 rounded-xl px-3 py-2.5"
              style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            >
              <span className="w-4 text-center text-[10px] font-mono flex-shrink-0" style={{ color: 'var(--text-3)' }}>
                {idx + 1}
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
              </div>

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
            {['mode', 'text', 'photo', 'scoreboard'].map(t => (
              <button key={t} onClick={() => setAddType(t)}
                className="flex-1 py-1.5 rounded-lg text-xs font-mono font-semibold tracking-wider transition-colors uppercase"
                style={addType === t
                  ? { background: 'var(--accent)', color: '#fff' }
                  : { background: 'var(--surface)', color: 'var(--text-3)', border: '1px solid var(--border)' }}>
                {t === 'mode' ? 'Mode' : t === 'text' ? 'Text' : t === 'photo' ? 'Photo' : 'Score'}
              </button>
            ))}
          </div>

          {addType === 'mode' && (
            <div className="grid grid-cols-2 gap-1.5">
              {availableModes.map(m => (
                <button key={m.id} onClick={() => setAddMode(m.id)}
                  className="flex items-center gap-2 rounded-lg px-3 py-2 text-left transition-colors"
                  style={addMode === m.id
                    ? { background: 'var(--accent-dim)', border: '1px solid var(--accent-border)', color: 'var(--text-1)' }
                    : { background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-3)' }}>
                  <span>{m.icon}</span>
                  <span className="font-mono text-xs">{m.label}</span>
                </button>
              ))}
            </div>
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

          <div className="flex gap-2 pt-1">
            <button onClick={addItem}
              disabled={saving || (addType === 'text' && !addText.trim()) || (addType === 'photo' && !addPhoto)
                || (addType === 'scoreboard' && (!addHomeName.trim() || !addAwayName.trim()))}
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
