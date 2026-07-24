import { BrowserRouter, Routes, Route, Navigate } from 'react-router'
import { Component, lazy, Suspense, type ReactNode } from 'react'
import Layout from '@/components/Layout'

const LandingPage = lazy(() => import('@/pages/landing/LandingPage'))
const CreateReviewPage = lazy(() => import('@/pages/CreateReviewPage'))
const ReviewProgressPage = lazy(() => import('@/pages/ReviewProgressPage'))
const ReportPage = lazy(() => import('@/pages/ReportPage'))
const PersonasPage = lazy(() => import('@/pages/PersonasPage'))
const TaskTypesPage = lazy(() => import('@/pages/TaskTypesPage'))
const TutorialPage = lazy(() => import('@/pages/TutorialPage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const PrivacyPage = lazy(() => import('@/pages/PrivacyPage'))
const ForgotPasswordPage = lazy(() => import('@/pages/ForgotPasswordPage'))
const ResetPasswordPage = lazy(() => import('@/pages/ResetPasswordPage'))
const VerifyEmailPage = lazy(() => import('@/pages/VerifyEmailPage'))
const SkillSelectPage = lazy(() => import('@/pages/SkillSelectPage'))
const EvaluationPage = lazy(() => import('@/pages/EvaluationPage'))
const AskPage = lazy(() => import('@/pages/AskPage'))
const LedgerPage = lazy(() => import('@/pages/LedgerPage'))
const ReviewHistoryPage = lazy(() => import('@/pages/ReviewHistoryPage'))
const LoginPage = lazy(() => import('@/pages/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/RegisterPage'))

/** Suspense 不捕获加载错误——发版后旧 chunk 404 会直接白屏，必须有边界兜底。 */
class ChunkErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-bg-primary text-text-secondary">
          <p className="text-sm">页面加载失败——可能是刚发布了新版本。</p>
          <button
            onClick={() => window.location.reload()}
            className="rounded-lg border border-neon-green/30 bg-neon-green/10 px-4 py-2 text-sm text-neon-green transition-all hover:bg-neon-green/20"
          >
            刷新页面
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  return (
    <BrowserRouter>
      <ChunkErrorBoundary>
      <Suspense fallback={<PageLoading />}>
        <Routes>
          <Route element={<Layout />}>
            {/* 营销落地页作为首页，与 app 共用同一套导航/页脚（一套导航全站通用） */}
            <Route path="/" element={<LandingPage />} />
            {/* 对话式入口：大白话 → 意图解析 → 发起评审 */}
            <Route path="/ask" element={<AskPage />} />
            {/* 判断复利闭环：预测留档 + 回填验证 + 命中率 */}
            <Route path="/ledger" element={<LedgerPage />} />
            {/* 评审历史列表——/api/reviews 现已按身份过滤，见后端 _check_review_owner */}
            <Route path="/history" element={<ReviewHistoryPage />} />
            <Route path="/review/new" element={<CreateReviewPage />} />
            <Route path="/review/:id" element={<ReviewProgressPage />} />
            <Route path="/review/:id/report" element={<ReportPage />} />
            <Route path="/personas" element={<PersonasPage />} />
            <Route path="/task-types" element={<TaskTypesPage />} />
            <Route path="/tutorial" element={<TutorialPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/verify-email" element={<VerifyEmailPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
            <Route path="/skills" element={<SkillSelectPage />} />
            <Route path="/evaluations/:id" element={<EvaluationPage />} />
            {/* 未知路径统一回首页——此前完全没有兜底，/home 下线后验证出这个空白页问题 */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Suspense>
      </ChunkErrorBoundary>
    </BrowserRouter>
  )
}

function PageLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-primary text-sm text-text-secondary">
      正在加载…
    </div>
  )
}
