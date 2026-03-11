// pages/RegisterPage.jsx
import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Mail, Lock, User, Zap, ArrowRight } from 'lucide-react'
import { useAuth } from '@/store/AuthContext'
import Button from '@/components/ui/Button'
import Input  from '@/components/ui/Input'

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate     = useNavigate()

  const [fullName, setFullName] = useState('')
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    setLoading(true)
    try {
      await register(email, password, fullName)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(err.message || 'Registration failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg-base)] mesh-bg flex items-center justify-center p-6">
      <div className="w-full max-w-sm space-y-8 animate-slide-up">

        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 bg-gradient-to-br from-saffron-400 to-saffron-600 rounded-xl flex items-center justify-center animate-glow-pulse">
            <Zap size={18} className="text-white" fill="white" />
          </div>
          <span className="font-display font-bold text-xl text-[var(--text-primary)]">BharatVantage</span>
        </div>

        {/* Heading */}
        <div>
          <h2 className="text-2xl font-display font-bold text-[var(--text-primary)]">
            Start your analytics
          </h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)] font-body">
            Set up your restaurant's analytics in minutes
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Your name"
            type="text"
            value={fullName}
            onChange={e => setFullName(e.target.value)}
            placeholder="Rohan Sharma"
            icon={<User size={15} />}
            required
          />
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="you@restaurant.com"
            icon={<Mail size={15} />}
            required
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="8+ characters"
            icon={<Lock size={15} />}
            hint="Minimum 8 characters"
            required
          />

          {error && (
            <div className="text-sm text-red-400 font-body bg-red-500/8 border border-red-500/15 rounded-lg px-3 py-2.5">
              {error}
            </div>
          )}

          <Button type="submit" loading={loading} size="lg" className="w-full mt-2"
            icon={<ArrowRight size={16} />}>
            Create account
          </Button>
        </form>

        <p className="text-sm text-[var(--text-muted)] font-body text-center">
          Already have an account?{' '}
          <Link to="/login" className="text-saffron-500 hover:text-saffron-400 font-medium transition-colors">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
