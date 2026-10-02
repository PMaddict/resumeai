import { useState } from 'react'
import { api } from '../api/client'
import { Button, PriorityBadge, Spinner, StrengthBadge } from '../components/Common'
import { Header } from '../components/Header'

const inputClass =
  'w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-gray-400 focus:outline-none focus:ring-1 focus:ring-gray-400'

export function JDTailoring() {
  const [step, setStep] = useState('input') // input | review | done
  const [mode, setMode] = useState('paste') // paste | upload
  const [rawText, setRawText] = useState('')
  const [file, setFile] = useState(null)
  const [company, setCompany] = useState('')
  const [role, setRole] = useState('')
  const [jobId, setJobId] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [busyLabel, setBusyLabel] = useState('')
  const [error, setError] = useState('')

  async function handleAnalyze(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    setBusyLabel('Parsing the job description and matching it against your evidence...')
    try {
      const job = mode === 'paste' ? await api.createJobFromText(rawText, company, role) : await api.createJobFromFile(file, company, role)
      setJobId(job.id)
      const analysisResult = await api.analyzeJob(job.id)
      setAnalysis(analysisResult)
      setStep('review')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleGenerate() {
    setError('')
    setBusy(true)
    setBusyLabel('Writing and validating your tailored resume...')
    try {
      const res = await api.generateJob(jobId)
      setResult(res)
      setStep('done')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function startOver() {
    setStep('input')
    setRawText('')
    setFile(null)
    setCompany('')
    setRole('')
    setJobId(null)
    setAnalysis(null)
    setResult(null)
    setError('')
  }

  return (
    <div>
      <Header title="Tailor Resume" subtitle="Paste or upload a job description to generate a tailored resume." />
      <div className="mx-auto max-w-3xl space-y-6 px-8 py-6">
        {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}
        {busy && <Spinner label={busyLabel} />}

        {step === 'input' && !busy && (
          <form onSubmit={handleAnalyze} className="space-y-4">
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setMode('paste')}
                className={`rounded-full px-3 py-1.5 text-sm font-medium ${mode === 'paste' ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600'}`}
              >
                Paste text
              </button>
              <button
                type="button"
                onClick={() => setMode('upload')}
                className={`rounded-full px-3 py-1.5 text-sm font-medium ${mode === 'upload' ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600'}`}
              >
                Upload file
              </button>
            </div>

            {mode === 'paste' ? (
              <textarea
                className={inputClass}
                rows={12}
                placeholder="Paste the full job description here..."
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                required
              />
            ) : (
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className={inputClass}
                required
              />
            )}

            <div className="grid grid-cols-2 gap-3">
              <input className={inputClass} placeholder="Company (optional)" value={company} onChange={(e) => setCompany(e.target.value)} />
              <input className={inputClass} placeholder="Role title (optional)" value={role} onChange={(e) => setRole(e.target.value)} />
            </div>

            <Button type="submit" disabled={busy}>
              Analyze JD
            </Button>
          </form>
        )}

        {step === 'review' && analysis && !busy && (
          <div className="space-y-6">
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <p className="text-sm font-semibold text-gray-900">
                {analysis.parsed_jd.role_title || 'Untitled role'} at {analysis.parsed_jd.company || 'Unknown company'}
              </p>
              <p className="text-xs text-gray-400">Seniority: {analysis.parsed_jd.seniority || 'Unknown'}</p>
            </div>

            <section>
              <h2 className="mb-2 text-sm font-semibold text-gray-700">These are the experiences I plan to emphasize</h2>
              {Object.keys(analysis.plan.emphasis_by_company).length === 0 ? (
                <p className="text-sm text-gray-400">No strong emphasis themes found — review the matches below.</p>
              ) : (
                <div className="space-y-2">
                  {Object.entries(analysis.plan.emphasis_by_company).map(([company, themes]) => (
                    <div key={company} className="rounded-xl border border-gray-200 bg-white p-3.5">
                      <p className="text-sm font-medium text-gray-900">{company}</p>
                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        {themes.map((t) => (
                          <span key={t} className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section>
              <h2 className="mb-2 text-sm font-semibold text-gray-700">Requirement Matches</h2>
              <div className="space-y-2">
                {analysis.matches.map((m, i) => (
                  <div key={i} className="rounded-xl border border-gray-200 bg-white p-3.5">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm text-gray-900">{m.requirement}</p>
                      <div className="flex shrink-0 gap-1.5">
                        <PriorityBadge priority={m.priority} />
                        <StrengthBadge strength={m.strength} />
                      </div>
                    </div>
                    {m.reasoning && <p className="mt-1 text-xs text-gray-400">{m.reasoning}</p>}
                  </div>
                ))}
              </div>
            </section>

            <div className="flex gap-2">
              <Button variant="secondary" onClick={startOver}>
                Start Over
              </Button>
              <Button onClick={handleGenerate}>Generate Tailored Resume</Button>
            </div>
          </div>
        )}

        {step === 'done' && result && !busy && (
          <div className="space-y-6">
            {result.blocked ? (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4">
                <p className="text-sm font-semibold text-red-800">Generation was blocked by validation</p>
                <ul className="mt-2 space-y-1 text-sm text-red-700">
                  {result.validation.issues.map((issue, i) => (
                    <li key={i}>
                      [{issue.severity}] {issue.message}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                <p className="text-sm font-semibold text-emerald-800">Tailored resume generated successfully</p>
                <p className="mt-1 text-xs text-emerald-700">All validation checks passed — zero unsupported claims.</p>
              </div>
            )}

            {!result.blocked && (
              <div className="flex gap-3">
                <a href={api.downloadUrl(result.docx_path)} className="rounded-lg bg-gray-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-gray-800">
                  Download DOCX
                </a>
                <a href={api.downloadUrl(result.pdf_path)} className="rounded-lg border border-gray-200 px-3.5 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
                  Download PDF
                </a>
                <a
                  href={api.downloadUrl(`${result.output_dir}/tailoring_report.md`)}
                  className="rounded-lg border border-gray-200 px-3.5 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Download Report
                </a>
              </div>
            )}

            <Button variant="secondary" onClick={startOver}>
              Tailor Another Resume
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
