import React, { useState, useEffect, useRef } from 'react';
import {
  BarChart2, Shield, Clock, Link, RefreshCw, Zap,
  CheckCircle, XCircle, ChevronDown, ChevronUp,
  PlayCircle, AlertTriangle, Loader, ExternalLink
} from 'lucide-react';

// ─── Constants ───────────────────────────────────────────────────────────────

const CATEGORY_META = {
  temporal:    { label: 'Temporal Reasoning', icon: Clock,      color: '#6366f1', benchmark: 'LongMemEval T1' },
  staleness:   { label: 'Knowledge Update',   icon: RefreshCw,  color: '#f59e0b', benchmark: 'LongMemEval T2 / AMB' },
  multihop:    { label: 'Multi-Hop Search',   icon: Link,       color: '#8b5cf6', benchmark: 'LoCoMo / AMA-Bench' },
  abstention:  { label: 'Hallucination Guard',icon: Shield,     color: '#10b981', benchmark: 'STATE-Bench' },
  agent:       { label: 'Agent State',        icon: Zap,        color: '#f26e22', benchmark: 'MemoryArena / STATE-Bench' },
  scalability: { label: 'Scalability',        icon: BarChart2,  color: '#06b6d4', benchmark: 'AMB (1000-doc corpus)' },
};

// ─── Utilities ────────────────────────────────────────────────────────────────

function scoreColor(pct) {
  if (pct >= 80) return '#10b981';
  if (pct >= 60) return '#f59e0b';
  return '#ef4444';
}

function latencyColor(ms) {
  if (ms < 20)  return '#10b981';
  if (ms < 100) return '#f59e0b';
  return '#ef4444';
}

// ─── Animated Ring ────────────────────────────────────────────────────────────

function RingGauge({ pct, color, size = 80, stroke = 8, label }) {
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const [filled, setFilled] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => setFilled(pct), 100);
    return () => clearTimeout(t);
  }, [pct]);

  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#1e2333" strokeWidth={stroke} />
        <circle
          cx={size/2} cy={size/2} r={r}
          fill="none" stroke={color} strokeWidth={stroke}
          strokeDasharray={circ}
          strokeDashoffset={circ - (circ * filled) / 100}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 1s cubic-bezier(0.4,0,0.2,1)' }}
        />
      </svg>
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center'
      }}>
        <span style={{ fontSize: 15, fontWeight: 700, color }}>{Math.round(filled)}%</span>
        {label && <span style={{ fontSize: 9, color: '#8892a4', marginTop: 1 }}>{label}</span>}
      </div>
    </div>
  );
}

// ─── Score Card ───────────────────────────────────────────────────────────────

function ScoreCard({ catKey, data, onClick, selected }) {
  const meta = CATEGORY_META[catKey] || {};
  const Icon = meta.icon || BarChart2;
  const color = meta.color || '#6366f1';
  const pct = data?.accuracy_pct ?? 0;
  const avgQ = data?.avg_query_ms ?? 0;

  return (
    <button
      onClick={onClick}
      style={{
        background: selected
          ? `linear-gradient(135deg, ${color}22 0%, #1a1f2e 100%)`
          : '#151927',
        border: `1px solid ${selected ? color : '#1e2333'}`,
        borderRadius: 16,
        padding: '20px 18px',
        cursor: 'pointer',
        textAlign: 'left',
        transition: 'all 0.2s',
        transform: selected ? 'scale(1.02)' : 'scale(1)',
        boxShadow: selected ? `0 0 24px ${color}44` : '0 2px 8px #00000033',
        display: 'flex', flexDirection: 'column', gap: 12
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 10,
            background: `${color}22`, display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <Icon size={16} color={color} />
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0' }}>{meta.label}</div>
            <div style={{ fontSize: 10, color: '#4a5568' }}>{meta.benchmark}</div>
          </div>
        </div>
        <RingGauge pct={pct} color={scoreColor(pct)} size={60} stroke={6} />
      </div>

      {/* Stats row */}
      <div style={{ display: 'flex', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 9, color: '#4a5568', textTransform: 'uppercase', letterSpacing: 1 }}>Pass/Fail</div>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', marginTop: 2 }}>
            <span style={{ color: '#10b981' }}>{data?.pass ?? 0}</span>
            <span style={{ color: '#4a5568' }}> / {data?.total ?? 0}</span>
          </div>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 9, color: '#4a5568', textTransform: 'uppercase', letterSpacing: 1 }}>Avg Latency</div>
          <div style={{ fontSize: 13, fontWeight: 600, marginTop: 2, color: latencyColor(avgQ) }}>
            {avgQ.toFixed(1)}ms
          </div>
        </div>
      </div>

      {/* Mini bar */}
      <div style={{ height: 4, background: '#1e2333', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{
          height: '100%', width: `${pct}%`,
          background: `linear-gradient(90deg, ${color} 0%, ${color}aa 100%)`,
          borderRadius: 4,
          transition: 'width 1.2s cubic-bezier(0.4,0,0.2,1)'
        }} />
      </div>
    </button>
  );
}

// ─── Latency Bar Chart ────────────────────────────────────────────────────────

function LatencyChart({ results }) {
  if (!results?.length) return null;
  const maxMs = Math.max(...results.map(r => r.query_ms || 0), 1);

  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 11, color: '#8892a4', marginBottom: 8 }}>Query Latency per Test Case (ms)</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
        {results.map(r => (
          <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 80, fontSize: 10, color: '#4a5568', flexShrink: 0, fontFamily: 'monospace' }}>
              {r.id}
            </div>
            <div style={{ flex: 1, height: 10, background: '#1e2333', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${(r.query_ms / maxMs) * 100}%`,
                background: latencyColor(r.query_ms),
                borderRadius: 3,
                transition: 'width 0.8s ease'
              }} />
            </div>
            <div style={{ width: 48, fontSize: 10, color: '#8892a4', textAlign: 'right' }}>
              {r.query_ms?.toFixed(1)}ms
            </div>
            <div>{r.status === 'PASS'
              ? <CheckCircle size={12} color="#10b981" />
              : <XCircle size={12} color="#ef4444" />}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Result Row ───────────────────────────────────────────────────────────────

function ResultRow({ r }) {
  const [open, setOpen] = useState(false);
  const pass = r.status === 'PASS';
  return (
    <div style={{
      background: '#11141f',
      border: `1px solid ${pass ? '#10b98122' : '#ef444422'}`,
      borderRadius: 10, overflow: 'hidden',
      marginBottom: 6
    }}>
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
          cursor: 'pointer', userSelect: 'none'
        }}
        onClick={() => setOpen(o => !o)}
      >
        {pass
          ? <CheckCircle size={14} color="#10b981" />
          : <XCircle size={14} color="#ef4444" />}
        <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#8892a4', width: 90, flexShrink: 0 }}>
          {r.id}
        </span>
        <span style={{ flex: 1, fontSize: 12, color: '#c7d2e0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {r.query}
        </span>
        <span style={{
          fontSize: 11, fontWeight: 700, width: 40, textAlign: 'right',
          color: r.f1 >= 0.3 ? '#10b981' : '#ef4444'
        }}>
          {typeof r.f1 === 'number' ? `F1:${r.f1.toFixed(2)}` : ''}
        </span>
        <span style={{ fontSize: 11, color: '#4a5568', width: 50, textAlign: 'right' }}>
          {r.query_ms?.toFixed(1)}ms
        </span>
        {open ? <ChevronUp size={12} color="#4a5568" /> : <ChevronDown size={12} color="#4a5568" />}
      </div>

      {open && (
        <div style={{ padding: '0 14px 14px', borderTop: '1px solid #1e2333' }}>
          <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div>
              <div style={{ fontSize: 10, color: '#4a5568', textTransform: 'uppercase', letterSpacing: 1 }}>Expected Answer</div>
              <div style={{ fontSize: 11, color: '#a0aec0', marginTop: 4, lineHeight: 1.5 }}>{r.expected}</div>
            </div>
            <div>
              <div style={{ fontSize: 10, color: '#4a5568', textTransform: 'uppercase', letterSpacing: 1 }}>Context Retrieved</div>
              <div style={{ fontSize: 11, color: '#718096', marginTop: 4, lineHeight: 1.5, fontStyle: 'italic' }}>
                {r.context_preview || 'No context retrieved'}
              </div>
            </div>
          </div>
          {r.stale_leaked && (
            <div style={{
              marginTop: 10, padding: '6px 10px', background: '#f59e0b11',
              border: '1px solid #f59e0b44', borderRadius: 6, fontSize: 11, color: '#f59e0b'
            }}>
              ⚠️ Stale value leaked into context — staleness guard partially triggered
            </div>
          )}
          {r.hallucinated && (
            <div style={{
              marginTop: 10, padding: '6px 10px', background: '#ef444411',
              border: '1px solid #ef444444', borderRadius: 6, fontSize: 11, color: '#ef4444'
            }}>
              🚨 Hallucinated content detected in abstention test
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Detail Panel ─────────────────────────────────────────────────────────────

function CategoryDetailPanel({ catKey, data, results }) {
  const meta = CATEGORY_META[catKey] || {};
  const Icon = meta.icon || BarChart2;
  const color = meta.color || '#6366f1';

  return (
    <div style={{
      background: '#151927', border: `1px solid ${color}33`,
      borderRadius: 16, padding: 24, flex: 1, overflow: 'hidden',
      display: 'flex', flexDirection: 'column'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <div style={{
          width: 42, height: 42, borderRadius: 12,
          background: `${color}22`, display: 'flex', alignItems: 'center', justifyContent: 'center'
        }}>
          <Icon size={20} color={color} />
        </div>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#e2e8f0' }}>{meta.label}</div>
          <div style={{ fontSize: 12, color: '#4a5568' }}>Mapped to: {meta.benchmark}</div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 12 }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 22, fontWeight: 800, color: scoreColor(data?.accuracy_pct ?? 0) }}>
              {data?.accuracy_pct ?? 0}%
            </div>
            <div style={{ fontSize: 10, color: '#4a5568' }}>Accuracy</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 22, fontWeight: 800, color: latencyColor(data?.avg_query_ms ?? 0) }}>
              {data?.avg_query_ms?.toFixed(1) ?? 0}ms
            </div>
            <div style={{ fontSize: 10, color: '#4a5568' }}>Avg Query</div>
          </div>
        </div>
      </div>

      <LatencyChart results={results} />

      <div style={{ marginTop: 20, overflowY: 'auto', flex: 1 }}>
        <div style={{ fontSize: 11, color: '#8892a4', marginBottom: 8 }}>Test Cases</div>
        {(results || []).map(r => <ResultRow key={r.id} r={r} />)}
      </div>
    </div>
  );
}

// ─── Overall Summary Bar ──────────────────────────────────────────────────────

function SummaryHeader({ overall }) {
  const pct = overall?.accuracy_pct ?? 0;
  return (
    <div style={{
      background: `linear-gradient(135deg, #1a1f2e 0%, #151927 100%)`,
      border: '1px solid #1e2333',
      borderRadius: 16, padding: '20px 28px',
      display: 'flex', alignItems: 'center', gap: 32, marginBottom: 24,
      flexShrink: 0
    }}>
      <div>
        <div style={{ fontSize: 11, color: '#4a5568', textTransform: 'uppercase', letterSpacing: 1 }}>Overall Accuracy</div>
        <div style={{ fontSize: 40, fontWeight: 900, color: scoreColor(pct), lineHeight: 1.1 }}>{pct}%</div>
        <div style={{ fontSize: 12, color: '#8892a4' }}>{overall?.pass}/{overall?.total} cases passed</div>
      </div>

      <div style={{ flex: 1 }}>
        <div style={{ height: 12, background: '#1e2333', borderRadius: 8, overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: 8,
            background: `linear-gradient(90deg, ${scoreColor(pct)} 0%, ${scoreColor(pct)}88 100%)`,
            width: `${pct}%`,
            transition: 'width 1.5s cubic-bezier(0.4,0,0.2,1)',
            boxShadow: `0 0 12px ${scoreColor(pct)}66`
          }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
          <span style={{ fontSize: 10, color: '#4a5568' }}>0%</span>
          <span style={{ fontSize: 10, color: '#4a5568' }}>STATE-Bench · AMB · LongMemEval · LoCoMo · AMA-Bench</span>
          <span style={{ fontSize: 10, color: '#4a5568' }}>100%</span>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 24 }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 24, fontWeight: 800, color: '#10b981' }}>{overall?.pass ?? 0}</div>
          <div style={{ fontSize: 10, color: '#4a5568' }}>PASS</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 24, fontWeight: 800, color: '#ef4444' }}>{(overall?.total ?? 0) - (overall?.pass ?? 0)}</div>
          <div style={{ fontSize: 10, color: '#4a5568' }}>FAIL</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 24, fontWeight: 800, color: latencyColor(overall?.avg_query_ms ?? 0) }}>
            {overall?.avg_query_ms?.toFixed(1) ?? '—'}ms
          </div>
          <div style={{ fontSize: 10, color: '#4a5568' }}>Avg Query</div>
        </div>
      </div>
    </div>
  );
}

// ─── Empty State ──────────────────────────────────────────────────────────────

function EmptyState({ onRun, running }) {
  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: 20
    }}>
      <div style={{
        width: 80, height: 80, borderRadius: 24,
        background: '#1e2333', display: 'flex', alignItems: 'center', justifyContent: 'center'
      }}>
        <BarChart2 size={36} color="#4a5568" />
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 20, fontWeight: 700, color: '#e2e8f0' }}>No Benchmark Results Yet</div>
        <div style={{ fontSize: 13, color: '#4a5568', marginTop: 6, maxWidth: 360 }}>
          Run the 60-case stress benchmark to validate LLM-Kosh against
          STATE-Bench, LongMemEval, LoCoMo, AMA-Bench, and AMB categories.
        </div>
      </div>
      <button
        onClick={onRun}
        disabled={running}
        style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '14px 32px',
          background: running ? '#1e2333' : 'linear-gradient(135deg, #f26e22, #e05510)',
          border: 'none', borderRadius: 12, cursor: running ? 'not-allowed' : 'pointer',
          color: '#fff', fontSize: 14, fontWeight: 700, transition: 'all 0.2s'
        }}
      >
        {running ? <Loader size={18} style={{ animation: 'spin 1s linear infinite' }} /> : <PlayCircle size={18} />}
        {running ? 'Benchmark Running…' : 'Run 60-Case Benchmark'}
      </button>
    </div>
  );
}

// ─── Main View ────────────────────────────────────────────────────────────────

export default function Benchmarks({ config }) {
  const [benchData, setBenchData] = useState(null);
  const [selectedCat, setSelectedCat] = useState(null);
  const [running, setRunning] = useState(false);
  const [runLog, setRunLog] = useState([]);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  // Try to load latest benchmark JSON from reports/benchmarks/
  const loadLatest = async () => {
    try {
      const root = config?.cartridgeRoot;
      if (!root) return;
      // Read the reports/benchmarks directory for stress_results_*.json
      const dir = root.replace(/\\/g, '/');
      const resp = await window.llmKosh?.runKoshCommand?.(root, [
        'python',
        `${root}/scripts/_read_latest_bench.py`.replace(/\\/g, '/'),
      ]);
      // Fallback: try via the api readDirectory
    } catch { /* no results yet */ }
  };

  // Attempt to read the latest JSON result file via the CLI bridge
  const readLatestResult = async () => {
    try {
      const api = window.llmKosh;
      if (!api?.runKoshCommand || !config?.cartridgeRoot) return null;
      const root = config.cartridgeRoot;
      const result = await api.runKoshCommand(root, [
        'python', '-c',
        `
import json, glob, sys
from pathlib import Path
files = sorted(glob.glob(r'${root}\\\\reports\\\\benchmarks\\\\stress_results_*.json'))
if files:
    data = json.load(open(files[-1], encoding='utf-8'))
    print(json.dumps(data))
else:
    print('null')
`.trim()
      ]);
      if (result?.stdout && result.stdout.trim() !== 'null') {
        return JSON.parse(result.stdout.trim());
      }
    } catch (e) {
      console.warn('Could not read benchmark result:', e);
    }
    return null;
  };

  useEffect(() => {
    readLatestResult().then(data => {
      if (data) {
        setBenchData(data);
        setSelectedCat(Object.keys(data.categories || {})[0] || null);
      }
    });
  }, [config]);

  const runBenchmark = async () => {
    setRunning(true);
    setError(null);
    setRunLog([]);
    try {
      const api = window.llmKosh;
      if (!api?.runKoshCommand || !config?.cartridgeRoot) {
        setError('No CLI bridge available. Run from the desktop app.');
        setRunning(false);
        return;
      }
      const root = config.cartridgeRoot;
      setRunLog(l => [...l, '⚙️  Starting 60-case stress benchmark...']);
      const result = await api.runKoshCommand(root, [
        'python', `${root}\\scripts\\stress_bench.py`
      ]);
      if (result?.stdout) {
        const lines = result.stdout.split('\n');
        setRunLog(lines);
      }
      // Re-read result
      const data = await readLatestResult();
      if (data) {
        setBenchData(data);
        setSelectedCat(Object.keys(data.categories || {})[0] || null);
      }
    } catch (e) {
      setError(String(e));
    }
    setRunning(false);
  };

  const catKeys = benchData ? Object.keys(benchData.categories || {}) : [];
  const selResults = benchData && selectedCat
    ? benchData.results?.filter(r => {
        // Match category key to result category name
        const meta = CATEGORY_META[selectedCat];
        return r.category === meta?.label ||
               r.id?.startsWith(selectedCat === 'temporal' ? 'tmp' :
                                selectedCat === 'staleness' ? 'stale' :
                                selectedCat === 'multihop' ? 'hop' :
                                selectedCat === 'abstention' ? 'abs' :
                                selectedCat === 'agent' ? 'agent' : 'scale');
      })
    : [];

  return (
    <div style={{
      height: '100%', display: 'flex', flexDirection: 'column',
      background: '#0e1118', padding: 24, gap: 0, overflow: 'hidden',
      fontFamily: "'Inter', -apple-system, sans-serif"
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24, flexShrink: 0 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 14,
          background: 'linear-gradient(135deg, #f26e2222, #6366f122)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          border: '1px solid #f26e2233'
        }}>
          <BarChart2 size={22} color="#f26e22" />
        </div>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: '#e2e8f0', margin: 0 }}>
            Agentic Memory Benchmark
          </h1>
          <div style={{ fontSize: 12, color: '#4a5568', marginTop: 2 }}>
            STATE-Bench · LongMemEval · LoCoMo · AMA-Bench · AMB — 60 test cases
          </div>
        </div>
        {benchData && (
          <button
            onClick={runBenchmark}
            disabled={running}
            style={{
              marginLeft: 'auto',
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '10px 20px',
              background: running ? '#1e2333' : '#f26e2211',
              border: '1px solid #f26e2244',
              borderRadius: 10, cursor: running ? 'not-allowed' : 'pointer',
              color: running ? '#4a5568' : '#f26e22',
              fontSize: 13, fontWeight: 600, transition: 'all 0.2s'
            }}
          >
            {running
              ? <><Loader size={14} style={{ animation: 'spin 1s linear infinite' }} /> Running…</>
              : <><RefreshCw size={14} /> Re-run</>}
          </button>
        )}
      </div>

      {!benchData ? (
        <EmptyState onRun={runBenchmark} running={running} />
      ) : (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Summary */}
          <SummaryHeader overall={benchData.overall} />

          {/* Body */}
          <div style={{ flex: 1, display: 'flex', gap: 20, overflow: 'hidden', minHeight: 0 }}>
            {/* Score grid */}
            <div style={{
              width: 340, flexShrink: 0, overflowY: 'auto',
              display: 'flex', flexDirection: 'column', gap: 10,
              paddingRight: 4
            }}>
              {catKeys.map(k => (
                <ScoreCard
                  key={k}
                  catKey={k}
                  data={benchData.categories[k]}
                  onClick={() => setSelectedCat(k)}
                  selected={selectedCat === k}
                />
              ))}

              {/* Timestamp */}
              <div style={{ fontSize: 10, color: '#2d3748', textAlign: 'center', paddingTop: 8 }}>
                Generated {benchData.generated_at?.slice(0, 19).replace('T', ' ')} UTC
              </div>
            </div>

            {/* Detail panel */}
            <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              {selectedCat && (
                <CategoryDetailPanel
                  catKey={selectedCat}
                  data={benchData.categories[selectedCat]}
                  results={selResults}
                />
              )}
            </div>
          </div>
        </div>
      )}

      {/* Run Log */}
      {runLog.length > 0 && (
        <div style={{
          marginTop: 16, background: '#0a0d14',
          border: '1px solid #1e2333', borderRadius: 10,
          padding: '12px 16px', maxHeight: 140, overflowY: 'auto',
          fontFamily: 'monospace', fontSize: 11, color: '#8892a4', flexShrink: 0
        }}>
          {runLog.map((l, i) => <div key={i}>{l}</div>)}
        </div>
      )}

      {error && (
        <div style={{
          marginTop: 12, padding: '10px 16px',
          background: '#ef444411', border: '1px solid #ef444433',
          borderRadius: 8, fontSize: 12, color: '#ef4444', display: 'flex', gap: 8, flexShrink: 0
        }}>
          <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
          {error}
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
