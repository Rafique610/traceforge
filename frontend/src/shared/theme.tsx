import { useState } from 'react'
import { Icon } from './ui'

export type Theme = 'light' | 'dark'
const KEY = 'tf-theme'

function systemTheme(): Theme {
  try {
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

function currentTheme(): Theme {
  const attr = document.documentElement.getAttribute('data-theme')
  return attr === 'dark' || attr === 'light' ? attr : systemTheme()
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(currentTheme)
  function toggle() {
    const next: Theme = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.setAttribute('data-theme', next)
    try {
      localStorage.setItem(KEY, next)
    } catch {
      /* storage unavailable: theme still applies for this session */
    }
    setTheme(next)
  }
  return (
    <button
      type="button"
      className="btn btn-ghost icon-btn"
      onClick={toggle}
      aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
      title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
    >
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
    </button>
  )
}
