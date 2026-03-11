// components/layout/AppLayout.jsx
//
// Reasoning: Fixed sidebar + scrollable main content is the right
// pattern for an analytics SaaS. Sidebar width is 220px — wide enough
// to show labels but not wasteful. Mobile collapses to bottom nav.

import React, { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { clsx } from 'clsx'
import {
  LayoutDashboard, Upload, Settings, LogOut,
  BarChart3, Sun, Moon, Menu, X, Zap
} from 'lucide-react'
import { useAuth } from '@/store/AuthContext'

const NAV_ITEMS = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/upload',    icon: Upload,          label: 'Upload Data' },
  { to: '/settings',  icon: Settings,        label: 'Settings' },
]

function Logo() {
  return (
    <div className="flex items-center gap-2.5 px-5 py-4">
      {/* Geometric saffron mark — inspired by chakra geometry */}
      <div className="relative w-8 h-8 flex-shrink-0">
        <div className="absolute inset-0 bg-gradient-to-br from-saffron-500 to-ember-600 rounded-lg rotate-6 opacity-80" />
        <div className="absolute inset-0 bg-gradient-to-br from-saffron-400 to-saffron-600 rounded-lg flex items-center justify-center">
          <Zap size={16} className="text-white" fill="white" />
        </div>
      </div>
      <div className="flex flex-col">
        <span className="font-display font-bold text-[15px] text-[var(--text-primary)] leading-none tracking-tight">
          BharatVantage
        </span>
        <span className="text-[10px] text-[var(--text-muted)] font-body leading-none mt-0.5">
          Restaurant Analytics
        </span>
      </div>
    </div>
  )
}

function ThemeToggle() {
  const [dark, setDark] = useState(true)
  const toggle = () => {
    setDark(d => !d)
    document.documentElement.classList.toggle('dark')
  }
  return (
    <button
      onClick={toggle}
      className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-subtle)] transition-all"
      title="Toggle theme"
    >
      {dark ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  )
}

export default function AppLayout() {
  const { user, logout } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex h-screen bg-[var(--bg-base)] overflow-hidden">

      {/* ── Sidebar ────────────────────────────────────────────── */}
      <aside className={clsx(
        // Desktop: always visible fixed sidebar
        'hidden md:flex flex-col w-[220px] flex-shrink-0',
        'bg-[var(--bg-elevated)] border-r border-[var(--border)]',
        'relative z-20'
      )}>

        <Logo />

        {/* Divider */}
        <div className="mx-4 h-px bg-[var(--border)]" />

        {/* Nav */}
        <nav className="flex-1 p-3 flex flex-col gap-0.5 mt-2">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-[10px]',
                'text-sm font-body font-medium transition-all duration-150',
                isActive
                  ? 'bg-saffron-500/10 text-saffron-500 glow-saffron-sm'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-subtle)]'
              )}
            >
              {({ isActive }) => (
                <>
                  <Icon size={16} className={isActive ? 'text-saffron-500' : ''} />
                  {label}
                  {isActive && (
                    <span className="ml-auto w-1 h-4 bg-saffron-500 rounded-full" />
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Bottom section */}
        <div className="p-3 border-t border-[var(--border)]">
          {/* User info */}
          <div className="flex items-center gap-2.5 px-3 py-2 mb-1">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-saffron-400 to-saffron-600 flex items-center justify-center flex-shrink-0">
              <span className="text-[11px] font-bold text-white font-display">
                {user?.userId?.slice(0,1)?.toUpperCase() || 'U'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-[var(--text-primary)] font-body truncate">
                Dev User
              </p>
              <p className="text-[10px] text-[var(--text-muted)] font-body">
                Restaurant Owner
              </p>
            </div>
            <ThemeToggle />
          </div>

          {/* Logout */}
          <button
            onClick={logout}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-[10px] text-sm font-body font-medium text-[var(--text-muted)] hover:text-red-400 hover:bg-red-500/5 transition-all duration-150"
          >
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      </aside>

      {/* ── Mobile Header ──────────────────────────────────────── */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-30 h-14 bg-[var(--bg-elevated)] border-b border-[var(--border)] flex items-center justify-between px-4">
        <Logo />
        <button onClick={() => setMobileOpen(o => !o)} className="p-2 text-[var(--text-secondary)]">
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile slide-out nav */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-20 bg-black/60" onClick={() => setMobileOpen(false)}>
          <div className="absolute left-0 top-14 bottom-0 w-64 bg-[var(--bg-elevated)] border-r border-[var(--border)] p-3"
               onClick={e => e.stopPropagation()}>
            <nav className="flex flex-col gap-0.5">
              {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
                <NavLink key={to} to={to} onClick={() => setMobileOpen(false)}
                  className={({ isActive }) => clsx(
                    'flex items-center gap-3 px-3 py-3 rounded-[10px] text-sm font-body font-medium transition-all',
                    isActive
                      ? 'bg-saffron-500/10 text-saffron-500'
                      : 'text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)]'
                  )}>
                  {({ isActive }) => <><Icon size={16} className={isActive ? 'text-saffron-500' : ''} />{label}</>}
                </NavLink>
              ))}
            </nav>
          </div>
        </div>
      )}

      {/* ── Main content ───────────────────────────────────────── */}
      <main className="flex-1 overflow-auto md:pt-0 pt-14 mesh-bg">
        <Outlet />
      </main>
    </div>
  )
}
