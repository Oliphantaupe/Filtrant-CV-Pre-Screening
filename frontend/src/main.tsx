import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import App from './App'
import UploadPage from './pages/UploadPage'
import CandidatesPage from './pages/CandidatesPage'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<Navigate to="/candidates" replace />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="candidates" element={<CandidatesPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
