import React from 'react'
import UploadPage from './pages/UploadPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import ResultsPage from './pages/ResultsPage.jsx'

// MVP navigation: Upload -> Dashboard (polls pipeline) -> Results (issues drill-down)
export default function App() {
  const [route, setRoute] = React.useState('upload')
  const [bidId, setBidId] = React.useState('')

  if (route === 'dashboard') return <DashboardPage bidId={bidId} onDone={() => setRoute('results')} />
  if (route === 'results') return <ResultsPage bidId={bidId} onReset={() => setRoute('upload')} />
  return <UploadPage onSubmitted={(id) => { setBidId(id); setRoute('dashboard') }} />
}