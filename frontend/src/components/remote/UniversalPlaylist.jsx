import React, { useState, useEffect, useRef, useCallback } from 'react'

export default function UniversalPlaylist({ rows, cols, screenId = 'main' }) {
  const [items, setItems] = useState([])
  const [availableModes, setAvailableModes] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [addType, setAddType] = useState('mode')
  const [addMode, setAddMode] = useState('clock')
  const [addText, setAddText] = useState('')
  const [addPhoto, setAddPhoto] = useState(null)
  const [addDuration, setAddDuration] = useState(30)
  const [saving, setSaving] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [editingDuration, setEditingDuration] = useState(null) // item id
  const photoRef = useRef(null)

  const modeById = Object.fromEntries(availableModes.map(m => [m.id, m]))

  const itemIcon = (item) => {
    if (item.type === 'text') return '📝'
    if (item.type === 'photo') return '🖼️'
    if (item.type === 'mode') return modeById[item.content?.mode]?.icon ?? '⬡'
    return '⬡'
  }

  const itemLabel = (item) => {
    if (item.type === 'text') {
      const t = item.content?.text ?? ''
      return `"${t.length > 40 ? t.slice(0, 40) + '…' : t}"`
    }
    if (item.type === 'photo') return item.content?.url?.split('/').pop() ?? 'Photo'
    if (item.type === 'mode') return modeById[item.content?.mode]?.label ?? item.content?.mode ?? 'Mode'
    return item.type
  }

  const qs = `?screen=${encodeURIComponent(screenId)}`

  useEffect(() => {
    fetch('/api/modes/available')
      .then(r => r.json())
      .then(list => {
        setAvailableModes(list)
        if (list.length > 0 && !list.find(m => m.id === addMode)) {
          setAddMode(list[0].id)
        }
      })
      .catch(() => {})
  }, [])

  const load = useCallback(async () => {
    const res = await fetch(`/api/playlist${qs}`)
    if (res.ok) setItems(await res.json())
  }, [qs])

  useEffect(() => { load() }, [load])

  // ── Add item ────────────────────────────────────────────────────────────────

  const addItem = async () => {
    setSaving(true)
    try {
      let content = {}

      if (addType === 'photo') {
        if (!addPhoto) return
        const fd = new FormData()
        fd.append('file', addPhoto)
        const res = await fetch('/api/upload', { method: 'POST', body: fd })
        const { url } = await res.json()
        content = { url }
      } else if (addType === 'text') {
        content = { text: addText }
      } else {
        content = { mode: addMode }
      }

      await fetch(`/api/playlist${qs}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: addType, content, duration: addDuration }),
      })

      await load()
      setShowAdd(false)
      setAddText('')
      setAddPhoto(null)
    } finally {
      setSaving(false)
    }
  }

  // ── Delete / clear ──────────────────────────────────────────────────────────

  const remove = async (id) => {
    await fetch(`/api/playlist/${id}${qs}`, { method: 'DELETE' })
    await load()
  }

  const clear = async () => {
    if (!window.confirm(`Remove all ${items.length} item${items.length !== 1 ? 's' : ''} from the playlist?`)) return
    await fetch(`/api/playlist/clear${qs}`, { method: 'POST' })
    setItems([])
  }

  // ── Reorder (move up / down) ────────────────────────────────────────────────

  const move = async (idx, dir) => {
    const newItems = [...items]
    const swapIdx = idx + dir
    if (swapIdx < 0 || swapIdx >= newItems.length) return
    ;[newItems[idx], newItems[swapIdx]] = [newItems[swapIdx], newItems[idx]]
    setItems(newItems)
    await fetch(`/api/playlist/reorder${qs}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: newItems.map(i => i.id) }),
    })
  }

  // ── Duration inline edit ────────────────────────────────────────────────────

  const saveDuration = async (item, newDuration) => {
    const dur = Math.max(5, parseInt(newDuration, 10) || 30)
    await fetch(`/api/playlist/${item.id}${qs}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: item.type, content: item.content, duration: dur }),
    })
    setEditingDuration(null)
    await load()
  }

  // ── Play ────────────────────────────────────────────────────────────────────

  const playNow = async () => {
    await fetch(`/api/playlist/play${qs}`, { method: 'POST' })
    setPlaying(true)
    setTimeout(() => setPlaying(false), 2000)
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-mono text-gray-200 font-semibold tracking-wider uppercase">
            Playlist
          </h2>
          <p className="text-xs text-gray-500 font-mono mt-1">
            {items.length > 0
              ? 'Active — playlist overrides the Modes rotation while items exist.'
              : 'Add items below to override the Modes rotation with a custom sequence.'}
          </p>
        </div>
        {items.length > 0 && (
          <button onClick={clear} className="text-xs font-mono text-red-500 hover:text-red-400 transition-colors mt-1">
            CLEAR ALL
          </button>
        )}
      </div>

      {/* Ordered list */}
      {items.length > 0 && (
        <div className="space-y-1.5">
          {items.map((item, idx) => (
            <div
              key={item.id}
              className="flex items-center gap-2 bg-gray-800 border border-gray-700 rounded-xl px-3 py-2"
            >
              {/* Position number */}
              <div className="w-5 text-center text-xs font-mono text-gray-600 flex-shrink-0">
                {idx + 1}
              </div>

              {/* Icon */}
              <div className="text-base flex-shrink-0">{itemIcon(item)}</div>

              {/* Label */}
              <div className="flex-1 min-w-0">
                {item.type === 'photo' ? (
                  <div className="flex items-center gap-2">
                    <img
                      src={item.content?.url}
                      alt=""
                      className="h-6 w-10 object-cover rounded border border-gray-600"
                    />
                    <span className="text-xs text-gray-300 font-mono truncate">{itemLabel(item)}</span>
                  </div>
                ) : (
                  <span className="text-xs text-gray-300 font-mono truncate block">{itemLabel(item)}</span>
                )}
              </div>

              {/* Duration */}
              <div className="flex items-center gap-1 flex-shrink-0">
                {editingDuration === item.id ? (
                  <input
                    type="number"
                    defaultValue={item.duration}
                    min={5}
                    max={3600}
                    autoFocus
                    className="w-14 bg-gray-700 border border-blue-500 text-gray-200 font-mono text-xs rounded px-1.5 py-0.5 text-center"
                    onBlur={(e) => saveDuration(item, e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') saveDuration(item, e.target.value)
                      if (e.key === 'Escape') setEditingDuration(null)
                    }}
                  />
                ) : (
                  <button
                    onClick={() => setEditingDuration(item.id)}
                    className="text-xs font-mono text-gray-400 hover:text-gray-200 bg-gray-700 rounded px-2 py-0.5 transition-colors"
                    title="Click to edit duration"
                  >
                    {item.duration}s
                  </button>
                )}
              </div>

              {/* Reorder */}
              <div className="flex gap-0.5 flex-shrink-0">
                <button
                  onClick={() => move(idx, -1)}
                  disabled={idx === 0}
                  className="w-5 h-5 flex items-center justify-center text-gray-500 hover:text-gray-200 disabled:opacity-20 transition-colors text-xs"
                >
                  ↑
                </button>
                <button
                  onClick={() => move(idx, 1)}
                  disabled={idx === items.length - 1}
                  className="w-5 h-5 flex items-center justify-center text-gray-500 hover:text-gray-200 disabled:opacity-20 transition-colors text-xs"
                >
                  ↓
                </button>
              </div>

              {/* Delete */}
              <button
                onClick={() => remove(item.id)}
                className="w-5 h-5 flex items-center justify-center text-gray-600 hover:text-red-400 transition-colors text-sm flex-shrink-0"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {items.length === 0 && !showAdd && (
        <div className="text-center py-8 text-gray-600 font-mono text-sm border border-dashed border-gray-800 rounded-xl">
          No items yet
        </div>
      )}

      {/* Add item form */}
      {showAdd ? (
        <div className="bg-gray-800 border border-gray-600 rounded-xl p-4 space-y-3">
          <div className="text-xs font-mono text-gray-400 uppercase tracking-wider">Add Item</div>

          {/* Type tabs */}
          <div className="flex gap-1">
            {['mode', 'text', 'photo'].map(t => (
              <button
                key={t}
                onClick={() => setAddType(t)}
                className={`flex-1 py-1.5 rounded-lg font-mono text-xs font-semibold tracking-wider transition-colors ${
                  addType === t
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-400 hover:text-gray-200'
                }`}
              >
                {t === 'mode' ? 'Mode' : t === 'text' ? 'Text' : 'Photo'}
              </button>
            ))}
          </div>

          {/* Type-specific content */}
          {addType === 'mode' && (
            <div className="grid grid-cols-2 gap-1.5">
              {availableModes.map(m => (
                <button
                  key={m.id}
                  onClick={() => setAddMode(m.id)}
                  className={`flex items-center gap-2 rounded-lg px-3 py-2 text-left transition-colors ${
                    addMode === m.id
                      ? 'bg-blue-900/50 border border-blue-600 text-gray-200'
                      : 'bg-gray-700 text-gray-400 hover:text-gray-200'
                  }`}
                >
                  <span>{m.icon}</span>
                  <span className="font-mono text-xs">{m.label}</span>
                </button>
              ))}
            </div>
          )}

          {addType === 'text' && (
            <textarea
              value={addText}
              onChange={e => setAddText(e.target.value)}
              placeholder="Enter message text…"
              rows={3}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-200 font-mono placeholder-gray-600 resize-none focus:outline-none focus:border-blue-500"
            />
          )}

          {addType === 'photo' && (
            <div
              onClick={() => photoRef.current?.click()}
              className="border border-dashed border-gray-600 rounded-lg p-4 text-center cursor-pointer hover:border-gray-400 transition-colors"
            >
              <input
                ref={photoRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={e => setAddPhoto(e.target.files[0])}
              />
              {addPhoto ? (
                <div className="space-y-1">
                  <img
                    src={URL.createObjectURL(addPhoto)}
                    alt=""
                    className="mx-auto h-16 object-contain rounded"
                  />
                  <div className="text-xs text-gray-400 font-mono">{addPhoto.name}</div>
                </div>
              ) : (
                <>
                  <div className="text-2xl mb-1">🖼️</div>
                  <div className="text-xs text-gray-400 font-mono">Click to select photo</div>
                </>
              )}
            </div>
          )}

          {/* Duration */}
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-gray-400">Duration</span>
            <input
              type="number"
              value={addDuration}
              min={5}
              max={3600}
              onChange={e => setAddDuration(parseInt(e.target.value, 10) || 30)}
              className="w-20 bg-gray-700 border border-gray-600 text-gray-200 font-mono text-sm rounded-lg px-2 py-1 text-center focus:outline-none focus:border-blue-500"
            />
            <span className="text-xs font-mono text-gray-500">seconds</span>
          </div>

          {/* Action buttons */}
          <div className="flex gap-2 pt-1">
            <button
              onClick={addItem}
              disabled={saving || (addType === 'text' && !addText.trim()) || (addType === 'photo' && !addPhoto)}
              className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-mono text-sm rounded-xl py-2.5 font-semibold tracking-wider transition-colors"
            >
              {saving ? 'ADDING…' : 'ADD TO PLAYLIST'}
            </button>
            <button
              onClick={() => { setShowAdd(false); setAddPhoto(null); setAddText('') }}
              className="bg-gray-700 hover:bg-gray-600 text-gray-300 font-mono text-sm rounded-xl px-4 transition-colors"
            >
              CANCEL
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setShowAdd(true)}
          className="w-full border-2 border-dashed border-gray-700 hover:border-gray-500 rounded-xl py-3 font-mono text-sm text-gray-500 hover:text-gray-300 transition-all"
        >
          + ADD ITEM
        </button>
      )}

      {/* Play Now */}
      {items.length > 0 && (
        <button
          onClick={playNow}
          className={`w-full font-mono text-sm rounded-xl py-3 transition-colors font-semibold tracking-wider ${
            playing ? 'bg-green-700 text-white' : 'bg-blue-600 hover:bg-blue-700 text-white'
          }`}
        >
          {playing ? '▶ PLAYING' : '▶ PLAY NOW'}
        </button>
      )}

      {/* Tips */}
      <div className="bg-gray-900 rounded-lg p-3 space-y-1.5">
        <div className="text-xs text-gray-600 font-mono uppercase tracking-wider mb-2">How it works</div>
        <div className="text-xs text-gray-500 font-mono">· Each item plays for its own duration, then advances automatically</div>
        <div className="text-xs text-gray-500 font-mono">· The sequence loops forever — playlist overrides the Modes tab</div>
        <div className="text-xs text-gray-500 font-mono">· Mix modes, text, and photos in any order</div>
        <div className="text-xs text-gray-500 font-mono">· Remove all items to return to the regular Modes rotation</div>
        <div className="text-xs text-gray-500 font-mono">· Click a duration badge to edit it inline</div>
      </div>
    </div>
  )
}
