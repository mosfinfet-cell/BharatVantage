// components/ui/Button.jsx
// Reasoning: Centralised button component ensures consistent saffron
// styling across all CTAs. Variants map to design spec:
//   primary = saffron gradient (main CTAs)
//   secondary = bordered (secondary actions)
//   ghost = text-only (nav items)
//   danger = red (destructive)

import React from 'react'
import { clsx } from 'clsx'
import { Loader2 } from 'lucide-react'

const variants = {
  primary: `
    bg-gradient-to-r from-saffron-500 to-ember-500
    text-white font-semibold
    hover:from-saffron-600 hover:to-ember-600
    shadow-[0_2px_12px_rgba(249,125,10,0.35)]
    hover:shadow-[0_4px_20px_rgba(249,125,10,0.5)]
    active:scale-[0.98]
  `,
  secondary: `
    bg-transparent
    border border-[var(--border-strong)]
    text-[var(--text-primary)]
    hover:border-saffron-500 hover:text-saffron-500
    hover:bg-[var(--saffron-subtle)]
  `,
  ghost: `
    bg-transparent text-[var(--text-secondary)]
    hover:text-[var(--text-primary)] hover:bg-[var(--bg-subtle)]
  `,
  danger: `
    bg-red-500/10 border border-red-500/20
    text-red-400
    hover:bg-red-500/20 hover:border-red-500/40
  `,
}

const sizes = {
  sm:  'text-sm px-3 py-1.5 gap-1.5',
  md:  'text-sm px-4 py-2.5 gap-2',
  lg:  'text-base px-6 py-3 gap-2.5',
}

export default function Button({
  variant  = 'primary',
  size     = 'md',
  loading  = false,
  disabled = false,
  icon,
  children,
  className,
  ...props
}) {
  return (
    <button
      disabled={disabled || loading}
      className={clsx(
        // Base
        'inline-flex items-center justify-center',
        'font-body font-medium rounded-[var(--radius-btn)]',
        'transition-all duration-150 cursor-pointer',
        'disabled:opacity-40 disabled:cursor-not-allowed',
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {loading
        ? <Loader2 size={16} className="animate-spin" />
        : icon && <span className="flex-shrink-0">{icon}</span>
      }
      {children && <span>{children}</span>}
    </button>
  )
}
