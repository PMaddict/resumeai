import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { EmptyState } from '../components/Common'
import { Header } from '../components/Header'

export function History() {
  const [outputs, setOutputs] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.listOutputs().then((d) => setOutputs(d.outputs)).catch((e) => setError(e.message))
  }, [])

  return (
    <div>
      <Header title="History" subtitle="Every resume you've generated, in its own timestamped folder — nothing is ever overwritten." />
      <div className="space-y-4 px-8 py-6">
        {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}
        {outputs && outputs.length === 0 && <EmptyState title="Nothing generated yet" />}
        {outputs?.map((out) => (
          <div key={out.name} className="rounded-xl border border-gray-200 bg-white p-4">
            <p className="text-sm font-medium text-gray-900">{out.name}</p>
            <div className="mt-2 flex flex-wrap gap-3">
              {Object.entries(out.files).map(([name, path]) => (
                <a key={name} href={api.downloadUrl(path)} className="text-xs font-medium text-gray-500 hover:text-gray-900">
                  {name}
                </a>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
