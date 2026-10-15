import { useMemo, useState } from 'react'
import { ArrowDownUp, CheckCircle2, Filter, SearchX, TriangleAlert } from 'lucide-react'
import type { Job, SearchResult } from '../types'
import { JobCard } from './JobCard'

interface ResultsViewProps {
  result: SearchResult
}

export function ResultsView({ result }: ResultsViewProps) {
  const [verification, setVerification] = useState<'all' | 'verified'>('all')
  const [type, setType] = useState('All types')
  const [remoteOnly, setRemoteOnly] = useState(false)
  const [sort, setSort] = useState<'relevance' | 'company'>('relevance')

  const jobs = useMemo(() => {
    let filtered = result.jobs.filter((job) => {
      if (verification === 'verified' && job.verification === 'discovered') return false
      if (type !== 'All types' && job.employmentType !== type) return false
      if (remoteOnly && !job.remote) return false
      return true
    })
    filtered = [...filtered].sort((a, b) => sort === 'company' ? a.company.localeCompare(b.company) : b.score - a.score)
    return filtered
  }, [result.jobs, verification, type, remoteOnly, sort])

  const employmentTypes = ['All types', ...Array.from(new Set(result.jobs.map((job) => job.employmentType))).filter(Boolean)]
  const searchedTime = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(new Date(result.searchedAt))

  return (
    <section className="results-section" id="results" aria-labelledby="results-title">
      <div className="results-heading">
        <div>
          <p className="eyebrow">Your live shortlist</p>
          <h2 id="results-title">{result.summary.uniqueResults} unique {result.summary.uniqueResults === 1 ? 'opening' : 'openings'}</h2>
          <p>
            {result.summary.verifiedResults} verified · {result.summary.pagesInspected} pages read · searched at {searchedTime}
          </p>
        </div>
        <div className="truth-summary">
          <CheckCircle2 size={16} />
          <span>{result.summary.successfulSources} sources responded</span>
        </div>
      </div>

      {result.demo && (
        <div className="demo-banner" role="status">
          <span>Demo dataset</span>
          <p>These fictional listings are shown for product demonstration and screenshots. No live search was run, and application actions are disabled.</p>
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="warning-banner" role="status">
          <TriangleAlert size={18} />
          <div>
            <strong>Partial source coverage</strong>
            <p>{result.warnings[0]} Successful sources and collected results are still shown.</p>
          </div>
        </div>
      )}

      {result.jobs.length > 0 && result.summary.verifiedResults === 0 && (
        <div className="verification-banner" role="status">
          <SearchX size={18} />
          <div>
            <strong>No pages were fully verified this run.</strong>
            <p>Individual listing candidates are shown as discovered only. Confirm details on the original page before applying.</p>
          </div>
        </div>
      )}

      <div className="results-layout">
        <aside className="filter-panel" aria-label="Result filters">
          <div className="filter-title"><Filter size={16} /> Refine</div>
          <fieldset>
            <legend>Verification</legend>
            <label><input type="radio" name="verification" checked={verification === 'all'} onChange={() => setVerification('all')} /> All listings</label>
            <label><input type="radio" name="verification" checked={verification === 'verified'} onChange={() => setVerification('verified')} /> Verified only</label>
          </fieldset>
          <label className="filter-select">
            <span>Opportunity type</span>
            <select value={type} onChange={(event) => setType(event.target.value)}>
              {employmentTypes.map((option) => <option key={option}>{option}</option>)}
            </select>
          </label>
          <label className="filter-check">
            <input type="checkbox" checked={remoteOnly} onChange={(event) => setRemoteOnly(event.target.checked)} />
            Remote options only
          </label>
          <div className="source-summary">
            <span>Source report</span>
            {result.sources.map((source) => (
              <div key={source.id}>
                <i className={`source-dot source-${source.status}`} />
                <p>{source.label}<small>{source.verifiedCount} verified</small></p>
              </div>
            ))}
          </div>
        </aside>

        <div className="result-feed">
          <div className="feed-toolbar">
            <span>Showing {jobs.length} of {result.jobs.length}</span>
            <label>
              <ArrowDownUp size={14} />
              <span className="sr-only">Sort results</span>
              <select value={sort} onChange={(event) => setSort(event.target.value as 'relevance' | 'company')}>
                <option value="relevance">Most relevant</option>
                <option value="company">Company A–Z</option>
              </select>
            </label>
          </div>
          {jobs.length > 0 ? jobs.map((job: Job, index) => <JobCard key={job.id} job={job} index={index} demo={result.demo} />) : (
            <div className="filtered-empty">
              <SearchX size={22} />
              <h3>No openings match these filters</h3>
              <p>Reset a filter to return to the full live shortlist.</p>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
