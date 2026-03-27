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
import { auth as authApi, config as configApi, tokenStore } from '@/lib/api'

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

    // Store token first — needed for the outlets fetch below
    tokenStore.setToken(data.access_token)

    // Decode token to extract user info
    const payload = JSON.parse(atob(data.access_token.split('.')[1]))
    setUser({ userId: payload.sub, orgId: payload.org_id })

    // Backend login response does NOT include outlet_id.
    // Fetch the org's outlets and auto-select the first one.
    // This is required so X-Outlet-ID header is always set for subsequent requests.
    if (data.outlet_id) {
      // Future-proof: use it directly if backend ever adds it to login response
      tokenStore.setOutlet(data.outlet_id)
      setOutletIdState(data.outlet_id)
    } else {
      try {
        const outlets = await configApi.listOutlets(data.access_token)
        const firstOutlet = Array.isArray(outlets) ? outlets[0] : outlets?.outlets?.[0]
        if (firstOutlet?.id) {
          tokenStore.setOutlet(firstOutlet.id)
          setOutletIdState(firstOutlet.id)
        }
      } catch (e) {
        // Non-fatal — user may need to select outlet manually in Settings
        console.warn('Could not auto-fetch outlet after login:', e)
      }
    }

    return data
  }, [])

  const register = useCallback(async (email, password, fullName, orgName) => {
    // authApi.register expects a single body object — NOT 3 separate args.
    // Field names must match the backend Pydantic schema (snake_case).
    // org_name is required by RegisterRequest — the backend creates the org record with it.
    const data = await authApi.register({
      email,
      password,
      full_name: fullName,
      org_name:  orgName,
    })
    tokenStore.setToken(data.access_token)
    const payload = JSON.parse(atob(data.access_token.split('.')[1]))
    setUser({ userId: payload.sub, orgId: payload.org_id })

    // After register, no outlet exists yet — create the first one automatically.
    // Without an outlet, every subsequent API call requiring X-Outlet-ID will fail.
    try {
      const outlet = await configApi.createOutlet(data.access_token, { name: orgName })
      if (outlet?.id) {
        tokenStore.setOutlet(outlet.id)
        setOutletIdState(outlet.id)
      }
    } catch (e) {
      // Non-fatal — user can create outlet manually in Settings
      console.warn('Could not auto-create outlet after register:', e)
    }

    return data
  }, [])

  const logout = useCallback(async () => {
    // Pass the current token so backend can revoke all refresh tokens for this user.
    // authApi.logout(token) → request("POST", "/auth/logout", null, token)
    const token = tokenStore.getToken()
    try { await authApi.logout(token) } catch { /* best effort */ }
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
