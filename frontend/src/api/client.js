// API client — wraps the backend REST /api/v1 surface.
// Contract shapes: contracts/api_envelope.schema.json + contract 6.

import axios from 'axios'

const client = axios.create({ baseURL: '/api/v1' })

export const uploadBid = (formData) => client.post('/upload', formData)
export const getJob = (requestId) => client.get(`/jobs/${requestId}`)
export const getDashboard = (bidId) => client.get(`/dashboard/${bidId}`)
export const runValidation = (requestId) => client.post(`/validate/${requestId}`)