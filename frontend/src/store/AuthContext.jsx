// store/AuthContext.jsx — Global auth state.
//
// Reasoning: We use React Context (not Redux/Zustand) because our auth
// state is simple: isLoggedIn, user, outletId. Context is sufficient
// and avoids an extra dependency.
//
// On login: store access token in tokenStore (sessionStorage),
//           set outletId from first outlet in org.
// On logout: clear all stored tokens and redirect to /login.

import React, { createContext, useContext, useState, useCallback } from 'react'
import { auth as authApi, tokenStore } from '@/lib/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    // Restore user from session if token exists
    const token = tokenStore.getToken()
    if (!token) return null
    try {
      // Decode JWT payload (no verification needed client-side)
      const payload = JSON.parse(atob(token.split('.')[1]))
      return { userId: payload.sub, orgId: payload.org_id }
    } catch {
      return null
    }
  })

  const [outletId, setOutletIdState] = useState(tokenStore.getOutlet)

  const login = useCallback(async (email, password) => {
    const data = await authApi.login(email, password)

    // Backend returns: { access_token, token_type, outlet_id }
    tokenStore.setToken(data.access_token)

    // Decode token to extract user info
    const payload = JSON.parse(atob(data.access_token.split('.')[1]))
    setUser({ userId: payload.sub, orgId: payload.org_id })

    // Use outlet_id from response if provided, otherwise require selection
    if (data.outlet_id) {
      tokenStore.setOutlet(data.outlet_id)
      setOutletIdState(data.outlet_id)
    }

    return data
  }, [])

  const register = useCallback(async (email, password, fullName) => {
    const data = await authApi.register(email, password, fullName)
    tokenStore.setToken(data.access_token)
    const payload = JSON.parse(atob(data.access_token.split('.')[1]))
    setUser({ userId: payload.sub, orgId: payload.org_id })
    return data
  }, [])

  const logout = useCallback(async () => {
    try { await authApi.logout() } catch { /* best effort */ }
    tokenStore.clear()
    setUser(null)
    setOutletIdState(null)
    window.location.href = '/login'
  }, [])

  const setOutletId = useCallback((id) => {
    tokenStore.setOutlet(id)
    setOutletIdState(id)
  }, [])

  return (
    <AuthContext.Provider value={{
      user,
      outletId,
      isLoggedIn: !!user,
      login,
      register,
      logout,
      setOutletId,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
