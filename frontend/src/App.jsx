import React from 'react'
import UploadPage from './pages/UploadPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import ResultsPage from './pages/ResultsPage.jsx'
import RulesManagementPage from './pages/RulesManagementPage.jsx'
import AboutPage from './pages/AboutPage.jsx'

const NAV_ITEMS = [
  { key: 'about', label: 'System Specs', icon: '◈' },
  { key: 'upload', label: 'Verify New Bid', icon: '⇪' },
  { key: 'rules', label: 'Rules Matrix', icon: '☷' },
]

// App shell: state-driven SPA routing (about landing -> upload -> dashboard ->
// results) plus the persistent master header so judges can jump between the
// admin views. The app boots directly onto the About (landing) view.
export default function App() {
  const [route, setRoute] = React.useState('about')
  const [bidId, setBidId] = React.useState('')

  const navigate = (next) => {
    if (next === route) return
    setRoute(next)
    window.scrollTo({ top: 0 })
  }

  let page
  if (route === 'dashboard') {
    page = <DashboardPage bidId={bidId} onDone={() => setRoute('results')} />
  } else if (route === 'results') {
    page = <ResultsPage bidId={bidId} onReset={() => setRoute('upload')} />
  } else if (route === 'rules') {
    page = <RulesManagementPage />
  } else if (route === 'upload') {
    page = (
      <UploadPage
        onSubmitted={(id) => {
          setBidId(id)
          setRoute('dashboard')
        }}
      />
    )
  } else {
    page = <AboutPage />
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-inner">
          <button type="button" className="app-brand" onClick={() => navigate('about')}>
            <span className="app-brand-mark">◆</span>
            <span className="app-brand-text">
              <strong>GeM Bid Compliance</strong>
              <small>Verification Console</small>
            </span>
          </button>

          <nav className="app-nav" aria-label="Primary">
            {NAV_ITEMS.map((item) => (
              <button
                type="button"
                key={item.key}
                className={`app-nav-link ${route === item.key ? 'app-nav-active' : ''}`}
                onClick={() => navigate(item.key)}
              >
                <span className="app-nav-icon" aria-hidden="true">{item.icon}</span>
                {item.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="app-main">{page}</main>
    </div>
  )
}