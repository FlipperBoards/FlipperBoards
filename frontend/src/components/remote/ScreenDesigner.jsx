import React, { useState, useRef, useEffect, useCallback } from 'react'
import { CHARS, COLOR_HEX, COLOR_NAMES, isColorCode, codeToChar } from '../../utils/charmap'

// ── Character categories ──────────────────────────────────────────────────────

const CATEGORIES = [
  { id: 'space',   label: 'SP',      codes: [0] },
  { id: 'letters', label: 'A–Z',     codes: Array.from({length: 26}, (_, i) => i + 1) },
  { id: 'numbers', label: '0–9',     codes: Array.from({length: 10}, (_, i) => i + 27) },
  { id: 'symbols', label: 'Sym',     codes: Array.from({length: 33}, (_, i) => i + 37) }, // 37-69 (skip 70 reserved)
  { id: 'colors',  label: 'Colors',  codes: Array.from({length: 7},  (_, i) => i + 71) },
]

// ── Tiny design thumbnail ─────────────────────────────────────────────────────

function DesignThumbnail({ matrix, cols }) {
  if (!matrix?.length) return null
  const rows = matrix.length
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: `repeat(${cols}, 1fr)`,
      width: 88, height: 24,
      borderRadius: 3, overflow: 'hidden',
      flexShrink: 0,
    }}>
      {matrix.flatMap((row, r) => row.map((code, c) => (
        <div key={`${r}-${c}`} style={{
          background: isColorCode(code) ? COLOR_HEX[code] : code === 0 ? '#0d0d1a' : '#c8d0e0',
        }} />
      )))}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ScreenDesigner({ rows, cols, screenId = 'main' }) {
  const blankMatrix = useCallback(
    () => Array.from({length: rows}, () => Array(cols).fill(0)),
    [rows, cols]
  )

  const [matrix, setMatrix]         = useState(blankMatrix)
  const [activeCode, setActiveCode] = useState(1)            // 'A'
  const [category, setCategory]     = useState('letters')
  const [designs, setDesigns]       = useState([])
  const [designName, setDesignName] = useState('')
  const [saveFeedback, setSaveFeedback] = useState('')
  const [pushFeedback, setPushFeedback] = useState('')
  const [pushDuration, setPushDuration] = useState('')
  const [queueDurations, setQueueDurations] = useState({})   // keyed by design id

  const isPainting = useRef(false)
  const qs = `?screen=${encodeURIComponent(screenId)}`

  // ── Load saved designs ──────────────────────────────────────────────────────

  const loadDesigns = useCallback(async () => {
    try {
      const res = await fetch(`/api/designs${qs}`)
      if (res.ok) setDesigns(await res.json())
    } catch { /* silent */ }
  }, [qs])

  useEffect(() => { loadDesigns() }, [loadDesigns])

  // ── Paint ───────────────────────────────────────────────────────────────────

  const paint = useCallback((r, c) => {
    setMatrix(prev => {
      const next = prev.map(row => [...row])
      next[r][c] = activeCode
      return next
    })
  }, [activeCode])

  const handlePointerDown = useCallback((e, r, c) => {
    e.preventDefault()
    isPainting.current = true
    paint(r, c)
  }, [paint])

  const handlePointerEnter = useCallback((r, c) => {
    if (isPainting.current) paint(r, c)
  }, [paint])

  const stopPainting = useCallback(() => { isPainting.current = false }, [])

  // ── Tools ───────────────────────────────────────────────────────────────────

  const fillAll   = () => setMatrix(Array.from({length: rows}, () => Array(cols).fill(activeCode)))
  const clearAll  = () => setMatrix(blankMatrix())

  // ── Push now ────────────────────────────────────────────────────────────────

  const pushNow = async () => {
    const dur = pushDuration !== '' ? parseInt(pushDuration, 10) : null
    const durQs = dur !== null ? `&duration=${dur}` : ''
    await fetch(`/api/display/matrix${qs}${durQs}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ matrix, duration: dur }),
    })
    setPushFeedback('sent')
    setTimeout(() => setPushFeedback(''), 2000)
  }

  // ── Save ────────────────────────────────────────────────────────────────────

  const saveDesign = async () => {
    if (!designName.trim()) { setSaveFeedback('Name required'); return }
    await fetch(`/api/designs${qs}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: designName.trim(), matrix }),
    })
    setSaveFeedback('saved')
    setTimeout(() => setSaveFeedback(''), 2000)
    setDesignName('')
    loadDesigns()
  }

  // ── Saved design actions ────────────────────────────────────────────────────

  const loadDesign  = (d) => setMatrix(d.matrix.map(r => [...r]))

  const pushDesign  = async (d) => {
    await fetch(`/api/designs/${d.id}/push${qs}`, { method: 'POST' })
  }

  const queueDesign = async (d) => {
    const dur = parseInt(queueDurations[d.id] || '30', 10)
    await fetch(`/api/designs/${d.id}/queue${qs}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ duration: dur }),
    })
  }

  const deleteDesign = async (d) => {
    await fetch(`/api/designs/${d.id}`, { method: 'DELETE' })
    loadDesigns()
  }

  // ── Character picker ────────────────────────────────────────────────────────

  const activeCat  = CATEGORIES.find(c => c.id === category) || CATEGORIES[1]
  const activeCodes = activeCat.codes

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5">
      <h2 className="text-sm font-semibold uppercase tracking-widest" style={{ color: 'var(--text-1)' }}>
        Screen Designer
      </h2>

      {/* ── Grid ── */}
      <div
        className="rounded-xl overflow-hidden select-none"
        style={{ border: '1px solid var(--border)', background: '#0d0d1a', touchAction: 'none' }}
        onPointerUp={stopPainting}
        onPointerLeave={stopPainting}
      >
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, 1fr)`, gap: '1px', background: '#0d0d1a' }}>
          {matrix.flatMap((row, r) =>
            row.map((code, c) => {
              const isColor = isColorCode(code)
              return (
                <div
                  key={`${r}-${c}`}
                  style={{
                    aspectRatio: '9/14',
                    background: isColor ? COLOR_HEX[code] : '#1a1a2e',
                    cursor: 'crosshair',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    touchAction: 'none',
                  }}
                  onPointerDown={e => handlePointerDown(e, r, c)}
                  onPointerEnter={() => handlePointerEnter(r, c)}
                >
                  {!isColor && code !== 0 && (
                    <span style={{
                      fontSize: '55%',
                      lineHeight: 1,
                      color: '#c8d0e0',
                      fontFamily: '"Bebas Neue", "Share Tech Mono", monospace',
                      pointerEvents: 'none',
                      userSelect: 'none',
                    }}>
                      {codeToChar(code)}
                    </span>
                  )}
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* ── Picker ── */}
      <div
        className="rounded-xl overflow-hidden"
        style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}
      >
        {/* Category tabs */}
        <div className="flex border-b" style={{ borderColor: 'var(--border)' }}>
          {CATEGORIES.map(cat => (
            <button
              key={cat.id}
              onClick={() => setCategory(cat.id)}
              className="flex-1 text-[10px] font-mono py-2 transition-colors"
              style={{
                color: category === cat.id ? 'var(--accent)' : 'var(--text-3)',
                background: category === cat.id ? 'var(--accent-dim)' : 'transparent',
                borderBottom: category === cat.id ? '2px solid var(--accent)' : '2px solid transparent',
              }}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Character grid */}
        <div className="p-3">
          {category === 'colors' ? (
            <div className="flex flex-wrap gap-2">
              {activeCodes.map(code => (
                <button
                  key={code}
                  onClick={() => setActiveCode(code)}
                  title={COLOR_NAMES[code]}
                  style={{
                    width: 32, height: 32,
                    borderRadius: 6,
                    background: COLOR_HEX[code],
                    border: activeCode === code ? '2px solid #fff' : '2px solid transparent',
                    boxShadow: activeCode === code ? `0 0 0 2px var(--accent)` : 'none',
                    flexShrink: 0,
                  }}
                />
              ))}
            </div>
          ) : (
            <div className="flex flex-wrap gap-1">
              {activeCodes.map(code => (
                <button
                  key={code}
                  onClick={() => setActiveCode(code)}
                  className="rounded flex items-center justify-center font-mono transition-colors"
                  style={{
                    width: code === 0 ? 48 : 26,
                    height: 26,
                    fontSize: 11,
                    background: activeCode === code ? 'var(--accent)' : 'rgba(255,255,255,0.06)',
                    color: activeCode === code ? '#fff' : 'var(--text-2)',
                    border: '1px solid',
                    borderColor: activeCode === code ? 'var(--accent)' : 'var(--border)',
                  }}
                >
                  {code === 0 ? 'SPACE' : codeToChar(code)}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Active char indicator */}
        <div
          className="flex items-center gap-3 px-3 pb-3"
        >
          <span className="text-[10px] font-mono" style={{ color: 'var(--text-3)' }}>Active:</span>
          <div
            className="w-8 h-10 rounded flex items-center justify-center flex-shrink-0"
            style={{
              background: isColorCode(activeCode) ? COLOR_HEX[activeCode] : 'var(--accent-dim)',
              border: '1px solid var(--accent-border)',
            }}
          >
            {isColorCode(activeCode) ? null : (
              <span style={{ color: 'var(--accent)', fontFamily: '"Bebas Neue", monospace', fontSize: 18 }}>
                {activeCode === 0 ? '·' : codeToChar(activeCode)}
              </span>
            )}
          </div>
          <div className="flex gap-2 ml-auto">
            <button
              onClick={fillAll}
              className="fb-btn-ghost text-[11px] px-3 py-1.5"
            >
              Fill All
            </button>
            <button
              onClick={clearAll}
              className="fb-btn-ghost text-[11px] px-3 py-1.5"
            >
              Clear
            </button>
          </div>
        </div>
      </div>

      {/* ── Push Now ── */}
      <div
        className="rounded-xl p-3 space-y-3"
        style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}
      >
        <p className="section-label">Push to Display</p>
        <div className="flex items-center gap-2">
          <label className="section-label whitespace-nowrap">Display for</label>
          <select
            value={pushDuration}
            onChange={e => setPushDuration(e.target.value)}
            className="fb-input py-1 text-[11px]"
          >
            <option value="">Until changed</option>
            <option value="10">10 sec</option>
            <option value="30">30 sec</option>
            <option value="60">1 min</option>
            <option value="300">5 min</option>
          </select>
          <button
            onClick={pushNow}
            className="fb-btn-primary text-[11px] px-4 py-1.5 ml-auto flex-shrink-0"
            style={pushFeedback === 'sent' ? { background: '#16a34a' } : {}}
          >
            {pushFeedback === 'sent' ? '✓ Sent' : 'Push Now'}
          </button>
        </div>
      </div>

      {/* ── Save Design ── */}
      <div
        className="rounded-xl p-3 space-y-3"
        style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}
      >
        <p className="section-label">Save Design</p>
        <div className="flex gap-2">
          <input
            type="text"
            value={designName}
            onChange={e => setDesignName(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') saveDesign() }}
            placeholder="Design name…"
            className="fb-input flex-1"
          />
          <button
            onClick={saveDesign}
            className="fb-btn-primary text-[11px] px-4 py-1.5 flex-shrink-0"
            style={saveFeedback === 'saved' ? { background: '#16a34a' } : {}}
          >
            {saveFeedback === 'saved' ? '✓ Saved' : saveFeedback || 'Save'}
          </button>
        </div>
      </div>

      {/* ── Saved Designs ── */}
      {designs.length > 0 && (
        <div className="space-y-2">
          <p className="section-label">Saved Designs</p>
          {designs.map(d => (
            <div
              key={d.id}
              className="rounded-xl p-3 space-y-2"
              style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}
            >
              <div className="flex items-center gap-3">
                <DesignThumbnail matrix={d.matrix} cols={cols} />
                <span
                  className="flex-1 text-xs font-mono truncate"
                  style={{ color: 'var(--text-1)' }}
                >
                  {d.name}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => loadDesign(d)}
                  className="fb-btn-ghost text-[10px] px-3 py-1"
                >
                  Load
                </button>
                <button
                  onClick={() => pushDesign(d)}
                  className="fb-btn-ghost text-[10px] px-3 py-1"
                >
                  Push
                </button>
                <div className="flex items-center gap-1 ml-auto">
                  <select
                    value={queueDurations[d.id] || '30'}
                    onChange={e => setQueueDurations(prev => ({ ...prev, [d.id]: e.target.value }))}
                    className="fb-input py-0.5 text-[10px]"
                    style={{ width: 72 }}
                  >
                    <option value="10">10s</option>
                    <option value="30">30s</option>
                    <option value="60">1 min</option>
                    <option value="300">5 min</option>
                  </select>
                  <button
                    onClick={() => queueDesign(d)}
                    className="fb-btn-ghost text-[10px] px-3 py-1"
                  >
                    + Queue
                  </button>
                  <button
                    onClick={() => deleteDesign(d)}
                    className="text-sm transition-colors"
                    style={{ color: 'var(--text-3)' }}
                    onMouseEnter={e => { e.currentTarget.style.color = '#ef4444' }}
                    onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-3)' }}
                  >
                    ×
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
