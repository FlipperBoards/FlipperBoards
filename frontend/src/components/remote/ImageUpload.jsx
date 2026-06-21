import React, { useState, useRef, useCallback } from 'react'
import {
  imageToMatrix,
  imageToColorMatrix,
  matrixToPreviewCanvas,
  colorMatrixToPreviewCanvas,
} from '../../utils/imageToMatrix'

const MODES = [
  {
    id: 'full',
    label: 'Full Color',
    desc: 'Every tile gets its exact pixel color — true photo mosaic',
    badge: '16M colors',
  },
  {
    id: 'color',
    label: '8-Color Mosaic',
    desc: 'Nearest Vestaboard color per tile — bold, graphic look',
    badge: '8 colors',
  },
  {
    id: 'mono',
    label: 'Monochrome',
    desc: 'Brightness mapped to character density — ASCII art aesthetic',
    badge: 'chars',
  },
]

export default function ImageUpload({ rows, cols, screenId = 'main' }) {
  const [mode, setMode] = useState('full')
  const [preview, setPreview] = useState(null)
  const [pending, setPending] = useState(null)   // { type: 'matrix'|'color', data }
  const [processing, setProcessing] = useState(false)
  const [pushed, setPushed] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef(null)
  const lastFileRef = useRef(null)

  const process = useCallback(async (file, selectedMode) => {
    if (!file || !file.type.startsWith('image/')) return
    setProcessing(true)
    setPreview(null)
    setPending(null)
    setPushed(false)
    lastFileRef.current = file

    try {
      if (selectedMode === 'full') {
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

  const push = async () => {
    if (!pending) return
    const qs = `?screen=${encodeURIComponent(screenId)}`

    if (pending.type === 'color') {
      await fetch(`/api/display/color-matrix${qs}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ color_matrix: pending.data }),
      })
    } else {
      await fetch(`/api/display/matrix${qs}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ matrix: pending.data }),
      })
    }
    setPushed(true)
    setTimeout(() => setPushed(false), 3000)
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-mono text-gray-200 font-semibold tracking-wider uppercase">
        Image Mosaic
      </h2>
      <p className="text-xs text-gray-500 font-mono">
        Upload any image — each tile becomes one pixel. Switching modes re-processes
        the same image instantly.
      </p>

      {/* Mode selector */}
      <div className="space-y-2">
        {MODES.map(m => (
          <button
            key={m.id}
            onClick={() => handleModeChange(m.id)}
            className={`w-full flex items-center gap-3 rounded-xl px-4 py-3 border text-left transition-all ${
              mode === m.id
                ? 'bg-blue-900/40 border-blue-600'
                : 'bg-gray-800 border-gray-700 hover:border-gray-500 opacity-70 hover:opacity-100'
            }`}
          >
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm text-gray-200 font-semibold">{m.label}</span>
                <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                  mode === m.id ? 'bg-blue-700 text-blue-200' : 'bg-gray-700 text-gray-400'
                }`}>{m.badge}</span>
              </div>
              <span className="text-xs text-gray-500 font-mono">{m.desc}</span>
            </div>
            <div className={`w-3 h-3 rounded-full border-2 flex-shrink-0 ${
              mode === m.id ? 'border-blue-400 bg-blue-400' : 'border-gray-600'
            }`} />
          </button>
        ))}
      </div>

      {/* Drop zone */}
      <div
        onClick={() => fileRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        className={`relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
          dragOver ? 'border-blue-500 bg-blue-900/20' : 'border-gray-700 hover:border-gray-500 bg-gray-900/50'
        }`}
      >
        <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleInputChange} />
        {processing ? (
          <div className="text-gray-400 font-mono text-sm animate-pulse">PROCESSING...</div>
        ) : (
          <>
            <div className="text-4xl mb-2">🖼️</div>
            <div className="text-gray-400 font-mono text-sm">DROP IMAGE or CLICK TO BROWSE</div>
            <div className="text-gray-600 font-mono text-xs mt-1">
              Will be sampled at {cols}×{rows} tiles
            </div>
          </>
        )}
      </div>

      {/* Preview + push */}
      {preview && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs text-gray-500 font-mono uppercase tracking-wider">
              Preview — {cols}×{rows} tiles
            </div>
            <div className="text-xs text-gray-600 font-mono">
              {MODES.find(m => m.id === mode)?.label}
            </div>
          </div>

          {/* Preview image */}
          <div className="overflow-hidden rounded-lg border border-gray-700 bg-black">
            <img
              src={preview}
              alt="Tile preview"
              className="w-full"
              style={{ imageRendering: 'pixelated' }}
            />
          </div>

          <div className="flex gap-2">
            <button
              onClick={push}
              className={`flex-1 font-mono text-sm rounded-xl py-3 transition-colors font-semibold tracking-wider ${
                pushed ? 'bg-green-700 text-white' : 'bg-blue-600 hover:bg-blue-700 text-white'
              }`}
            >
              {pushed ? '✓ SENT TO DISPLAY' : 'PUSH TO DISPLAY'}
            </button>
            <button
              onClick={() => fileRef.current?.click()}
              className="bg-gray-700 hover:bg-gray-600 text-gray-300 font-mono text-sm rounded-xl px-4 transition-colors"
            >
              NEW
            </button>
          </div>
        </div>
      )}

      {/* Tips */}
      <div className="bg-gray-900 rounded-lg p-3 space-y-1.5">
        <div className="text-xs text-gray-600 font-mono uppercase tracking-wider mb-2">Tips</div>
        <div className="text-xs text-gray-500 font-mono">· Full Color: best for photos and artwork — exact RGB per tile</div>
        <div className="text-xs text-gray-500 font-mono">· 8-Color: bold graphic look, great for logos and icons</div>
        <div className="text-xs text-gray-500 font-mono">· Mono: high-contrast images work best, like faces or silhouettes</div>
        <div className="text-xs text-gray-500 font-mono">· Square crop your image first for best fit on square grids</div>
        <div className="text-xs text-gray-500 font-mono">· Switching modes re-processes without re-uploading</div>
      </div>
    </div>
  )
}
