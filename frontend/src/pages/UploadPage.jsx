// Upload page (Stage 0): role-tagged multi-file upload.
// Glassmorphic drag-and-drop with per-file doc_role tracking. Builds the
// multipart payload via buildUploadFormData() and submits to /upload — the
// backend persists every file into ONE pipeline job so the cross-check pass
// (Rule-XCHK) can reconcile identity fields across all documents.

import React from 'react'
import { buildUploadFormData, uploadBid } from '../api/client.js'

const DOC_ROLES = [
  { value: 'technical_bid', label: 'Technical Bid' },
  { value: 'financial_bid', label: 'Financial Bid' },
  { value: 'emd', label: 'EMD / Bank Guarantee' },
  { value: 'certificates', label: 'Certificates / Incorporation' },
  { value: 'annexure', label: 'Annexure' },
]

const ACCEPT = '.pdf,.doc,.docx,.png,.jpg,.jpeg'

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return ''
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

function fileTypeTag(fileName) {
  const ext = (fileName.split('.').pop() || '').toLowerCase()
  if (ext === 'pdf') return 'PDF'
  if (['png', 'jpg', 'jpeg'].includes(ext)) return 'IMG'
  if (ext === 'doc' || ext === 'docx') return 'DOC'
  return 'FILE'
}

export default function UploadPage({ onSubmitted }) {
  const [tenderId, setTenderId] = React.useState('GeM/2026/B/123456')
  const [bidId, setBidId] = React.useState('')
  const [supplier, setSupplier] = React.useState('')
  const [category, setCategory] = React.useState('')
  const [files, setFiles] = React.useState([])
  const [dragging, setDragging] = React.useState(false)
  const [error, setError] = React.useState('')
  const [loading, setLoading] = React.useState(false)
  const inputRef = React.useRef(null)

  const addFiles = (list) => {
    const next = Array.from(list || []).map((blob) => ({
      blob,
      fileName: blob.name,
      size: blob.size,
      docRole: 'technical_bid',
    }))
    if (next.length) {
      setError('')
      setFiles((prev) => [...prev, ...next])
    }
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    addFiles(e.dataTransfer?.files)
  }

  const setRole = (index, docRole) => {
    setFiles((prev) => prev.map((f, i) => (i === index ? { ...f, docRole } : f)))
  }

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (files.length === 0) {
      setError('Attach at least one document before submitting.')
      return
    }
    if (!tenderId.trim() || !bidId.trim() || !supplier.trim()) {
      setError('Tender ID, Bid ID and Supplier are required.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const formData = buildUploadFormData({
        tenderId: tenderId.trim(),
        bidId: bidId.trim(),
        supplier: supplier.trim(),
        category: category.trim(),
        docs: files,
      })
      const res = await uploadBid(formData)
      const data = res.data?.data ?? res.data ?? {}
      const submittedBidId = data.bid_id || bidId.trim()
      onSubmitted(submittedBidId)
    } catch (err) {
      const msg = err?.response?.data?.error?.message || err.message || 'Upload failed. Please try again.'
      setError(msg)
      setLoading(false)
    }
  }

  return (
    <section className="app-page upload-page">
      <header className="page-heading">
        <h1>GeM Bid Compliance Verification</h1>
        <p>
          Upload your role-tagged tender documents. Identity fields are
          cross-checked across every file for discrepancies.
        </p>
      </header>

      <form className="upload-card" onSubmit={handleSubmit}>
        <div className="metadata-grid">
          <div className="field">
            <label className="field-label" htmlFor="tender-id">Tender ID</label>
            <input
              id="tender-id"
              className="text-input"
              value={tenderId}
              onChange={(e) => setTenderId(e.target.value)}
              placeholder="e.g. GeM/2026/B/123456"
              autoComplete="off"
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="bid-id">Bid ID</label>
            <input
              id="bid-id"
              className="text-input"
              value={bidId}
              onChange={(e) => setBidId(e.target.value)}
              placeholder="e.g. bid-2026-001"
              autoComplete="off"
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="supplier">Supplier</label>
            <input
              id="supplier"
              className="text-input"
              value={supplier}
              onChange={(e) => setSupplier(e.target.value)}
              placeholder="e.g. Acme Industries Pvt Ltd"
              autoComplete="off"
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="category">Category</label>
            <input
              id="category"
              className="text-input"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="e.g. Petroleum Products"
              autoComplete="off"
            />
          </div>
        </div>

        <div
          className={`dropzone${dragging ? ' dragover' : ''}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          role="button"
          tabIndex={0}
          aria-label="Attach tender documents"
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              inputRef.current?.click()
            }
          }}
        >
          <input
            ref={inputRef}
            type="file"
            multiple
            hidden
            accept={ACCEPT}
            onChange={(e) => {
              addFiles(e.target.files)
              e.target.value = ''
            }}
          />
          <span className="dropzone-icon" aria-hidden="true">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 16V4" />
              <path d="m7 9 5-5 5 5" />
              <path d="M4 16v1a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-1" />
            </svg>
          </span>
          <strong>Drag &amp; drop documents here</strong>
          <p>or <span className="link">browse files</span> — PDF, DOCX or scanned images</p>
        </div>

        {files.length > 0 && (
          <ul className="file-list" aria-label="Attached documents">
            {files.map((file, index) => (
              <li className="file-row" key={`${file.fileName}-${index}`}>
                <span className="file-badge" aria-hidden="true">{fileTypeTag(file.fileName)}</span>
                <span className="file-meta">
                  <strong>{file.fileName}</strong>
                  <small>{formatBytes(file.size) || 'Unknown size'}</small>
                </span>
                <select
                  className="role-select"
                  value={file.docRole}
                  onChange={(e) => setRole(index, e.target.value)}
                  aria-label={`Document role for ${file.fileName}`}
                >
                  {DOC_ROLES.map((role) => (
                    <option key={role.value} value={role.value}>{role.label}</option>
                  ))}
                </select>
                <button
                  type="button"
                  className="file-remove"
                  onClick={() => removeFile(index)}
                  aria-label={`Remove ${file.fileName}`}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}

        {error && (
          <p className="form-error" role="alert">{error}</p>
        )}

        <div className="form-actions">
          <button
            type="submit"
            className="btn-primary"
            disabled={loading || files.length === 0}
          >
            {loading
              ? 'Submitting…'
              : `Submit${files.length ? ` (${files.length} document${files.length > 1 ? 's' : ''})` : ''}`}
          </button>
        </div>
      </form>
    </section>
  )
}