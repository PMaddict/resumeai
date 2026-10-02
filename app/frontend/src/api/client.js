const BASE = '/api'

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || JSON.stringify(body)
    } catch {
      // ignore
    }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  dashboard: () => fetch(`${BASE}/dashboard`).then(handle),

  listResumes: () => fetch(`${BASE}/resumes`).then(handle),
  uploadResume: (file) => {
    const form = new FormData()
    form.append('file', file)
    return fetch(`${BASE}/resumes`, { method: 'POST', body: form }).then(handle)
  },
  deleteResume: (filename) => fetch(`${BASE}/resumes/${encodeURIComponent(filename)}`, { method: 'DELETE' }).then(handle),
  reingestResumes: () => fetch(`${BASE}/resumes/reingest`, { method: 'POST' }).then(handle),
  rebuildIndex: () => fetch(`${BASE}/resumes/rebuild-index`, { method: 'POST' }).then(handle),

  getEvidence: () => fetch(`${BASE}/evidence`).then(handle),
  addManualEvidence: (kind, data) =>
    fetch(`${BASE}/evidence/manual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind, data }),
    }).then(handle),

  createJobFromText: (rawText, company, role) => {
    const form = new FormData()
    form.append('raw_text', rawText)
    if (company) form.append('company', company)
    if (role) form.append('role', role)
    return fetch(`${BASE}/jobs`, { method: 'POST', body: form }).then(handle)
  },
  createJobFromFile: (file, company, role) => {
    const form = new FormData()
    form.append('file', file)
    if (company) form.append('company', company)
    if (role) form.append('role', role)
    return fetch(`${BASE}/jobs`, { method: 'POST', body: form }).then(handle)
  },
  listJobs: () => fetch(`${BASE}/jobs`).then(handle),
  analyzeJob: (jobId) => fetch(`${BASE}/jobs/${jobId}/analyze`, { method: 'POST' }).then(handle),
  generateJob: (jobId) => fetch(`${BASE}/jobs/${jobId}/generate`, { method: 'POST' }).then(handle),

  listOutputs: () => fetch(`${BASE}/outputs`).then(handle),
  downloadUrl: (path) => `${BASE}/outputs/download?path=${encodeURIComponent(path)}`,
}
