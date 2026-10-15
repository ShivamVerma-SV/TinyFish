import { RefreshCw } from 'lucide-react'

interface HeaderProps {
  canRefresh: boolean
  searching: boolean
  onRefresh: () => void
}

export function Header({ canRefresh, searching, onRefresh }: HeaderProps) {
  return (
    <header className="site-header">
      <a className="wordmark" href="#top" aria-label="RoleCurrent home">
        Role<span>Current</span>
      </a>
      <div className="header-actions">
        <nav aria-label="Primary navigation">
          <a href="#search">Search</a>
          <a href="#results">Results</a>
        </nav>
        <div className="powered-badge" title="Live discovery uses TinyFish Search, Fetch, and optional Agent">
          <span className="status-dot" aria-hidden="true" />
          Live discovery by TinyFish
        </div>
        <button
          className="refresh-button"
          type="button"
          onClick={onRefresh}
          disabled={!canRefresh || searching}
          aria-label="Refresh the latest search"
        >
          <RefreshCw size={15} className={searching ? 'spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>
    </header>
  )
}
