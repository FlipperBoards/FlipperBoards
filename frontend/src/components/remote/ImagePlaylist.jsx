import React, { useState, useEffect, useRef, useCallback } from 'react'

export default function ImagePlaylist({ rows, cols, screenId = 'main' }) {
  const [playlist, setPlaylist] = useState([])
  const [uploading, setUploading] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef(null)

  const qs = `?screen=${encodeURIComponent(screenId)}`

  const load = useCallback(async () => {
    const res = await fetch(`/api/display/playlist${qs}`)
    if (res.ok) setPlaylist(await res.json())
  }, [qs])

  useEffect(() => { load() }, [load])

  const handleFiles = async (files) => {
    const imageFiles = Array.from(files).filter(f => f.type.startsWith('image/'))
    if (!imageFiles.length) return
    setUploading(true)
    for (const file of imageFiles) {
      const fd = new FormData()
      fd.append('file', file)
      await fetch(`/api/display/playlist/add${qs}`, { method: 'POST', body: fd })
    }
    await load()
    setUploading(false)
  }

  const remove = async (id) => {
    await fetch(`/api/display/playlist/${id}${qs}`, { method: 'DELETE' })
    await load()
  }

  const clear = async () => {
    if (!window.confirm(`Remove all ${playlist.length} image${playlist.length !== 1 ? 's' : ''} from the playlist?`)) return
    await fetch(`/api/display/playlist/clear${qs}`, { method: 'POST' })
    setPlaylist([])
  }

  const playNow = async () => {
    await fetch(`/api/display/playlist/play${qs}`, { method: 'POST' })
    setPlaying(true)
    setTimeout(() => setPlaying(false), 2500)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    handleFiles(e.dataTransfer.files)
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-mono text-gray-200 font-semibold tracking-wider uppercase">
        Photo Playlist
      </h2>
      <p className="text-xs text-gray-500 font-mono">
        Build a queue of photos that rotate automatically. Each image displays for one rotation
        interval. Enable <span className="text-gray-300">Photo Playlist</span> in the Modes tab
        to include it in the rotation.
      </p>

      {/* Drop zone / upload area */}
      <div
        onClick={() => fileRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
          dragOver
            ? 'border-blue-500 bg-blue-900/20'
            : 'border-gray-700 hover:border-gray-500 bg-gray-900/50'
        }`}
      >
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
        {uploading ? (
          <div className="text-gray-400 font-mono text-sm animate-pulse">UPLOADING...</div>
        ) : (
          <>
            <div className="text-3xl mb-1">+</div>
            <div className="text-gray-400 font-mono text-sm">ADD IMAGES TO PLAYLIST</div>
            <div className="text-gray-600 font-mono text-xs mt-1">
              Drop multiple files or click to browse · {cols}×{rows} tile grid
            </div>
          </>
        )}
      </div>

      {/* Playlist grid */}
      {playlist.length > 0 ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs font-mono text-gray-500 uppercase tracking-wider">
              {playlist.length} image{playlist.length !== 1 ? 's' : ''} in queue
            </div>
            <button
              onClick={clear}
              className="text-xs font-mono text-red-500 hover:text-red-400 transition-colors"
            >
              CLEAR ALL
            </button>
          </div>

          <div className="grid grid-cols-3 gap-2">
            {playlist.map((item, idx) => (
              <div key={item.id} className="relative group rounded-lg overflow-hidden border border-gray-700 bg-gray-900">
                <img
                  src={item.url}
                  alt={`Playlist item ${idx + 1}`}
                  className="w-full aspect-video object-cover"
                />
                {/* Tile grid overlay */}
                <div
                  className="absolute inset-0 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{
                    backgroundImage: `
                      repeating-linear-gradient(to right, rgba(0,0,0,0.3) 0px, rgba(0,0,0,0.3) 1px, transparent 1px, transparent calc(100% / ${cols})),
                      repeating-linear-gradient(to bottom, rgba(0,0,0,0.3) 0px, rgba(0,0,0,0.3) 1px, transparent 1px, transparent calc(100% / ${rows}))
                    `,
                  }}
                />
                {/* Index badge */}
                <div className="absolute top-1 left-1 text-xs font-mono bg-black/60 text-white px-1.5 py-0.5 rounded">
                  #{idx + 1}
                </div>
                {/* Delete button */}
                <button
                  onClick={() => remove(item.id)}
                  className="absolute top-1 right-1 w-5 h-5 flex items-center justify-center bg-red-800/80 hover:bg-red-600 text-white rounded text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  ×
                </button>
              </div>
            ))}
          </div>

          {/* Actions */}
          <div className="flex gap-2 pt-1">
            <button
              onClick={playNow}
              className={`flex-1 font-mono text-sm rounded-xl py-3 transition-colors font-semibold tracking-wider ${
                playing ? 'bg-green-700 text-white' : 'bg-blue-600 hover:bg-blue-700 text-white'
              }`}
            >
              {playing ? '▶ PLAYING PLAYLIST' : '▶ PLAY NOW'}
            </button>
          </div>
        </div>
      ) : (
        !uploading && (
          <div className="text-center py-8 text-gray-600 font-mono text-sm">
            No images yet — add some above
          </div>
        )
      )}

      {/* Tips */}
      <div className="bg-gray-900 rounded-lg p-3 space-y-1.5">
        <div className="text-xs text-gray-600 font-mono uppercase tracking-wider mb-2">How it works</div>
        <div className="text-xs text-gray-500 font-mono">· Each image displays for one rotation interval (set in Settings)</div>
        <div className="text-xs text-gray-500 font-mono">· After all images are shown, the rotation moves to the next mode</div>
        <div className="text-xs text-gray-500 font-mono">· "Play Now" starts the playlist immediately regardless of rotation</div>
        <div className="text-xs text-gray-500 font-mono">· Enable Photo Playlist in the Modes tab to include it in automatic rotation</div>
        <div className="text-xs text-gray-500 font-mono">· Great for a slideshow of client logos or event photos in the background</div>
      </div>
    </div>
  )
}
