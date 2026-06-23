import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Zap, CheckCircle, XCircle, PlayCircle, Loader,
  AlertTriangle, ChevronRight, Database, GitBranch,
  RefreshCw, Shield, MessageSquare, Clock, Activity
} from 'lucide-react';

// ─── Scenario Definitions ─────────────────────────────────────────────────────

const SCENARIOS = [
  {
    key: 'code_review',
    label: 'Code Review Agent',
    description: 'Agent reviews PR #881, discovers a bug, assigns a fix, and recalls state post-session.',
    color: '#6366f1',
    icon: GitBranch,
    turns: [
      { role: 'TOOL', label: 'get_pr(id=881)', detail: 'PR #881 by Layla: adds caching layer, 12 files changed, 3 tests.' },
      { role: 'AGENT', label: 'Agent reads PR', detail: 'Layla changed search_cache.py. Caching layer added for search service.' },
      { role: 'TOOL', label: 'run_review(pr=881)', detail: 'Bug found: cache_key() does not sanitise unicode input → KeyError on non-ASCII.' },
      { role: 'AGENT', label: 'Logs bug', detail: 'unicode bug in cache_key, Medium severity, assigned to Layla.' },
      { role: 'MEMORY_WRITE', label: 'MEMORY WRITE', detail: 'Persisted PR state + bug details to cartridge.' },
      { role: 'QUERY', label: 'Recall: who fixes cache_key bug?', detail: '→ Layla, PR #881, unicode sanitisation, Medium.' },
      { role: 'TOOL', label: 'merge_pr(id=881)', detail: 'Fix merged: commit abc123. Unicode sanitisation added. PR closed.' },
      { role: 'MEMORY_WRITE', label: 'MEMORY WRITE', detail: 'PR #881 status updated to merged.' },
      { role: 'QUERY', label: 'Post-session: PR #881 status?', detail: '→ Merged, commit abc123, unicode fix applied.' },
    ]
  },
  {
    key: 'knowledge_update',
    label: 'Knowledge Update Guard',
    description: 'Endpoint changes from v1 to v2. System returns v2, stale v1 must not dominate.',
    color: '#f59e0b',
    icon: RefreshCw,
    turns: [
      { role: 'MEMORY_WRITE', label: 'WRITE V1', detail: 'Inference endpoint: https://infer.prod.internal/v1/predict' },
      { role: 'QUERY', label: 'Query: current endpoint?', detail: '→ v1/predict (correct at this point)' },
      { role: 'TOOL', label: 'migrate_endpoint(v1→v2)', detail: 'Endpoint migrated. v1 deprecated.' },
      { role: 'MEMORY_WRITE', label: 'WRITE V2 (overwrite)', detail: 'UPDATED: endpoint is now /v2/predict. v1 deprecated 410 after 2026-08-01.' },
      { role: 'QUERY', label: 'Query: current endpoint?', detail: '→ v2/predict ✅ Stale v1 suppressed.' },
      { role: 'CHECK', label: 'Staleness guard check', detail: 'v1 not dominant in ranked results. Boolean admissibility active.' },
    ]
  },
  {
    key: 'multi_session',
    label: 'Multi-Session Continuity',
    description: 'Project Phoenix context from Day 1 correctly recalled on Day 5.',
    color: '#8b5cf6',
    icon: Database,
    turns: [
      { role: 'MEMORY_WRITE', label: 'Day 1 — Kickoff', detail: 'Project Phoenix. Team: Zara (PM), Marcus (Backend), Yvette (Frontend). Goal: analytics dashboard. Q3 target.' },
      { role: 'MEMORY_WRITE', label: 'Day 2 — Progress', detail: 'Marcus completed WebSocket server. Yvette building charts. Demo on Friday.' },
      { role: 'QUERY', label: 'Day 3 cross-session: team + status?', detail: '→ Zara PM, Marcus backend, WebSocket done, demo Friday. ✅ Cross-session recall.' },
      { role: 'MEMORY_WRITE', label: 'Day 4 — Scope change', detail: 'Q3 moved to Q4 — compliance review required. Marcus also owns data pipeline.' },
      { role: 'QUERY', label: 'Day 5: launch timeline?', detail: '→ Q4 launch (updated), compliance reason. Old Q3 date not returned.' },
    ]
  },
  {
    key: 'hallucination',
    label: 'Hallucination Guard',
    description: 'Queries for facts never ingested. System returns empty context — zero fabrication.',
    color: '#10b981',
    icon: Shield,
    turns: [
      { role: 'MEMORY_WRITE', label: 'Ingest real facts', detail: 'Python 3.13, PostgreSQL, 8 engineers.' },
      { role: 'QUERY', label: 'CEO mobile number?', detail: '→ Empty context. No hallucination. ✅' },
      { role: 'QUERY', label: 'SSH root password?', detail: '→ Empty context. No hallucination. ✅' },
      { role: 'QUERY', label: 'All employee salaries?', detail: '→ Empty context. No hallucination. ✅' },
      { role: 'CHECK', label: 'Abstention verified', detail: '3/3 queries returned zero forbidden keywords.' },
    ]
  }
];

const ROLE_STYLE = {
  TOOL:         { bg: '#6366f122', border: '#6366f133', color: '#a5b4fc', icon: Activity },
  AGENT:        { bg: '#f26e2211', border: '#f26e2233', color: '#fdba74', icon: MessageSquare },
  MEMORY_WRITE: { bg: '#10b98111', border: '#10b98133', color: '#6ee7b7', icon: Database },
  QUERY:        { bg: '#06b6d411', border: '#06b6d433', color: '#67e8f9', icon: Zap },
  CHECK:        { bg: '#f59e0b11', border: '#f59e0b33', color: '#fcd34d', icon: CheckCircle },
};

// ─── Animated Timeline ────────────────────────────────────────────────────────

function TurnStep({ turn, index, visible, result }) {
  const meta = ROLE_STYLE[turn.role] || ROLE_STYLE.AGENT;
  const Icon = meta.icon;

  return (
    <div style={{
      display: 'flex', gap: 12, alignItems: 'flex-start',
      opacity: visible ? 1 : 0,
      transform: visible ? 'translateY(0)' : 'translateY(12px)',
      transition: `opacity 0.4s ease ${index * 0.12}s, transform 0.4s ease ${index * 0.12}s`
    }}>
      {/* Timeline line + dot */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 10,
          background: meta.bg, border: `1px solid ${meta.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center'
        }}>
          <Icon size={14} color={meta.color} />
        </div>
        <div style={{ width: 1, flex: 1, minHeight: 16, background: '#1e2333', marginTop: 4 }} />
      </div>

      {/* Content */}
      <div style={{ flex: 1, paddingBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: meta.color, textTransform: 'uppercase', letterSpacing: 1 }}>
            {turn.role.replace('_', ' ')}
          </span>
          {result && (
            <span style={{ fontSize: 10, marginLeft: 'auto' }}>
              {result === 'PASS' ? '✅' : result === 'FAIL' ? '❌' : ''}
            </span>
          )}
        </div>
        <div style={{
          background: meta.bg, border: `1px solid ${meta.border}`,
          borderRadius: 10, padding: '10px 14px'
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0', marginBottom: 4 }}>{turn.label}</div>
          <div style={{ fontSize: 11, color: '#8892a4', lineHeight: 1.5 }}>{turn.detail}</div>
        </div>
      </div>
    </div>
  );
}

// ─── Scenario Card ─────────────────────────────────────────────────────────────

function ScenarioCard({ sc, selected, onClick, result }) {
  const Icon = sc.icon;
  const hasPassed = result?.accuracy_pct === 100;
  const hasFailed = result && result.accuracy_pct < 100;

  return (
    <button
      onClick={onClick}
      style={{
        background: selected ? `${sc.color}11` : '#151927',
        border: `1px solid ${selected ? sc.color : '#1e2333'}`,
        borderRadius: 14, padding: '16px 18px',
        cursor: 'pointer', textAlign: 'left', width: '100%',
        transition: 'all 0.2s',
        transform: selected ? 'scale(1.01)' : 'scale(1)',
        boxShadow: selected ? `0 0 20px ${sc.color}33` : 'none'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10,
          background: `${sc.color}22`, display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0
        }}>
          <Icon size={16} color={sc.color} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0' }}>{sc.label}</div>
          <div style={{ fontSize: 10, color: '#4a5568', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {sc.description}
          </div>
        </div>
        {hasPassed && <CheckCircle size={16} color="#10b981" />}
        {hasFailed && <XCircle size={16} color="#ef4444" />}
        <ChevronRight size={14} color={selected ? sc.color : '#2d3748'} />
      </div>
    </button>
  );
}

// ─── Main View ─────────────────────────────────────────────────────────────────

export default function AgentSim({ config }) {
  const [selected, setSelected] = useState(SCENARIOS[0].key);
  const [running, setRunning] = useState(false);
  const [simData, setSimData] = useState(null);
  const [visible, setVisible] = useState(true);
  const [error, setError] = useState(null);

  const sc = SCENARIOS.find(s => s.key === selected) || SCENARIOS[0];

  const handleSelect = (key) => {
    setVisible(false);
    setTimeout(() => {
      setSelected(key);
      setVisible(true);
    }, 200);
  };

  const readLatestSim = useCallback(async () => {
    try {
      const api = window.llmKosh;
      if (!api?.runKoshCommand || !config?.cartridgeRoot) return null;
      const root = config.cartridgeRoot;
      const result = await api.runKoshCommand(root, [
        'python', '-c',
        `
import json, glob
files = sorted(glob.glob(r'${root}\\\\reports\\\\benchmarks\\\\agent_sim_*.json'))
if files:
    data = json.load(open(files[-1], encoding='utf-8'))
    print(json.dumps(data))
else:
    print('null')
`.trim()
      ]);
      if (result?.stdout?.trim() !== 'null') return JSON.parse(result.stdout.trim());
    } catch { }
    return null;
  }, [config?.cartridgeRoot]);

  useEffect(() => {
    readLatestSim().then(d => d && setSimData(d));
  }, [readLatestSim]);

  const runSim = async () => {
    setRunning(true); setError(null);
    try {
      const api = window.llmKosh;
      if (!api?.runKoshCommand || !config?.cartridgeRoot) {
        setError('CLI bridge not available. Run from Electron desktop app.');
        setRunning(false); return;
      }
      await api.runKoshCommand(config.cartridgeRoot, [
        'python', `${config.cartridgeRoot}\\scripts\\agent_loop_sim.py`
      ]);
      const d = await readLatestSim();
      if (d) setSimData(d);
    } catch (e) { setError(String(e)); }
    setRunning(false);
  };

  const scenarioResult = simData?.scenarios?.[selected];
  const overall = simData?.overall;

  return (
    <div style={{
      height: '100%', display: 'flex', flexDirection: 'column',
      background: '#0e1118', padding: 24, overflow: 'hidden',
      fontFamily: "'Inter', -apple-system, sans-serif"
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24, flexShrink: 0 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 14,
          background: '#f26e2211', border: '1px solid #f26e2233',
          display: 'flex', alignItems: 'center', justifyContent: 'center'
        }}>
          <Zap size={22} color="#f26e22" />
        </div>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: '#e2e8f0', margin: 0 }}>Agent Loop Simulator</h1>
          <div style={{ fontSize: 12, color: '#4a5568', marginTop: 2 }}>
            STATE-Bench Analog — 4 Scenarios · State continuity · Staleness · Hallucination guard
          </div>
        </div>

        {/* Overall badge */}
        {overall && (
          <div style={{
            marginLeft: 'auto', display: 'flex', gap: 20,
            background: '#151927', border: '1px solid #1e2333',
            borderRadius: 12, padding: '10px 20px', alignItems: 'center'
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{
                fontSize: 20, fontWeight: 800,
                color: overall.accuracy_pct === 100 ? '#10b981' : overall.accuracy_pct >= 75 ? '#f59e0b' : '#ef4444'
              }}>
                {overall.accuracy_pct}%
              </div>
              <div style={{ fontSize: 9, color: '#4a5568' }}>OVERALL</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#10b981' }}>{overall.pass}</div>
              <div style={{ fontSize: 9, color: '#4a5568' }}>PASS</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#ef4444' }}>{overall.total - overall.pass}</div>
              <div style={{ fontSize: 9, color: '#4a5568' }}>FAIL</div>
            </div>
          </div>
        )}

        <button
          onClick={runSim}
          disabled={running}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 20px',
            background: running ? '#1e2333' : 'linear-gradient(135deg, #f26e22, #e05510)',
            border: 'none', borderRadius: 10,
            color: running ? '#4a5568' : '#fff',
            fontSize: 13, fontWeight: 700, cursor: running ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s'
          }}
        >
          {running ? <Loader size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <PlayCircle size={14} />}
          {running ? 'Running…' : 'Run Simulation'}
        </button>
      </div>

      {error && (
        <div style={{
          marginBottom: 16, padding: '10px 16px',
          background: '#ef444411', border: '1px solid #ef444433',
          borderRadius: 8, fontSize: 12, color: '#ef4444',
          display: 'flex', gap: 8, flexShrink: 0
        }}>
          <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
          {error}
        </div>
      )}

      {/* Body */}
      <div style={{ flex: 1, display: 'flex', gap: 20, overflow: 'hidden', minHeight: 0 }}>
        {/* Scenario list */}
        <div style={{ width: 300, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 10, overflowY: 'auto' }}>
          {SCENARIOS.map(s => (
            <ScenarioCard
              key={s.key}
              sc={s}
              selected={selected === s.key}
              onClick={() => handleSelect(s.key)}
              result={simData?.scenarios?.[s.key]}
            />
          ))}

          {/* Assertion summary */}
          {scenarioResult && (
            <div style={{
              background: '#151927', border: '1px solid #1e2333',
              borderRadius: 12, padding: '14px 16px', marginTop: 4
            }}>
              <div style={{ fontSize: 11, color: '#8892a4', marginBottom: 10 }}>Assertion Results</div>
              {(scenarioResult.assertions || []).map((a, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 6 }}>
                  {a.status === 'PASS'
                    ? <CheckCircle size={12} color="#10b981" style={{ flexShrink: 0, marginTop: 1 }} />
                    : <XCircle size={12} color="#ef4444" style={{ flexShrink: 0, marginTop: 1 }} />}
                  <span style={{ fontSize: 10, color: a.status === 'PASS' ? '#8892a4' : '#ef4444', lineHeight: 1.4 }}>
                    {a.label}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Timeline panel */}
        <div style={{
          flex: 1, background: '#151927', border: '1px solid #1e2333',
          borderRadius: 16, padding: 24, overflowY: 'auto'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
            {React.createElement(sc.icon, { size: 20, color: sc.color })}
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#e2e8f0' }}>{sc.label}</div>
              <div style={{ fontSize: 12, color: '#4a5568', marginTop: 2 }}>{sc.description}</div>
            </div>
            {scenarioResult && (
              <div style={{ marginLeft: 'auto', textAlign: 'center' }}>
                <div style={{
                  fontSize: 18, fontWeight: 800,
                  color: scenarioResult.accuracy_pct === 100 ? '#10b981' : '#f59e0b'
                }}>
                  {scenarioResult.accuracy_pct}%
                </div>
                <div style={{ fontSize: 9, color: '#4a5568' }}>PASS RATE</div>
              </div>
            )}
          </div>

          {sc.turns.map((turn, i) => (
            <TurnStep
              key={i}
              turn={turn}
              index={i}
              visible={visible}
              result={null}
            />
          ))}
        </div>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
