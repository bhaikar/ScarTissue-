import { useEffect, useState } from 'react'
import { api } from './api'

type Incident = { incident_id: string; service: string; severity: string; summary: string; symptoms: string[]; logs: { level: string; message: string }[]; deployment?: Record<string, unknown> }
type Diagnosis = { output: { summary: string; confidence: string; hypotheses: { cause: string; current_evidence: string[]; supporting_incident_ids: string[]; contradicting_evidence: string[] }[]; recommended_actions: { action: string; reason: string }[]; approaches_to_avoid: { approach: string; reason: string }[]; missing_evidence: string[] }; memory_evidence: { incident_id?: string; document_id?: string; text: string; type: string }[]; mode: string }
type Eval = { decision: string; deployment_id: string; violations: { rule_id: string; name: string; message: string; source_incident_ids: string[] }[]; needs_review: { rule_id: string; message: string }[] }

const risky = { deployment_id: 'deploy-901', service: 'checkout', retry_attempts: 20, retry_budget: null, feature_flags: { batch_retries: true } }
const safe = { deployment_id: 'deploy-safe-001', service: 'checkout', retry_attempts: 3, retry_budget: 5, feature_flags: { batch_retries: false } }

function DiagnosisView({ diagnosis, title }: { diagnosis: Diagnosis | null; title: string }) {
  if (!diagnosis) return <div className="empty">Run this mode to see its result.</div>
  return <><div className="confidence"><span>{title} · CONFIDENCE</span><strong>{diagnosis.output.confidence.toUpperCase()}</strong></div><p className="diagnosis-summary">{diagnosis.output.summary}</p>{diagnosis.output.hypotheses.map(h => <div className="card" key={h.cause}><b>{h.cause}</b><p>{h.current_evidence.join(' · ')}</p><small>Sources: {h.supporting_incident_ids.join(', ') || 'Current evidence only'}</small></div>)}{diagnosis.output.approaches_to_avoid.length > 0 && <div className="warning"><b>Previously failed — do not repeat</b>{diagnosis.output.approaches_to_avoid.map(x => <p key={x.approach}>{x.approach}<br /><small>{x.reason}</small></p>)}</div>}{diagnosis.output.recommended_actions.map(x => <div className="action" key={x.action}><b>Next action</b><p>{x.action}</p><small>{x.reason}</small></div>)}{diagnosis.output.missing_evidence.length > 0 && <div className="muted"><b>Missing evidence</b><p>{diagnosis.output.missing_evidence.join(' · ')}</p></div>}</>
}

function App() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [selected, setSelected] = useState<Incident | null>(null)
  const [mode, setMode] = useState('on')
  const [diagnosis, setDiagnosis] = useState<Diagnosis | null>(null)
  const [baseline, setBaseline] = useState<Diagnosis | null>(null)
  const [evalResult, setEvalResult] = useState<Eval | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [learned, setLearned] = useState('')
  const [ruleId, setRuleId] = useState('')

  useEffect(() => { api<Incident[]>('/incidents').then(items => { setIncidents(items); setSelected(items.find(x => x.incident_id === 'INC-101') || items[0] || null) }).catch(e => setError(e.message)) }, [])
  async function diagnose() {
    if (!selected) return
    setBusy(true); setError('')
    try {
      const result = await api<Diagnosis>(`/incidents/${selected.incident_id}/diagnoses`, { method: 'POST', body: JSON.stringify({ mode }) }); setDiagnosis(result)
      if (mode === 'on') setBaseline(await api<Diagnosis>(`/incidents/${selected.incident_id}/diagnoses`, { method: 'POST', body: JSON.stringify({ mode: 'off' }) }))
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  async function resolve() {
    if (!selected) return
    setBusy(true); setError('')
    try {
      const result = await api<{ memory_status: string; proposed_rule?: { rule_id: string } }>(`/incidents/${selected.incident_id}/resolution`, { method: 'POST', body: JSON.stringify({ idempotency_key: `${selected.incident_id}-resolution-v1`, root_cause: 'Retry amplification after deployment', action_taken: 'Disabled batch retries and rolled back deployment', outcome: 'succeeded', verification_evidence: ['Connection utilization returned below 60%', 'Checkout p99 returned below 500ms'], applicability_conditions: ['Retry attempts increased before saturation'], contradiction_conditions: ['Lock waits indicate a different cause'], proposed_rule: { all: [{ field: 'retry_attempts', operator: 'gt', value: 5 }, { field: 'retry_budget', operator: 'not_exists' }] } }) })
      setLearned(result.memory_status); if (result.proposed_rule) setRuleId(result.proposed_rule.rule_id)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  async function approve() { if (!ruleId) return; try { await api(`/preventive-rules/${ruleId}/approval`, { method: 'POST', body: JSON.stringify({ approver: 'demo-engineer' }) }); setLearned('Rule active') } catch (e) { setError((e as Error).message) } }
  async function evaluate(deployment: object) { try { setEvalResult(await api<Eval>('/deployments/evaluate', { method: 'POST', body: JSON.stringify({ deployment }) })) } catch (e) { setError((e as Error).message) } }

  return <main><header><div><span className="eyebrow">SCARTISSUE / INCIDENT RESPONSE</span><h1>Diagnose incidents. Prevent repeats.</h1></div><span className="live">● LOCAL DEMO</span></header>{error && <div className="error">{error}</div>}<div className="layout">
    <aside className="panel incident-list"><div className="label">INCIDENTS</div>{incidents.map(item => <button className={selected?.incident_id === item.incident_id ? 'incident selected' : 'incident'} onClick={() => { setSelected(item); setDiagnosis(null); setBaseline(null) }} key={item.incident_id}><span>{item.incident_id}</span><b>{item.severity}</b><small>{item.summary}</small></button>)}</aside>
    {selected && <section className="panel evidence"><div className="section-head"><div><div className="label">CURRENT EVIDENCE</div><h2>{selected.incident_id} · {selected.service}</h2></div><span className="severity">{selected.severity}</span></div><p className="summary">{selected.summary}</p><h3>Symptoms</h3><ul>{selected.symptoms.map(x => <li key={x}>{x}</li>)}</ul><h3>Logs</h3><div className="logs">{selected.logs.map((x, i) => <div key={i}><span>{x.level}</span>{x.message}</div>)}</div><h3>Deployment</h3><pre>{JSON.stringify(selected.deployment, null, 2)}</pre></section>}
    <section className="panel diagnosis"><div className="section-head"><div><div className="label">DIAGNOSIS</div><h2>Compare diagnosis modes</h2></div><select value={mode} onChange={e => setMode(e.target.value)}><option value="off">Memory off</option><option value="on">Memory on</option><option value="full_context">Full context</option></select></div><button className="primary" onClick={diagnose} disabled={busy || !selected}>{busy ? 'Running…' : 'Run diagnosis'}</button>{diagnosis && mode === 'on' ? <div className="comparison"><div className="comparison-col"><DiagnosisView diagnosis={baseline} title="Memory off" /></div><div className="comparison-col"><DiagnosisView diagnosis={diagnosis} title="Memory on" /></div></div> : <DiagnosisView diagnosis={diagnosis} title={mode} />}<div className="learning-actions"><button className="secondary" onClick={resolve} disabled={busy || !selected}>Submit verified resolution</button>{learned && <span className="status">{learned}</span>}{ruleId && <button className="secondary" onClick={approve}>Approve rule</button>}</div></section>
    <section className="panel memory"><div className="label">HISTORICAL EVIDENCE</div><h2>Memory trail</h2>{diagnosis?.memory_evidence.length ? diagnosis.memory_evidence.map(x => <div className="memory-card" key={x.incident_id + x.text}><span>{x.type} · {x.incident_id} · {x.document_id}</span><p>{x.text}</p></div>) : <div className="empty">Memory on returns no matching facts.</div>}<div className="learning"><div className="label">DEPLOYMENT CHECK</div><p>Approved rules block risky changes. Safe changes pass.</p><button className="secondary" onClick={() => evaluate(risky)}>Evaluate risky deployment</button><button className="secondary" onClick={() => evaluate(safe)}>Evaluate safe control</button>{evalResult && <div className={evalResult.decision === 'PASS' ? 'pass result' : 'blocked result'}><b>{evalResult.decision === 'BLOCKED' ? 'Deployment blocked' : 'Deployment passes'}</b><p>{evalResult.violations.map(v => v.message).join(' ') || 'No active rule matched.'}</p><small>{evalResult.violations.flatMap(v => v.source_incident_ids).join(', ')}</small></div>}</div></section>
  </div></main>
}
export default App
