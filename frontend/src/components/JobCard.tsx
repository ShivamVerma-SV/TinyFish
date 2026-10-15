import { ArrowUpRight, Building2, CheckCircle2, CircleHelp, MapPin, Radar, Wifi } from 'lucide-react'
import type { Job } from '../types'

const verificationLabel = (job: Job) => {
  if (job.verification === 'fetch_verified') return { label: 'Page verified', icon: <CheckCircle2 size={14} /> }
  if (job.verification === 'agent_verified') return { label: 'Agent verified', icon: <Radar size={14} /> }
  return { label: 'Discovered — verify details', icon: <CircleHelp size={14} /> }
}

export function JobCard({ job, index, demo = false }: { job: Job; index: number; demo?: boolean }) {
  const verification = verificationLabel(job)
  return (
    <article className="job-card">
      <div className="job-number" aria-hidden="true">{String(index + 1).padStart(2, '0')}</div>
      <div className="job-content">
        <div className="job-heading">
          <div>
            <p className="job-company"><Building2 size={14} /> {job.company}</p>
            <h3>{job.title}</h3>
          </div>
          <span className="match-score"><strong>{job.score}%</strong> match</span>
        </div>
        <div className="job-meta">
          <span><MapPin size={14} /> {job.location}</span>
          {job.remote && <span><Wifi size={14} /> Remote option</span>}
          <span>{job.employmentType}</span>
        </div>
        <p className="job-description">{job.description || 'Open the original listing to review the complete role details.'}</p>
        {job.skills.length > 0 && (
          <ul className="skill-list" aria-label="Relevant skills">
            {job.skills.map((skill) => <li key={skill}>{skill}</li>)}
          </ul>
        )}
        <div className="job-footer">
          <div className={`verification verification-${job.verification}`}>
            {verification.icon}
            <span>{verification.label}</span>
            {demo ? <span className="demo-source">{job.source}</span> : (
              <a href={job.apply_url} target="_blank" rel="noopener noreferrer" aria-label={`Open source listing on ${job.source}`}>
                {job.source} <ArrowUpRight size={12} />
              </a>
            )}
          </div>
          {demo ? (
            <span className="apply-button apply-button-demo" aria-label="Demo application action, disabled">
              View & apply <ArrowUpRight size={15} />
            </span>
          ) : (
            <a className="apply-button" href={job.apply_url} target="_blank" rel="noopener noreferrer">
              View & apply <ArrowUpRight size={15} />
            </a>
          )}
        </div>
      </div>
    </article>
  )
}
