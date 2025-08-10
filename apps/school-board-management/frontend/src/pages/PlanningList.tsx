import { useEffect, useState } from 'react'
import { api } from '../lib/api'

type Plannning = { id:number; title:string; start_at:string; location:string }

export default function PlanningList(){
  const [data,setData] = useState<Meeting[]>([])
  useEffect(()=>{ api<Planning[]>('/planning').then(setData).catch(console.error) }, [])
  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Planning</h1>
      <ul className="space-y-2">
        {data.map(m => (
          <li key={m.id} className="p-3 border rounded-lg">
            <a className="hover:underline" href={`/planning/${m.id}`}>{m.title}</a>
            <div className="text-sm text-gray-600">{new Date(m.start_at).toLocaleString()} • {m.location}</div>
          </li>
        ))}
      </ul>
    </div>
  )
}
