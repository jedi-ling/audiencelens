import type { Review, Report, Persona, PersonaPack, Preset, WSMessage, Example, ReviewModeConfig, TaskTypeDetail, ReviewResultData, SkillType, SkillDetail, EvaluationScorecard, EthicsReport } from './mock-data'
import { getToken } from './apiClient'

/** v1 链路统一出口：所有请求都带上登录态——
 *  后端按身份归属/裁剪数据，漏带 token 的调用会拿到匿名视角（见 fetchReport 的教训）。 */
function authedFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const token = getToken()
  const headers = new Headers(init.headers)
  if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`)
  return fetch(input, { ...init, headers })
}

export async function fetchReviews(): Promise<Review[]> {
  const res = await authedFetch('/api/reviews')
  if (!res.ok) throw new Error(`Failed to fetch reviews: ${res.statusText}`)
  return res.json()
}

export async function fetchReview(id: string): Promise<Review> {
  const res = await authedFetch(`/api/reviews/${id}`)
  if (!res.ok) throw new Error(`Failed to fetch review: ${res.statusText}`)
  return res.json()
}

export async function fetchReport(reviewId: string): Promise<{ report_json: Report; report_markdown: string; calibration: unknown }> {
  const res = await authedFetch(`/api/reviews/${reviewId}/report`)
  if (!res.ok) throw new Error(`Failed to fetch report: ${res.statusText}`)
  return res.json()
}

export async function fetchPersonas(): Promise<Persona[]> {
  const res = await authedFetch('/api/personas')
  if (!res.ok) throw new Error(`Failed to fetch personas: ${res.statusText}`)
  return res.json()
}

export async function fetchPersonaPacks(): Promise<PersonaPack[]> {
  const res = await authedFetch('/api/personas/packs')
  if (!res.ok) throw new Error(`Failed to fetch persona packs: ${res.statusText}`)
  return res.json()
}

export async function fetchExamples(): Promise<Example[]> {
  const res = await authedFetch('/api/examples')
  if (!res.ok) throw new Error(`Failed to fetch examples: ${res.statusText}`)
  return res.json()
}

export async function fetchPresets(): Promise<Preset[]> {
  const res = await authedFetch('/api/presets')
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
  const res = await authedFetch('/api/reviews', {
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
  const res = await authedFetch('/api/extract-materials', {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) throw new Error(`Failed to extract materials: ${res.statusText}`)
  return res.json()
}

export async function deleteReview(id: string): Promise<void> {
  const res = await authedFetch(`/api/reviews/${id}`, { method: 'DELETE' })
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

export async function fetchTaskTypes(): Promise<TaskTypeDetail[]> {
  const res = await authedFetch('/api/task-types')
  if (!res.ok) throw new Error(`Failed to fetch task types: ${res.statusText}`)
  return res.json()
}

export async function fetchTaskType(taskType: string): Promise<TaskTypeDetail> {
  const res = await authedFetch(`/api/task-types/${taskType}`)
  if (!res.ok) throw new Error(`Failed to fetch task type: ${res.statusText}`)
  return res.json()
}

export async function fetchReviewModes(): Promise<ReviewModeConfig[]> {
  const res = await authedFetch('/api/review-modes')
  if (!res.ok) throw new Error(`Failed to fetch review modes: ${res.statusText}`)
  return res.json()
}

export async function fetchPersonasByPack(pack: string): Promise<Persona[]> {
  const res = await authedFetch(`/api/personas/packs/${pack}`)
  if (!res.ok) throw new Error(`Failed to fetch personas by pack: ${res.statusText}`)
  return res.json()
}

export async function fetchReviewResult(reviewId: string): Promise<ReviewResultData> {
  const res = await authedFetch(`/api/reviews/${reviewId}/result`)
  if (!res.ok) throw new Error(`Failed to fetch review result: ${res.statusText}`)
  return res.json()
}

export async function fetchSkills(): Promise<SkillDetail[]> {
  const res = await authedFetch('/api/skills')
  if (!res.ok) throw new Error(`Failed to fetch skills: ${res.statusText}`)
  return res.json()
}

export async function fetchSkill(skillType: SkillType): Promise<SkillDetail> {
  const res = await authedFetch(`/api/skills/${skillType}`)
  if (!res.ok) throw new Error(`Failed to fetch skill: ${res.statusText}`)
  return res.json()
}

export async function runEvaluation(reviewId: string): Promise<EvaluationScorecard> {
  const res = await authedFetch(`/api/evaluations/${reviewId}`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to run evaluation: ${res.statusText}`)
  return res.json()
}

export async function fetchEvaluation(reviewId: string): Promise<EvaluationScorecard> {
  const res = await authedFetch(`/api/evaluations/${reviewId}`)
  if (!res.ok) throw new Error(`Failed to fetch evaluation: ${res.statusText}`)
  return res.json()
}

export async function fetchEthicsReport(reviewId: string): Promise<EthicsReport[]> {
  const res = await authedFetch(`/api/evaluations/${reviewId}/ethics`)
  if (!res.ok) throw new Error(`Failed to fetch ethics report: ${res.statusText}`)
  return res.json()
}

export async function fetchRubric(): Promise<{ dimensions: { id: string; name: string; description: string }[] }> {
  const res = await authedFetch('/api/rubric')
  if (!res.ok) throw new Error(`Failed to fetch rubric: ${res.statusText}`)
  return res.json()
}

export async function generatePersonas(data: {
  skill_type: SkillType
  task_type: string
  count?: number
  constraints?: Record<string, unknown>
}): Promise<Persona[]> {
  const res = await authedFetch('/api/generate-personas', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`Failed to generate personas: ${res.statusText}`)
  return res.json()
}
