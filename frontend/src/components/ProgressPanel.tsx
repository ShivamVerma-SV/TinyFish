import { Check, Circle, LoaderCircle, Minus, TriangleAlert } from 'lucide-react'
import type { ProgressPhase, SourceState } from '../types'

interface ProgressPanelProps {
  phases: ProgressPhase[]
  sources: SourceState[]
}

const iconFor = (state: ProgressPhase['state']) => {
  if (state === 'active') return <LoaderCircle size={17} className="spin" />
  if (state === 'complete') return <Check size={17} />
  if (state === 'warning') return <TriangleAlert size={17} />
  if (state === 'skipped') return <Minus size={17} />
  return <Circle size={15} />
}

export function ProgressPanel({ phases, sources }: ProgressPanelProps) {
  return (
    <section className="progress-panel" aria-live="polite" aria-label="Live search progress">
      <div className="progress-heading">
        <div>
          <p className="eyebrow">Live discovery</p>
          <h2>Building your shortlist</h2>
        </div>
        <span className="live-label"><i /> In progress</span>
      </div>
      <ol className="phase-list">
        {phases.map((phase) => (
          <li key={phase.id} className={`phase phase-${phase.state}`}>
            <span className="phase-icon">{iconFor(phase.state)}</span>
            <div>
              <strong>{phase.label}</strong>
              <p>{phase.message}</p>
            </div>
            {phase.total && phase.state === 'active' ? <span className="phase-count">{phase.completed ?? 0}/{phase.total}</span> : null}
          </li>
        ))}
      </ol>
      {sources.length > 0 && (
        <div className="source-strip">
          {sources.map((source) => (
            <span key={source.id} className={`source-pill source-${source.status}`} title={source.error || source.label}>
              <i /> {source.label}
            </span>
          ))}
        </div>
      )}
    </section>
  )
}
