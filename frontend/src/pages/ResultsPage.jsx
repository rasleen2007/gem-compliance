// Results page: discrepancy list with evidence drill-down + adjudication.
// TODO Phase P2: render data.issues severity-sorted with expandable evidence
// (page/bbox/raw text via source_span), and persist adjudication decision.

import React from 'react'
import IssueCard from '../components/IssueCard.jsx'
import { getDashboard } from '../api/client.js'

export default function ResultsPage({ bidId, onReset }) {
  const [issues, setIssues] = React.useState([])

  React.useEffect(() => {
    getDashboard(bidId).then((res) => setIssues(res.data.data.issues ?? []))
  }, [bidId])

  return (
    <section>
      <h2>Compliance Review</h2>
      {issues.map((it) => <IssueCard key={it.rule_id} issue={it} />)}
      <button onClick={onReset}>New bid</button>
    </section>
  )
}