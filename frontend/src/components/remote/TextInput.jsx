import React, { useState, useEffect, useMemo } from 'react'
import DurationPicker from './DurationPicker'
import { apiFetch, apiJson } from '../../utils/api'
import { useToast } from '../Toast'
import { textToMatrixColored, codeToChar } from '../../utils/charmap'

function TextPreview({ text, rows = 6, cols = 22 }) {
  const [matrix, colorMap] = useMemo(() => textToMatrixColored(text, rows, cols), [text, rows, cols])
  return (
    <div
      className="rounded-lg overflow-hidden mx-3 mb-3"
      style={{ border: '1px solid var(--border)', background: '#0d0d1a' }}
    >
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, 1fr)`, gap: 1 }}>
        {matrix.flatMap((row, r) => row.map((code, c) => (
          <div
            key={`${r}-${c}`}
            className="flex items-center justify-center"
            style={{ aspectRatio: '9/14', background: '#1a1a2e' }}
          >
            {code !== 0 && (
              <span style={{
                fontSize: '50%', lineHeight: 1, color: colorMap?.[r]?.[c] || '#c8d0e0',
                fontFamily: '"Bebas Neue", "Share Tech Mono", monospace',
              }}>
                {codeToChar(code)}
              </span>
            )}
          </div>
        )))}
      </div>
    </div>
  )
}

export default function TextInput({ screenId = 'main', onRefresh, rows = 6, cols = 22 }) {
  const [text, setText] = useState('')
  const [messages, setMessages] = useState([])
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const [pushDuration, setPushDuration] = useState('')   // '' = until changed
  const [rotDuration, setRotDuration] = useState(30)     // rotation queue hold time
  const showToast = useToast()

  const qs = `?screen=${encodeURIComponent(screenId)}`

  const fetchMessages = async () => {
    try {
      setMessages(await apiFetch(`/api/messages${qs}`) || [])
    } catch {
      // non-fatal: queue list just stays empty
    }
  }

  useEffect(() => { fetchMessages() }, [screenId]) // eslint-disable-line react-hooks/exhaustive-deps

  const pushText = async (e) => {
    e.preventDefault()
    if (!text.trim() || busy) return
    setBusy(true)
    try {
      await apiJson(`/api/display/text${qs}`, 'POST', {
        text,
        duration: pushDuration !== '' ? parseInt(pushDuration, 10) : null,
      })
      setStatus('sent')
      setTimeout(() => setStatus(''), 2000)
      setText('')  // only cleared on success — a failed send keeps the draft
    } catch (err) {
      showToast(`Send failed: ${err.message}`)
    } finally {
      setBusy(false)
    }
  }

  const addMessage = async () => {
    if (!text.trim() || busy) return
    setBusy(true)
    try {
      await apiJson(`/api/messages${qs}`, 'POST', { text, duration: rotDuration })
      setText('')
      fetchMessages()
    } catch (err) {
      showToast(`Could not add message: ${err.message}`)
    } finally {
      setBusy(false)
    }
  }

  const deleteMessage = async (id) => {
    try {
      await apiFetch(`/api/messages/${id}`, { method: 'DELETE' })
    } catch (err) {
      showToast(`Delete failed: ${err.message}`)
    }
    fetchMessages()
  }

  return (
    <div className="space-y-5">
      <h2 className="text-sm font-semibold uppercase tracking-widest" style={{ color: 'var(--text-1)' }}>
        Push Text
      </h2>

      {/* Compose area */}
      <div
        className="rounded-xl overflow-hidden"
        style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
      >
        <textarea
          className="w-full bg-transparent font-mono text-sm p-4 resize-none focus:outline-none"
          style={{ color: 'var(--text-1)' }}
          rows={3}
          placeholder="Type a message to display…"
          value={text}
          onChange={e => setText(e.target.value)}
        />

        {/* Live board preview — exactly how the text will wrap and center */}
        {text.trim() && <TextPreview text={text} rows={rows} cols={cols} />}

        {/* Color markup hint */}
        <p className="px-4 pb-2 text-[10px] font-mono" style={{ color: 'var(--text-3)' }}>
          Color text with {'{red}'}HAPPY HOUR{'{/}'} — red, orange, yellow, green, blue, violet, white
        </p>

        {/* Send Now row */}
        <div
          className="flex items-center justify-between gap-2 px-3 py-2.5"
          style={{ borderTop: '1px solid var(--border)' }}
        >
          <DurationPicker value={pushDuration} onChange={setPushDuration} />
          <button
            type="submit"
            form="text-form"
            onClick={pushText}
            disabled={!text.trim() || busy}
            className="fb-btn-primary text-[11px] px-4 py-1.5 flex-shrink-0"
            style={status === 'sent' ? { background: '#16a34a' } : {}}
          >
            {busy ? 'Sending…' : status === 'sent' ? '✓ Sent' : 'Send Now'}
          </button>
        </div>

        {/* Rotation queue row */}
        <div
          className="flex items-center justify-between gap-2 px-3 pb-3"
          style={{ borderTop: '1px solid var(--border)' }}
        >
          <div className="flex items-center gap-2">
            <label className="section-label whitespace-nowrap">Rotation hold</label>
            <input
              type="number"
              min={5}
              max={600}
              value={rotDuration}
              onChange={e => setRotDuration(Number(e.target.value))}
              className="w-16 text-center fb-input py-1"
            />
            <span className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>sec</span>
          </div>
          <button
            type="button"
            onClick={addMessage}
            disabled={!text.trim() || busy}
            className="fb-btn-ghost text-[11px] px-3 py-1.5 flex-shrink-0"
          >
            + Rotation
          </button>
        </div>
      </div>

      {/* Saved messages */}
      {messages.length > 0 && (
        <div className="space-y-2">
          <p className="section-label">Rotation Queue</p>
          {messages.map(msg => (
            <div
              key={msg.id}
              className="flex items-center gap-3 rounded-xl px-3 py-2.5"
              style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            >
              <span className="flex-1 text-xs font-mono truncate" style={{ color: 'var(--text-2)' }}>
                {msg.text}
              </span>
              <span className="text-[10px] font-mono flex-shrink-0" style={{ color: 'var(--text-3)' }}>
                {msg.duration}s
              </span>
              <button
                onClick={() => deleteMessage(msg.id)}
                className="text-sm flex-shrink-0 transition-colors"
                style={{ color: 'var(--text-3)' }}
                onMouseEnter={e => { e.currentTarget.style.color = '#ef4444' }}
                onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-3)' }}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {messages.length === 0 && (
        <p className="text-[11px] font-mono text-center py-2" style={{ color: 'var(--text-3)' }}>
          Messages added to rotation will cycle automatically
        </p>
      )}
    </div>
  )
}
