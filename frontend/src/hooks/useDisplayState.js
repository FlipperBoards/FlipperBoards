import { useState, useCallback } from 'react'
import { useWebSocket } from './useWebSocket'

export function useDisplayState(screenId = 'main') {
  const [matrix, setMatrix] = useState([])
  const [colorMatrix, setColorMatrix] = useState(null)
  const [photoUrl, setPhotoUrl] = useState(null)
  const [rows, setRows] = useState(6)
  const [cols, setCols] = useState(22)
  const [mode, setMode] = useState('clock')
  const [appSettings, setAppSettings] = useState({})
  const [modes, setModes] = useState([])
  const [screens, setScreens] = useState([])
  const [connected, setConnected] = useState(false)
  const [sweepNonce, setSweepNonce] = useState(0)

  const handleMessage = useCallback((data) => {
    const forMe = !data.screen_id || data.screen_id === screenId
    switch (data.type) {
      case 'display_update':
        if (forMe) {
          if (data.transition === 'sweep') setSweepNonce(n => n + 1)
          setMatrix(data.matrix || [])
          setRows(data.rows || 6)
          setCols(data.cols || 22)
          setMode(data.mode || 'clock')
          setColorMatrix(null)
          setPhotoUrl(null)
        }
        break
      case 'image_update':
        if (forMe) {
          setColorMatrix(data.color_matrix || null)
          setPhotoUrl(null)
          setRows(r => data.rows || r)
          setCols(c => data.cols || c)
          setMode('image_push')
        }
        break
      case 'photo_split':
        if (forMe) {
          setPhotoUrl(data.image_url || null)
          setColorMatrix(null)
          setRows(r => data.rows || r)
          setCols(c => data.cols || c)
          setMode('photo_push')
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

  // Connection state tracks the actual socket lifecycle — not message
  // receipt — so indicators go red when the server dies or Wi-Fi drops.
  useWebSocket(handleMessage, screenId, setConnected)

  return { matrix, colorMatrix, photoUrl, rows, cols, mode, appSettings, modes, screens, connected, sweepNonce }
}
