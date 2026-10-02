import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Button, EmptyState } from '../components/Common'
import { Header } from '../components/Header'

const inputClass =
  'w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-gray-400 focus:outline-none focus:ring-1 focus:ring-gray-400'

function AddEvidenceForm({ onAdded }) {
  const [kind, setKind] = useState('achievement')
  const [claim, setClaim] = useState('')
  const [skillsText, setSkillsText] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      let data
      if (kind === 'achievement') {
        data = { claim, skills: skillsText.split(',').map((s) => s.trim()).filter(Boolean) }
      } else if (kind === 'skill') {
        data = { name }
      } else {
        data = { name, description, skills: skillsText.split(',').map((s) => s.trim()).filter(Boolean) }
      }
      await api.addManualEvidence(kind, data)
      setClaim('')
      setSkillsText('')
      setName('')
      setDescription('')
      onAdded()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-xl border border-gray-200 bg-white p-4">
      <div className="flex gap-2">
        {['achievement', 'skill', 'project'].map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => setKind(k)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium capitalize ${
              kind === k ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600'
            }`}
          >
            {k}
          </button>
        ))}
      </div>

      {kind === 'achievement' && (
        <>
          <textarea
            className={inputClass}
            rows={2}
            placeholder="Describe the achievement, e.g. 'Shipped a referral program that drove 1,200 signups in Q1 2024.'"
            value={claim}
            onChange={(e) => setClaim(e.target.value)}
            required
          />
          <input
            className={inputClass}
            placeholder="Related skills (comma separated)"
            value={skillsText}
            onChange={(e) => setSkillsText(e.target.value)}
          />
        </>
      )}

      {kind === 'skill' && (
        <input className={inputClass} placeholder="Skill name" value={name} onChange={(e) => setName(e.target.value)} required />
      )}

      {kind === 'project' && (
        <>
          <input className={inputClass} placeholder="Project name" value={name} onChange={(e) => setName(e.target.value)} required />
          <textarea
            className={inputClass}
            rows={2}
            placeholder="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <input
            className={inputClass}
            placeholder="Related skills (comma separated)"
            value={skillsText}
            onChange={(e) => setSkillsText(e.target.value)}
          />
        </>
      )}

      {error && <p className="text-xs text-red-500">{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Saving...' : 'Add to Evidence Database'}
      </Button>
    </form>
  )
}

export function Profile() {
  const [evidence, setEvidence] = useState(null)
  const [error, setError] = useState('')

  function refresh() {
    api.getEvidence().then(setEvidence).catch((e) => setError(e.message))
  }

  useEffect(refresh, [])

  return (
    <div>
      <Header title="Profile" subtitle="Everything extracted from your resumes, plus anything you add manually." />
      <div className="grid grid-cols-[1fr_380px] gap-6 px-8 py-6">
        <div className="space-y-6">
          {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}

          {evidence?.profile?.full_name && (
            <section className="rounded-xl border border-gray-200 bg-white p-4">
              <h2 className="text-sm font-semibold text-gray-700">Personal Info</h2>
              <p className="mt-2 text-sm text-gray-900">{evidence.profile.full_name}</p>
              <p className="text-xs text-gray-500">
                {[...(evidence.profile.emails || []), ...(evidence.profile.phones || []), evidence.profile.location]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
            </section>
          )}

          <section>
            <h2 className="mb-3 text-sm font-semibold text-gray-700">Experience</h2>
            {!evidence?.experiences?.length ? (
              <EmptyState title="No experience extracted yet" />
            ) : (
              <div className="space-y-3">
                {evidence.experiences.map((exp) => {
                  const achievements = evidence.achievements.filter((a) => a.experience_id === exp.id)
                  return (
                    <div key={exp.id} className="rounded-xl border border-gray-200 bg-white p-4">
                      <p className="text-sm font-medium text-gray-900">
                        {exp.role} — {exp.company}
                      </p>
                      <p className="text-xs text-gray-400">
                        {exp.start_date || '?'} - {exp.is_current ? 'Present' : exp.end_date || '?'}
                      </p>
                      <ul className="mt-2 space-y-1">
                        {achievements.map((a) => (
                          <li key={a.id} className="flex items-start gap-1.5 text-sm text-gray-600">
                            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-gray-400" />
                            <span>
                              {a.claim}
                              {a.source_file === 'user_added' && (
                                <span className="ml-1.5 rounded-full bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-600">
                                  manually added
                                </span>
                              )}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )
                })}
              </div>
            )}
          </section>

          {evidence?.achievements?.some((a) => !a.experience_id) && (
            <section>
              <h2 className="mb-3 text-sm font-semibold text-gray-700">General Achievements</h2>
              <p className="mb-2 text-xs text-gray-400">Not tied to a specific role — still usable as evidence when tailoring.</p>
              <ul className="space-y-1 rounded-xl border border-gray-200 bg-white p-4">
                {evidence.achievements
                  .filter((a) => !a.experience_id)
                  .map((a) => (
                    <li key={a.id} className="flex items-start gap-1.5 text-sm text-gray-600">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-gray-400" />
                      <span>
                        {a.claim}
                        {a.source_file === 'user_added' && (
                          <span className="ml-1.5 rounded-full bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-600">
                            manually added
                          </span>
                        )}
                      </span>
                    </li>
                  ))}
              </ul>
            </section>
          )}

          {evidence?.projects?.length > 0 && (
            <section>
              <h2 className="mb-3 text-sm font-semibold text-gray-700">Projects</h2>
              <div className="space-y-2">
                {evidence.projects.map((p) => (
                  <div key={p.id} className="rounded-xl border border-gray-200 bg-white p-4">
                    <p className="text-sm font-medium text-gray-900">{p.name}</p>
                    <p className="text-sm text-gray-600">{p.description}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section>
            <h2 className="mb-3 text-sm font-semibold text-gray-700">Skills</h2>
            {!evidence?.skills?.length ? (
              <EmptyState title="No skills extracted yet" />
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {evidence.skills.map((s) => (
                  <span
                    key={s.id}
                    className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                      s.source === 'user_added' ? 'bg-blue-50 text-blue-700' : 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    {s.name}
                  </span>
                ))}
              </div>
            )}
          </section>

          {evidence?.education?.length > 0 && (
            <section>
              <h2 className="mb-3 text-sm font-semibold text-gray-700">Education</h2>
              {evidence.education.map((e, i) => (
                <p key={i} className="text-sm text-gray-600">
                  {e.degree} — {e.institution}
                </p>
              ))}
            </section>
          )}

          {evidence?.certifications?.length > 0 && (
            <section>
              <h2 className="mb-3 text-sm font-semibold text-gray-700">Certifications</h2>
              {evidence.certifications.map((c, i) => (
                <p key={i} className="text-sm text-gray-600">
                  {c.name} {c.issuer && `— ${c.issuer}`}
                </p>
              ))}
            </section>
          )}
        </div>

        <div>
          <h2 className="mb-3 text-sm font-semibold text-gray-700">Add Manual Evidence</h2>
          <AddEvidenceForm onAdded={refresh} />
          <p className="mt-2 text-xs text-gray-400">
            Anything you add here is tagged <code className="rounded bg-gray-100 px-1">user_added</code> and treated
            as real evidence for future tailored resumes.
          </p>
        </div>
      </div>
    </div>
  )
}
