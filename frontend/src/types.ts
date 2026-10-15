export type LocationScope = 'preferred' | 'remote' | 'anywhere'
export type OpportunityType = 'Internship' | 'Full-time' | 'Both'
export type ExperienceLevel = 'Entry-level' | 'Mid-level' | 'Senior' | 'Any'
export type PhaseState = 'pending' | 'active' | 'complete' | 'warning' | 'skipped'

export interface SearchPreferences {
  role: string
  location: string
  locationScope: LocationScope
  skills: string[]
  opportunityType: OpportunityType
  experienceLevel: ExperienceLevel
  useAgent: boolean
  maxResults: number
}

export interface Job {
  id: string
  title: string
  company: string
  location: string
  remote: boolean
  employmentType: string
  description: string
  skills: string[]
  apply_url: string
  source: string
  score: number
  verification: 'fetch_verified' | 'agent_verified' | 'discovered'
}

export interface SourceState {
  id: string
  label: string
  status: 'pending' | 'active' | 'complete' | 'empty' | 'failed'
  discoveredCount: number
  verifiedCount: number
  error: string
}

export interface SearchResult {
  demo?: boolean
  jobs: Job[]
  sources: SourceState[]
  warnings: string[]
  summary: {
    uniqueResults: number
    verifiedResults: number
    searchResultsScreened: number
    pagesInspected: number
    successfulSources: number
    failedSources: number
  }
  searchedAt: string
}

export interface ProgressPhase {
  id: string
  label: string
  state: PhaseState
  message: string
  completed?: number
  total?: number
}

export type SearchEvent =
  | { type: 'progress'; phase: string; state: PhaseState; message: string; completed?: number; total?: number }
  | { type: 'source'; source: SourceState }
  | { type: 'complete'; result: SearchResult }
  | { type: 'error'; error: { code: string; message: string } }
