/** Fetch wrapper that turns non-2xx responses into thrown errors so callers
 * can't silently swallow failures. Returns parsed JSON (or null for empty). */
export async function apiFetch(url, options = {}) {
  let res
  try {
    res = await fetch(url, options)
  } catch {
    throw new Error('Network error — is the server reachable?')
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : detail
    } catch { /* non-JSON error body */ }
    if (res.status === 401) {
      // Session missing/expired — LoginGate listens for this
      window.dispatchEvent(new CustomEvent('fb-auth-required'))
    }
    throw new Error(detail)
  }
  try {
    return await res.json()
  } catch {
    return null
  }
}

/** JSON POST/PUT convenience. */
export function apiJson(url, method, body) {
  return apiFetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}
