// components/ui/Input.jsx
import React from 'react'
import { clsx } from 'clsx'

export default function Input({
  label,
  error,
  hint,
  icon,
  className,
  ...props
}) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label className="text-sm font-medium text-[var(--text-secondary)] font-body">
          {label}
        </label>
      )}
      <div className="relative">
        {icon && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]">
            {icon}
          </span>
        )}
        <input
          className={clsx(
            'w-full bg-[var(--bg-subtle)] border border-[var(--border)]',
            'text-[var(--text-primary)] placeholder:text-[var(--text-muted)]',
            'rounded-[var(--radius-btn)] px-3 py-2.5 text-sm font-body',
            'transition-all duration-150 input-saffron',
            icon && 'pl-9',
            error && 'border-red-400 focus:border-red-400 focus:shadow-[0_0_0_3px_rgba(248,113,113,0.15)]',
            className
          )}
          {...props}
        />
      </div>
      {error && <p className="text-xs text-red-400 font-body">{error}</p>}
      {hint && !error && <p className="text-xs text-[var(--text-muted)] font-body">{hint}</p>}
    </div>
  )
}
