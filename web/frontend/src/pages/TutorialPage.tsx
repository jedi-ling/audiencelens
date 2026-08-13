import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { TASK_MATERIALS, TASK_TYPES } from '@/lib/mock-data'
import { fetchExamples } from '@/lib/api'
import { api } from '@/lib/apiClient'
import type { UploadConfig } from '@/lib/types'
import {
  ListChecks,
  FileText,
  Upload,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Users,
  AlertTriangle,
  Eye,
  BarChart3,
  BrainCircuit,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { PageShell, PageHeader, SectionCard, PRIMARY_BUTTON_CLASS } from '@/components/ui'
import { t } from '@/i18n/runtime'
import { useDocumentTitle } from '@/i18n/head'
import { formatBytes } from '@/i18n/format'
import type { PlainMessageKey } from '@/i18n/keys.gen'

/**
 * 四个流程步骤。
 *
 * 存的是 **key 不是文案**：这个数组在模块求值时就固定了，存翻译结果的话
 * 切换语言不会重新求值，四张步骤卡会一直停在打开页面时的那种语言。
 */
const steps: { icon: LucideIcon; labelKey: PlainMessageKey; descKey: PlainMessageKey }[] = [
  { icon: ListChecks, labelKey: 'page.tutorial.step_select_type.label', descKey: 'page.tutorial.step_select_type.desc' },
  { icon: Upload, labelKey: 'page.tutorial.step_upload.label', descKey: 'page.tutorial.step_upload.desc' },
  { icon: FileText, labelKey: 'page.tutorial.step_edit.label', descKey: 'page.tutorial.step_edit.desc' },
  { icon: Users, labelKey: 'page.tutorial.step_panel.label', descKey: 'page.tutorial.step_panel.desc' },
]

// 示例数量必须来自后端 /api/examples（examples/ 目录的真实文件数），
// 写死数字的话改了 examples/ 目录这页就会撒谎。拿不到数量时退化成不含数字的说法，
// 不能给一个占位数假装知道。
// 这个函数在**渲染期**被调用（不是模块级常量），所以里面的 t() 每次重渲染都会
// 重新求值，切语言时这三张卡会跟着变。放到模块级去算就不会。
function buildUploadMethods(exampleCount: number | null) {
  const exampleLine =
    exampleCount === null
      ? t('page.tutorial.count.unknown')
      : t('page.tutorial.count.with_number', { count: exampleCount })
  return [
  {
    icon: Upload,
    title: t('page.tutorial.method_file.title'),
    desc: t('page.tutorial.method_file.desc'),
    details: [
      // 这里不能写 .doc：后端对它有专门的拒绝分支（api/__init__.py:622，
      // python-docx 解不了旧版 .doc），用户照着教程传 .doc 会直接撞报错。
      // 教程页把一个后端明确拒收的格式写成"支持"，是最不该出的错。
      // 口径对齐 CreateReviewPage 的 accept 属性。
      t('page.tutorial.method_file_formats.hint'),
      t('page.tutorial.method_file_autofill.hint'),
      t('page.tutorial.method_file_editable.hint'),
      t('page.tutorial.method_file_any_doc.hint'),
    ],
    highlight: true,
  },
  {
    icon: Sparkles,
    title: t('page.tutorial.method_example.title'),
    desc: t('page.tutorial.method_example.desc'),
    details: [
      exampleLine,
      t('page.tutorial.method_example_first_use.hint'),
    ],
    highlight: false,
  },
  {
    icon: FileText,
    title: t('page.tutorial.method_manual.title'),
    desc: t('page.tutorial.method_manual.desc'),
    details: [
      t('page.tutorial.method_manual_fields.hint'),
      t('page.tutorial.method_manual_when.hint'),
    ],
    highlight: false,
  },
  ]
}

// 表里的任务类型名与字段名是**目录数据**，不是本页文案：中文读 mock-data 的
// TASK_TYPES / TASK_MATERIALS，英文的事实源是后端目录 + catalog.* overlay
// （契约 D5/D6）。在这里 t() 一份等于给同一批字段名造第二套译名，
// 教程写的字段名和创建评审页表单里的字段名会对不上。
const taskTypeTable = TASK_TYPES.map((tt) => {
  const fields = TASK_MATERIALS[tt.id] ?? []
  const required = fields.filter((f) => f.required).map((f) => f.label)
  const optional = fields.filter((f) => !f.required).map((f) => f.label)
  return { name: tt.name, required, optional }
})

// 同样存 key 不存文案（理由见 steps）。color 是样式不是文案，留在这里。
const resultItems: { icon: LucideIcon; labelKey: PlainMessageKey; descKey: PlainMessageKey; color: string }[] = [
  { icon: ShieldCheck, labelKey: 'page.tutorial.result_risk.label', descKey: 'page.tutorial.result_risk.desc', color: 'text-brand-primary' },
  // 立场不是固定的四档。它由各任务类型自己定义（"加愿望单"/"值得推进"/"观望"…），
  // ReportPage 的 STANCE_PALETTE 就是因为无法穷举才改成按出现顺序配色的。
  // 原来写死的"支持/中立/怀疑/反对"在真实报告里基本不会原样出现。
  { icon: Users, labelKey: 'page.tutorial.result_stance.label', descKey: 'page.tutorial.result_stance.desc', color: 'text-cyan' },
  { icon: AlertTriangle, labelKey: 'page.tutorial.result_issues.label', descKey: 'page.tutorial.result_issues.desc', color: 'text-severity-warning' },
  { icon: Eye, labelKey: 'page.tutorial.result_persona.label', descKey: 'page.tutorial.result_persona.desc', color: 'text-text-primary' },
  { icon: BarChart3, labelKey: 'page.tutorial.result_calibration.label', descKey: 'page.tutorial.result_calibration.desc', color: 'text-text-secondary' },
]

export default function TutorialPage() {
  // useDocumentTitle 内部 useLocale()，本页借它一并订阅 ui_lang：
  // t() 是普通函数、不带响应性，切语言时必须有人触发重渲染。
  useDocumentTitle('page.tutorial.meta.title')
  // null 表示"数量未知"（加载中或接口失败），此时文案不出现数字。
  // 教程页不因为一个可选的计数而报错或阻塞，失败就静默降级。
  const [exampleCount, setExampleCount] = useState<number | null>(null)
  // 同样是"接口失败就不显示，不能编"：允许的扩展名必须来自
  // app/config.py 的真实白名单，写死一份示例扩展名的话后端一改配置这页就撒谎。
  const [uploadConfig, setUploadConfig] = useState<UploadConfig | null>(null)

  useEffect(() => {
    let alive = true
    fetchExamples()
      .then((list) => {
        if (alive) setExampleCount(list.length)
      })
      .catch(() => {
        if (alive) setExampleCount(null)
      })
    api
      .uploadConfig()
      .then((config) => {
        if (alive) setUploadConfig(config)
      })
      .catch(() => {
        if (alive) setUploadConfig(null)
      })
    return () => {
      alive = false
    }
  }, [])

  const uploadMethods = buildUploadMethods(exampleCount)

  return (
    <PageShell size="reading">
      <PageHeader
        title={t('page.tutorial.header.title')}
        subtitle={t('page.tutorial.header.subtitle')}
      />

      <div className="space-y-6">
        <SectionCard>
          <h2 className="text-lg font-semibold text-text-primary mb-1">
            {t('page.tutorial.flow.title')}
          </h2>
          <p className="text-sm text-text-secondary mb-6">
            {t('page.tutorial.flow.desc')}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {steps.map((s, i) => {
              const Icon = s.icon
              return (
                <div key={i} className="relative">
                  <div className="flex flex-col items-center text-center gap-3 p-4 rounded-lg bg-bg-secondary/30">
                    <div className="w-10 h-10 rounded-full bg-brand-primary/10 flex items-center justify-center">
                      <Icon className="w-5 h-5 text-brand-primary" strokeWidth={1.25} />
                    </div>
                    <div>
                      <div className="text-xs text-brand-primary font-mono mb-1">{t('page.tutorial.flow.step', { n: i + 1 })}</div>
                      <div className="text-sm font-medium text-text-primary">{t(s.labelKey)}</div>
                      <div className="text-xs text-text-secondary mt-1">{t(s.descKey)}</div>
                    </div>
                  </div>
                  {i < steps.length - 1 && (
                    <div className="hidden lg:flex absolute -right-2 top-1/2 -translate-y-1/2 z-10">
                      <ArrowRight className="w-4 h-4 text-brand-primary/50" strokeWidth={1.25} />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </SectionCard>

        <SectionCard>
          <h2 className="text-lg font-semibold text-text-primary mb-1">
            {t('page.tutorial.upload.title')}
          </h2>
          <p className="text-sm text-text-secondary mb-6">
            {t('page.tutorial.upload.desc')}
          </p>
          <div className="space-y-4">
            {uploadMethods.map((m, i) => {
              const Icon = m.icon
              return (
                <div key={i} className={`flex gap-4 p-4 rounded-lg ${m.highlight ? 'bg-brand-primary/5 border border-brand-primary/20' : 'bg-bg-secondary/30'}`}>
                  <div className={`w-10 h-10 shrink-0 rounded-lg flex items-center justify-center ${m.highlight ? 'bg-brand-primary/20' : 'bg-brand-primary/10'}`}>
                    <Icon className={`w-5 h-5 ${m.highlight ? 'text-brand-primary' : 'text-brand-primary/70'}`} strokeWidth={1.25} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-text-primary">
                      {m.title}
                      {m.highlight && <span className="ml-2 text-xs text-brand-primary">{t('page.tutorial.method.badge')}</span>}
                    </div>
                    <div className="text-sm text-text-secondary mt-0.5">{m.desc}</div>
                    {m.details && (
                      <ul className="mt-2 space-y-1">
                        {m.details.map((d, j) => (
                          <li key={j} className="text-xs text-text-secondary flex items-start gap-1.5">
                            <span className="text-brand-primary mt-0.5">•</span>
                            {d}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
          <div className="mt-4 flex items-start gap-2 p-3 rounded-lg bg-cyan/5 border border-cyan/20">
            <BrainCircuit className="w-4 h-4 text-cyan shrink-0 mt-0.5" strokeWidth={1.25} />
            <p className="text-xs text-text-secondary">
              {t('page.tutorial.upload.hint')}
            </p>
          </div>
        </SectionCard>

        <SectionCard>
          <h2 className="text-lg font-semibold text-text-primary mb-1">
            {t('page.tutorial.filetypes.title')}
          </h2>
          <p className="text-sm text-text-secondary mb-6">
            {t('page.tutorial.filetypes.desc')}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {([
              ['page.tutorial.filetype_gdd.title', 'page.tutorial.filetype_gdd.desc'],
              ['page.tutorial.filetype_devlog.title', 'page.tutorial.filetype_devlog.desc'],
              ['page.tutorial.filetype_store.title', 'page.tutorial.filetype_store.desc'],
              ['page.tutorial.filetype_crowdfunding.title', 'page.tutorial.filetype_crowdfunding.desc'],
              ['page.tutorial.filetype_community.title', 'page.tutorial.filetype_community.desc'],
              ['page.tutorial.filetype_localization.title', 'page.tutorial.filetype_localization.desc'],
            ] as [PlainMessageKey, PlainMessageKey][]).map(([titleKey, descKey]) => (
              <div key={titleKey} className="flex items-start gap-3 p-3 rounded-lg bg-bg-secondary/30">
                <FileText className="w-4 h-4 text-brand-primary shrink-0 mt-0.5" strokeWidth={1.25} />
                <div>
                  <div className="text-sm font-medium text-text-primary">{t(titleKey)}</div>
                  <div className="text-xs text-text-secondary mt-0.5">{t(descKey)}</div>
                </div>
              </div>
            ))}
          </div>
          {uploadConfig && (
            // 体积上限走 formatBytes：原来是 Math.round(bytes/1024/1024) + 写死的 "MB"，
            // 那个写法在英文界面上会出现中文数字格式，而且后端把上限调到 GB 级时会显示
            // "2048MB"。扩展名清单原样 join，它们是文件后缀不是文案。
            <p className="mt-4 text-xs text-text-secondary">
              {t('page.tutorial.limits.hint', {
                text_ext: uploadConfig.allowed_ext.join(' / '),
                text_max: formatBytes(uploadConfig.max_bytes),
                image_ext: uploadConfig.allowed_image_ext.join(' / '),
                image_max: formatBytes(uploadConfig.max_image_bytes),
              })}
            </p>
          )}
        </SectionCard>

        <SectionCard>
          <h2 className="text-lg font-semibold text-text-primary mb-1">
            {t('page.tutorial.materials.title')}
          </h2>
          <p className="text-sm text-text-secondary mb-6">
            {t('page.tutorial.materials.desc')}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-3 text-text-secondary font-medium">{t('page.tutorial.materials_task_type.label')}</th>
                  <th className="text-left py-3 px-3 text-text-secondary font-medium">{t('page.tutorial.materials_required.label')}</th>
                  <th className="text-left py-3 px-3 text-text-secondary font-medium">{t('page.tutorial.materials_optional.label')}</th>
                </tr>
              </thead>
              <tbody>
                {taskTypeTable.map((row, i) => (
                  <tr key={i} className="border-b border-border/50 hover:bg-bg-secondary/20 transition-colors">
                    <td className="py-3 px-3 text-text-primary font-medium whitespace-nowrap">{row.name}</td>
                    <td className="py-3 px-3">
                      <div className="flex flex-wrap gap-1">
                        {row.required.map((f) => (
                          <span key={f} className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-brand-primary/10 text-brand-primary">
                            {f}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <div className="flex flex-wrap gap-1">
                        {row.optional.map((f) => (
                          <span key={f} className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-bg-secondary/50 text-text-secondary">
                            {f}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>

        <SectionCard>
          <h2 className="text-lg font-semibold text-text-primary mb-1">
            {t('page.tutorial.results.title')}
          </h2>
          <p className="text-sm text-text-secondary mb-6">
            {t('page.tutorial.results.desc')}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {resultItems.map((item, i) => {
              const Icon = item.icon
              return (
                <div key={i} className="flex items-start gap-3 p-4 rounded-lg bg-bg-secondary/30">
                  <Icon className={`w-5 h-5 shrink-0 mt-0.5 ${item.color}`} strokeWidth={1.25} />
                  <div>
                    <div className="text-sm font-medium text-text-primary">{t(item.labelKey)}</div>
                    <div className="text-xs text-text-secondary mt-0.5">{t(item.descKey)}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </SectionCard>

        <div className="flex items-center justify-center py-4">
          <Link to="/review/new" className={PRIMARY_BUTTON_CLASS}>
            {t('page.tutorial.start.cta')}
            <ArrowRight className="w-4 h-4" strokeWidth={1.25} />
          </Link>
        </div>
      </div>
    </PageShell>
  )
}
