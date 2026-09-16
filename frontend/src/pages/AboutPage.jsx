// About page — "System Specifications & Core Intelligence Engine".
// Politech pitch screen: a clean grid of the 100% free, local-first stack
// (PyMuPDF OCR, geometric layout parsing, deterministic regex NLP) plus the
// Ministry-facing architectural benefits. No team credits — product only.

import React from 'react'

const PIPELINE = [
  {
    phase: '01 · READ',
    title: 'Local OCR Document Reading',
    tech: 'PyMuPDF',
    tag: 'OPEN SOURCE',
    icon: '⇲',
    points: [
      'On-device text + vector extraction',
      'No cloud OCR key or API account',
      'Handles PDF, scanned TIFF & images',
    ],
    accent: 'blue',
  },
  {
    phase: '02 · STRUCTURE',
    title: 'Geometric Layout & Partition Parsing',
    tech: 'Layout Engine',
    tag: 'DETERMINISTIC',
    icon: '▦',
    points: [
      'Stamps, tables & signatures as regions',
      'Document partition ownership map',
      'Price-breakup and annexure detection',
    ],
    accent: 'emerald',
  },
  {
    phase: '03 · EXTRACT',
    title: 'Deterministic Regex NLP Extraction',
    tech: 'Rule-based NLP',
    tag: 'AUDITABLE',
    icon: '⌗',
    points: [
      'GSTIN / PAN / CIN / dates / turnovers',
      'Cross-document identity reconciliation',
      'Every extraction carries a source span',
    ],
    accent: 'amber',
  },
]

const BENEFITS = [
  {
    title: 'Zero Cloud API Expenses',
    icon: '₹0',
    accent: 'emerald',
    body: 'The entire verification pipeline runs locally on the review desk. No paid OCR, '
      + 'no metered LLM calls, no per-document processing fees — total cost of compute is zero.',
  },
  {
    title: 'High-Speed Local Runtime',
    icon: '⚡',
    accent: 'blue',
    body: 'Documents are parsed in-process with PyMuPDF and a lightweight regex NLP layer, '
      + 'so a multi-file bid completes verification in seconds without network latency.',
  },
  {
    title: 'Contract-Driven Data Isolation',
    icon: '⛨',
    accent: 'amber',
    body: 'Every stage emits a typed, versioned payload (OCR → layout → parsed → validation). '
      + 'Modules only read what their contract allows, keeping data at each boundary isolated.',
  },
]

function accentClass(name) {
  return { blue: 'about-accent-blue', emerald: 'about-accent-emerald', amber: 'about-accent-amber' }[name] || ''
}

function PillarCard({ p }) {
  return (
    <article className={`about-pillar about-${p.accent}`}>
      <div className="about-pillar-head">
        <span className="about-pillar-icon">{p.icon}</span>
        <span className="about-tag">{p.tag}</span>
      </div>
      <h3>{p.title}</h3>
      <p className="about-pillar-tech">{p.tech}</p>
      <ul>
        {p.points.map((pt) => (
          <li key={pt}>{pt}</li>
        ))}
      </ul>
      <div className="about-pillar-phase">{p.phase}</div>
    </article>
  )
}

function BenefitCard({ b }) {
  return (
    <article className={`about-benefit about-${b.accent}`}>
      <div className="about-benefit-icon">{b.icon}</div>
      <div>
        <h4>{b.title}</h4>
        <p>{b.body}</p>
      </div>
    </article>
  )
}

export default function AboutPage({ onNavigate }) {
  return (
    <div className="app-page about-page">
      <header className="page-heading about-hero">
        <span className="about-eyebrow">GeM Bid Compliance Platform</span>
        <h1>System Specifications &amp; Core Intelligence Engine</h1>
        <p>
          A 100% free, local-first verification stack built for the Ministry — from raw upload
          to a contract-typed compliance verdict, with zero recurring software cost.
        </p>
      </header>

      <section className="about-section">
        <h2 className="about-section-title">Core Intelligence Pipeline</h2>
        <p className="about-section-sub">
          Three deterministic stages transform uploaded documents into structured, auditable data.
        </p>
        <div className="about-pillars">
          {PIPELINE.map((p) => (
            <PillarCard key={p.phase} p={p} />
          ))}
        </div>
      </section>

      <section className="about-section">
        <h2 className="about-section-title">Why This Architecture Serves the Ministry</h2>
        <p className="about-section-sub">
          Built to run entirely within government review environments — no external dependencies,
          no data leaving the workstation.
        </p>
        <div className="about-benefits">
          {BENEFITS.map((b) => (
            <BenefitCard key={b.title} b={b} />
          ))}
        </div>
      </section>
    </div>
  )
}