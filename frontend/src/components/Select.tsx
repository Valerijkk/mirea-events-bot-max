import { useEffect, useRef, useState } from 'react'

export interface SelectOption {
  value: string
  label: string
}

interface SelectProps {
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  id?: string
  'data-testid'?: string
}

export function Select({ value, onChange, options, placeholder = 'Выбрать…', id, 'data-testid': testId }: SelectProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const selected = options.find((o) => o.value === value)
  const label = selected?.label ?? placeholder

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  return (
    <div ref={ref} className="relative" id={id}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        data-testid={testId}
        className={[
          'w-full flex items-center justify-between gap-2 px-3 py-2 rounded-xl border text-sm transition-colors text-left',
          open
            ? 'border-brand-500 bg-white dark:bg-[#1a2238]'
            : 'border-slate-300 dark:border-[#344063] bg-white dark:bg-[#131a2e]',
          'text-slate-900 dark:text-slate-100',
        ].join(' ')}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="truncate">{label}</span>
        <svg
          aria-hidden="true"
          className={`w-4 h-4 shrink-0 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`}
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}
          strokeLinecap="round" strokeLinejoin="round"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <ul
          role="listbox"
          className="absolute z-50 mt-1.5 w-full min-w-max rounded-xl border border-slate-200 dark:border-[#344063] bg-white dark:bg-[#1a2238] shadow-lg overflow-hidden py-1 max-h-64 overflow-y-auto scrollbar-hide"
        >
          {options.map((opt) => (
            <li
              key={opt.value}
              role="option"
              data-value={opt.value}
              aria-selected={opt.value === value}
              onClick={() => { onChange(opt.value); setOpen(false) }}
              className={[
                'px-3 py-2 text-sm cursor-pointer transition-colors select-none',
                opt.value === value
                  ? 'bg-brand-50 dark:bg-[#1e2b4a] text-brand-700 dark:text-brand-300 font-medium'
                  : 'text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-[#232c44]',
              ].join(' ')}
            >
              {opt.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
