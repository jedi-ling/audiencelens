/**
 * /samples —— 只读的样例报告列表。
 *
 * 数据是构建期就在的静态文件（public/sample-reports/，由 scripts/sync_sample_reports.py
 * 从 examples/reports/ 同步），不走后端 API：不需要登录，也不需要 API Key。
 * 每份报告都是一次真实引擎运行的原始产物，没有手工修改过——所以连"有几位人格
 * 没通过校验""交叉质询没有跑"这种不好看的结果也原样展示，不藏。
 */
import { useEffect, useState } from 'react'
import { ExternalLink, FileText, Loader2 } from 'lucide-react'
import { t } from '@/i18n/runtime'
import { useDocumentTitle } from '@/i18n/head'
import { formatUsd } from '@/i18n/format'
import { findTaskType } from '@/i18n/catalog'

interface SampleReport {
  slug: string
  title: string
  task_type: string
  persona_pack: string
  model_id: string
  date: string
  cost_usd: number
  personas_passed: number | null
  personas_attempted: number | null
  cross_exam_ran: boolean
  disputes: number
}

const BASE = '/sample-reports'

export default function SamplesPage() {
  useDocumentTitle('page.samples.meta.title')
  const [samples, setSamples] = useState<SampleReport[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetch(`${BASE}/index.json`)
      .then((res) => {
        if (!res.ok) throw new Error(String(res.status))
        return res.json() as Promise<SampleReport[]>
      })
      .then((data) => {
        if (!cancelled) setSamples(data)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="max-w-4xl mx-auto px-4 py-10 animate-fade-in">
      <header className="mb-8">
        <h1 className="font-display text-3xl md:text-4xl font-bold text-text-primary mb-3">
          {t('page.samples.header.title')}
        </h1>
        <p className="text-text-secondary text-[15px] leading-relaxed">{t('page.samples.header.desc')}</p>
        <p className="mt-3 text-xs text-text-muted">{t('page.samples.notice.desc')}</p>
      </header>

      {failed ? (
        <div className="rounded-xl border border-border bg-bg-card p-4 text-sm text-text-muted">
          {t('page.samples.load.error')}
        </div>
      ) : samples === null ? (
        <div className="flex items-center gap-2 text-sm text-text-muted">
          <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} />
          {t('page.samples.load.pending')}
        </div>
      ) : (
        <ul className="space-y-4">
          {samples.map((s) => (
            <li key={s.slug} className="rounded-xl border border-border bg-bg-card p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="flex items-center gap-2 font-display text-lg font-semibold text-text-primary">
                    <FileText className="h-4 w-4 shrink-0 text-brand-primary" strokeWidth={1.5} />
                    <span className="break-words">{s.title}</span>
                  </h2>
                  <p className="mt-1 text-sm text-text-secondary">
                    {findTaskType(s.task_type)?.name ?? s.task_type}
                  </p>
                </div>
                <a
                  href={`${BASE}/${s.slug}/report.html`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-lg bg-brand-primary px-3 py-2 text-sm font-semibold text-white hover:bg-brand-primary/90"
                >
                  {t('page.samples.open.cta')}
                  <ExternalLink className="h-3.5 w-3.5" strokeWidth={1.75} />
                </a>
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
                <div>
                  <dt className="text-text-muted">{t('page.samples.model.label')}</dt>
                  <dd className="font-mono text-text-primary">{s.model_id}</dd>
                </div>
                <div>
                  <dt className="text-text-muted">{t('page.samples.date.label')}</dt>
                  <dd className="text-text-primary">{s.date}</dd>
                </div>
                <div>
                  <dt className="text-text-muted">{t('page.samples.cost.label')}</dt>
                  <dd className="tabular-nums text-text-primary">{formatUsd(s.cost_usd, 2)}</dd>
                </div>
                <div>
                  <dt className="text-text-muted">{t('page.samples.personas.label')}</dt>
                  <dd className="tabular-nums text-text-primary">
                    {s.personas_passed ?? '–'} / {s.personas_attempted ?? '–'}
                  </dd>
                </div>
              </dl>
              <p className="mt-3 text-xs text-text-muted">
                {s.cross_exam_ran
                  ? t('page.samples.disputes.label', { count: s.disputes })
                  : t('page.samples.no_cross_exam.hint')}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
