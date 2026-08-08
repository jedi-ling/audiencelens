import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { TASK_MATERIALS, TASK_TYPES } from '@/lib/mock-data'
import { fetchExamples } from '@/lib/api'
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

const steps = [
  { icon: ListChecks, label: '选择任务类型', desc: '根据评审目标选择对应的任务类型' },
  { icon: Upload, label: '上传文件', desc: '上传任意文档，AI 自动提取结构化材料' },
  { icon: FileText, label: '编辑材料', desc: '检查 AI 提取结果，手动修改补充' },
  { icon: Users, label: '选择角色并启动', desc: '选择角色包，启动评审查看报告' },
]

// 示例数量必须来自后端 /api/examples（examples/ 目录的真实文件数），
// 写死数字的话改了 examples/ 目录这页就会撒谎。拿不到数量时退化成不含数字的说法，
// 不能给一个占位数假装知道。
function buildUploadMethods(exampleCount: number | null) {
  const exampleLine =
    exampleCount === null
      ? '预设示例覆盖多种任务类型'
      : `${exampleCount} 个预设示例覆盖多种任务类型`
  return [
  {
    icon: Upload,
    title: '文件上传（推荐）',
    desc: '上传任意文档，AI 自动阅读并提取结构化材料',
    details: [
      // 这里不能写 .doc：后端对它有专门的拒绝分支（api/__init__.py:622，
      // python-docx 解不了旧版 .doc），用户照着教程传 .doc 会直接撞报错。
      // 教程页把一个后端明确拒收的格式写成"支持"，是最不该出的错。
      // 口径对齐 CreateReviewPage 的 accept 属性。
      '支持 .txt .md .json .pdf .docx（旧版 .doc 需先另存为 .docx）',
      'AI 阅读文档后自动填充所有字段',
      '提取完成后可手动修改每个字段',
      'GDD、设计文档、开发日志等均可直接上传',
    ],
    highlight: true,
  },
  {
    icon: Sparkles,
    title: '示例导入',
    desc: '一键导入预设示例数据，快速体验评审流程',
    details: [
      exampleLine,
      '适合首次使用时了解系统功能',
    ],
    highlight: false,
  },
  {
    icon: FileText,
    title: '手动填写',
    desc: '根据任务类型自动生成结构化表单，逐项填写',
    details: [
      '每个任务类型有专属的必填/选填字段',
      '适合材料较少或需要精确控制内容的场景',
    ],
    highlight: false,
  },
  ]
}

const taskTypeTable = TASK_TYPES.map((tt) => {
  const fields = TASK_MATERIALS[tt.id] ?? []
  const required = fields.filter((f) => f.required).map((f) => f.label)
  const optional = fields.filter((f) => !f.required).map((f) => f.label)
  return { name: tt.name, required, optional }
})

const resultItems = [
  { icon: ShieldCheck, label: '风险等级', desc: '绿/黄/橙/红 四级风险评估', color: 'text-brand-primary' },
  // 立场不是固定的四档。它由各任务类型自己定义（"加愿望单"/"值得推进"/"观望"…），
  // ReportPage 的 STANCE_PALETTE 就是因为无法穷举才改成按出现顺序配色的。
  // 原来写死的"支持/中立/怀疑/反对"在真实报告里基本不会原样出现。
  { icon: Users, label: '立场分布', desc: '各角色的立场取向（具体档位由任务类型决定）', color: 'text-cyan' },
  { icon: AlertTriangle, label: '优先问题列表', desc: '按严重程度排序的关键问题', color: 'text-severity-warning' },
  { icon: Eye, label: '每个角色的详细视角', desc: '各角色的独立评审观点', color: 'text-text-primary' },
  { icon: BarChart3, label: '校准指标', desc: '一致性、覆盖率、幻觉率等质量指标', color: 'text-text-secondary' },
]

export default function TutorialPage() {
  // null 表示"数量未知"（加载中或接口失败），此时文案不出现数字。
  // 教程页不因为一个可选的计数而报错或阻塞，失败就静默降级。
  const [exampleCount, setExampleCount] = useState<number | null>(null)

  useEffect(() => {
    let alive = true
    fetchExamples()
      .then((list) => {
        if (alive) setExampleCount(list.length)
      })
      .catch(() => {
        if (alive) setExampleCount(null)
      })
    return () => {
      alive = false
    }
  }, [])

  const uploadMethods = buildUploadMethods(exampleCount)

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 animate-fade-in">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary font-display">
          使用教程
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          了解 AudienceLens 评审系统的完整流程与材料要求
        </p>
      </div>

      <div className="space-y-6">
        <section className="rounded-xl border border-border bg-bg-card p-6">
          <h2 className="text-xl font-semibold text-text-primary mb-1">
            评审流程总览
          </h2>
          <p className="text-sm text-text-secondary mb-6">
            上传文件 → AI 提取 → 编辑确认 → 启动评审
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
                      <div className="text-xs text-brand-primary font-mono mb-1">Step {i + 1}</div>
                      <div className="text-sm font-medium text-text-primary">{s.label}</div>
                      <div className="text-xs text-text-secondary mt-1">{s.desc}</div>
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
        </section>

        <section className="rounded-xl border border-border bg-bg-card p-6">
          <h2 className="text-xl font-semibold text-text-primary mb-1">
            上传文件，AI 自动提取
          </h2>
          <p className="text-sm text-text-secondary mb-6">
            核心流程：上传文档 → AI 阅读提取 → 你来编辑确认
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
                      {m.highlight && <span className="ml-2 text-xs text-brand-primary">推荐</span>}
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
              AI 提取完成后，所有字段均可手动修改。你可以补充 AI 遗漏的信息、修正不准确的内容、或添加额外说明。最终提交的内容以你的编辑为准。
            </p>
          </div>
        </section>

        <section className="rounded-xl border border-border bg-bg-card p-6">
          <h2 className="text-xl font-semibold text-text-primary mb-1">
            适合上传的文件类型
          </h2>
          <p className="text-sm text-text-secondary mb-6">
            任何包含游戏相关信息的文档都可以上传
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              { title: '游戏设计文档 (GDD)', desc: '包含核心循环、系统设计、角色设定等' },
              { title: '开发日志 / 更新说明', desc: '版本更新内容、开发进度、路线图' },
              { title: 'Steam / 商店页文案', desc: '游戏描述、标签、截图说明、定价信息' },
              { title: '众筹页面内容', desc: '项目介绍、回报层级、团队信息' },
              { title: '社区运营文档', desc: 'Discord 频道规划、社区策略、活动计划' },
              { title: '本地化翻译文件', desc: '翻译样本、文化适配说明、UI 适配问题' },
            ].map((item, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-bg-secondary/30">
                <FileText className="w-4 h-4 text-brand-primary shrink-0 mt-0.5" strokeWidth={1.25} />
                <div>
                  <div className="text-sm font-medium text-text-primary">{item.title}</div>
                  <div className="text-xs text-text-secondary mt-0.5">{item.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-border bg-bg-card p-6">
          <h2 className="text-xl font-semibold text-text-primary mb-1">
            任务类型材料需求
          </h2>
          <p className="text-sm text-text-secondary mb-6">
            AI 会根据任务类型自动提取对应字段，你也可以手动补充
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-3 text-text-secondary font-medium">任务类型</th>
                  <th className="text-left py-3 px-3 text-text-secondary font-medium">必填字段</th>
                  <th className="text-left py-3 px-3 text-text-secondary font-medium">选填字段</th>
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
        </section>

        <section className="rounded-xl border border-border bg-bg-card p-6">
          <h2 className="text-xl font-semibold text-text-primary mb-1">
            评审结果说明
          </h2>
          <p className="text-sm text-text-secondary mb-6">
            评审报告包含以下核心内容
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {resultItems.map((item, i) => {
              const Icon = item.icon
              return (
                <div key={i} className="flex items-start gap-3 p-4 rounded-lg bg-bg-secondary/30">
                  <Icon className={`w-5 h-5 shrink-0 mt-0.5 ${item.color}`} strokeWidth={1.25} />
                  <div>
                    <div className="text-sm font-medium text-text-primary">{item.label}</div>
                    <div className="text-xs text-text-secondary mt-0.5">{item.desc}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </section>

        <div className="flex items-center justify-center py-4">
          <Link
            to="/review/new"
            className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-brand-primary text-white font-medium hover:bg-brand-primary-dim glow-green transition-all"
          >
            开始创建评审
            <ArrowRight className="w-4 h-4" strokeWidth={1.25} />
          </Link>
        </div>
      </div>
    </div>
  )
}
