// Light-mode status pill — flat corporate accent tag.
// COMPLIANT: emerald text on a light-green strip with a sharp border.
// DISCREPANT/FAILED: dark-crimson text on a clean light-red banner.
// See index.css for the .badge-* accent tones (no glow, no neon).

const TONES = {
  COMPLIANT: 'compliant',
  DISCREPANT: 'discrepant',
  NEEDS_REVIEW: 'review',
  IN_PROGRESS: 'progress',
  RUNNING: 'progress',
  PASS: 'pass',
  VALIDATED: 'pass',
  OK: 'pass',
  FAIL: 'fail',
  FAILED: 'error',
  ERROR: 'error',
  WARN: 'warn',
  SKIP: 'skip',
  PARSED: 'progress',
  DONE: 'pass',
}

export default function StatusBadge({ status }) {
  const key = String(status ?? '').toUpperCase()
  const tone = TONES[key] || 'skip'
  return <span className={`status-badge badge-${tone}`}>{status}</span>
}