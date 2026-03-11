// pages/LoginPage.jsx
//
// Design rationale:
// Split-screen: left = animated saffron gradient identity panel,
// right = clean login form. The left panel communicates brand
// energy without being decorative noise.
// On mobile: full-width form, identity panel hidden.

import React, { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { Mail, Lock, Zap, ArrowRight, BarChart3, TrendingUp, Shield } from 'lucide-react'
import { useAuth } from '@/store/AuthContext'
import Button from '@/components/ui/Button'
import Input  from '@/components/ui/Input'

const FEATURE_BULLETS = [
  { icon: BarChart3, text: 'Restaurant-grade P&L analytics' },
  { icon: TrendingUp, text: 'Swiggy & Zomato commission audit' },
  { icon: Shield,    text: 'Your data stays private, always' },
]

function IdentityPanel() {
  return (
    <div className="relative hidden lg:flex flex-col justify-between h-full p-10 overflow-hidden">
      {/* Deep gradient background */}
      <div className="absolute inset-0 bg-gradient-to-br from-[#1a0a00] via-[#1f0d00] to-[#0f0e0d]" />

      {/* Geometric saffron glow radials */}
      <div className="absolute top-0 right-0 w-96 h-96 bg-saffron-500/20 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
      <div className="absolute bottom-0 left-0 w-64 h-64 bg-amber-500/15 rounded-full blur-2xl translate-y-1/2 -translate-x-1/4" />

      {/* Subtle geometric grid pattern */}
      <div className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(249,125,10,1) 1px, transparent 1px),
            linear-gradient(90deg, rgba(249,125,10,1) 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px'
        }}
      />

      {/* Top: Logo */}
      <div className="relative flex items-center gap-3">
        <div className="relative w-10 h-10">
          <div className="absolute inset-0 bg-gradient-to-br from-saffron-500 to-ember-600 rounded-xl rotate-6 opacity-60" />
          <div className="absolute inset-0 bg-gradient-to-br from-saffron-400 to-saffron-600 rounded-xl flex items-center justify-center animate-glow-pulse">
            <Zap size={18} className="text-white" fill="white" />
          </div>
        </div>
        <div>
          <div className="font-display font-bold text-lg text-white leading-none">BharatVantage</div>
          <div className="text-xs text-saffron-400/70 font-body mt-0.5">Restaurant Analytics</div>
        </div>
      </div>

      {/* Center: Hero statement */}
      <div className="relative space-y-6">
        <div className="space-y-3">
          <div className="text-[11px] font-semibold tracking-[0.15em] text-saffron-400 font-body uppercase">
            Built for India's restaurants
          </div>
          <h1 className="text-4xl font-display font-bold text-white leading-tight">
            Know your numbers.
            <br />
            <span className="gradient-text text-glow">Grow your business.</span>
          </h1>
          <p className="text-base text-white/50 font-body leading-relaxed max-w-xs">
            Upload your Swiggy, Zomato, and Tally exports.
            Get restaurant-grade analytics in minutes.
          </p>
        </div>

        {/* Feature bullets */}
        <div className="space-y-3">
          {FEATURE_BULLETS.map(({ icon: Icon, text }) => (
            <div key={text} className="flex items-center gap-3">
              <div className="w-7 h-7 rounded-lg bg-saffron-500/15 border border-saffron-500/20 flex items-center justify-center flex-shrink-0">
                <Icon size={13} className="text-saffron-400" />
              </div>
              <span className="text-sm text-white/60 font-body">{text}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom: Metric preview teaser */}
      <div className="relative">
        <div className="card bg-white/5 backdrop-blur-sm border-white/10 p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs text-white/40 font-body">Prime Cost %</span>
            <span className="text-[10px] badge-complete px-2 py-0.5 rounded-full">Complete</span>
          </div>
          <div className="text-3xl font-display font-bold text-white">
            61.4<span className="text-lg text-white/40 font-body">%</span>
          </div>
          <div className="flex items-center gap-1.5 mt-1">
            <TrendingUp size={12} className="text-emerald-400" />
            <span className="text-xs text-emerald-400 font-body">−3.2% vs last period</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function LoginPage() {
  const { login }  = useAuth()
  const navigate   = useNavigate()
  const location   = useLocation()
  const from       = location.state?.from?.pathname || '/dashboard'

  const [email,    setEmail]    = useState('dev@bharatvantage.local')
  const [password, setPassword] = useState('DevPassword123')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err.message || 'Login failed. Please check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg-base)] flex">

      {/* Left identity panel */}
      <div className="w-[480px] flex-shrink-0">
        <IdentityPanel />
      </div>

      {/* Right: Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm space-y-8 animate-slide-up">

          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2.5">
            <div className="w-8 h-8 bg-gradient-to-br from-saffron-400 to-saffron-600 rounded-lg flex items-center justify-center">
              <Zap size={16} className="text-white" fill="white" />
            </div>
            <span className="font-display font-bold text-lg text-[var(--text-primary)]">BharatVantage</span>
          </div>

          {/* Heading */}
          <div>
            <h2 className="text-2xl font-display font-bold text-[var(--text-primary)]">
              Welcome back
            </h2>
            <p className="mt-1 text-sm text-[var(--text-secondary)] font-body">
              Sign in to your restaurant analytics
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@restaurant.com"
              icon={<Mail size={15} />}
              required
              autoComplete="email"
            />
            <Input
              label="Password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              icon={<Lock size={15} />}
              required
              autoComplete="current-password"
            />

            {error && (
              <div className="text-sm text-red-400 font-body bg-red-500/8 border border-red-500/15 rounded-lg px-3 py-2.5">
                {error}
              </div>
            )}

            <Button
              type="submit"
              loading={loading}
              size="lg"
              className="w-full mt-2"
              icon={<ArrowRight size={16} />}
            >
              Sign in
            </Button>
          </form>

          {/* Register link */}
          <p className="text-sm text-[var(--text-muted)] font-body text-center">
            New to BharatVantage?{' '}
            <Link to="/register" className="text-saffron-500 hover:text-saffron-400 font-medium transition-colors">
              Create an account
            </Link>
          </p>

          {/* Dev hint */}
          <div className="border border-[var(--border)] rounded-lg p-3 bg-[var(--bg-subtle)]">
            <p className="text-[11px] text-[var(--text-muted)] font-body font-medium mb-1">Dev credentials pre-filled</p>
            <p className="text-[11px] text-[var(--text-muted)] font-mono">dev@bharatvantage.local</p>
          </div>
        </div>
      </div>
    </div>
  )
}
