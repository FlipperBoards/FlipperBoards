import React, { useState, useRef, useCallback, useEffect } from 'react'
import DurationPicker from './DurationPicker'
import { apiFetch, apiJson } from '../../utils/api'
import { useToast } from '../Toast'
import {
  imageToMatrix,
  imageToColorMatrix,
  matrixToPreviewCanvas,
  colorMatrixToPreviewCanvas,
} from '../../utils/imageToMatrix'

const MODES = [
  { id: 'photo', label: 'Photo Split',   desc: 'Full photo divided across tiles — like a puzzle', badge: 'puzzle' },
  { id: 'full',  label: 'Full Color',    desc: 'True photo mosaic — one pixel color per tile',    badge: '16M colors' },
  { id: 'color', label: '8-Color Mosaic', desc: 'Nearest Vestaboard color per tile',              badge: '8 colors' },
  { id: 'mono',  label: 'Monochrome',    desc: 'Brightness → character density (ASCII art)',       badge: 'chars' },
]

export default function ImageUpload({ rows, cols, screenId = 'main' }) {
  const [mode, setMode] = useState('photo')
  const [preview, setPreview] = useState(null)
  const [pending, setPending] = useState(null)   // {type, data, libraryId?}
  const [processing, setProcessing] = useState(false)
  const [pushed, setPushed] = useState(false)
  const [dragOver, setDragOver] = useState(false)

  // Name / folder for the current pending image
  const [nameInput, setNameInput] = useState('')
  const [folderInput, setFolderInput] = useState('')
  const [pushDuration, setPushDuration] = useState('')   // '' = until changed

  // Library
  const [library, setLibrary] = useState([])
  const [activeFolder, setActiveFolder] = useState('_all')
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')

  const fileRef = useRef(null)
  const lastFileRef = useRef(null)
  const previewBlobRef = useRef(null)
  const showToast = useToast()

  const loadLibrary = useCallback(async () => {
    try {
      const res = await fetch('/api/uploads')
      if (res.ok) setLibrary(await res.json())
    } catch { /* silent */ }
  }, [])

  useEffect(() => { loadLibrary() }, [loadLibrary])

  const process = useCallback(async (file, selectedMode, nameOverride = null) => {
    if (!file || !file.type.startsWith('image/')) return
    setProcessing(true)
    setPreview(null)
    setPending(null)
    setPushed(false)
    // nameOverride keeps a library item's saved name instead of the blob filename
    setNameInput(nameOverride ?? (file.name ? file.name.replace(/\.[^.]+$/, '') : ''))

    if (previewBlobRef.current) {
      URL.revokeObjectURL(previewBlobRef.current)
      previewBlobRef.current = null
    }

    lastFileRef.current = file

    try {
      if (selectedMode === 'photo') {
        const url = URL.createObjectURL(file)
        previewBlobRef.current = url
        setPreview(url)
        setPending({ type: 'photo', data: file })
      } else if (selectedMode === 'full') {
        const cm = await imageToColorMatrix(file, rows, cols)
        const canvas = colorMatrixToPreviewCanvas(cm, rows, cols, 12)
        setPreview(canvas.toDataURL())
        setPending({ type: 'color', data: cm })
      } else {
        const m = await imageToMatrix(file, rows, cols, selectedMode)
        const canvas = matrixToPreviewCanvas(m, rows, cols, 12)
        setPreview(canvas.toDataURL())
        setPending({ type: 'matrix', data: m })
      }
    } finally {
      setProcessing(false)
    }
  }, [rows, cols])

  const handleFile = (file) => { lastFileRef.current = file; process(file, mode) }
  const handleInputChange = (e) => handleFile(e.target.files[0])
  const handleDrop = (e) => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]) }

  const handleModeChange = (newMode) => {
    setMode(newMode)
    if (lastFileRef.current) process(lastFileRef.current, newMode)
  }

  // Use a library image — photo mode uses push-by-id; other modes re-download and process
  const useFromLibrary = async (item) => {
    setPushed(false)
    if (mode === 'photo') {
      setPreview(item.url)
      setNameInput(item.name || '')
      setFolderInput(item.folder || '')
      setPending({ type: 'photo', data: null, libraryId: item.id })
      lastFileRef.current = null
    } else {
      setProcessing(true)
      try {
        const res = await fetch(item.url)
        const blob = await res.blob()
        const file = new File([blob], item.name || 'image.jpg', { type: blob.type || 'image/jpeg' })
        setFolderInput(item.folder || '')
        process(file, mode, item.name || '')
      } catch {
        setProcessing(false)
        showToast('Could not load that image from the library')
      }
    }
  }

  const deleteFromLibrary = async (item, e) => {
    e.stopPropagation()
    try {
      await apiFetch(`/api/uploads/${item.id}`, { method: 'DELETE' })
    } catch (err) {
      showToast(`Delete failed: ${err.message}`)
    }
    loadLibrary()
  }

  const startRename = (item, e) => {
    e.stopPropagation()
    setEditingId(item.id)
    setEditName(item.name || '')
  }

  const commitRename = async (id) => {
    try {
      await apiJson(`/api/uploads/${id}`, 'PATCH', { name: editName })
    } catch (err) {
      showToast(`Rename failed: ${err.message}`)
    }
    setEditingId(null)
    loadLibrary()
  }

  const push = async () => {
    if (!pending || processing) return
    const qs = `?screen=${encodeURIComponent(screenId)}`
    const dur = pushDuration !== '' ? parseInt(pushDuration, 10) : null

    try {
      if (pending.type === 'photo') {
        if (pending.libraryId) {
          const durQs = dur !== null ? `&duration=${dur}` : ''
          await apiFetch(`/api/display/photo/push/${pending.libraryId}${qs}${durQs}`, { method: 'POST' })
        } else {
          const fd = new FormData()
          fd.append('file', pending.data)
          if (nameInput.trim()) fd.append('name', nameInput.trim())
          if (folderInput.trim()) fd.append('folder', folderInput.trim())
          if (dur !== null) fd.append('duration', String(dur))
          await apiFetch(`/api/display/photo${qs}`, { method: 'POST', body: fd })
          loadLibrary()
        }
      } else if (pending.type === 'color') {
        await apiJson(`/api/display/color-matrix${qs}`, 'POST',
                      { color_matrix: pending.data, duration: dur })
      } else {
        await apiJson(`/api/display/matrix${qs}`, 'POST',
                      { matrix: pending.data, duration: dur })
      }
      setPushed(true)
      setTimeout(() => setPushed(false), 3000)
    } catch (err) {
      showToast(`Push failed: ${err.message}`)
    }
  }

  // Derived library state
  const folders = [...new Set(library.map(i => i.folder).filter(Boolean))].sort()
  const visibleLibrary = activeFolder === '_all'
    ? library
    : library.filter(i => i.folder === activeFolder)

  return (
    <div className="space-y-5">
      <h2 className="text-sm font-semibold uppercase tracking-widest" style={{ color: 'var(--text-1)' }}>
        Image Push
      </h2>

      {/* Mode selector */}
      <div className="space-y-1.5">
        {MODES.map(m => (
          <button
            key={m.id}
            onClick={() => handleModeChange(m.id)}
            className="w-full flex items-center gap-3 rounded-xl px-4 py-3 text-left transition-all"
            style={{
              background: mode === m.id ? 'var(--accent-dim)' : 'var(--surface)',
              border: `1px solid ${mode === m.id ? 'var(--accent-border)' : 'var(--border)'}`,
              opacity: mode === m.id ? 1 : 0.7,
            }}
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold" style={{ color: 'var(--text-1)' }}>{m.label}</span>
                <span
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded"
                  style={{
                    background: mode === m.id ? 'rgba(59,130,246,0.2)' : 'var(--surface)',
                    color: mode === m.id ? 'var(--accent)' : 'var(--text-3)',
                  }}
                >
                  {m.badge}
                </span>
              </div>
              <span className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>{m.desc}</span>
            </div>
            <span
              className="w-3 h-3 rounded-full border-2 flex-shrink-0 transition-all"
              style={{
                borderColor: mode === m.id ? 'var(--accent)' : 'var(--text-3)',
                background: mode === m.id ? 'var(--accent)' : 'transparent',
              }}
            />
          </button>
        ))}
      </div>

      {/* Drop zone */}
      <div
        onClick={() => fileRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        className="relative rounded-xl p-8 text-center cursor-pointer transition-all"
        style={{
          border: `2px dashed ${dragOver ? 'var(--accent)' : 'var(--border)'}`,
          background: dragOver ? 'var(--accent-dim)' : 'rgba(0,0,0,0.2)',
        }}
      >
        <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleInputChange} />
        {processing ? (
          <div className="text-sm font-mono animate-pulse" style={{ color: 'var(--text-2)' }}>
            Processing…
          </div>
        ) : (
          <>
            <div className="text-3xl mb-2 opacity-60">🖼️</div>
            <div className="text-xs font-mono font-medium" style={{ color: 'var(--text-2)' }}>
              Drop image or click to browse
            </div>
            <div className="text-[11px] font-mono mt-1" style={{ color: 'var(--text-3)' }}>
              {mode === 'photo'
                ? `Divided across ${cols}×${rows} tiles`
                : `Sampled at ${cols}×${rows} tiles`}
            </div>
          </>
        )}
      </div>

      {/* Preview + push */}
      {preview && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="section-label">Preview — {cols}×{rows}</p>
            <span className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>
              {MODES.find(m => m.id === mode)?.label}
            </span>
          </div>

          <div
            className="overflow-hidden rounded-xl relative"
            style={{ border: '1px solid var(--border)', background: '#000' }}
          >
            <img
              src={preview}
              alt="Tile preview"
              className="w-full block"
              style={{ imageRendering: mode === 'photo' ? 'auto' : 'pixelated' }}
            />
            {mode === 'photo' && (
              <div
                className="absolute inset-0 pointer-events-none"
                style={{
                  backgroundImage: `
                    repeating-linear-gradient(to right, rgba(0,0,0,0.3) 0px, rgba(0,0,0,0.3) 1px, transparent 1px, transparent calc(100% / ${cols})),
                    repeating-linear-gradient(to bottom, rgba(0,0,0,0.3) 0px, rgba(0,0,0,0.3) 1px, transparent 1px, transparent calc(100% / ${rows}))
                  `,
                }}
              />
            )}
          </div>

          {/* Name + folder (photo mode only — saved to library) */}
          {mode === 'photo' && !pending?.libraryId && (
            <div className="grid grid-cols-2 gap-2">
              <div className="flex flex-col gap-1">
                <label className="section-label">Name</label>
                <input
                  type="text"
                  value={nameInput}
                  onChange={e => setNameInput(e.target.value)}
                  placeholder="Optional label"
                  className="fb-input"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="section-label">Folder</label>
                <input
                  type="text"
                  list="folder-suggestions"
                  value={folderInput}
                  onChange={e => setFolderInput(e.target.value)}
                  placeholder="e.g. Logos"
                  className="fb-input"
                />
                <datalist id="folder-suggestions">
                  {folders.map(f => <option key={f} value={f} />)}
                </datalist>
              </div>
            </div>
          )}

          <div className="flex items-center justify-between gap-2 pb-1">
            <DurationPicker value={pushDuration} onChange={setPushDuration} />
          </div>

          <div className="flex gap-2">
            <button
              onClick={push}
              className="fb-btn-primary flex-1 py-3"
              style={pushed ? { background: '#16a34a' } : {}}
            >
              {pushed ? '✓ Sent to Display' : 'Push to Display'}
            </button>
            <button onClick={() => fileRef.current?.click()} className="fb-btn-ghost px-4">
              New
            </button>
          </div>
        </div>
      )}

      {/* Saved image library */}
      {library.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="section-label">Saved Images</p>
            <button
              onClick={loadLibrary}
              className="text-[11px] font-mono opacity-40 hover:opacity-80 transition-opacity"
              style={{ color: 'var(--text-2)' }}
            >
              refresh
            </button>
          </div>

          {/* Folder tabs */}
          {folders.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {['_all', ...folders].map(f => (
                <button
                  key={f}
                  onClick={() => setActiveFolder(f)}
                  className="text-[10px] font-mono px-2.5 py-1 rounded-lg transition-all"
                  style={{
                    background: activeFolder === f ? 'var(--accent-dim)' : 'var(--surface)',
                    border: `1px solid ${activeFolder === f ? 'var(--accent-border)' : 'var(--border)'}`,
                    color: activeFolder === f ? 'var(--accent)' : 'var(--text-3)',
                  }}
                >
                  {f === '_all' ? 'All' : f}
                </button>
              ))}
            </div>
          )}

          {/* Thumbnail grid */}
          <div
            className="rounded-xl p-3 overflow-y-auto"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)', maxHeight: 280 }}
          >
            <div className="grid grid-cols-4 gap-2">
              {visibleLibrary.map(item => (
                <div key={item.id} className="flex flex-col gap-1">
                  {/* Thumbnail */}
                  <div
                    onClick={() => useFromLibrary(item)}
                    className="relative rounded-lg overflow-hidden cursor-pointer group"
                    style={{ aspectRatio: '1', background: '#000' }}
                  >
                    <img src={item.url} alt={item.name || 'image'} className="w-full h-full object-cover" />
                    {/* Hover overlay */}
                    <div
                      className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
                      style={{ background: 'rgba(59,130,246,0.35)' }}
                    >
                      <span className="text-[10px] font-mono font-bold text-white">USE</span>
                    </div>
                    {/* Delete */}
                    <button
                      onClick={(e) => deleteFromLibrary(item, e)}
                      className="absolute top-1 right-1 w-4 h-4 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity text-white"
                      style={{ background: 'rgba(220,38,38,0.9)', fontSize: 10, lineHeight: 1 }}
                      title="Delete"
                    >
                      ×
                    </button>
                  </div>

                  {/* Inline rename */}
                  {editingId === item.id ? (
                    <input
                      autoFocus
                      value={editName}
                      onChange={e => setEditName(e.target.value)}
                      onBlur={() => commitRename(item.id)}
                      onKeyDown={e => { if (e.key === 'Enter') commitRename(item.id); if (e.key === 'Escape') setEditingId(null) }}
                      className="fb-input"
                      style={{ fontSize: 9, padding: '2px 4px' }}
                    />
                  ) : (
                    <button
                      onClick={(e) => startRename(item, e)}
                      className="text-left truncate text-[9px] font-mono opacity-50 hover:opacity-100 transition-opacity"
                      style={{ color: 'var(--text-2)' }}
                      title="Click to rename"
                    >
                      {item.name || 'Unnamed'}
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tips */}
      <div
        className="rounded-xl p-4 space-y-1.5"
        style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
      >
        <p className="section-label mb-2">Tips</p>
        <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>· Photo Split: great for logos &amp; artwork on Zoom backgrounds</p>
        <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>· Full Color: exact RGB per tile — best for photos</p>
        <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>· 8-Color: bold graphic look, great for icons</p>
        <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>· Mono: high-contrast images work best (faces, silhouettes)</p>
        <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>· Use the Queue tab to build a rotating photo playlist</p>
      </div>
    </div>
  )
}
