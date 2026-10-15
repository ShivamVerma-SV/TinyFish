import type { SearchEvent, SearchPreferences } from './types'

export async function getStatus(): Promise<{ keyConfigured: boolean }> {
  const response = await fetch('/api/status')
  if (!response.ok) throw new Error('The RoleCurrent server is not available.')
  return response.json()
}

export async function streamSearch(
  preferences: SearchPreferences,
  onEvent: (event: SearchEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(preferences),
    signal,
  })
  if (!response.ok || !response.body) {
    if (response.status === 422) throw new Error('Review the highlighted preferences and try again.')
    throw new Error('The search request could not be started.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let pending = ''
  while (true) {
    const { value, done } = await reader.read()
    pending += decoder.decode(value, { stream: !done })
    const lines = pending.split('\n')
    pending = lines.pop() ?? ''
    for (const line of lines) {
      if (line.trim()) onEvent(JSON.parse(line) as SearchEvent)
    }
    if (done) break
  }
  if (pending.trim()) onEvent(JSON.parse(pending) as SearchEvent)
}
