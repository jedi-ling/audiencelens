import { BrowserRouter, Routes, Route } from 'react-router'
import { lazy, Suspense } from 'react'
import Layout from '@/components/Layout'

const HomePage = lazy(() => import('@/pages/HomePage'))
const CreateReviewPage = lazy(() => import('@/pages/CreateReviewPage'))
const ReviewProgressPage = lazy(() => import('@/pages/ReviewProgressPage'))
const ReportPage = lazy(() => import('@/pages/ReportPage'))
const PersonasPage = lazy(() => import('@/pages/PersonasPage'))
const TaskTypesPage = lazy(() => import('@/pages/TaskTypesPage'))
const TutorialPage = lazy(() => import('@/pages/TutorialPage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const PrivacyPage = lazy(() => import('@/pages/PrivacyPage'))
const SkillSelectPage = lazy(() => import('@/pages/SkillSelectPage'))
const EvaluationPage = lazy(() => import('@/pages/EvaluationPage'))
const AskPage = lazy(() => import('@/pages/AskPage'))
const LedgerPage = lazy(() => import('@/pages/LedgerPage'))
const AdminPage = lazy(() => import('@/pages/AdminPage'))

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoading />}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<HomePage />} />
            {/* 对话式入口：大白话 → 意图解析 → 发起评审 */}
            <Route path="/ask" element={<AskPage />} />
            {/* 判断复利闭环：预测留档 + 回填验证 + 命中率 */}
            <Route path="/ledger" element={<LedgerPage />} />
            <Route path="/review/new" element={<CreateReviewPage />} />
            <Route path="/review/:id" element={<ReviewProgressPage />} />
            <Route path="/review/:id/report" element={<ReportPage />} />
            <Route path="/personas" element={<PersonasPage />} />
            <Route path="/task-types" element={<TaskTypesPage />} />
            <Route path="/tutorial" element={<TutorialPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
            <Route path="/skills" element={<SkillSelectPage />} />
            <Route path="/evaluations/:id" element={<EvaluationPage />} />
            {/* 管理后台：运行时配置 + 平台 API Key + 系统概览/巡检，需 X-Admin-Token */}
            <Route path="/admin" element={<AdminPage />} />
          </Route>
        </Routes>
      </Suspense>
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
