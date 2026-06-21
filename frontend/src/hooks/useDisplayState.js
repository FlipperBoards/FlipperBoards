import { useState, useCallback } from 'react'
import { useWebSocket } from './useWebSocket'

export function useDisplayState(screenId = 'main') {
  const [matrix, setMatrix] = useState([])
  const [rows, setRows] = useState(6)
  const [cols, setCols] = useState(22)
  const [mode, setMode] = useState('clock')
  const [appSettings, setAppSettings] = useState({})
  const [modes, setModes] = useState([])
  const [screens, setScreens] = useState([])
  const [connected, setConnected] = useState(false)

  const handleMessage = useCallback((data) => {
    setConnected(true)
    switch (data.type) {
      case 'display_update':
        // Only update matrix if this message is for our screen
        if (!data.screen_id || data.screen_id === screenId) {
          setMatrix(data.matrix || [])
          setRows(data.rows || 6)
          setCols(data.cols || 22)
          setMode(data.mode || 'clock')
        }
        break
      case 'settings_update':
        setAppSettings(data.settings || {})
        break
      case 'modes_update':
        setModes(data.modes || [])
        break
      case 'screens_update':
        setScreens(data.screens || [])
        break
    }
  }, [screenId])

  useWebSocket(handleMessage, screenId)

  return { matrix, rows, cols, mode, appSettings, modes, screens, connected }
}
