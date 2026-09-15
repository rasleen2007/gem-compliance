// Upload page (Stage 0): role-tagged multi-file upload.
// TODO Phase P2: form fields (tender_id, bid_id, supplier, category) + per-file
// doc_role selector, progress, then uploadBid(formData) -> document_upload.

import React from 'react'
import { uploadBid } from '../api/client.js'

export default function UploadPage({ onSubmitted }) {
  const [loading, setLoading] = React.useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    // TODO: build FormData from fields; call uploadBid; onSubmitted(payload.data.bid_id)
    setLoading(false)
  }

  return (
    <form onSubmit={handleSubmit}>
      <h1>GeM Bid Compliance Verification</h1>
      <p>Tender ID / files selection UI — implement in MVP Phase P2.</p>
      <button type="submit" disabled={loading}>Submit (stub)</button>
    </form>
  )
}