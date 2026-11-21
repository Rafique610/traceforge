import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  /** Changing this value (e.g. the route) clears a caught error. */
  resetKey?: string
}

export class ErrorBoundary extends Component<Props, { error: Error | null }> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('UI error boundary caught', error, info.componentStack)
  }

  componentDidUpdate(prev: Props) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null })
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="err-page" role="alert">
        <div className="code">!</div>
        <h1>Something went wrong in the UI</h1>
        <p className="muted">This page crashed while rendering. Your data on the server is not affected.</p>
        <pre>{this.state.error.message}</pre>
        <p style={{ marginTop: 16 }}>
          <a className="btn" href="#/">
            Go to dashboard
          </a>{' '}
          <button type="button" className="btn btn-primary" onClick={() => window.location.reload()}>
            Reload
          </button>
        </p>
      </div>
    )
  }
}

export function NotFound() {
  return (
    <div className="err-page">
      <div className="code">404</div>
      <h1>Page not found</h1>
      <p className="muted">That address does not match any TraceForge page.</p>
      <p style={{ marginTop: 16 }}>
        <a className="btn btn-primary" href="#/">
          Back to dashboard
        </a>{' '}
        <a className="btn" href="#/incidents">
          All incidents
        </a>
      </p>
    </div>
  )
}
