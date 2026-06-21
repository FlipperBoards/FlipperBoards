import { useState, useCallback } from 'react'
import { useWebSocket } from './useWebSocket'

export function useDisplayState() {
  const [matrix, setMatrix] = useState([])
  const [rows, setRows] = useState(6)
  const [cols, setCols] = useState(22)
  const [mode, setMode] = useState('clock')
  const [appSettings, setAppSettings] = useState({})
  const [modes, setModes] = useState([])
  const [connected, setConnected] = useState(false)

  const handleMessage = useCallback((data) => {
    setConnected(true)
    if (data.type === 'display_update') {
      setMatrix(data.matrix || [])
      setRows(data.rows || 6)
      setCols(data.cols || 22)
      setMode(data.mode || 'clock')
    } else if (data.type === 'settings_update') {
      setAppSettings(data.settings || {})
    } else if (data.type === 'modes_update') {
      setModes(data.modes || [])
    }
  }, [])

  useWebSocket(handleMessage)

  return { matrix, rows, cols, mode, appSettings, modes, connected }
}
