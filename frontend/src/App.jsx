import React from 'react'
import { Routes, Route } from 'react-router-dom'
import RemoteControl from './components/remote/RemoteControl'
import DisplayView from './components/DisplayView'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RemoteControl />} />
      <Route path="/display" element={<DisplayView />} />
    </Routes>
  )
}
