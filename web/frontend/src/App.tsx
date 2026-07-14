import { BrowserRouter, Routes, Route } from 'react-router'
import Layout from '@/components/Layout'
import HomePage from '@/pages/HomePage'
import CreateReviewPage from '@/pages/CreateReviewPage'
import ReviewProgressPage from '@/pages/ReviewProgressPage'
import ReportPage from '@/pages/ReportPage'
import PersonasPage from '@/pages/PersonasPage'
import TaskTypesPage from '@/pages/TaskTypesPage'
import TutorialPage from '@/pages/TutorialPage'
import SettingsPage from '@/pages/SettingsPage'
import PrivacyPage from '@/pages/PrivacyPage'
import SkillSelectPage from '@/pages/SkillSelectPage'
import EvaluationPage from '@/pages/EvaluationPage'
import AskPage from '@/pages/AskPage'
import LedgerPage from '@/pages/LedgerPage'

export default function App() {
  return (
    <BrowserRouter>
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
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
