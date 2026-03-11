// LandingPage.jsx — Public marketing/landing page
//
// Reasoning: This is the first page visitors see before logging in.
// It must communicate what BharatVantage is, what it does, and drive
// conversions to login/register. Uses the same saffron dark design
// system as the rest of the app for brand consistency.
// Route: /  (unauthenticated users) → protected users go to /dashboard

import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

// ── Utility: intersection observer for scroll reveals ────────────
function useReveal() {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect() } },
      { threshold: 0.12 }
    )
    if (ref.current) obs.observe(ref.current)
    return () => obs.disconnect()
  }, [])
  return [ref, visible]
}

// ── Section reveal wrapper ────────────────────────────────────────
function Reveal({ children, delay = 0, className = '' }) {
  const [ref, visible] = useReveal()
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(32px)',
        transition: `opacity 0.7s ease ${delay}ms, transform 0.7s ease ${delay}ms`,
      }}
    >
      {children}
    </div>
  )
}

// ── Data ──────────────────────────────────────────────────────────
const FEATURES = [
  {
    icon: '⚡',
    title: 'Real-Time Analytics',
    desc: 'Ingest data from Swiggy, Zomato, Petpooja, and Tally in minutes. See your restaurant\'s pulse as it happens.',
  },
  {
    icon: '₹',
    title: 'Prime Cost Tracking',
    desc: 'Monitor food cost, labour cost, and prime cost against industry benchmarks. Know your danger zone before it hits.',
  },
  {
    icon: '📊',
    title: 'RevPASH & Covers',
    desc: 'Revenue Per Available Seat Hour, covers, and platform payout breakdowns — all in one unified view.',
  },
  {
    icon: '🔔',
    title: 'Smart Alerts',
    desc: 'Get proactive warnings when metrics approach thresholds. Flag shifts, raise disputes, and export reports instantly.',
  },
  {
    icon: '🔒',
    title: 'DPDP Compliant',
    desc: 'Customer IDs are hashed and anonymised at ingestion. Built for India\'s Digital Personal Data Protection Act.',
  },
  {
    icon: '🏪',
    title: 'Multi-Outlet Ready',
    desc: 'Manage multiple outlets under one organisation. Each outlet\'s data stays isolated, secure, and auditable.',
  },
]

const METRICS = [
  { value: '₹420k', label: 'Avg Monthly Net Revenue tracked' },
  { value: '6+',    label: 'Data sources integrated' },
  { value: '<2min', label: 'Time to first insight' },
  { value: '100%',  label: 'Data privacy compliant' },
]

const TESTIMONIALS = [
  {
    quote: 'Before BharatVantage we were looking at three different Excel sheets to understand one day\'s performance. Now it\'s one screen.',
    name: 'Rohan Mehta',
    role: 'Owner, The Curry House, Bangalore',
  },
  {
    quote: 'The prime cost alert saved us from a bad month. We caught the labour spike on day 8, not day 30.',
    name: 'Priya Nair',
    role: 'Operations Head, Cloud Kitchen Group, Mumbai',
  },
  {
    quote: 'Platform dispute generation alone saved us ₹15,000 in a single quarter. The ROI is obvious.',
    name: 'Aarav Singh',
    role: 'Finance Lead, QSR Chain, Delhi',
  },
]

const PLATFORMS = ['Swiggy', 'Zomato', 'Petpooja', 'Tally', 'EazyDiner', 'Dotpe']

// ── Nav ───────────────────────────────────────────────────────────
function Nav() {
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 40)
    window.addEventListener('scroll', fn)
    return () => window.removeEventListener('scroll', fn)
  }, [])

  return (
    <nav style={{
      position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
      padding: '0 2rem',
      height: '64px',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      background: scrolled ? 'rgba(15,14,13,0.92)' : 'transparent',
      backdropFilter: scrolled ? 'blur(16px)' : 'none',
      borderBottom: scrolled ? '1px solid rgba(255,255,255,0.07)' : 'none',
      transition: 'all 0.3s ease',
    }}>
      {/* Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8,
          background: 'linear-gradient(135deg, #f97d0a, #fbbf24)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 16, fontWeight: 700, color: '#0f0e0d',
        }}>B</div>
        <span style={{
          fontFamily: "'Syne', sans-serif", fontWeight: 700,
          fontSize: '1.1rem', color: '#f5f0e8', letterSpacing: '-0.02em',
        }}>BharatVantage</span>
      </div>

      {/* Links */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
        {['Features', 'Integrations', 'About'].map(label => (
          <a key={label} href={`#${label.toLowerCase()}`} style={{
            color: '#9c9584', fontSize: '0.875rem', textDecoration: 'none',
            fontFamily: "'DM Sans', sans-serif", fontWeight: 500,
            transition: 'color 0.2s',
          }}
            onMouseEnter={e => e.target.style.color = '#f5f0e8'}
            onMouseLeave={e => e.target.style.color = '#9c9584'}
          >{label}</a>
        ))}
        <Link to="/login" style={{
          padding: '8px 20px', borderRadius: 10,
          background: 'rgba(249,125,10,0.12)',
          border: '1px solid rgba(249,125,10,0.3)',
          color: '#f97d0a', fontSize: '0.875rem',
          fontFamily: "'DM Sans', sans-serif", fontWeight: 600,
          textDecoration: 'none', transition: 'all 0.2s',
        }}
          onMouseEnter={e => { e.target.style.background = '#f97d0a'; e.target.style.color = '#0f0e0d' }}
          onMouseLeave={e => { e.target.style.background = 'rgba(249,125,10,0.12)'; e.target.style.color = '#f97d0a' }}
        >Sign in</Link>
      </div>
    </nav>
  )
}

// ── Hero ──────────────────────────────────────────────────────────
function Hero() {
  return (
    <section style={{
      minHeight: '100vh',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: '8rem 2rem 4rem',
      position: 'relative', overflow: 'hidden',
      textAlign: 'center',
    }}>
      {/* Background glow */}
      <div style={{
        position: 'absolute', top: '20%', left: '50%',
        transform: 'translateX(-50%)',
        width: 600, height: 600, borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(249,125,10,0.12) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />
      {/* Grid pattern */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        backgroundImage: `linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
                          linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)`,
        backgroundSize: '48px 48px',
      }} />

      {/* Badge */}
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 8,
        padding: '6px 14px', borderRadius: 100,
        background: 'rgba(249,125,10,0.08)',
        border: '1px solid rgba(249,125,10,0.2)',
        marginBottom: '1.5rem',
        animation: 'fadeUp 0.6s ease both',
      }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#f97d0a', display: 'inline-block' }} />
        <span style={{ color: '#f97d0a', fontSize: '0.8rem', fontWeight: 600, letterSpacing: '0.04em', fontFamily: "'DM Sans', sans-serif" }}>
          BUILT FOR INDIAN RESTAURANTS
        </span>
      </div>

      {/* Headline */}
      <h1 style={{
        fontFamily: "'Syne', sans-serif",
        fontSize: 'clamp(2.5rem, 6vw, 4.5rem)',
        fontWeight: 800,
        color: '#f5f0e8',
        lineHeight: 1.1,
        letterSpacing: '-0.03em',
        maxWidth: 800,
        margin: '0 0 1.5rem',
        animation: 'fadeUp 0.6s ease 0.1s both',
      }}>
        Restaurant analytics<br />
        <span style={{
          background: 'linear-gradient(90deg, #f97d0a, #fbbf24)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
        }}>that actually work</span>
        <br />for India.
      </h1>

      {/* Subheadline */}
      <p style={{
        color: '#9c9584', fontSize: 'clamp(1rem, 2vw, 1.2rem)',
        maxWidth: 560, lineHeight: 1.7, margin: '0 0 2.5rem',
        fontFamily: "'DM Sans', sans-serif",
        animation: 'fadeUp 0.6s ease 0.2s both',
      }}>
        Connect Swiggy, Zomato, Petpooja and Tally. Get unified P&L, prime cost
        tracking, and platform dispute tools — in under two minutes.
      </p>

      {/* CTAs */}
      <div style={{
        display: 'flex', gap: '1rem', flexWrap: 'wrap', justifyContent: 'center',
        animation: 'fadeUp 0.6s ease 0.3s both',
      }}>
        <Link to="/register" style={{
          padding: '14px 32px', borderRadius: 12,
          background: 'linear-gradient(135deg, #f97d0a, #e06d00)',
          color: '#0f0e0d', fontWeight: 700, fontSize: '1rem',
          fontFamily: "'DM Sans', sans-serif",
          textDecoration: 'none', boxShadow: '0 0 32px rgba(249,125,10,0.35)',
          transition: 'all 0.2s',
        }}
          onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-2px)'}
          onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
        >
          Start free →
        </Link>
        <Link to="/login" style={{
          padding: '14px 32px', borderRadius: 12,
          background: 'rgba(255,255,255,0.05)',
          border: '1px solid rgba(255,255,255,0.1)',
          color: '#f5f0e8', fontWeight: 600, fontSize: '1rem',
          fontFamily: "'DM Sans', sans-serif",
          textDecoration: 'none', transition: 'all 0.2s',
        }}
          onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.09)'}
          onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
        >
          Sign in
        </Link>
      </div>

      {/* Metric strip */}
      <div style={{
        display: 'flex', gap: '3rem', flexWrap: 'wrap', justifyContent: 'center',
        marginTop: '4rem',
        animation: 'fadeUp 0.6s ease 0.4s both',
      }}>
        {METRICS.map(m => (
          <div key={m.label} style={{ textAlign: 'center' }}>
            <div style={{
              fontFamily: "'Syne', sans-serif", fontWeight: 800,
              fontSize: '1.75rem', color: '#f97d0a',
            }}>{m.value}</div>
            <div style={{ color: '#6b6659', fontSize: '0.8rem', marginTop: 4, fontFamily: "'DM Sans', sans-serif" }}>
              {m.label}
            </div>
          </div>
        ))}
      </div>

      <style>{`
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(24px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </section>
  )
}

// ── Platforms strip ───────────────────────────────────────────────
function Platforms() {
  return (
    <section id="integrations" style={{ padding: '3rem 2rem', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
      <Reveal>
        <p style={{
          textAlign: 'center', color: '#6b6659', fontSize: '0.8rem',
          letterSpacing: '0.1em', fontWeight: 600, marginBottom: '1.5rem',
          fontFamily: "'DM Sans', sans-serif", textTransform: 'uppercase',
        }}>Integrates with your existing stack</p>
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
          {PLATFORMS.map(p => (
            <div key={p} style={{
              padding: '10px 24px', borderRadius: 100,
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
              color: '#9c9584', fontSize: '0.875rem', fontWeight: 600,
              fontFamily: "'DM Sans', sans-serif",
            }}>{p}</div>
          ))}
        </div>
      </Reveal>
    </section>
  )
}

// ── Features ──────────────────────────────────────────────────────
function Features() {
  return (
    <section id="features" style={{ padding: '6rem 2rem', maxWidth: 1100, margin: '0 auto' }}>
      <Reveal>
        <div style={{ textAlign: 'center', marginBottom: '4rem' }}>
          <p style={{ color: '#f97d0a', fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', fontFamily: "'DM Sans', sans-serif", marginBottom: 12 }}>
            WHAT WE DO
          </p>
          <h2 style={{
            fontFamily: "'Syne', sans-serif", fontSize: 'clamp(2rem, 4vw, 3rem)',
            fontWeight: 800, color: '#f5f0e8', letterSpacing: '-0.03em', margin: 0,
          }}>
            Everything your restaurant CFO needs
          </h2>
          <p style={{ color: '#6b6659', marginTop: 16, fontSize: '1.05rem', fontFamily: "'DM Sans', sans-serif" }}>
            Purpose-built for India's restaurant industry — from QSRs to cloud kitchens.
          </p>
        </div>
      </Reveal>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
        gap: '1.5rem',
      }}>
        {FEATURES.map((f, i) => (
          <Reveal key={f.title} delay={i * 80}>
            <div style={{
              padding: '2rem',
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.07)',
              borderRadius: 16,
              transition: 'border-color 0.2s, transform 0.2s',
              cursor: 'default',
            }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = 'rgba(249,125,10,0.3)'
                e.currentTarget.style.transform = 'translateY(-4px)'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)'
                e.currentTarget.style.transform = 'translateY(0)'
              }}
            >
              <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>{f.icon}</div>
              <h3 style={{
                fontFamily: "'Syne', sans-serif", fontWeight: 700,
                fontSize: '1.1rem', color: '#f5f0e8', margin: '0 0 0.75rem',
              }}>{f.title}</h3>
              <p style={{ color: '#6b6659', fontSize: '0.9rem', lineHeight: 1.6, margin: 0, fontFamily: "'DM Sans', sans-serif" }}>
                {f.desc}
              </p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  )
}

// ── Dashboard preview ─────────────────────────────────────────────
function DashboardPreview() {
  return (
    <section style={{ padding: '4rem 2rem', maxWidth: 1100, margin: '0 auto' }}>
      <Reveal>
        <div style={{
          borderRadius: 20,
          border: '1px solid rgba(249,125,10,0.15)',
          background: 'rgba(249,125,10,0.04)',
          padding: '2rem',
          position: 'relative', overflow: 'hidden',
        }}>
          {/* Glow top */}
          <div style={{
            position: 'absolute', top: -60, left: '50%', transform: 'translateX(-50%)',
            width: 400, height: 120, borderRadius: '50%',
            background: 'radial-gradient(ellipse, rgba(249,125,10,0.2), transparent 70%)',
          }} />

          <p style={{ color: '#f97d0a', fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', fontFamily: "'DM Sans', sans-serif", marginBottom: 8 }}>LIVE DASHBOARD PREVIEW</p>
          <h2 style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: '1.75rem', color: '#f5f0e8', margin: '0 0 2rem', letterSpacing: '-0.02em' }}>
            Analytics Report · March 2024
          </h2>

          {/* Mock metric cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
            {[
              { label: 'Net Revenue', val: '₹420k', tag: 'Complete' },
              { label: 'Gross Revenue', val: '₹468k', tag: 'Complete' },
              { label: 'RevPASH', val: '₹485', tag: 'Complete' },
              { label: 'Prime Cost %', val: '61.4%', tag: 'Warning' },
            ].map(c => (
              <div key={c.label} style={{
                background: 'rgba(255,255,255,0.04)',
                border: `1px solid ${c.tag === 'Warning' ? 'rgba(251,191,36,0.25)' : 'rgba(255,255,255,0.07)'}`,
                borderRadius: 12, padding: '1.25rem',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <span style={{ color: '#6b6659', fontSize: '0.8rem', fontFamily: "'DM Sans', sans-serif" }}>{c.label}</span>
                  <span style={{
                    fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px', borderRadius: 100,
                    background: c.tag === 'Warning' ? 'rgba(251,191,36,0.15)' : 'rgba(34,197,94,0.12)',
                    color: c.tag === 'Warning' ? '#fbbf24' : '#4ade80',
                    fontFamily: "'DM Sans', sans-serif",
                  }}>{c.tag}</span>
                </div>
                <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: '1.5rem', color: '#f5f0e8' }}>{c.val}</div>
              </div>
            ))}
          </div>

          {/* Insight alerts mock */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
            {[
              { icon: '⚠️', title: 'Prime Cost approaching threshold', color: 'rgba(251,191,36,0.12)', border: 'rgba(251,191,36,0.2)', text: 'At 61.4%, you\'re within 3.6% of the 65% danger zone.' },
              { icon: '↓', title: 'Penalties down ₹1,200 vs last month', color: 'rgba(34,197,94,0.08)', border: 'rgba(34,197,94,0.18)', text: 'Dispute rate has improved. 3 orders still pending reversal.' },
            ].map(a => (
              <div key={a.title} style={{ background: a.color, border: `1px solid ${a.border}`, borderRadius: 12, padding: '1.25rem' }}>
                <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                  <span style={{ fontSize: '1.2rem' }}>{a.icon}</span>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#f5f0e8', fontFamily: "'DM Sans', sans-serif", marginBottom: 4 }}>{a.title}</div>
                    <div style={{ fontSize: '0.8rem', color: '#9c9584', fontFamily: "'DM Sans', sans-serif" }}>{a.text}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </Reveal>
    </section>
  )
}

// ── Testimonials ──────────────────────────────────────────────────
function Testimonials() {
  return (
    <section style={{ padding: '6rem 2rem', maxWidth: 1100, margin: '0 auto' }}>
      <Reveal>
        <p style={{ color: '#f97d0a', fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', fontFamily: "'DM Sans', sans-serif", textAlign: 'center', marginBottom: 12 }}>
          WHAT OPERATORS SAY
        </p>
        <h2 style={{ fontFamily: "'Syne', sans-serif", fontSize: 'clamp(1.8rem, 3vw, 2.5rem)', fontWeight: 800, color: '#f5f0e8', letterSpacing: '-0.03em', textAlign: 'center', margin: '0 0 3rem' }}>
          Trusted by restaurant operators across India
        </h2>
      </Reveal>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.5rem' }}>
        {TESTIMONIALS.map((t, i) => (
          <Reveal key={t.name} delay={i * 100}>
            <div style={{
              padding: '2rem', borderRadius: 16,
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.07)',
            }}>
              <p style={{ color: '#9c9584', fontSize: '0.95rem', lineHeight: 1.7, margin: '0 0 1.5rem', fontFamily: "'DM Sans', sans-serif", fontStyle: 'italic' }}>
                "{t.quote}"
              </p>
              <div>
                <div style={{ fontWeight: 700, color: '#f5f0e8', fontFamily: "'DM Sans', sans-serif", fontSize: '0.9rem' }}>{t.name}</div>
                <div style={{ color: '#6b6659', fontSize: '0.8rem', fontFamily: "'DM Sans', sans-serif", marginTop: 2 }}>{t.role}</div>
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  )
}

// ── About ─────────────────────────────────────────────────────────
function About() {
  return (
    <section id="about" style={{
      padding: '6rem 2rem',
      borderTop: '1px solid rgba(255,255,255,0.06)',
      borderBottom: '1px solid rgba(255,255,255,0.06)',
    }}>
      <div style={{ maxWidth: 900, margin: '0 auto', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4rem', alignItems: 'center' }}>
        <Reveal>
          <p style={{ color: '#f97d0a', fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', fontFamily: "'DM Sans', sans-serif", marginBottom: 12 }}>
            ABOUT US
          </p>
          <h2 style={{ fontFamily: "'Syne', sans-serif", fontSize: 'clamp(1.8rem, 3vw, 2.5rem)', fontWeight: 800, color: '#f5f0e8', letterSpacing: '-0.03em', margin: '0 0 1.5rem' }}>
            We understand the Indian restaurant business
          </h2>
          <p style={{ color: '#6b6659', lineHeight: 1.8, fontFamily: "'DM Sans', sans-serif", margin: '0 0 1rem' }}>
            BharatVantage was founded by operators who spent years staring at disconnected spreadsheets, commission statements, and POS reports. We built the tool we wished existed.
          </p>
          <p style={{ color: '#6b6659', lineHeight: 1.8, fontFamily: "'DM Sans', sans-serif", margin: 0 }}>
            Our platform is purpose-built for India — with support for INR, DPDP compliance, GST-aware reporting, and integrations with the platforms Indian restaurants actually use.
          </p>
        </Reveal>
        <Reveal delay={150}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            {[
              { icon: '🇮🇳', label: 'India First', desc: 'Built for Indian platforms, pricing, and compliance requirements.' },
              { icon: '🔐', label: 'Data Safe', desc: 'DPDP compliant. Your customer data is never stored raw.' },
              { icon: '⚙️', label: 'Ops Focused', desc: 'Designed with restaurant operators, not just developers.' },
              { icon: '📈', label: 'Action Oriented', desc: 'Every metric links to a decision. Not just data, but insights.' },
            ].map(v => (
              <div key={v.label} style={{
                padding: '1.5rem', borderRadius: 14,
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.07)',
              }}>
                <div style={{ fontSize: '1.5rem', marginBottom: 8 }}>{v.icon}</div>
                <div style={{ fontWeight: 700, color: '#f5f0e8', fontFamily: "'DM Sans', sans-serif", fontSize: '0.9rem', marginBottom: 4 }}>{v.label}</div>
                <div style={{ color: '#6b6659', fontSize: '0.8rem', lineHeight: 1.5, fontFamily: "'DM Sans', sans-serif" }}>{v.desc}</div>
              </div>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  )
}

// ── CTA ───────────────────────────────────────────────────────────
function CTA() {
  return (
    <section style={{ padding: '8rem 2rem', textAlign: 'center', position: 'relative', overflow: 'hidden' }}>
      <div style={{
        position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
        width: 500, height: 300,
        background: 'radial-gradient(ellipse, rgba(249,125,10,0.12), transparent 70%)',
        pointerEvents: 'none',
      }} />
      <Reveal>
        <h2 style={{ fontFamily: "'Syne', sans-serif", fontSize: 'clamp(2rem, 5vw, 3.5rem)', fontWeight: 800, color: '#f5f0e8', letterSpacing: '-0.03em', margin: '0 0 1.5rem' }}>
          Ready to see your restaurant clearly?
        </h2>
        <p style={{ color: '#6b6659', fontSize: '1.1rem', marginBottom: '2.5rem', fontFamily: "'DM Sans', sans-serif" }}>
          Join operators already using BharatVantage to manage their margins.
        </p>
        <Link to="/register" style={{
          display: 'inline-block', padding: '16px 40px', borderRadius: 14,
          background: 'linear-gradient(135deg, #f97d0a, #e06d00)',
          color: '#0f0e0d', fontWeight: 700, fontSize: '1.05rem',
          fontFamily: "'DM Sans', sans-serif", textDecoration: 'none',
          boxShadow: '0 0 48px rgba(249,125,10,0.4)',
          transition: 'transform 0.2s',
        }}
          onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.03)'}
          onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
        >
          Get started free →
        </Link>
      </Reveal>
    </section>
  )
}

// ── Footer ────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer style={{
      padding: '2.5rem 2rem',
      borderTop: '1px solid rgba(255,255,255,0.06)',
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      flexWrap: 'wrap', gap: '1rem',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 28, height: 28, borderRadius: 7,
          background: 'linear-gradient(135deg, #f97d0a, #fbbf24)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 14, fontWeight: 700, color: '#0f0e0d',
        }}>B</div>
        <span style={{ fontFamily: "'Syne', sans-serif", fontWeight: 700, color: '#9c9584', fontSize: '0.9rem' }}>
          BharatVantage
        </span>
      </div>
      <p style={{ color: '#6b6659', fontSize: '0.8rem', fontFamily: "'DM Sans', sans-serif", margin: 0 }}>
        © 2024 BharatVantage. Built for Indian restaurant operators.
      </p>
      <div style={{ display: 'flex', gap: '1.5rem' }}>
        {['Privacy', 'Terms', 'Contact'].map(l => (
          <a key={l} href="#" style={{ color: '#6b6659', fontSize: '0.8rem', fontFamily: "'DM Sans', sans-serif", textDecoration: 'none' }}>{l}</a>
        ))}
      </div>
    </footer>
  )
}

// ── Page ──────────────────────────────────────────────────────────
export default function LandingPage() {
  return (
    <div style={{ background: '#0f0e0d', minHeight: '100vh', color: '#f5f0e8' }}>
      <Nav />
      <Hero />
      <Platforms />
      <Features />
      <DashboardPreview />
      <Testimonials />
      <About />
      <CTA />
      <Footer />
    </div>
  )
}
