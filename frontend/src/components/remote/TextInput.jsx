import React, { useState, useEffect } from 'react'

export default function TextInput({ onRefresh }) {
  const [text, setText] = useState('')
  const [messages, setMessages] = useState([])
  const [status, setStatus] = useState('')
  const [duration, setDuration] = useState(30)

  const fetchMessages = async () => {
    const res = await fetch('/api/messages')
    const data = await res.json()
    setMessages(data)
  }

  useEffect(() => { fetchMessages() }, [])

  const pushText = async (e) => {
    e.preventDefault()
    if (!text.trim()) return
    await fetch('/api/display/text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
    setStatus('Sent!')
    setTimeout(() => setStatus(''), 2000)
    setText('')
  }

  const addMessage = async () => {
    if (!text.trim()) return
    await fetch('/api/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, duration }),
    })
    setText('')
    fetchMessages()
  }

  const deleteMessage = async (id) => {
    await fetch(`/api/messages/${id}`, { method: 'DELETE' })
    fetchMessages()
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-mono text-gray-200 font-semibold tracking-wider uppercase">
        Push Text
      </h2>

      {/* Quick send */}
      <form onSubmit={pushText} className="space-y-2">
        <textarea
          className="w-full bg-gray-800 text-white font-mono text-sm rounded-lg p-3 border border-gray-600 focus:border-blue-500 focus:outline-none resize-none"
          rows={3}
          placeholder="Type a message to display..."
          value={text}
          onChange={e => setText(e.target.value)}
        />
        <div className="flex gap-2">
          <button
            type="submit"
            className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-mono text-sm rounded-lg py-2 transition-colors"
          >
            SEND NOW
          </button>
          <button
            type="button"
            onClick={addMessage}
            className="flex-1 bg-gray-700 hover:bg-gray-600 text-white font-mono text-sm rounded-lg py-2 transition-colors"
          >
            + ADD TO ROTATION
          </button>
        </div>
        {status && (
          <div className="text-green-400 text-xs font-mono text-center">{status}</div>
        )}
      </form>

      {/* Duration */}
      <div className="flex items-center gap-3">
        <label className="text-gray-400 text-xs font-mono uppercase tracking-wider w-24">Duration</label>
        <input
          type="number"
          min={5}
          max={600}
          value={duration}
          onChange={e => setDuration(Number(e.target.value))}
          className="w-20 bg-gray-800 text-white font-mono text-sm rounded px-2 py-1 border border-gray-600 focus:outline-none"
        />
        <span className="text-gray-500 text-xs font-mono">seconds</span>
      </div>

      {/* Saved messages */}
      {messages.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs text-gray-500 font-mono uppercase tracking-wider">Rotation Messages</div>
          {messages.map(msg => (
            <div key={msg.id} className="flex items-center gap-2 bg-gray-800 rounded-lg px-3 py-2">
              <span className="flex-1 text-sm font-mono text-gray-300 truncate">{msg.text}</span>
              <span className="text-xs text-gray-600 font-mono w-12 text-right">{msg.duration}s</span>
              <button
                onClick={() => deleteMessage(msg.id)}
                className="text-gray-600 hover:text-red-400 transition-colors text-sm ml-1"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
