// One discrepancy row: severity, summary, expandable evidence from RuleResult.

import React from 'react'
import StatusBadge from './StatusBadge.jsx'

export default function IssueCard({ issue }) {
  const [open, setOpen] = React.useState(false)

  return (
    <article
      className="issue-item"
      onClick={() => setOpen(!open)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          setOpen(!open)
        }
      }}
    >
      <div className="issue-item-head">
        <StatusBadge status={issue.status} />
        <span className="issue-sev">{issue.severity}</span>
        <span className="issue-rule">{issue.rule_id}</span>
        <span className="issue-chevron" aria-hidden="true">{open ? '−' : '+'}</span>
      </div>
      <p className="issue-summary">{issue.summary}</p>
      {open && issue.evidence && (
        <blockquote className="issue-evidence">{issue.evidence}</blockquote>
      )}
    </article>
  )
}