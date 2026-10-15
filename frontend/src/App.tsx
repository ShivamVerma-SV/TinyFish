import { useEffect, useRef, useState } from 'react'
import { ArrowDown, ExternalLink, FileSearch, Radar, ShieldCheck, TriangleAlert } from 'lucide-react'
import { getStatus, streamSearch } from './api'
import { EmptyState } from './components/EmptyState'
import { Header } from './components/Header'
import { ProgressPanel } from './components/ProgressPanel'
import { ResultsView } from './components/ResultsView'
import { SearchPanel } from './components/SearchPanel'
import { DEMO_RESULTS, DEMO_SEARCH } from './demoData'
import type { ProgressPhase, SearchEvent, SearchPreferences, SearchResult, SourceState } from './types'

const DEFAULT_SEARCH: SearchPreferences = {
  role: '',
  location: '',
  locationScope: 'preferred',
  skills: [],
  opportunityType: 'Both',
  experienceLevel: 'Any',
  useAgent: false,
  maxResults: 16,
}

const initialPhases = (): ProgressPhase[] => [
  { id: 'discovering', label: 'Discovering opportunities', state: 'pending', message: 'Waiting to search live sources' },
  { id: 'reading', label: 'Reading job listings', state: 'pending', message: 'Waiting for individual pages' },
  { id: 'agent', label: 'Agent fallback', state: 'pending', message: 'Used only when requested and needed' },
  { id: 'deduplicating', label: 'Removing duplicates', state: 'pending', message: 'Waiting for verified candidates' },
  { id: 'matching', label: 'Matching preferences', state: 'pending', message: 'Waiting to rank the shortlist' },
]

function App() {
  const demoMode = new URLSearchParams(window.location.search).get('demo') === 'results'
  const [keyConfigured, setKeyConfigured] = useState<boolean | null>(null)
  const [searching, setSearching] = useState(false)
  const [lastSearch, setLastSearch] = useState<SearchPreferences | null>(null)
  const [phases, setPhases] = useState<ProgressPhase[]>(initialPhases)
  const [sources, setSources] = useState<SourceState[]>([])
  const [result, setResult] = useState<SearchResult | null>(demoMode ? DEMO_RESULTS : null)
  const [hasSearched, setHasSearched] = useState(demoMode)
  const [error, setError] = useState<{ code: string; message: string } | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    getStatus()
      .then((status) => setKeyConfigured(status.keyConfigured))
      .catch(() => setError({ code: 'SERVER_UNAVAILABLE', message: 'The backend is not responding. Start the RoleCurrent API and reload this page.' }))
    return () => abortRef.current?.abort()
  }, [])

  const handleEvent = (event: SearchEvent) => {
    if (event.type === 'progress') {
      setPhases((current) => current.map((phase) => phase.id === event.phase ? {
        ...phase,
        state: event.state,
        message: event.message,
        completed: event.completed,
        total: event.total,
      } : phase))
    } else if (event.type === 'source') {
      setSources((current) => {
        const exists = current.some((source) => source.id === event.source.id)
        return exists ? current.map((source) => source.id === event.source.id ? event.source : source) : [...current, event.source]
      })
    } else if (event.type === 'complete') {
      setResult(event.result)
    } else if (event.type === 'error') {
      setError(event.error)
    }
  }

  const runSearch = async (preferences: SearchPreferences) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setSearching(true)
    setHasSearched(true)
    setLastSearch(preferences)
    setError(null)
    setResult(null)
    setSources([])
    setPhases(initialPhases())
    try {
      await streamSearch(preferences, handleEvent, controller.signal)
    } catch (requestError) {
      if (!controller.signal.aborted) {
        setError({ code: 'REQUEST_FAILED', message: requestError instanceof Error ? requestError.message : 'The request failed.' })
      }
    } finally {
      if (!controller.signal.aborted) setSearching(false)
    }
  }

  return (
    <div className="app-shell" id="top">
      <Header canRefresh={Boolean(lastSearch)} searching={searching} onRefresh={() => lastSearch && runSearch(lastSearch)} />

      {demoMode && (
        <div className="global-demo-label" role="status">
          Screenshot demo mode · fictional jobs · no TinyFish credits used
        </div>
      )}

      <main>
        <section className="hero-section" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow"><span /> TinyFish × TechnoJam</p>
            <h1 id="hero-title">Live opportunities.<br /><em>Less searching.</em></h1>
            <p className="hero-lede">RoleCurrent turns the open web into a concise, evidence-first job feed — matched to what you want now.</p>
            <a className="text-link" href="#search">Shape your search <ArrowDown size={15} /></a>
          </div>
          <div className="editorial-note" aria-label="How RoleCurrent works">
            <span className="note-index">RC / 01</span>
            <blockquote>“A smaller list of real openings beats a wall of stale links.”</blockquote>
            <div className="principles">
              <div><FileSearch size={17} /><span><strong>Read the source</strong>Search finds; Fetch verifies the page.</span></div>
              <div><ShieldCheck size={17} /><span><strong>Keep claims honest</strong>Unverified results remain clearly labelled.</span></div>
              <div><Radar size={17} /><span><strong>Stay current</strong>Every search starts from live web results.</span></div>
            </div>
          </div>
        </section>

        <SearchPanel initial={demoMode ? DEMO_SEARCH : DEFAULT_SEARCH} searching={searching} keyConfigured={keyConfigured} onSearch={runSearch} />

        {searching && <ProgressPanel phases={phases} sources={sources} />}

        {error && !searching && (
          <section className="error-state" role="alert">
            <TriangleAlert size={22} />
            <div>
              <p className="eyebrow">Search interrupted</p>
              <h2>{error.code === 'MISSING_API_KEY' ? 'TinyFish key missing' : 'The live search could not finish'}</h2>
              <p>{error.message}</p>
              {lastSearch && error.code !== 'MISSING_API_KEY' && <button type="button" onClick={() => runSearch(lastSearch)}>Try this search again</button>}
            </div>
          </section>
        )}

        {!searching && !error && result && result.jobs.length > 0 && <ResultsView result={result} />}
        {!searching && !error && hasSearched && result && result.jobs.length === 0 && <EmptyState />}

        {!hasSearched && (
          <section className="initial-state" id="results" aria-label="Discovery method">
            <p className="eyebrow">A deliberate pipeline</p>
            <div className="method-grid">
              <div><span>01</span><h2>Discover</h2><p>Search across independent ATS and career sources with current TinyFish results.</p></div>
              <div><span>02</span><h2>Verify</h2><p>Read individual pages, reject generic career hubs, and report source failures honestly.</p></div>
              <div><span>03</span><h2>Match</h2><p>Deduplicate and rank by your role, skills, location, and experience preferences.</p></div>
            </div>
          </section>
        )}
      </main>

      <footer>
        <a className="wordmark wordmark-small" href="#top">Role<span>Current</span></a>
        <p>Live opportunities. Less searching.</p>
        <a href="https://www.tinyfish.ai" target="_blank" rel="noreferrer">Powered by TinyFish <ExternalLink size={13} /></a>
      </footer>
    </div>
  )
}

export default App
