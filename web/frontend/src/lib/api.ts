import type { Review, Report, Persona, PersonaPack, Preset, WSMessage, Example, ReviewModeConfig, TaskTypeDetail, ReviewResultData, SkillType, SkillDetail, EvaluationScorecard, EthicsReport } from './mock-data'

export async function fetchReviews(): Promise<Review[]> {
  const res = await fetch('/api/reviews')
  if (!res.ok) throw new Error(`Failed to fetch reviews: ${res.statusText}`)
  return res.json()
}

export async function fetchReview(id: string): Promise<Review> {
  const res = await fetch(`/api/reviews/${id}`)
  if (!res.ok) throw new Error(`Failed to fetch review: ${res.statusText}`)
  return res.json()
}

export async function fetchReport(reviewId: string): Promise<{ report_json: Report; report_markdown: string; calibration: unknown }> {
  const res = await fetch(`/api/reviews/${reviewId}/report`)
  if (!res.ok) throw new Error(`Failed to fetch report: ${res.statusText}`)
  return res.json()
}

export async function fetchPersonas(): Promise<Persona[]> {
  const res = await fetch('/api/personas')
  if (!res.ok) throw new Error(`Failed to fetch personas: ${res.statusText}`)
  return res.json()
}

export async function fetchPersonaPacks(): Promise<PersonaPack[]> {
  const res = await fetch('/api/personas/packs')
  if (!res.ok) throw new Error(`Failed to fetch persona packs: ${res.statusText}`)
  return res.json()
}

export async function fetchExamples(): Promise<Example[]> {
  const res = await fetch('/api/examples')
  if (!res.ok) throw new Error(`Failed to fetch examples: ${res.statusText}`)
  return res.json()
}

export async function fetchPresets(): Promise<Preset[]> {
  const res = await fetch('/api/presets')
  if (!res.ok) throw new Error(`Failed to fetch presets: ${res.statusText}`)
  return res.json()
}

export async function createReview(data: {
  task_type: string
  artifact_bundle: Record<string, unknown>
  persona_pack?: string
  selected_personas?: string[]
  mode?: string
  skill_type?: SkillType
  enable_evaluation?: boolean
  enable_red_team?: boolean
}): Promise<Review> {
  const res = await fetch('/api/reviews', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`Failed to create review: ${res.statusText}`)
  return res.json()
}

export async function extractMaterials(taskType: string, file: File): Promise<{ title: string; materials: Record<string, string> }> {
  const formData = new FormData()
  formData.append('task_type', taskType)
  formData.append('file', file)
  const res = await fetch('/api/extract-materials', {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) throw new Error(`Failed to extract materials: ${res.statusText}`)
  return res.json()
}

export async function deleteReview(id: string): Promise<void> {
  const res = await fetch(`/api/reviews/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`Failed to delete review: ${res.statusText}`)
}

export function connectReviewWS(
  reviewId: string,
  onMessage: (msg: WSMessage) => void
): () => void {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/ws/review/${reviewId}`
  const ws = new WebSocket(wsUrl)
  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      onMessage(msg)
    } catch {}
  }
  return () => {
    ws.close()
  }
}

export interface LLMFormat {
  name: string
  description: string
  default_base: string
  requires_api_key: boolean
}

export interface LLMPreset {
  id: string
  name: string
  api_format: string
  model: string
  api_base: string
  has_env_key: boolean
}

export async function fetchLLMFormats(): Promise<Record<string, LLMFormat>> {
  const res = await fetch('/api/settings/llm/formats')
  if (!res.ok) throw new Error(`Failed to fetch LLM formats: ${res.statusText}`)
  return res.json()
}

export async function fetchLLMPresets(): Promise<LLMPreset[]> {
  const res = await fetch('/api/settings/llm/presets')
  if (!res.ok) throw new Error(`Failed to fetch LLM presets: ${res.statusText}`)
  return res.json()
}

export async function saveLLMSettings(data: {
  api_format: string
  api_key?: string
  model: string
  api_base?: string
  session_id?: string
}): Promise<{ status: string }> {
  const res = await fetch('/api/settings/llm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`Failed to save LLM settings: ${res.statusText}`)
  return res.json()
}

export async function testLLMConnection(data: {
  api_format: string
  api_key?: string
  model: string
  api_base?: string
}): Promise<{ connected: boolean; model?: string; error?: string }> {
  const res = await fetch('/api/settings/llm/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`Failed to test LLM connection: ${res.statusText}`)
  return res.json()
}

export async function fetchTaskTypes(): Promise<TaskTypeDetail[]> {
  const res = await fetch('/api/task-types')
  if (!res.ok) throw new Error(`Failed to fetch task types: ${res.statusText}`)
  return res.json()
}

export async function fetchTaskType(taskType: string): Promise<TaskTypeDetail> {
  const res = await fetch(`/api/task-types/${taskType}`)
  if (!res.ok) throw new Error(`Failed to fetch task type: ${res.statusText}`)
  return res.json()
}

export async function fetchReviewModes(): Promise<ReviewModeConfig[]> {
  const res = await fetch('/api/review-modes')
  if (!res.ok) throw new Error(`Failed to fetch review modes: ${res.statusText}`)
  return res.json()
}

export async function fetchPersonasByPack(pack: string): Promise<Persona[]> {
  const res = await fetch(`/api/personas/packs/${pack}`)
  if (!res.ok) throw new Error(`Failed to fetch personas by pack: ${res.statusText}`)
  return res.json()
}

export async function fetchReviewResult(reviewId: string): Promise<ReviewResultData> {
  const res = await fetch(`/api/reviews/${reviewId}/result`)
  if (!res.ok) throw new Error(`Failed to fetch review result: ${res.statusText}`)
  return res.json()
}

export async function fetchSkills(): Promise<SkillDetail[]> {
  const res = await fetch('/api/skills')
  if (!res.ok) throw new Error(`Failed to fetch skills: ${res.statusText}`)
  return res.json()
}

export async function fetchSkill(skillType: SkillType): Promise<SkillDetail> {
  const res = await fetch(`/api/skills/${skillType}`)
  if (!res.ok) throw new Error(`Failed to fetch skill: ${res.statusText}`)
  return res.json()
}

export async function runEvaluation(reviewId: string): Promise<EvaluationScorecard> {
  const res = await fetch(`/api/evaluations/${reviewId}`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to run evaluation: ${res.statusText}`)
  return res.json()
}

export async function fetchEvaluation(reviewId: string): Promise<EvaluationScorecard> {
  const res = await fetch(`/api/evaluations/${reviewId}`)
  if (!res.ok) throw new Error(`Failed to fetch evaluation: ${res.statusText}`)
  return res.json()
}

export async function fetchEthicsReport(reviewId: string): Promise<EthicsReport[]> {
  const res = await fetch(`/api/evaluations/${reviewId}/ethics`)
  if (!res.ok) throw new Error(`Failed to fetch ethics report: ${res.statusText}`)
  return res.json()
}

export async function fetchRubric(): Promise<{ dimensions: { id: string; name: string; description: string }[] }> {
  const res = await fetch('/api/rubric')
  if (!res.ok) throw new Error(`Failed to fetch rubric: ${res.statusText}`)
  return res.json()
}

export async function generatePersonas(data: {
  skill_type: SkillType
  task_type: string
  count?: number
  constraints?: Record<string, unknown>
}): Promise<Persona[]> {
  const res = await fetch('/api/generate-personas', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`Failed to generate personas: ${res.statusText}`)
  return res.json()
}
