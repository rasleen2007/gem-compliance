// Colored status pill: COMPLIANT/DISCREPANT/NEEDS_REVIEW/IN_PROGRESS and pass/fail/warn/skip/error.

const COLORS = {
  COMPLIANT: 'green', DISCREPANT: 'red', NEEDS_REVIEW: 'amber', IN_PROGRESS: 'blue',
  pass: 'green', fail: 'red', warn: 'amber', skip: 'gray', error: 'red'
}

export default function StatusBadge({ status }) {
  return <span style={{ color: COLORS[status] || 'gray' }}>{status}</span>
}