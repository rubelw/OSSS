import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../lib/api'

type VersionMeta = { id:number; version_no:number; adopted_on?:string|null; effective_on?:string|null }
type Policy = { id:number; code:string; title:string; status:string; category?:string|null; versions: VersionMeta[] }
type VersionBody = { id:number; policy_id:number; version_no:number; body_md:string, adopted_on?:string|null, effective_on?:string|null }

export default function PolicyDetail(){
  const { id } = useParams()
  const [policy,setPolicy] = useState<Policy | null>(null)
  const [fromId,setFromId] = useState<number | null>(null)
  const [toId,setToId] = useState<number | null>(null)
  const [html,setHtml] = useState<string>('')
  const [body,setBody] = useState<VersionBody | null>(null)

  useEffect(()=>{
    api<Policy>(`/policies/${id}`).then(p => {
      setPolicy(p)
      if (p.versions.length >= 2) {
        setFromId(p.versions[p.versions.length-2].id)
        setToId(p.versions[p.versions.length-1].id)
      } else if (p.versions.length === 1) {
        setToId(p.versions[0].id)
      }
    }).catch(console.error)
  }, [id])

  useEffect(()=>{
    if (fromId && toId) {
      fetch(`${import.meta.env.VITE_API_BASE || 'http://localhost:8000'}/policies/${id}/diff?from_id=${fromId}&to_id=${toId}`, {
        credentials: 'include',
        headers: { 'Accept':'text/html' }
      }).then(r=>r.text()).then(setHtml).catch(console.error)
    } else if (toId) {
      api<VersionBody>(`/policies/${id}/versions/${toId}`).then(setBody).catch(console.error)
    }
  }, [fromId, toId, id])

  if(!policy) return <div>Loading…</div>

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">{policy.code} — {policy.title}</h1>
        <div className="text-sm text-gray-600 uppercase">{policy.status}</div>
      </div>

      <div className="flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-sm text-gray-700">From version</label>
          <select className="border rounded px-2 py-1" value={fromId ?? ''} onChange={e=>setFromId(e.target.value? Number(e.target.value): null)}>
            <option value="">(none)</option>
            {policy.versions.map(v=> <option key={v.id} value={v.id}>v{v.version_no}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-700">To version</label>
          <select className="border rounded px-2 py-1" value={toId ?? ''} onChange={e=>setToId(e.target.value? Number(e.target.value): null)}>
            <option value="">(none)</option>
            {policy.versions.map(v=> <option key={v.id} value={v.id}>v{v.version_no}</option>)}
          </select>
        </div>
      </div>

      {fromId && toId ? (
        <div>
          <h2 className="font-semibold mb-2">Redline (v{policy.versions.find(v=>v.id===fromId)?.version_no} → v{policy.versions.find(v=>v.id===toId)?.version_no})</h2>
          <div className="border rounded p-3 overflow-auto" dangerouslySetInnerHTML={{__html: html}} />
        </div>
      ) : body ? (
        <div>
          <h2 className="font-semibold mb-2">Version v{body.version_no}</h2>
          <pre className="whitespace-pre-wrap border rounded p-3 bg-gray-50">{body.body_md}</pre>
        </div>
      ) : (
        <div className="text-gray-600">Select at least a "To version" to view content.</div>
      )}
    </div>
  )
}
