// Dashboard page (contract 6): polls GET /dashboard/{bid_id} while the bid is
// IN_PROGRESS, then renders the top-metric score row, category compliance
// breakdown, per-document stage statuses, and the severity-sorted issues
// table with expandable evidence (page/bbox/raw text via source_span).

import React from 'react'
import { getDashboard, poll } from '../api/client.js'
import StatusBadge from '../components/StatusBadge.jsx'
import IssueCard from '../components/IssueCard.jsx'
import PipelineTimeline from '../components/PipelineTimeline.jsx'

const PROJECT_STAGES = ['ocr', 'nlp', 'validation']

function isTerminal(d) {
  return !d || d.status !== 'IN_PROGRESS'
}

export default function DashboardPage({ bidId, onDone }) {
  const [envelope, setEnvelope] = React.useState(null)
  const [error, setError] = React.useState(null)

  React.useEffect(() => {
    let cancelled = false
    setEnvelope(null)
    setError(null)

    ;(async () => {
      try {
        const d = await poll(
          () => getDashboard(bidId),
          isTerminal,
          { intervalMs: 2000, maxTries: 90 },
        )
        if (!cancelled) {
          setEnvelope(d)
          if (onDone) onDone(d)
        }
      } catch (err) {
        if (!cancelled) setError(err.message)
      }
    })()

    return () => { cancelled = true }
  }, [bidId])

  if (error) {
    return (
      <div className="app-page">
        <header className="page-heading">
          <h1>Compliance Dashboard</h1>
          <p role="alert">Failed to load dashboard: {error}</p>
        </header>
        <StatusBadge status="error" />
      </div>
    )
  }

  if (!envelope) {
    return (
      <div className="app-page">
        <header className="page-heading">
          <h1>Compliance Dashboard</h1>
          <p aria-live="polite">Pipeline in progress — polling…</p>
        </header>
        <StatusBadge status="IN_PROGRESS" />
      </div>
    )
  }

  const { score = {}, issues = [], documents = [], category_breakdown: breakdown = [] } = envelope

  return (
    <div className="app-page">
      <header className="page-heading">
        <span className="page-sub">
          {envelope.tender_id} / {envelope.bid_id} — {envelope.supplier}
        </span>
        <h1 style={{ marginTop: 2 }}>Compliance Dashboard</h1>
        <p className="page-sub" style={{ marginTop: 8 }}>Verification result: <StatusBadge status={envelope.status} /></p>
      </header>

      {/* --- top metrics row ------------------------------------------------- */}
      <div className="metric-row">
        <div className="metric">
          <span className="metric-label">Overall Status</span>
          <strong>{envelope.status}</strong>
        </div>
        <div className="metric">
          <span className="metric-label">Compliance Score</span>
          <strong>{score.compliance_pct ?? 0}%</strong>
        </div>
        <div className="metric">
          <span className="metric-label">Rules Evaluated</span>
          <strong>{score.total ?? 0}</strong>
        </div>
        <div className="metric">
          <span className="metric-label">Pass/Fail</span>
          <strong>{score.pass ?? 0} / {score.fail ?? 0}</strong>
        </div>
      </div>

      {/* --- pipeline timeline (OCR -> LAYOUT -> NLP -> VALIDATION) --------- */}
      <PipelineTimeline envelope={envelope} />

      {/* --- category breakdown --------------------------------------------- */}
      <section className="dash-section">
      <h3>Category Breakdown</h3>
      {breakdown.length === 0 ? (
        <p>No rules evaluated yet.</p>
      ) : (
        <table aria-label="Category compliance breakdown">
          <thead>
            <tr><th>Category</th><th>Pass</th><th>Fail</th><th>Warn</th><th>Total</th><th>Compliance</th></tr>
          </thead>
          <tbody>
            {breakdown.map((cat) => (
              <tr key={cat.category}>
                <td>{cat.category}</td>
                <td>{cat.pass ?? 0}</td>
                <td>{cat.fail ?? 0}</td>
                <td>{cat.warn ?? 0}</td>
                <td>{cat.total ?? 0}</td>
                <td>
                  {cat.total ? `${Math.round(((cat.pass ?? 0) / cat.total) * 100)}%` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      </section>

      {/* --- document states ------------------------------------------------- */}
      <section className="dash-section">
      <h3>Documents</h3>
      {documents.length === 0 ? (
        <p>No documents tracked.</p>
      ) : (
        <ul className="file-list">
          {documents.map((doc) => (
            <li className="file-row" key={doc.file_id}>
              <span className="file-meta">
                <strong>{doc.file_name || doc.file_id}</strong>
                <small>{doc.doc_role || 'document'}</small>
              </span>
              <StatusBadge status={doc.status} />
            </li>
          ))}
        </ul>
      )}
      </section>

      {/* --- issues table (evidence drill-down) ------------------------------ */}
      <section className="dash-section">
      <h3>Compliance Issues</h3>
      {issues.length === 0 ? (
        <p>No compliance issues found — all rules passed.</p>
      ) : (
        <div className="stack-issues">
          {issues.map((issue) => <IssueCard key={issue.rule_id} issue={issue} />)}
        </div>
      )}
      </section>
    </div>
  )
}
