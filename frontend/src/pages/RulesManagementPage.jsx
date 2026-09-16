// Rules Management — "Tender Verification Rules Matrix" admin panel.
// Fetches the active rule pack from GET /rules and renders each contract-4 rule
// as a crisp light-theme row (ID, title, severity, target, expected value) with
// a decorative toggle that simulates how administrators can activate/deactivate
// rule behaviour for future tenders without rewriting engine code.

import React from 'react'
import { getRules } from '../api/client.js'

const SEVERITY = {
  blocking: { label: 'Blocking', cls: 'rule-sev-blocking' },
  mandatory: { label: 'Mandatory', cls: 'rule-sev-mandatory' },
  advisory: { label: 'Advisory', cls: 'rule-sev-advisory' },
}

const FAMILY_ORDER = { EMD: 0, Eligibility: 1, Certificates: 2, Financial: 3, 'Cross-Check': 4 }

function describeExpected(rule) {
  const target = rule.target || '—'
  const opMap = {
    '>=': '≥', '<=': '≤', '==': '=', '!=': '≠', '>': '>', '<': '<',
    contains: 'contains', exists: 'exists', not_exists: 'absent', regex: 'matches',
    date_after: 'after', date_before: 'before', cross_check: 'across docs', llm_judge: 'judged',
  }
  const op = opMap[rule.operator] || rule.operator
  const val = rule.expected_value ?? ''
  return val === '' ? `${target} · ${op}` : `${target} · ${op} ${val}`
}

export default function RulesManagementPage() {
  const [rules, setRules] = React.useState(null)
  const [active, setActive] = React.useState({}) // toggled state, simulated
  const [error, setError] = React.useState(null)

  React.useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await getRules()
        const loaded = res.data?.data?.rules ?? []
        if (cancelled) return
        setRules(loaded)
        setActive(Object.fromEntries(loaded.map((r) => [r.rule_id, r.enabled !== 0])))
      } catch (e) {
        if (!cancelled) setError(e.message || 'Could not load the rule pack')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const counts = React.useMemo(() => {
    const c = { blocking: 0, mandatory: 0, advisory: 0, active: 0 }
    for (const r of rules || []) {
      c[r.severity] = (c[r.severity] || 0) + 1
      if (active[r.rule_id]) c.active += 1
    }
    return c
  }, [rules, active])

  const grouped = React.useMemo(() => {
    const g = {}
    for (const r of rules || []) {
      const key = FAMILY_ORDER[r.category] != null ? r.category : 'Other'
      ;(g[key] ||= []).push(r)
    }
    return Object.entries(g)
  }, [rules])

  return (
    <div className="app-page rules-page">
      <header className="page-heading rules-heading">
        <span className="rules-eyebrow">Administrative Console</span>
        <h1>Tender Verification Rules Matrix</h1>
        <p>
          The live rule pack driving automated compliance checks — 13 rules across five families,
          editable per-tender without touching engine code.
        </p>
      </header>

      <div className="rules-metrics metric-row">
        <div className="metric">
          <span className="metric-label">Rules</span>
          <strong>{rules ? rules.length : '…'}</strong>
        </div>
        <div className="metric">
          <span className="metric-label">Blocking</span>
          <strong>{counts.blocking}</strong>
        </div>
        <div className="metric">
          <span className="metric-label">Mandatory</span>
          <strong>{counts.mandatory}</strong>
        </div>
        <div className="metric">
          <span className="metric-label">Advisory</span>
          <strong>{counts.advisory}</strong>
        </div>
        <div className="metric">
          <span className="metric-label">Active</span>
          <strong>{counts.active}</strong>
        </div>
      </div>

      {error && <div className="form-error">{error}</div>}

      {!rules && !error && (
        <div className="rules-loading">
          <span className="rules-spinner" aria-hidden="true" />
          Loading rule pack…
        </div>
      )}

      {rules &&
        grouped.map(([family, items]) => (
          <section className="rules-family" key={family}>
            <h2 className="rules-family-title">
              {family}
              <span className="rules-family-count">{items.length}</span>
            </h2>
            <div className="rules-list">
              {items.map((rule) => {
                const sev = SEVERITY[rule.severity] || SEVERITY.advisory
                const isOn = !!active[rule.rule_id]
                return (
                  <article className={`rule-row ${isOn ? 'is-on' : 'is-off'}`} key={rule.rule_id}>
                    <div className="rule-row-main">
                      <div className="rule-head">
                        <code className="rule-id">{rule.rule_id}</code>
                        <span className={`rule-sev ${sev.cls}`}>{sev.label}</span>
                        <span className={`rule-state ${isOn ? 'rule-state-on' : 'rule-state-off'}`}>
                          {isOn ? 'ENABLED' : 'DISABLED'}
                        </span>
                      </div>
                      <h3 className="rule-title">{rule.description}</h3>
                      <div className="rule-params">
                        <span className="rule-param">
                          <span className="rule-param-key">Target</span>
                          <span className="rule-param-val">{rule.element || 'all'}</span>
                        </span>
                        <span className="rule-sep" />
                        <span className="rule-param">
                          <span className="rule-param-key">Expected</span>
                          <span className="rule-param-val">{describeExpected(rule)}</span>
                        </span>
                        {rule.notes && (
                          <>
                            <span className="rule-sep" />
                            <span className="rule-param rule-param-notes">
                              <span className="rule-param-key">Notes</span>
                              <span className="rule-param-val">{rule.notes}</span>
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="rule-toggle-wrap">
                      <button
                        type="button"
                        role="switch"
                        aria-checked={isOn}
                        aria-label={`Toggle ${rule.rule_id}`}
                        className={`toggle ${isOn ? 'toggle-on' : ''}`}
                        onClick={() => setActive((s) => ({ ...s, [rule.rule_id]: !s[rule.rule_id] }))}
                      >
                        <span className="toggle-knob" />
                      </button>
                      <span className="toggle-cap">{isOn ? 'Active' : 'Paused'}</span>
                    </div>
                  </article>
                )
              })}
            </div>
          </section>
        ))}

      <footer className="rules-note">
        <span className="rules-note-icon">ℹ</span>
        Toggles simulate administrator control for the pitch — rule packs are read at validation
        time, so changes apply to future tenders with no engine redeployment.
      </footer>
    </div>
  )
}