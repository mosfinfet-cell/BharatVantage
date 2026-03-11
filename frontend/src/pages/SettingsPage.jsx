// pages/SettingsPage.jsx
//
// Reasoning: Settings maps to the backend config endpoints.
// GET /config → loads current outlet settings (seats, hours, GST, commission %)
// PUT /config  → saves changes
// Form is grouped logically: Outlet Info, Platform Rates, Account

import React, { useState } from 'react'
import { Save, Store, Percent, User, Bell, Shield } from 'lucide-react'
import Button from '@/components/ui/Button'
import Input  from '@/components/ui/Input'
import { clsx } from 'clsx'

function SectionCard({ title, icon: Icon, children }) {
  return (
    <div className="card p-6 animate-slide-up">
      <div className="flex items-center gap-2.5 mb-5">
        <div className="w-8 h-8 rounded-lg bg-saffron-500/10 border border-saffron-500/20 flex items-center justify-center">
          <Icon size={14} className="text-saffron-500" />
        </div>
        <h3 className="text-sm font-display font-semibold text-[var(--text-primary)]">{title}</h3>
      </div>
      {children}
    </div>
  )
}

export default function SettingsPage() {
  const [saved,   setSaved]   = useState(false)
  const [loading, setLoading] = useState(false)

  // Outlet config (would load from GET /config)
  const [outlet, setOutlet] = useState({
    name:          'Main Outlet — Koregaon Park',
    city:          'Pune',
    seats:         60,
    openingHours:  14,
    gstRate:       5,
  })

  // Platform commission rates
  const [platforms, setPlatforms] = useState({
    swiggy: 22,
    zomato: 25,
  })

  const handleSave = async () => {
    setLoading(true)
    // In production: PUT /config with outlet + platforms data
    await new Promise(r => setTimeout(r, 800))
    setLoading(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  return (
    <div className="p-6 md:p-8 max-w-[720px] mx-auto">

      {/* Header */}
      <div className="mb-8 animate-fade-in">
        <h1 className="text-2xl font-display font-bold text-[var(--text-primary)]">Settings</h1>
        <p className="text-sm text-[var(--text-secondary)] font-body mt-0.5">
          Outlet configuration and platform rates
        </p>
      </div>

      <div className="space-y-5">

        {/* Outlet info */}
        <SectionCard title="Outlet Information" icon={Store}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="Outlet name"
              value={outlet.name}
              onChange={e => setOutlet(p => ({ ...p, name: e.target.value }))}
            />
            <Input
              label="City"
              value={outlet.city}
              onChange={e => setOutlet(p => ({ ...p, city: e.target.value }))}
            />
            <Input
              label="Seating capacity"
              type="number"
              value={outlet.seats}
              onChange={e => setOutlet(p => ({ ...p, seats: +e.target.value }))}
              hint="Used to calculate RevPASH"
            />
            <Input
              label="Daily operating hours"
              type="number"
              value={outlet.openingHours}
              onChange={e => setOutlet(p => ({ ...p, openingHours: +e.target.value }))}
              hint="e.g. 14 for 11AM–1AM"
            />
            <Input
              label="GST rate (%)"
              type="number"
              value={outlet.gstRate}
              onChange={e => setOutlet(p => ({ ...p, gstRate: +e.target.value }))}
              hint="5% for most restaurants"
            />
          </div>
        </SectionCard>

        {/* Platform rates */}
        <SectionCard title="Platform Commission Rates" icon={Percent}>
          <p className="text-xs text-[var(--text-muted)] font-body mb-4 leading-relaxed">
            These rates are used to compute net payouts when platform export files
            don't include commission data directly. Match them to your current contract.
          </p>
          <div className="grid grid-cols-2 gap-4">
            {Object.entries(platforms).map(([key, val]) => (
              <div key={key}>
                <label className="text-sm font-medium text-[var(--text-secondary)] font-body capitalize mb-1.5 block">
                  {key} commission %
                </label>
                <div className="relative">
                  <input
                    type="number"
                    min={0} max={50} step={0.5}
                    value={val}
                    onChange={e => setPlatforms(p => ({ ...p, [key]: +e.target.value }))}
                    className="w-full bg-[var(--bg-subtle)] border border-[var(--border)] rounded-[var(--radius-btn)] px-3 py-2.5 pr-8 text-sm font-body text-[var(--text-primary)] input-saffron"
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-[var(--text-muted)] font-body">%</span>
                </div>
              </div>
            ))}
          </div>

          {/* Visual rate comparison */}
          <div className="mt-4 p-3 bg-[var(--bg-subtle)] rounded-xl">
            <p className="text-xs text-[var(--text-muted)] font-body mb-2">Commission impact preview</p>
            <div className="space-y-2">
              {Object.entries(platforms).map(([key, pct]) => (
                <div key={key} className="flex items-center gap-3 text-xs font-body">
                  <span className="w-12 text-[var(--text-secondary)] capitalize">{key}</span>
                  <div className="flex-1 h-1.5 bg-[var(--bg-elevated)] rounded-full overflow-hidden">
                    <div className="h-full bg-saffron-500 rounded-full" style={{ width: `${(pct / 50) * 100}%` }} />
                  </div>
                  <span className="text-[var(--text-primary)] font-medium w-8 text-right">{pct}%</span>
                </div>
              ))}
            </div>
          </div>
        </SectionCard>

        {/* Account */}
        <SectionCard title="Account" icon={User}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input label="Full name" defaultValue="Dev User" />
            <Input label="Email" type="email" defaultValue="dev@bharatvantage.local" disabled
              hint="Contact support to change email" />
          </div>
          <div className="mt-4 pt-4 border-t border-[var(--border)]">
            <Button variant="danger" size="sm">
              Delete account
            </Button>
          </div>
        </SectionCard>

        {/* Save */}
        <div className="flex items-center gap-3">
          <Button
            loading={loading}
            onClick={handleSave}
            icon={<Save size={15} />}
            size="lg"
          >
            Save changes
          </Button>
          {saved && (
            <span className="text-sm text-emerald-400 font-body animate-fade-in flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              Saved
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
