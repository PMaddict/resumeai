import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { EmptyState, StatCard } from '../components/Common'
import { Header } from '../components/Header'

export function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.dashboard().then(setData).catch((e) => setError(e.message))
  }, [])

  return (
    <div>
      <Header title="Dashboard" subtitle="Your local resume tailoring workspace." />
      <div className="space-y-6 px-8 py-6">
        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
        )}

        {data && !data.llm_available && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
            The local model isn't reachable. Run <code className="rounded bg-amber-100 px-1">ollama serve</code> to
            enable ingestion, JD analysis, and resume generation.
          </div>
        )}

        <div className="grid grid-cols-4 gap-4">
          <StatCard label="Source Resumes" value={data?.source_resume_count ?? '—'} />
          <StatCard label="Experiences" value={data?.evidence_stats?.experiences ?? '—'} />
          <StatCard label="Achievements" value={data?.evidence_stats?.achievements ?? '—'} />
          <StatCard label="Skills" value={data?.evidence_stats?.skills ?? '—'} />
        </div>

        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700">Recent JDs</h2>
            <Link to="/tailor" className="text-sm font-medium text-gray-500 hover:text-gray-900">
              + Tailor a new resume
            </Link>
          </div>
          {!data?.recent_jobs?.length ? (
            <EmptyState title="No JDs yet" description="Paste or upload a job description to get started." />
          ) : (
            <div className="space-y-2">
              {data.recent_jobs.map((job) => (
                <div key={job.id} className="flex items-center justify-between rounded-xl border border-gray-200 bg-white p-3.5">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-gray-900">{job.role || 'Untitled role'}</p>
                    <p className="truncate text-xs text-gray-400">{job.company || 'Unknown company'}</p>
                  </div>
                  <span className="shrink-0 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
                    {job.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700">Recent Generated Resumes</h2>
            <Link to="/history" className="text-sm font-medium text-gray-500 hover:text-gray-900">
              View all
            </Link>
          </div>
          {!data?.recent_outputs?.length ? (
            <EmptyState title="Nothing generated yet" description="Tailored resumes will show up here." />
          ) : (
            <div className="space-y-2">
              {data.recent_outputs.map((out) => (
                <div key={out.name} className="flex items-center justify-between rounded-xl border border-gray-200 bg-white p-3.5">
                  <p className="truncate text-sm font-medium text-gray-900">{out.name}</p>
                  <div className="flex gap-2">
                    {out.files['tailored_resume.docx'] && (
                      <a
                        className="text-xs font-medium text-gray-500 hover:text-gray-900"
                        href={api.downloadUrl(out.files['tailored_resume.docx'])}
                      >
                        DOCX
                      </a>
                    )}
                    {out.files['tailored_resume.pdf'] && (
                      <a
                        className="text-xs font-medium text-gray-500 hover:text-gray-900"
                        href={api.downloadUrl(out.files['tailored_resume.pdf'])}
                      >
                        PDF
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
