import { FormEvent, useState } from 'react'
import { ArrowRight, Bot, BriefcaseBusiness, MapPin, Search, Tags } from 'lucide-react'
import type { ExperienceLevel, LocationScope, OpportunityType, SearchPreferences } from '../types'

interface SearchPanelProps {
  initial: SearchPreferences
  searching: boolean
  keyConfigured: boolean | null
  onSearch: (preferences: SearchPreferences) => void
}

export function SearchPanel({ initial, searching, keyConfigured, onSearch }: SearchPanelProps) {
  const [form, setForm] = useState(initial)
  const [skillsText, setSkillsText] = useState(initial.skills.join(', '))
  const [error, setError] = useState('')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!form.role.trim()) {
      setError('Enter a role or job title to begin.')
      return
    }
    if (form.locationScope === 'preferred' && !form.location.trim()) {
      setError('Enter a preferred location, or choose Remote or Anywhere.')
      return
    }
    setError('')
    onSearch({
      ...form,
      role: form.role.trim(),
      location: form.location.trim(),
      skills: skillsText.split(',').map((skill) => skill.trim()).filter(Boolean).slice(0, 12),
    })
  }

  const setScope = (locationScope: LocationScope) => setForm((current) => ({ ...current, locationScope }))

  return (
    <section className="search-panel" id="search" aria-labelledby="search-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Build your live shortlist</p>
          <h2 id="search-title">What are you looking for?</h2>
        </div>
        <span className="panel-step">01 / Search</span>
      </div>

      <form onSubmit={submit} noValidate>
        <div className="form-grid">
          <label className="field field-wide">
            <span><BriefcaseBusiness size={15} /> Role or job title</span>
            <input
              value={form.role}
              onChange={(event) => setForm({ ...form, role: event.target.value })}
              placeholder="e.g. Product designer or backend engineer"
              autoComplete="off"
              aria-describedby={error ? 'form-error' : undefined}
            />
          </label>

          <fieldset className="field location-field field-wide">
            <legend><MapPin size={15} /> Location</legend>
            <div className="segmented" aria-label="Location preference">
              {([
                ['preferred', 'Preferred place'],
                ['remote', 'Remote'],
                ['anywhere', 'Anywhere'],
              ] as [LocationScope, string][]).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className={form.locationScope === value ? 'selected' : ''}
                  onClick={() => setScope(value)}
                  aria-pressed={form.locationScope === value}
                >
                  {label}
                </button>
              ))}
            </div>
            <input
              className="location-input"
              value={form.location}
              onChange={(event) => setForm({ ...form, location: event.target.value })}
              placeholder="e.g. Bengaluru, India"
              disabled={form.locationScope !== 'preferred'}
              aria-label="Preferred location"
            />
          </fieldset>

          <label className="field field-wide">
            <span><Tags size={15} /> Skills and keywords</span>
            <input
              value={skillsText}
              onChange={(event) => setSkillsText(event.target.value)}
              placeholder="e.g. TypeScript, React, design systems"
              autoComplete="off"
            />
            <small>Separate skills with commas. They improve ranking, not the source data.</small>
          </label>

          <label className="field">
            <span>Opportunity type</span>
            <select
              value={form.opportunityType}
              onChange={(event) => setForm({ ...form, opportunityType: event.target.value as OpportunityType })}
            >
              <option>Both</option>
              <option>Internship</option>
              <option>Full-time</option>
            </select>
          </label>

          <label className="field">
            <span>Experience level</span>
            <select
              value={form.experienceLevel}
              onChange={(event) => setForm({ ...form, experienceLevel: event.target.value as ExperienceLevel })}
            >
              <option>Any</option>
              <option>Entry-level</option>
              <option>Mid-level</option>
              <option>Senior</option>
            </select>
          </label>
        </div>

        <div className="agent-option">
          <label>
            <input
              type="checkbox"
              checked={form.useAgent}
              onChange={(event) => setForm({ ...form, useAgent: event.target.checked })}
            />
            <span className="custom-check" aria-hidden="true" />
            <Bot size={16} />
            <span>
              <strong>Use Agent fallback</strong>
              <small>Checks one difficult dynamic listing when Fetch cannot verify it. Slower and may use paid Agent capacity.</small>
            </span>
          </label>
        </div>

        {error && <p className="form-error" id="form-error" role="alert">{error}</p>}
        {keyConfigured === false && (
          <div className="inline-notice" role="alert">
            <strong>Server key required.</strong> Add <code>TINYFISH_API_KEY</code> to <code>.env</code>, then restart the backend.
          </div>
        )}

        <button className="search-button" type="submit" disabled={searching || keyConfigured === false}>
          {searching ? <Search size={18} className="searching-icon" /> : <Search size={18} />}
          {searching ? 'Searching live sources…' : 'Find live opportunities'}
          {!searching && <ArrowRight size={17} />}
        </button>
      </form>
    </section>
  )
}
