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

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
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
