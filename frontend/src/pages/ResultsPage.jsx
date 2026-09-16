// Results page: discrepancy list with evidence drill-down + adjudication.

import React from 'react'
import IssueCard from '../components/IssueCard.jsx'
import { getDashboard } from '../api/client.js'

export default function ResultsPage({ bidId, onReset }) {
  const [issues, setIssues] = React.useState([])

  React.useEffect(() => {
    getDashboard(bidId).then((res) => setIssues(res.data?.data?.issues ?? []))
  }, [bidId])

  return (
    <div className="app-page">
      <header className="page-heading">
        <h1>Compliance Review</h1>
        <p>{issues.length} issue{issues.length !== 1 ? 's' : ''} flagged — click any row to expand evidence.</p>
      </header>

      {issues.length === 0 ? (
        <p>No compliance issues found — all rules passed.</p>
      ) : (
        <div className="stack-issues">
          {issues.map((it) => <IssueCard key={it.rule_id} issue={it} />)}
        </div>
      )}

      <div className="form-actions" style={{ marginTop: 24 }}>
        <button type="button" className="btn-primary" onClick={onReset}>
          Verify New Bid
        </button>
      </div>
    </div>
  )
}