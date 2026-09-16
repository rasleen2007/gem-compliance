// API client — thin axios wrapper over the backend REST /api/v1 surface.
// Envelope shapes: contracts 1/3/5 (upload, jobs, dashboard). All calls
// resolve to the envelope's `data` payload.

import axios from 'axios'

const client = axios.create({ baseURL: '/api/v1' })

// --- upload / validation ------------------------------------------------
export const uploadBid = (formData) => client.post('/upload', formData)
export const runValidation = (requestId) => client.post(`/validate/${requestId}`)

// --- polling (jobs + dashboard) ----------------------------------------
export const getJob = (requestId) => client.get(`/jobs/${requestId}`)
export const getDashboard = (bidId) => client.get(`/dashboard/${bidId}`)

/**
 * Build the multipart payload the upload contract (contract 1) expects:
 * `file` + `tender_id`, `bid_id`, `supplier`, `category`, `doc_role`.
 *
 * `docs` entries: { blob, fileName, docRole }. One extra `file` part is sent
 * per document, all tagged with the same bid metadata fields.
 */
export function buildUploadFormData({ tenderId, bidId, supplier, category, docs }) {
  const fd = new FormData()
  fd.append('tender_id', tenderId)
  fd.append('bid_id', bidId)
  fd.append('supplier', supplier)
  fd.append('category', category ?? '')
  docs.forEach((doc) => {
    fd.append('file', doc.blob, doc.fileName)
    fd.append('doc_role', doc.docRole)
  })
  return fd
}

/**
 * Poll a promise-producing GET until its terminal condition is reached.
 * Used for the pipeline job timeline and the compliance dashboard while the
 * bid is still IN_PROGRESS. `terminal` receives the envelope `data` payload.
 */
export async function poll(createRequest, terminal, { intervalMs = 2000, maxTries = 90 } = {}) {
  let tries = 0
  for (;;) {
    const res = await createRequest()
    const payload = res.data?.data
    if (terminal(payload)) return payload
    if (++tries >= maxTries) throw new Error(`poll timeout after ${tries * intervalMs}ms`)
    await new Promise((r) => setTimeout(r, intervalMs))
  }
}
