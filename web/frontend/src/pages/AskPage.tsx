/**
 * 对话式入口 —— 用户用大白话说，系统自己推断评审参数。
 *
 * 完整链路：
 *   输入 → POST /api/intent/parse（无 key 自动降级启发式）
 *        → 展示解析结果，置信度低时追问而不是瞎猜
 *        → 确认 → POST /api/v2/reviews（无 key 返回 428，引导去设置页）
 *        → 跳到进度页，WS 推送实时进度
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { api, ApiError } from '@/lib/apiClient'
import { useSessionStore } from '@/store/session-store'
import type { IntentResult } from '@/lib/types'

const EXAMPLES = [
  '帮我评审这个 Roguelike 的 Steam 商店页，重点看信任信号和转化',
  '这是我的付费设计，帮我看付费墙会不会太早劝退玩家',
  'Demo 首玩体验评审，重点看前 15 分钟的上手摩擦',
]

const TASK_LABELS: Record<string, string> = {
  steam_page_review: 'Steam 商店页评审',
  demo_first_play: 'Demo 首玩评审',
  concept_review: '概念评审',
  monetization_review: '付费设计评审',
  looking_for_party_post: '组队招募文案评审',
  update_announcement_review: '更新公告评审',
  devlog_review: '开发日志评审',
  kickstarter_review: '众筹页评审',
  localization_review: '本地化评审',
  discord_community_review: 'Discord 社区评审',
}

export default function AskPage() {
  const navigate = useNavigate()
  const { config, keyStatus, bootstrap, canReview } = useSessionStore()

  const [text, setText] = useState('')
  const [intent, setIntent] = useState<IntentResult | null>(null)
  const [parsing, setParsing] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [needsKey, setNeedsKey] = useState(false)

  useEffect(() => {
    void bootstrap()
  }, [bootstrap])

  const handleParse = async () => {
    if (!text.trim()) return
    setParsing(true)
    setError(null)
    setNeedsKey(false)
    try {
      setIntent(await api.parseIntent(text))
    } catch (e) {
      setError(e instanceof Error ? e.message : '解析失败')
    } finally {
      setParsing(false)
    }
  }

  const handleSubmit = async () => {
    if (!intent?.task_type) return
    setSubmitting(true)
    setError(null)
    try {
      const res = await api.createReview({
        task_type: intent.task_type,
        artifact: {
          title: text.slice(0, 60),
          materials: [{ type: 'text', text: intent.artifact_text || text }],
        },
        mode: intent.mode,
        persona_pack: intent.persona_pack,
      })
      navigate(`/review/${res.review_id}`)
    } catch (e) {
      // 关键分支：缺 key 不是报错，是引导
      if (e instanceof ApiError && e.needsApiKey) {
        setNeedsKey(true)
        setError(e.message)
      } else {
        setError(e instanceof Error ? e.message : '发起评审失败')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const ready = canReview()

  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <header className="mb-10 text-center">
        <h1 className="text-4xl font-bold tracking-tight">让 75 位 AI 观众先吵一架</h1>
        <p className="mt-3 text-muted-foreground">
          直接说你想评审什么，或把材料贴进来——系统会自己判断该开哪种庭。
        </p>
      </header>

      {/* 无 key 提醒：BYOK 模式下先引导填 key，别等提交才报错 */}
      {config && !ready && (
        <div className="mb-6 rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-sm">
          <p className="font-medium">尚未配置 API Key</p>
          <p className="mt-1 text-muted-foreground">
            评审必须使用真实模型——模拟数据没有评审价值。
            <button
              className="ml-1 underline underline-offset-2"
              onClick={() => navigate('/settings')}
            >
              去设置页填写
            </button>
          </p>
        </div>
      )}

      <div className="rounded-xl border bg-card shadow-sm">
        <textarea
          className="min-h-[120px] w-full resize-y bg-transparent p-4 text-base outline-none"
          placeholder="把你的 Steam 页面文案、Demo 描述或概念文档贴进来，评审团即刻开庭…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void handleParse()
            }
          }}
        />
        <div className="flex items-center gap-3 border-t px-4 py-3">
          <span className="text-xs text-muted-foreground">Enter 解析 · Shift+Enter 换行</span>
          <button
            className="ml-auto rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            onClick={handleParse}
            disabled={parsing || !text.trim()}
          >
            {parsing ? '解析中…' : '解析意图'}
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            className="rounded-md border px-3 py-1.5 text-xs text-muted-foreground hover:border-primary"
            onClick={() => setText(ex)}
          >
            {ex.slice(0, 22)}…
          </button>
        ))}
      </div>

      {error && (
        <div className="mt-6 rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm">
          {error}
          {needsKey && (
            <button
              className="ml-2 underline underline-offset-2"
              onClick={() => navigate('/settings')}
            >
              去填写 API Key
            </button>
          )}
        </div>
      )}

      {intent && (
        <div className="mt-8 rounded-xl border bg-card p-6">
          <div className="mb-4 flex items-center gap-2 text-xs text-muted-foreground">
            <span>解析结果</span>
            {/* 如实声明用了哪档解析，不假装都是 AI */}
            <span className="rounded bg-muted px-2 py-0.5">
              {intent.method === 'llm' ? 'LLM 解析' : '规则解析（无 Key 降级）'}
            </span>
            <span>置信度 {(intent.confidence * 100).toFixed(0)}%</span>
          </div>

          {intent.needs_clarification ? (
            <div>
              <p className="font-medium">{intent.clarifying_question ?? '需要更多信息'}</p>
              {intent.candidates.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {intent.candidates.map((c) => (
                    <button
                      key={c}
                      className="rounded-md border px-3 py-1.5 text-sm hover:border-primary"
                      onClick={() =>
                        setIntent({
                          ...intent,
                          task_type: c as IntentResult['task_type'],
                          needs_clarification: false,
                        })
                      }
                    >
                      {TASK_LABELS[c] ?? c}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <>
              <dl className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <dt className="text-muted-foreground">任务类型</dt>
                  <dd className="mt-1 font-medium">
                    {TASK_LABELS[intent.task_type ?? ''] ?? intent.task_type}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">深度</dt>
                  <dd className="mt-1 font-medium">{intent.mode}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">人格包</dt>
                  <dd className="mt-1 font-medium">{intent.persona_pack}</dd>
                </div>
              </dl>
              <button
                className="mt-6 w-full rounded-md bg-primary py-2.5 font-semibold text-primary-foreground disabled:opacity-50"
                onClick={handleSubmit}
                disabled={submitting}
              >
                {submitting ? '开庭中…' : '开庭评审 →'}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
