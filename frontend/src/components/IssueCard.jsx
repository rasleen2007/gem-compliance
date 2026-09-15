// One discrepancy row: severity, summary, expandable evidence from RuleResult.

import React from 'react'
import StatusBadge from './StatusBadge.jsx'

export default function IssueCard({ issue }) {
  const [open, setOpen] = React.useState(false)

  return (
    <div onClick={() => setOpen(!open)}>
      <StatusBadge status={issue.status} /> {issue.severity} — {issue.summary}
      {open && issue.evidence && <blockquote>{issue.evidence}</blockquote>}
    </div>
  )
}