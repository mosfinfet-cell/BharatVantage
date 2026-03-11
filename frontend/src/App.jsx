// App.jsx — Root router and theme setup.
//
// Reasoning: We use React Router v6 with protected routes.
// Protected routes check isLoggedIn from AuthContext.
// Theme defaults to dark (per design spec — dark mode is primary).

import React, { useEffect, useState } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/store/AuthContext'
import LoginPage     from '@/pages/LoginPage'
import RegisterPage  from '@/pages/RegisterPage'
import DashboardPage from '@/pages/DashboardPage'
import UploadPage    from '@/pages/UploadPage'
import SettingsPage  from '@/pages/SettingsPage'
import MetricsPage   from '@/pages/MetricsPage'
import AppLayout     from '@/components/layout/AppLayout'

// Protected route — redirects to /login if not authenticated
function Protected({ children }) {
  const { isLoggedIn } = useAuth()
  const location = useLocation()
  if (!isLoggedIn) return <Navigate to="/login" state={{ from: location }} replace />
  return children
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login"    element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* Protected — wrapped in sidebar layout */}
      <Route path="/" element={
        <Protected>
          <AppLayout />
        </Protected>
      }>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard"           element={<DashboardPage />} />
        <Route path="upload"              element={<UploadPage />} />
        <Route path="metrics/:sessionId"  element={<MetricsPage />} />
        <Route path="settings"            element={<SettingsPage />} />
      </Route>

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default function App() {
  // Apply dark class to html element by default (dark mode is primary)
  useEffect(() => {
    document.documentElement.classList.add('dark')
  }, [])

  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}
