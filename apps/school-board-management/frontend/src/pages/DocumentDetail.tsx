import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../lib/api'

type AgendaItem = { id:number; title:string; order_no:number; consent:boolean }
type Document = { id:number; title:string; start_at:string; location:string; agenda_items:AgendaItem[] }

export default function DocumentDetail(){
  const { id } = useParams()
  const [m,setM] = useState<Document | null>(null)
  useEffect(()=>{ api<Document>(`/document/${id}`).then(setM).catch(console.error) }, [id])
  if(!m) return <div>Loading…</div>
  return (
    <div>
      <h1 className="text-xl font-semibold mb-2">{m.title}</h1>
      <div className="text-sm text-gray-600 mb-4">{new Date(m.start_at).toLocaleString()} • {m.location}</div>
      <h2 className="font-semibold">Agenda</h2>
      <ol className="list-decimal ml-5 mt-2 space-y-2">
        {m.agenda_items?.sort((a,b)=>a.order_no-b.order_no).map(i => (
          <li key={i.id}><span className="font-medium">{i.title}</span> {i.consent && <em className="text-xs text-gray-500">(Consent)</em>}</li>
        ))}
      </ol>
    </div>
  )
}
