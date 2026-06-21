import { useState, useCallback } from 'react'
import { useWebSocket } from './useWebSocket'

export function useDisplayState(screenId = 'main') {
  const [matrix, setMatrix] = useState([])
  const [colorMatrix, setColorMatrix] = useState(null)  // null = character mode, string[][] = full-color
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
        if (!data.screen_id || data.screen_id === screenId) {
          setMatrix(data.matrix || [])
          setRows(data.rows || 6)
          setCols(data.cols || 22)
          setMode(data.mode || 'clock')
          setColorMatrix(null)  // leaving image mode — clear color matrix
        }
        break
      case 'image_update':
        if (!data.screen_id || data.screen_id === screenId) {
          setColorMatrix(data.color_matrix || null)
          setRows(data.rows || rows)
          setCols(data.cols || cols)
          setMode('image_push')
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
  }, [screenId]) // eslint-disable-line react-hooks/exhaustive-deps

  useWebSocket(handleMessage, screenId)

  return { matrix, colorMatrix, rows, cols, mode, appSettings, modes, screens, connected }
}
