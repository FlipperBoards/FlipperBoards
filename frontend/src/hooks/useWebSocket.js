import { useEffect, useRef, useCallback } from 'react'

export function useWebSocket(onMessage, screenId = 'main', onConnectionChange = null) {
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const destroyedRef = useRef(false)
  const onMessageRef = useRef(onMessage)
  const screenIdRef = useRef(screenId)
  const onConnectionChangeRef = useRef(onConnectionChange)
  onMessageRef.current = onMessage
  screenIdRef.current = screenId
  onConnectionChangeRef.current = onConnectionChange

  const connect = useCallback(() => {
    if (destroyedRef.current) return
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/ws?screen=${encodeURIComponent(screenIdRef.current)}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
      onConnectionChangeRef.current?.(true)
    }

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data)
        onMessageRef.current(data)
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      onConnectionChangeRef.current?.(false)
      if (!destroyedRef.current) {
        reconnectTimer.current = setTimeout(connect, 2000)
      }
    }

    ws.onerror = () => ws.close()
  }, []) // intentionally stable — screenId changes handled via ref

  useEffect(() => {
    destroyedRef.current = false
    connect()
    return () => {
      destroyedRef.current = true
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      if (wsRef.current) {
        wsRef.current.onclose = null  // prevent stale handler from scheduling reconnect
        wsRef.current.close()
      }
    }
  }, [connect, screenId]) // reconnect when screenId changes

  return wsRef
}
