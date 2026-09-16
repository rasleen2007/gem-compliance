// PipelineTimeline — visual stage tracker for contract 6.
// Renders the documented pipeline stages (upload -> OCR -> LAYOUT -> NLP ->
// VALIDATION) in order, with a flat color-coded band per stage state and the
// runtime/status/message from the matching pipeline event. Stages without a
// recorded event are shown as `pending` until one arrives.

import React from 'react'
import StatusBadge from './StatusBadge.jsx'

// Contract-6 stage keys -> canonical display order + label.
const STAGE_ORDER = [
  { key: 'upload', label: 'Upload' },
  { key: 'ocr', label: 'OCR' },
  { key: 'layout', label: 'Layout' },
  { key: 'nlp', label: 'NLP' },
  { key: 'validation', label: 'Validation' },
]

// Pipeline event stage -> the canonical keys it satisfies. The orchestrator
// emits OCR/"layout" work inside the `ocr` event, so we map it onto both the
// OCR and LAYOUT slots.
const EVENT_TO_STAGE = {
  upload: 'upload',
  ocr: 'ocr',
  layout: 'layout',
  nlp: 'nlp',
  validation: 'validation',
  adjudication: 'validation',
}

function normalizeEvent(event) {
  return {
    status: event?.status ?? 'pending',
    ts: event?.ts ?? null,
    runtime_ms: event?.runtime_ms ?? null,
    message: event?.message ?? '',
  }
}

export default function PipelineTimeline({ envelope }) {
  const timeline = React.useMemo(() => {
    const events = envelope?.timeline ?? []
    const byStage = {}
    for (const ev of events) {
      const key = EVENT_TO_STAGE[ev?.stage]
      if (!key) continue
      byStage[key] = normalizeEvent(ev)
    }
    return STAGE_ORDER.map((s) => ({ ...s, ...byStage[s.key] ?? normalizeEvent(null) }))
  }, [envelope])

  const running = timeline.find((s) => s.status === 'running')

  return (
    <div className="pipeline-timeline" aria-label="Pipeline stage timeline">
      <ol>
        {timeline.map((stage) => (
          <li key={stage.key}>
            <div className={`pt-card pt-${stage.status}`}>
              <div className="pt-head">
                <span className="pt-label">{stage.label}</span>
                <StatusBadge status={stage.status} />
              </div>
              {stage.runtime_ms != null && (
                <div className="pt-meta">{stage.runtime_ms} ms</div>
              )}
              {stage.message && <div className="pt-meta">{stage.message}</div>}
            </div>
          </li>
        ))}
      </ol>
      <p className="pt-status-line" aria-live="polite">
        {running ? `${running.label} in progress…` : 'All tracked stages complete.'}
      </p>
    </div>
  )
}