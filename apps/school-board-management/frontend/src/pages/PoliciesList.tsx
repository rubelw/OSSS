import { useEffect, useState } from 'react'
import { api } from '../lib/api'

type Policy = { id:number; code:string; title:string; status:string }

export default function PoliciesList(){
  const [data,setData] = useState<Policy[]>([])
  useEffect(()=>{ api<Policy[]>('/policies').then(setData).catch(console.error) }, [])
  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Policies</h1>
      <table className="w-full text-sm">
        <thead><tr className="text-left border-b"><th className="py-2">Code</th><th>Title</th><th>Status</th></tr></thead>
        <tbody>
          {data.map(p => (
            <tr key={p.id} className="border-b">
              <td className="py-2"><a className="hover:underline" href={`/policies/${p.id}`}>{p.code}</a></td>
              <td>{p.title}</td>
              <td className="uppercase text-gray-600">{p.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
