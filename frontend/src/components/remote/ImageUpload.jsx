import React, { useState, useRef, useCallback } from 'react'
import { imageToMatrix, matrixToPreviewCanvas } from '../../utils/imageToMatrix'

export default function ImageUpload({ rows, cols, screenId = 'main' }) {
  const [mode, setMode] = useState('color')
  const [preview, setPreview] = useState(null)   // canvas data URL
  const [matrix, setMatrix] = useState(null)
  const [processing, setProcessing] = useState(false)
  const [pushed, setPushed] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef(null)

  const processFile = useCallback(async (file) => {
    if (!file || !file.type.startsWith('image/')) return
    setProcessing(true)
    setPreview(null)
    setMatrix(null)
    setPushed(false)

    try {
      const mat = await imageToMatrix(file, rows, cols, mode)
      const canvas = matrixToPreviewCanvas(mat, rows, cols, 12)
      setPreview(canvas.toDataURL())
      setMatrix(mat)
    } finally {
      setProcessing(false)
    }
  }, [rows, cols, mode])

  const handleFile = (e) => processFile(e.target.files[0])

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    processFile(e.dataTransfer.files[0])
  }

  const push = async () => {
    if (!matrix) return
    await fetch(`/api/display/matrix?screen=${encodeURIComponent(screenId)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ matrix }),
    })
    setPushed(true)
    setTimeout(() => setPushed(false), 3000)
  }

  // Re-process when mode changes (if we already have a matrix)
  const handleModeChange = (newMode) => {
    setMode(newMode)
    setMatrix(null)
    setPreview(null)
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-mono text-gray-200 font-semibold tracking-wider uppercase">
        Image Mosaic
      </h2>
      <p className="text-xs text-gray-500 font-mono">
        Upload any image — each tile becomes a pixel. The board maps it to the nearest
        Vestaboard color (color mode) or a brightness character (mono mode).
      </p>

      {/* Mode selector */}
      <div className="flex gap-2">
        {[['color', '8-Color Mosaic'], ['mono', 'Monochrome']].map(([val, label]) => (
          <button
            key={val}
            onClick={() => handleModeChange(val)}
            className={`flex-1 py-2 rounded-lg font-mono text-sm border transition-all ${
              mode === val
                ? 'bg-blue-900/40 border-blue-600 text-blue-300'
                : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Drop zone */}
      <div
        onClick={() => fileRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        className={`
          relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all
          ${dragOver
            ? 'border-blue-500 bg-blue-900/20'
            : 'border-gray-700 hover:border-gray-500 bg-gray-900/50'
          }
        `}
      >
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleFile}
        />
        {processing ? (
          <div className="text-gray-400 font-mono text-sm animate-pulse">PROCESSING...</div>
        ) : (
          <>
            <div className="text-4xl mb-2">🖼️</div>
            <div className="text-gray-400 font-mono text-sm">
              DROP IMAGE HERE or CLICK TO BROWSE
            </div>
            <div className="text-gray-600 font-mono text-xs mt-1">
              JPG, PNG, GIF, WebP — will be resized to {cols}×{rows} tiles
            </div>
          </>
        )}
      </div>

      {/* Preview */}
      {preview && (
        <div className="space-y-3">
          <div className="text-xs text-gray-500 font-mono uppercase tracking-wider">Preview ({cols}×{rows} tiles)</div>
          <div className="overflow-hidden rounded-lg border border-gray-700">
            <img
              src={preview}
              alt="Matrix preview"
              className="w-full"
              style={{ imageRendering: 'pixelated' }}
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={push}
              className={`flex-1 font-mono text-sm rounded-xl py-3 transition-colors ${
                pushed
                  ? 'bg-green-700 text-white'
                  : 'bg-blue-600 hover:bg-blue-700 text-white'
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
      <div className="bg-gray-900 rounded-lg p-3 space-y-1">
        <div className="text-xs text-gray-600 font-mono uppercase tracking-wider mb-2">Tips</div>
        <div className="text-xs text-gray-500 font-mono">· High contrast images work best</div>
        <div className="text-xs text-gray-500 font-mono">· Color mode: 8 colors + black (Vestaboard palette)</div>
        <div className="text-xs text-gray-500 font-mono">· Mono mode: 6 brightness levels using character density</div>
        <div className="text-xs text-gray-500 font-mono">· Square images fit best on a square-ish grid</div>
      </div>
    </div>
  )
}
