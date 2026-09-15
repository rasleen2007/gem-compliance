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
      <section>
        <h2>Compliance Dashboard</h2>
        <p role="alert">Failed to load dashboard: {error}</p>
        <StatusBadge status="error" />
      </section>
    )
  }

  if (!envelope) {
    return (
      <section>
        <h2>Compliance Dashboard</h2>
        <p aria-live="polite">Pipeline in progress — polling…</p>
        <StatusBadge status="IN_PROGRESS" />
      </section>
    )
  }

  const { score = {}, issues = [], documents = [], category_breakdown: breakdown = [] } = envelope

  return (
    <section>
      <header>
        <h2>Compliance Dashboard</h2>
        <span>
          {envelope.tender_id} / {envelope.bid_id} — {envelope.supplier}
        </span>
        <StatusBadge status={envelope.status} />
      </header>

      {/* --- top metrics row ------------------------------------------------- */}
      <div className="metric-row" style={{ display: 'flex', gap: 16 }}>
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

      {/* --- document states ------------------------------------------------- */}
      <h3>Documents</h3>
      {documents.length === 0 ? (
        <p>No documents tracked.</p>
      ) : (
        <ul>
          {documents.map((doc) => (
            <li key={doc.file_id}>
              <span>{doc.file_name || doc.file_id}</span> —{' '}
              <StatusBadge status={doc.stage} /> <StatusBadge status={doc.status} />
            </li>
          ))}
        </ul>
      )}

      {/* --- issues table (evidence drill-down) ------------------------------ */}
      <h3>Compliance Issues</h3>
      {issues.length === 0 ? (
        <p>No compliance issues found — all rules passed.</p>
      ) : (
        <div>
          {issues.map((issue) => <IssueCard key={issue.rule_id} issue={issue} />)}
        </div>
      )}
    </section>
  )
}
