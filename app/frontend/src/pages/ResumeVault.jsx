import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { Button, EmptyState, Spinner } from '../components/Common'
import { Header } from '../components/Header'

export function ResumeVault() {
  const [resumes, setResumes] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [busyLabel, setBusyLabel] = useState('')
  const fileInputRef = useRef(null)

  function refresh() {
    api.listResumes().then((d) => setResumes(d.resumes)).catch((e) => setError(e.message))
  }

  useEffect(refresh, [])

  async function handleUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setError('')
    setBusy(true)
    setBusyLabel(`Uploading and ingesting ${file.name}...`)
    try {
      await api.uploadResume(file)
      refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
      e.target.value = ''
    }
  }

  async function handleDelete(filename) {
    if (!confirm(`Remove ${filename} from the vault? This does not delete the file's evidence until you rebuild the index.`)) return
    try {
      await api.deleteResume(filename)
      refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleReingest() {
    setBusy(true)
    setBusyLabel('Re-ingesting all resumes...')
    setError('')
    try {
      await api.reingestResumes()
      refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleRebuildIndex() {
    if (!confirm('This wipes the evidence database and re-extracts everything from scratch. Continue?')) return
    setBusy(true)
    setBusyLabel('Rebuilding evidence index from scratch...')
    setError('')
    try {
      await api.rebuildIndex()
      refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <Header
        title="Resume Vault"
        subtitle="Your original resumes are never modified — they're the single source of truth."
        actions={
          <>
            <input ref={fileInputRef} type="file" accept=".pdf,.docx,.txt" className="hidden" onChange={handleUpload} />
            <Button variant="secondary" onClick={handleReingest} disabled={busy}>
              Re-ingest All
            </Button>
            <Button variant="secondary" onClick={handleRebuildIndex} disabled={busy}>
              Rebuild Index
            </Button>
            <Button onClick={() => fileInputRef.current?.click()} disabled={busy}>
              + Add Resume
            </Button>
          </>
        }
      />
      <div className="space-y-4 px-8 py-6">
        {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}
        {busy && <Spinner label={busyLabel} />}

        {resumes && resumes.length === 0 ? (
          <EmptyState
            title="No resumes yet"
            description="Upload 3-5 of your existing resumes (PDF, DOCX, or TXT) to build your evidence database."
            action={
              <Button onClick={() => fileInputRef.current?.click()} disabled={busy}>
                + Add Resume
              </Button>
            }
          />
        ) : (
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-xs text-gray-400">
                  <th className="px-4 py-2.5 font-medium">File</th>
                  <th className="px-4 py-2.5 font-medium">Size</th>
                  <th className="px-4 py-2.5 font-medium">Ingested</th>
                  <th className="px-4 py-2.5 font-medium">Extracted</th>
                  <th className="px-4 py-2.5 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {resumes?.map((r) => (
                  <tr key={r.filename}>
                    <td className="px-4 py-3 font-medium text-gray-900">{r.filename}</td>
                    <td className="px-4 py-3 text-gray-500">{Math.round(r.size_bytes / 1024)} KB</td>
                    <td className="px-4 py-3">
                      {r.ingested ? (
                        <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">Yes</span>
                      ) : (
                        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">Not yet</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {r.ingestion_summary
                        ? `${r.ingestion_summary.num_experiences} exp · ${r.ingestion_summary.num_achievements} achievements · ${r.ingestion_summary.num_skills} skills`
                        : '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleDelete(r.filename)}
                        className="text-xs font-medium text-red-500 hover:text-red-700"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="text-xs text-gray-400">
          Want to see everything extracted from your resumes? Check the <strong>Profile</strong> page.
        </p>
      </div>
    </div>
  )
}
