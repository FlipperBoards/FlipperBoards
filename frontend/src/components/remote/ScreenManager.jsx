import React, { useState } from 'react'

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
  const [confirmDelete, setConfirmDelete] = useState(null)

  const createScreen = async () => {
    if (!newName.trim()) return
    const id = slugify(newName) || `screen-${Date.now()}`
    await fetch('/api/screens', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, name: newName.trim(), rows: newRows, cols: newCols }),
    })
    setCreating(false)
    setNewName('')
    onRefresh()
    onSelectScreen(id)
  }

  const saveEdit = async (sid) => {
    await fetch(`/api/screens/${sid}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: editName, rows: editRows, cols: editCols }),
    })
    setEditingId(null)
    onRefresh()
  }

  const deleteScreen = async (sid) => {
    await fetch(`/api/screens/${sid}`, { method: 'DELETE' })
    setConfirmDelete(null)
    if (activeScreenId === sid) onSelectScreen('main')
    onRefresh()
  }

  const inputCls = "bg-gray-800 text-white font-mono text-sm rounded-lg px-3 py-2 border border-gray-600 focus:border-blue-500 focus:outline-none"

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-mono text-gray-200 font-semibold tracking-wider uppercase">
          Screens
        </h2>
        <button
          onClick={() => setCreating(true)}
          className="bg-blue-600 hover:bg-blue-700 text-white font-mono text-xs rounded-lg px-3 py-1.5 transition-colors"
        >
          + NEW SCREEN
        </button>
      </div>

      <p className="text-xs text-gray-600 font-mono">
        Each screen is independent. Open <code className="text-gray-400">/display?screen=ID</code> in any browser,
        cast tab, or go fullscreen. Unlimited screens supported.
      </p>

      {/* Create form */}
      {creating && (
        <div className="bg-gray-800 rounded-xl p-4 border border-blue-800 space-y-3">
          <div className="text-xs text-blue-400 font-mono uppercase tracking-wider">New Screen</div>
          <input
            autoFocus
            type="text"
            placeholder="Screen name (e.g. Living Room)"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && createScreen()}
            className={`${inputCls} w-full`}
          />
          <div className="text-xs text-gray-600 font-mono">
            ID: <span className="text-gray-400">{slugify(newName) || '...'}</span>
          </div>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-xs text-gray-500 font-mono">Rows</label>
              <input type="number" min={1} max={20} value={newRows}
                onChange={e => setNewRows(Number(e.target.value))}
                className={`${inputCls} w-full mt-1`} />
            </div>
            <div className="flex-1">
              <label className="text-xs text-gray-500 font-mono">Cols</label>
              <input type="number" min={1} max={60} value={newCols}
                onChange={e => setNewCols(Number(e.target.value))}
                className={`${inputCls} w-full mt-1`} />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={createScreen}
              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-mono text-sm rounded-lg py-2 transition-colors">
              CREATE
            </button>
            <button onClick={() => setCreating(false)}
              className="flex-1 bg-gray-700 hover:bg-gray-600 text-gray-300 font-mono text-sm rounded-lg py-2 transition-colors">
              CANCEL
            </button>
          </div>
        </div>
      )}

      {/* Screen list */}
      <div className="space-y-2">
        {screens.map(screen => (
          <div key={screen.id}>
            {editingId === screen.id ? (
              <div className="bg-gray-800 rounded-xl p-3 border border-yellow-800 space-y-2">
                <input type="text" value={editName} onChange={e => setEditName(e.target.value)}
                  className={`${inputCls} w-full`} />
                <div className="flex gap-2">
                  <input type="number" min={1} max={20} value={editRows}
                    onChange={e => setEditRows(Number(e.target.value))}
                    className={`${inputCls} flex-1`} placeholder="Rows" />
                  <input type="number" min={1} max={60} value={editCols}
                    onChange={e => setEditCols(Number(e.target.value))}
                    className={`${inputCls} flex-1`} placeholder="Cols" />
                </div>
                <div className="flex gap-2">
                  <button onClick={() => saveEdit(screen.id)}
                    className="flex-1 bg-yellow-700 hover:bg-yellow-600 text-white font-mono text-sm rounded-lg py-1.5 transition-colors">
                    SAVE
                  </button>
                  <button onClick={() => setEditingId(null)}
                    className="flex-1 bg-gray-700 hover:bg-gray-600 text-gray-300 font-mono text-sm rounded-lg py-1.5 transition-colors">
                    CANCEL
                  </button>
                </div>
              </div>
            ) : (
              <div
                className={`flex items-center gap-3 rounded-xl px-4 py-3 border transition-all cursor-pointer ${
                  activeScreenId === screen.id
                    ? 'bg-blue-900/30 border-blue-700'
                    : 'bg-gray-800 border-gray-700 hover:border-gray-500'
                }`}
                onClick={() => onSelectScreen(screen.id)}
              >
                {/* Status dot */}
                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                  screen.online ? 'bg-green-400' : 'bg-gray-600'
                }`} />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm text-gray-200 font-semibold truncate">
                      {screen.name}
                    </span>
                    {screen.id === 'main' && (
                      <span className="text-xs text-gray-600 font-mono">(default)</span>
                    )}
                    {activeScreenId === screen.id && (
                      <span className="text-xs text-blue-400 font-mono">● active</span>
                    )}
                  </div>
                  <div className="text-xs text-gray-600 font-mono">
                    {screen.id} · {screen.rows}×{screen.cols} · {screen.mode?.toUpperCase()}
                  </div>
                </div>

                {/* Display link */}
                <a
                  href={`/display?screen=${screen.id}`}
                  target="_blank"
                  rel="noreferrer"
                  onClick={e => e.stopPropagation()}
                  className="text-xs font-mono text-gray-500 hover:text-blue-400 transition-colors px-2 py-1 rounded border border-gray-700 hover:border-blue-600"
                >
                  OPEN ↗
                </a>

                {/* Edit */}
                <button
                  onClick={e => {
                    e.stopPropagation()
                    setEditingId(screen.id)
                    setEditName(screen.name)
                    setEditRows(screen.rows)
                    setEditCols(screen.cols)
                  }}
                  className="text-gray-600 hover:text-yellow-400 transition-colors text-sm px-1"
                  title="Edit"
                >
                  ✎
                </button>

                {/* Delete (not for main) */}
                {screen.id !== 'main' && (
                  confirmDelete === screen.id ? (
                    <div className="flex gap-1" onClick={e => e.stopPropagation()}>
                      <button onClick={() => deleteScreen(screen.id)}
                        className="text-xs font-mono bg-red-700 hover:bg-red-600 text-white rounded px-2 py-0.5 transition-colors">
                        YES
                      </button>
                      <button onClick={() => setConfirmDelete(null)}
                        className="text-xs font-mono bg-gray-700 hover:bg-gray-600 text-gray-300 rounded px-2 py-0.5 transition-colors">
                        NO
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={e => { e.stopPropagation(); setConfirmDelete(screen.id) }}
                      className="text-gray-600 hover:text-red-400 transition-colors text-sm px-1"
                      title="Delete"
                    >
                      ✕
                    </button>
                  )
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Cast / fullscreen tips */}
      <div className="bg-gray-900 rounded-lg p-3 space-y-1.5">
        <div className="text-xs text-gray-600 font-mono uppercase tracking-wider mb-2">Display Tips</div>
        <div className="text-xs text-gray-500 font-mono">· Press F11 or use the ⊞ button on the display page for fullscreen</div>
        <div className="text-xs text-gray-500 font-mono">· In Chrome: three-dot menu → Cast → Cast tab to a Chromecast</div>
        <div className="text-xs text-gray-500 font-mono">· Add <code className="text-gray-400">?kiosk=1</code> to hide all UI chrome</div>
        <div className="text-xs text-gray-500 font-mono">· Each screen can show different content simultaneously</div>
      </div>
    </div>
  )
}
