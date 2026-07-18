import React, { createContext, useCallback, useContext, useRef, useState } from 'react'

const ToastContext = createContext(() => {})

/** useToast() returns showToast(message, kind) — kind: 'error' | 'success' */
export function useToast() {
  return useContext(ToastContext)
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const idRef = useRef(0)

  const showToast = useCallback((message, kind = 'error') => {
    const id = ++idRef.current
    setToasts(prev => [...prev.slice(-2), { id, message, kind }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 4000)
  }, [])

  return (
    <ToastContext.Provider value={showToast}>
      {children}
      <div
        className="fixed left-0 right-0 z-[100] flex flex-col items-center gap-2 pointer-events-none"
        style={{ bottom: 'calc(env(safe-area-inset-bottom, 0px) + 76px)' }}
      >
        {toasts.map(t => (
          <div
            key={t.id}
            className="pointer-events-auto rounded-xl px-4 py-2.5 text-xs font-mono shadow-lg max-w-[90vw]"
            style={{
              background: t.kind === 'error' ? 'rgba(127,29,29,0.95)' : 'rgba(20,83,45,0.95)',
              color: t.kind === 'error' ? '#fecaca' : '#bbf7d0',
              border: `1px solid ${t.kind === 'error' ? '#dc2626' : '#16a34a'}`,
              backdropFilter: 'blur(8px)',
            }}
            onClick={() => setToasts(prev => prev.filter(x => x.id !== t.id))}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
