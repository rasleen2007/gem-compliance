// Light-mode status pill — Uiverse-style high-contrast tag.
// COMPLIANT: crisp emerald pill with a clean glowing outline text effect.
// DISCREPANT: high-visibility crimson pill with a soft light-red aura.
// See index.css for the .badge-* accent tones.

const TONES = {
  COMPLIANT: 'compliant',
  DISCREPANT: 'discrepant',
  NEEDS_REVIEW: 'review',
  IN_PROGRESS: 'progress',
  PASS: 'pass',
  FAIL: 'fail',
  WARN: 'warn',
  SKIP: 'skip',
  ERROR: 'error',
  FAILED: 'error',
}

export default function StatusBadge({ status }) {
  const key = String(status ?? '').toUpperCase()
  const tone = TONES[key] || 'skip'
  return <span className={`status-badge badge-${tone}`}>{status}</span>
}