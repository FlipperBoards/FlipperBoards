import React, { useState, useEffect, useCallback } from 'react'

/** Overlays the remote control with a password prompt when auth is enabled
 * and there is no valid session. The display view never mounts this — TVs
 * keep working without a login. */
export default function LoginGate() {
  const [needed, setNeeded] = useState(false)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    // Initial check so the gate appears before the first failed action
    fetch('/api/auth/status')
      .then(r => r.json())
      .then(s => { if (s.enabled && !s.authenticated) setNeeded(true) })
      .catch(() => {})

    const onRequired = () => setNeeded(true)
    window.addEventListener('fb-auth-required', onRequired)
    return () => window.removeEventListener('fb-auth-required', onRequired)
  }, [])

  const submit = useCallback(async (e) => {
    e.preventDefault()
    if (!password || busy) return
    setBusy(true)
    setError('')
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      })
      if (!res.ok) {
        setError(res.status === 401 ? 'Wrong password' : `Login failed (${res.status})`)
        return
      }
      setNeeded(false)
      setPassword('')
    } catch {
      setError('Network error — is the server reachable?')
    } finally {
      setBusy(false)
    }
  }, [password, busy])

  if (!needed) return null

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-6"
      style={{ background: 'rgba(5,5,12,0.92)', backdropFilter: 'blur(8px)' }}
    >
      <form
        onSubmit={submit}
        className="w-full max-w-xs rounded-2xl p-6 space-y-4"
        style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
      >
        <div className="text-center space-y-1">
          <div className="text-2xl">🔒</div>
          <h2 className="text-sm font-bold tracking-[0.2em] uppercase" style={{ color: 'var(--text-1)' }}>
            Flipper<span style={{ color: 'var(--accent)' }}>Boards</span>
          </h2>
          <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>
            Enter the password to control this display
          </p>
        </div>

        <input
          type="password"
          autoFocus
          value={password}
          onChange={e => setPassword(e.target.value)}
          placeholder="Password"
          className="fb-input w-full text-center"
        />

        {error && (
          <p className="text-[11px] font-mono text-center" style={{ color: '#f87171' }}>
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={!password || busy}
          className="fb-btn-primary w-full py-2.5"
        >
          {busy ? 'Signing in…' : 'Sign In'}
        </button>

        <p className="text-[10px] font-mono text-center" style={{ color: 'var(--text-3)' }}>
          The display view works without a login — only control is protected.
        </p>
      </form>
    </div>
  )
}
