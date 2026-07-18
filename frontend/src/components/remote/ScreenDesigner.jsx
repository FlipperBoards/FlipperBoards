import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { CHARS, COLOR_HEX, COLOR_NAMES, isColorCode, codeToChar } from '../../utils/charmap'
import { apiFetch, apiJson } from '../../utils/api'
import { useToast } from '../Toast'
import { renderIconToTiles } from '../../utils/iconStamp'
import { ICON_CATEGORIES, ALL_ICONS } from '../../data/icons'
import * as FaSolid from '@fortawesome/free-solid-svg-icons'
import { library } from '@fortawesome/fontawesome-svg-core'

// Register all solid icons once
library.add(...Object.values(FaSolid).filter(v => v && v.prefix === 'fas'))

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
  const [busy, setBusy] = useState(false)
  const showToast = useToast()

  // ── Icon stamp state ──────────────────────────────────────────────────────────
  const [stampSearch, setStampSearch]         = useState('')
  const [stampIconName, setStampIconName]     = useState(null)   // importName string
  const [stampIconCat, setStampIconCat]       = useState(ICON_CATEGORIES[0].id)
  const [stampFgCode, setStampFgCode]         = useState(77)     // white
  const [stampBgCode, setStampBgCode]         = useState(0)      // space
  const [stampOriginX, setStampOriginX]       = useState(0)
  const [stampOriginY, setStampOriginY]       = useState(0)
  const [stampWidth, setStampWidth]           = useState(cols)
  const [stampHeight, setStampHeight]         = useState(rows)
  const [stampFitBoard, setStampFitBoard]     = useState(true)
  const [stampApplying, setStampApplying]     = useState(false)
  const [stampFeedback, setStampFeedback]     = useState('')
  const [stampThreshold, setStampThreshold]   = useState(80)

  // Paint mode: on touch devices the grid steals the scroll gesture, so
  // painting is opt-in there. Fine pointers (mouse) default to paint.
  const [paintMode, setPaintMode] = useState(
    () => !window.matchMedia?.('(pointer: coarse)')?.matches
  )

  const isPainting = useRef(false)
  const qs = `?screen=${encodeURIComponent(screenId)}`
  const draftKey = `fb-designer-draft-${screenId}`

  // ── Undo / redo (bounded history of matrix snapshots) ───────────────────────

  const undoStack = useRef([])
  const redoStack = useRef([])
  const [historyVersion, setHistoryVersion] = useState(0)  // re-render for button states

  const snapshot = useCallback((m) => {
    undoStack.current.push(m.map(row => [...row]))
    if (undoStack.current.length > 50) undoStack.current.shift()
    redoStack.current = []
    setHistoryVersion(v => v + 1)
  }, [])

  const undo = useCallback(() => {
    if (!undoStack.current.length) return
    setMatrix(prev => {
      redoStack.current.push(prev.map(row => [...row]))
      const restored = undoStack.current.pop()
      setHistoryVersion(v => v + 1)
      return restored
    })
  }, [])

  const redo = useCallback(() => {
    if (!redoStack.current.length) return
    setMatrix(prev => {
      undoStack.current.push(prev.map(row => [...row]))
      const restored = redoStack.current.pop()
      setHistoryVersion(v => v + 1)
      return restored
    })
  }, [])

  useEffect(() => {
    const onKey = (e) => {
      if (!(e.ctrlKey || e.metaKey)) return
      if (e.key === 'z' && !e.shiftKey) { e.preventDefault(); undo() }
      else if (e.key === 'y' || (e.key === 'z' && e.shiftKey)) { e.preventDefault(); redo() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [undo, redo])

  // ── Draft autosave — switching tabs unmounts this component ─────────────────

  useEffect(() => {
    try {
      const saved = localStorage.getItem(draftKey)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed) && parsed.length === rows && parsed[0]?.length === cols) {
          setMatrix(parsed)
        }
      }
    } catch { /* corrupt draft — ignore */ }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftKey])

  useEffect(() => {
    try { localStorage.setItem(draftKey, JSON.stringify(matrix)) } catch { /* full */ }
  }, [matrix, draftKey])

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
    if (!paintMode) {
      // Tap-to-place mode: single tap paints one tile, no drag capture
      snapshot(matrixRef.current)
      paint(r, c)
      return
    }
    e.preventDefault()
    isPainting.current = true
    snapshot(matrixRef.current)  // one undo step per stroke
    paint(r, c)
  }, [paint, paintMode, snapshot])

  const handlePointerEnter = useCallback((r, c) => {
    if (paintMode && isPainting.current) paint(r, c)
  }, [paint, paintMode])

  const stopPainting = useCallback(() => { isPainting.current = false }, [])

  // Live matrix ref for stroke snapshots (avoids stale closure)
  const matrixRef = useRef(matrix)
  matrixRef.current = matrix

  // ── Tools ───────────────────────────────────────────────────────────────────

  const fillAll = () => {
    snapshot(matrixRef.current)
    setMatrix(Array.from({length: rows}, () => Array(cols).fill(activeCode)))
  }
  const clearAll = () => {
    snapshot(matrixRef.current)
    setMatrix(blankMatrix())
  }

  // ── Icon stamp ──────────────────────────────────────────────────────────────

  const stampFilteredIcons = useMemo(() => {
    if (stampSearch.trim()) {
      const q = stampSearch.toLowerCase()
      return ALL_ICONS.filter(i =>
        i.label.toLowerCase().includes(q) || i.id.includes(q)
      )
    }
    const cat = ICON_CATEGORIES.find(c => c.id === stampIconCat)
    return cat ? cat.icons : []
  }, [stampSearch, stampIconCat])

  const applyStamp = useCallback(async () => {
    if (!stampIconName) return
    const iconDef = FaSolid[stampIconName]
    if (!iconDef) return
    setStampApplying(true)
    setStampFeedback('')
    try {
      const sw = stampFitBoard ? cols : Math.min(stampWidth, cols - stampOriginX)
      const sh = stampFitBoard ? rows : Math.min(stampHeight, rows - stampOriginY)
      const ox = stampFitBoard ? 0 : Math.max(0, stampOriginX)
      const oy = stampFitBoard ? 0 : Math.max(0, stampOriginY)
      const stamp = await renderIconToTiles(iconDef, sw, sh, stampFgCode, stampBgCode, stampThreshold)
      snapshot(matrixRef.current)
      setMatrix(prev => {
        const next = prev.map(row => [...row])
        for (let r = 0; r < sh; r++) {
          for (let c = 0; c < sw; c++) {
            if (oy + r < rows && ox + c < cols) {
              next[oy + r][ox + c] = stamp[r][c]
            }
          }
        }
        return next
      })
      setStampFeedback('applied')
      setTimeout(() => setStampFeedback(''), 2000)
    } catch (err) {
      setStampFeedback('error')
      setTimeout(() => setStampFeedback(''), 2000)
    } finally {
      setStampApplying(false)
    }
  }, [stampIconName, stampFgCode, stampBgCode, stampFitBoard, stampWidth, stampHeight, stampOriginX, stampOriginY, stampThreshold, cols, rows])

  // ── Push now ────────────────────────────────────────────────────────────────

  const pushNow = async () => {
    if (busy) return
    const dur = pushDuration !== '' ? parseInt(pushDuration, 10) : null
    setBusy(true)
    try {
      await apiJson(`/api/display/matrix${qs}`, 'POST', { matrix, duration: dur })
      setPushFeedback('sent')
      setTimeout(() => setPushFeedback(''), 2000)
    } catch (err) {
      showToast(`Push failed: ${err.message}`)
    } finally {
      setBusy(false)
    }
  }

  // ── Save ────────────────────────────────────────────────────────────────────

  const saveDesign = async () => {
    if (!designName.trim()) { setSaveFeedback('Name required'); return }
    if (busy) return
    setBusy(true)
    try {
      await apiJson(`/api/designs${qs}`, 'POST', { name: designName.trim(), matrix })
      setSaveFeedback('saved')
      setTimeout(() => setSaveFeedback(''), 2000)
      setDesignName('')  // only cleared on success
      loadDesigns()
    } catch (err) {
      showToast(`Save failed: ${err.message}`)
    } finally {
      setBusy(false)
    }
  }

  // ── Saved design actions ────────────────────────────────────────────────────

  const loadDesign  = (d) => {
    snapshot(matrixRef.current)
    setMatrix(d.matrix.map(r => [...r]))
  }

  const pushDesign  = async (d) => {
    try {
      await apiFetch(`/api/designs/${d.id}/push${qs}`, { method: 'POST' })
    } catch (err) {
      showToast(`Push failed: ${err.message}`)
    }
  }

  const queueDesign = async (d) => {
    const dur = parseInt(queueDurations[d.id] || '30', 10)
    try {
      await apiJson(`/api/designs/${d.id}/queue${qs}`, 'POST', { duration: dur })
      showToast(`"${d.name}" added to the queue`, 'success')
    } catch (err) {
      showToast(`Queue failed: ${err.message}`)
    }
  }

  const deleteDesign = async (d) => {
    try {
      await apiFetch(`/api/designs/${d.id}`, { method: 'DELETE' })
    } catch (err) {
      showToast(`Delete failed: ${err.message}`)
    }
    loadDesigns()
  }

  // ── Character picker ────────────────────────────────────────────────────────

  const activeCat  = CATEGORIES.find(c => c.id === category) || CATEGORIES[1]
  const activeCodes = activeCat.codes

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-widest" style={{ color: 'var(--text-1)' }}>
          Screen Designer
        </h2>
        <div className="flex items-center gap-1.5">
          <button
            onClick={undo}
            disabled={undoStack.current.length === 0}
            className="fb-btn-ghost text-[11px] px-2.5 py-1 disabled:opacity-25"
            title="Undo (Ctrl+Z)"
          >
            ↩ Undo
          </button>
          <button
            onClick={redo}
            disabled={redoStack.current.length === 0}
            className="fb-btn-ghost text-[11px] px-2.5 py-1 disabled:opacity-25"
            title="Redo (Ctrl+Y)"
          >
            ↪ Redo
          </button>
          <button
            onClick={() => setPaintMode(p => !p)}
            className="text-[11px] font-mono px-2.5 py-1 rounded-lg transition-colors"
            style={paintMode
              ? { background: 'var(--accent)', color: '#fff' }
              : { background: 'var(--surface)', color: 'var(--text-3)', border: '1px solid var(--border)' }}
            title={paintMode
              ? 'Drag paints tiles (page scroll disabled over the grid)'
              : 'Tap places one tile; the page scrolls normally'}
          >
            {paintMode ? '🖌 Paint' : '👆 Tap'}
          </button>
        </div>
      </div>

      {/* ── Grid ── */}
      <div
        className="rounded-xl overflow-hidden select-none"
        style={{ border: '1px solid var(--border)', background: '#0d0d1a',
                 touchAction: paintMode ? 'none' : 'auto' }}
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
                    touchAction: paintMode ? 'none' : 'auto',
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

      {/* ── Icon Stamp ── */}
      <div
        className="rounded-xl overflow-hidden"
        style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}
      >
        <div className="px-3 pt-3 pb-2 flex items-center gap-2">
          <p className="section-label flex-1">Icon Stamp</p>
          <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 rounded" style={{ background: 'var(--accent-dim)', color: 'var(--accent)' }}>FA Free</span>
        </div>

        {/* Search + category tabs */}
        <div className="px-3 pb-2">
          <input
            type="text"
            value={stampSearch}
            onChange={e => setStampSearch(e.target.value)}
            placeholder="Search icons…"
            className="fb-input w-full text-[11px]"
          />
        </div>

        {!stampSearch.trim() && (
          <div className="flex overflow-x-auto border-b" style={{ borderColor: 'var(--border)' }}>
            {ICON_CATEGORIES.map(cat => (
              <button
                key={cat.id}
                onClick={() => setStampIconCat(cat.id)}
                className="flex-shrink-0 text-[9px] font-mono px-2.5 py-1.5 whitespace-nowrap transition-colors"
                style={{
                  color: stampIconCat === cat.id ? 'var(--accent)' : 'var(--text-3)',
                  background: stampIconCat === cat.id ? 'var(--accent-dim)' : 'transparent',
                  borderBottom: stampIconCat === cat.id ? '2px solid var(--accent)' : '2px solid transparent',
                }}
              >
                {cat.label}
              </button>
            ))}
          </div>
        )}

        {/* Icon grid */}
        <div className="p-2 flex flex-wrap gap-1 max-h-40 overflow-y-auto">
          {stampFilteredIcons.map(icon => {
            const iconDef = FaSolid[icon.importName]
            const isSelected = stampIconName === icon.importName
            const svgData = iconDef?.icon
            const path = svgData ? (Array.isArray(svgData[4]) ? svgData[4].join(' ') : svgData[4]) : null
            const vw = svgData ? svgData[0] : 512
            const vh = svgData ? svgData[1] : 512
            return (
              <button
                key={icon.id}
                onClick={() => setStampIconName(icon.importName)}
                title={icon.label}
                className="rounded flex flex-col items-center justify-center gap-0.5 transition-all"
                style={{
                  width: 40, height: 44,
                  background: isSelected ? 'var(--accent)' : 'rgba(255,255,255,0.05)',
                  border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`,
                  boxShadow: isSelected ? '0 0 0 2px var(--accent-glow)' : 'none',
                  flexShrink: 0,
                  padding: '4px 4px 2px',
                }}
              >
                {path ? (
                  <svg viewBox={`0 0 ${vw} ${vh}`} width="18" height="18" fill={isSelected ? '#fff' : 'var(--text-2)'}>
                    <path d={path} />
                  </svg>
                ) : (
                  <span style={{ fontSize: 10, color: 'var(--text-3)' }}>?</span>
                )}
                <span style={{ fontSize: '7px', color: isSelected ? '#fff' : 'var(--text-3)', lineHeight: 1, maxWidth: 36, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {icon.label}
                </span>
              </button>
            )
          })}
          {stampFilteredIcons.length === 0 && (
            <span className="text-[11px] px-2 py-2" style={{ color: 'var(--text-3)' }}>No icons found</span>
          )}
        </div>

        {/* Stamp settings */}
        <div className="px-3 pb-3 space-y-2.5">
          {/* Foreground / background color */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] font-mono" style={{ color: 'var(--text-3)', whiteSpace: 'nowrap' }}>Icon color:</span>
            <div className="flex gap-1">
              {Array.from({length: 7}, (_, i) => i + 71).map(code => (
                <button
                  key={code}
                  onClick={() => setStampFgCode(code)}
                  title={COLOR_NAMES[code]}
                  style={{
                    width: 20, height: 20, borderRadius: 4,
                    background: COLOR_HEX[code],
                    border: stampFgCode === code ? '2px solid #fff' : '2px solid transparent',
                    boxShadow: stampFgCode === code ? '0 0 0 2px var(--accent)' : 'none',
                    flexShrink: 0,
                  }}
                />
              ))}
              <button
                onClick={() => setStampFgCode(0)}
                title="Space"
                style={{
                  width: 20, height: 20, borderRadius: 4,
                  background: '#0d0d1a',
                  border: stampFgCode === 0 ? '2px solid #fff' : '1px solid var(--border)',
                  boxShadow: stampFgCode === 0 ? '0 0 0 2px var(--accent)' : 'none',
                  flexShrink: 0,
                }}
              />
            </div>
            <span className="text-[10px] font-mono ml-2" style={{ color: 'var(--text-3)', whiteSpace: 'nowrap' }}>BG:</span>
            <div className="flex gap-1">
              <button
                onClick={() => setStampBgCode(0)}
                title="Space (transparent)"
                style={{
                  width: 20, height: 20, borderRadius: 4,
                  background: '#0d0d1a',
                  border: stampBgCode === 0 ? '2px solid #fff' : '1px solid var(--border)',
                  boxShadow: stampBgCode === 0 ? '0 0 0 2px var(--accent)' : 'none',
                  flexShrink: 0,
                }}
              />
              {Array.from({length: 7}, (_, i) => i + 71).map(code => (
                <button
                  key={code}
                  onClick={() => setStampBgCode(code)}
                  title={COLOR_NAMES[code]}
                  style={{
                    width: 20, height: 20, borderRadius: 4,
                    background: COLOR_HEX[code],
                    border: stampBgCode === code ? '2px solid #fff' : '2px solid transparent',
                    boxShadow: stampBgCode === code ? '0 0 0 2px var(--accent)' : 'none',
                    flexShrink: 0,
                  }}
                />
              ))}
            </div>
          </div>

          {/* Region */}
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={stampFitBoard}
                onChange={e => setStampFitBoard(e.target.checked)}
                className="accent-blue-500"
              />
              <span className="text-[10px] font-mono" style={{ color: 'var(--text-2)' }}>Fit full board</span>
            </label>
          </div>
          {!stampFitBoard && (
            <div className="grid grid-cols-4 gap-1.5">
              {[
                { label: 'X', val: stampOriginX, set: v => setStampOriginX(Math.max(0, Math.min(v, cols - 1))) },
                { label: 'Y', val: stampOriginY, set: v => setStampOriginY(Math.max(0, Math.min(v, rows - 1))) },
                { label: 'W', val: stampWidth,   set: v => setStampWidth(Math.max(1, Math.min(v, cols))) },
                { label: 'H', val: stampHeight,  set: v => setStampHeight(Math.max(1, Math.min(v, rows))) },
              ].map(({ label, val, set }) => (
                <div key={label} className="flex flex-col items-center gap-0.5">
                  <span className="text-[9px] font-mono" style={{ color: 'var(--text-3)' }}>{label}</span>
                  <input
                    type="number"
                    min={label === 'W' || label === 'H' ? 1 : 0}
                    max={label === 'W' || label === 'X' ? cols : rows}
                    value={val}
                    onChange={e => set(parseInt(e.target.value, 10) || 0)}
                    className="fb-input text-center text-[11px] py-1"
                    style={{ width: '100%' }}
                  />
                </div>
              ))}
            </div>
          )}

          {/* Threshold */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono whitespace-nowrap" style={{ color: 'var(--text-3)' }}>
              Threshold: {stampThreshold}
            </span>
            <input
              type="range"
              min={10} max={220} step={5}
              value={stampThreshold}
              onChange={e => setStampThreshold(parseInt(e.target.value, 10))}
              className="flex-1 accent-blue-500"
              style={{ height: 4 }}
            />
          </div>

          {/* Apply button */}
          <button
            onClick={applyStamp}
            disabled={!stampIconName || stampApplying}
            className="fb-btn-primary w-full text-[11px] py-2 disabled:opacity-40"
            style={stampFeedback === 'applied' ? { background: '#16a34a' } : stampFeedback === 'error' ? { background: '#dc2626' } : {}}
          >
            {stampApplying ? 'Applying…' : stampFeedback === 'applied' ? '✓ Applied' : stampFeedback === 'error' ? '✗ Error' : stampIconName ? `Stamp "${ALL_ICONS.find(i => i.importName === stampIconName)?.label || stampIconName}"` : 'Select an icon above'}
          </button>
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
