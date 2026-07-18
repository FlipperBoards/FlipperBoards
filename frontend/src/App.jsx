import React from 'react'
import { Routes, Route } from 'react-router-dom'
import RemoteControl from './components/remote/RemoteControl'
import DisplayView from './components/DisplayView'
import { ToastProvider } from './components/Toast'

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route path="/" element={<RemoteControl />} />
        <Route path="/display" element={<DisplayView />} />
      </Routes>
    </ToastProvider>
  )
}
