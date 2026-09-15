// Dashboard page: polls GET /dashboard/{bidId} (contract 6), renders pipeline
// timeline, score gauge, category breakdown, document statuses.
// TODO Phase P2: poll every 2s while status === IN_PROGRESS.

import React from 'react'
import StatusBadge from '../components/StatusBadge.jsx'
import { getDashboard } from '../api/client.js'

export default function DashboardPage({ bidId, onDone }) {
  const [data, setData] = React.useState(null)

  React.useEffect(() => {
    // TODO: poll loop; when terminal call onDone()
    getDashboard(bidId).then((res) => setData(res.data.data))
  }, [bidId])

  if (!data) return <p>Loading pipeline status…</p>

  return (
    <section>
      <h2>{data.tender_id} / {data.bid_id}</h2>
      <StatusBadge status={data.status} />
      <pre>{JSON.stringify(data.timeline, null, 2)}</pre>
    </section>
  )
}