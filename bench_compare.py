from __future__ import annotations
import json, math, shutil, tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter, defaultdict, deque
from typing import Any

from llm_kosh.engine.reasoning import ReasoningEngine
from llm_kosh.engine.reasoning.causal_dag import EdgeType, EdgeOrigin, EdgeRole, EdgeProvenance, EvidenceRef
from llm_kosh.engine.reasoning.causal_retrieval import tokenize

UTC=timezone.utc
def dt(s): return datetime.fromisoformat(s.replace('Z','+00:00'))
def ts(s): return dt(s).timestamp()

@dataclass
class FactRec:
    key: str
    id: str
    content: str
    valid_from: datetime
    valid_until: datetime|None

# ---------- Corpus ----------
def build_engine(root: Path):
    if root.exists(): shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    eng = ReasoningEngine(root)
    facts: dict[str, FactRec] = {}
    def add(key, content, vf, vu=None, conf=0.9):
        t=dt(vf); u=dt(vu) if vu else None
        fid=eng.dag.add_fact(content=content, ingested_at=dt('2026-06-01T00:00:00+00:00'), documented_at=t, valid_from=t, valid_until=u, confidence=conf, source='benchmark')
        facts[key]=FactRec(key,fid,content,t,u)
        return fid
    # temporal policy corpus
    remote_old = add('remote_old','Remote work policy: employees may work from home three days per week under Policy A. Valid Jan to Mar.', '2026-01-01T00:00:00+00:00','2026-04-01T00:00:00+00:00')
    remote_new = add('remote_new','Remote work policy: employees must be in office four days per week under Policy B. Valid from April onward. This supersedes Policy A.', '2026-04-01T00:00:00+00:00')
    eng.add_edge_at(remote_old, remote_new, 'SUPERSEDES', .95, dt('2026-04-01T00:00:00+00:00'), origin='OBSERVED', role='MECHANISTIC')
    # incident corpus
    dep = add('deployment','Service X deployment patch P17 was deployed at 12:05 UTC.', '2026-05-10T12:05:00+00:00')
    leak = add('leak','Patch P17 introduced a memory leak in worker service X.', '2026-05-10T12:20:00+00:00')
    heap = add('heap','Heap saturation reached 97 percent on service X workers.', '2026-05-10T13:00:00+00:00')
    outage = add('outage','Service X outage occurred at 13:30 UTC due to worker saturation.', '2026-05-10T13:30:00+00:00')
    traffic = add('traffic','Traffic spike occurred during promotion window and may have contributed to saturation.', '2026-05-10T13:05:00+00:00', conf=.65)
    status = add('status_contradiction','Status report at 13:10 says no memory pressure was observed on service X.', '2026-05-10T13:10:00+00:00', conf=.7)
    mitigation = add('mitigation_expired','Old memory mitigation expired before the outage window.', '2026-05-09T00:00:00+00:00', '2026-05-10T12:00:00+00:00', conf=.8)
    eng.add_edge_at(dep, leak, 'CAUSES', .90, facts['deployment'].valid_from, origin='OBSERVED', role='MECHANISTIC')
    eng.add_edge_at(leak, heap, 'CAUSES', .88, facts['leak'].valid_from, origin='OBSERVED', role='MECHANISTIC')
    eng.add_edge_at(heap, outage, 'CAUSES', .86, facts['heap'].valid_from, origin='OBSERVED', role='MECHANISTIC')
    eng.add_edge_at(traffic, heap, 'CAUSES', .45, facts['traffic'].valid_from, origin='HYPOTHETICAL', role='PREDICTIVE')
    eng.add_edge_at(status, heap, 'CONTRADICTS', .75, facts['status_contradiction'].valid_from, origin='OBSERVED', role='MECHANISTIC')
    # inferred compressed shortcut from deployment to outage
    e_short = eng.add_edge_at(dep, outage, 'INFERS', .42, facts['deployment'].valid_from, established_by='inference', origin='INFERRED', role='COMPRESSED', derived_from=['deployment->leak','leak->heap','heap->outage'])
    for _ in range(3): eng.reinforce_edge(e_short, dt('2026-05-11T00:00:00+00:00'))
    # hyperedge corpus
    flag = add('flag','Checkout feature flag F was enabled at 09:00.', '2026-05-12T09:00:00+00:00')
    schema = add('schema','Checkout schema migration S was applied at 09:05.', '2026-05-12T09:05:00+00:00')
    fail = add('checkout_fail','Checkout failure began after feature flag F and schema migration S were both active.', '2026-05-12T09:15:00+00:00')
    eng.dag.add_hyperedge({flag, schema}, fail, EdgeType.CAUSES, .82, dt('2026-05-12T09:05:00+00:00'), None, EdgeProvenance(origin=EdgeOrigin.OBSERVED, role=EdgeRole.CAUSAL, evidence_refs=[EvidenceRef('postmortem#checkout','joint condition')]))
    eng._retrieval = __import__('llm_kosh.engine.reasoning.causal_retrieval', fromlist=['CausalRetrieval']).CausalRetrieval(eng.dag)
    return eng, facts

# ---------- Baselines ----------
def toks(s): return set(tokenize(s))
def active(facts: dict[str,FactRec], time_s: str|None):
    if not time_s: return list(facts.values())
    t=ts(time_s)
    return [f for f in facts.values() if f.valid_from.timestamp() <= t and (f.valid_until is None or f.valid_until.timestamp() > t)]
def overlap_score(q, text):
    qt=toks(q); tt=toks(text)
    return len(qt & tt) / max(1, len(qt))

def keyword_rag(q, facts, query_time=None, k=5):
    rows=list(facts.values()) # no temporal filter, common weakness
    rows=sorted(rows, key=lambda f: (-overlap_score(q,f.content), -f.valid_from.timestamp()))[:k]
    return {f.key for f in rows if overlap_score(q,f.content)>0}

def temporal_rag(q, facts, query_time=None, k=5):
    rows=active(facts, query_time)
    rows=sorted(rows, key=lambda f: (-overlap_score(q,f.content), -f.valid_from.timestamp()))[:k]
    return {f.key for f in rows if overlap_score(q,f.content)>0}

def agent_memory(q, facts, query_time=None, k=5):
    rows=active(facts, query_time) if query_time else list(facts.values())
    rows=sorted(rows, key=lambda f: (-(0.6*overlap_score(q,f.content)+0.4*(f.valid_from.timestamp()/ts('2026-12-31T00:00:00+00:00')))))[:k]
    return {f.key for f in rows if overlap_score(q,f.content)>0}

def graph_rag(q, facts, eng, query_time=None, k=3, hops=2):
    # Keyword anchors, then binary edge expansion only; no provenance, no fiber/critic, no hyperedge joint semantics.
    ids_to_key={v.id:k for k,v in facts.items()}
    anchors=sorted(active(facts,query_time) if query_time else facts.values(), key=lambda f:-overlap_score(q,f.content))[:k]
    seen={a.id for a in anchors if overlap_score(q,a.content)>0}
    frontier=list(seen)
    t=ts(query_time) if query_time else ts('2026-06-01T00:00:00+00:00')
    for _ in range(hops):
        nxt=[]
        for fid in frontier:
            for e in eng.dag.get_outgoing_edges(fid,t):
                if e.target_id not in seen:
                    seen.add(e.target_id); nxt.append(e.target_id)
        frontier=nxt
    return {ids_to_key[i] for i in seen if i in ids_to_key}

def self_rag_like(q, facts, query_time=None):
    # retrieve temporally, then add contradiction if both sides lexical-related; no causal chain expansion or provenance.
    result=temporal_rag(q,facts,query_time,k=6)
    # tries to include contradiction fact if query asks contradict
    if 'contradict' in q.lower() or 'evidence' in q.lower():
        result |= {k for k,f in facts.items() if overlap_score('contradict status report memory pressure service x',f.content)>0.25}
    return result

def react_like(q, facts, eng, query_time=None):
    # step 1 temporal rag; step 2 follow causes/contradiction terms one hop; no multi-path provenance.
    base=temporal_rag(q,facts,query_time,k=4)
    ids={facts[k].id for k in base}
    ids_to_key={v.id:k for k,v in facts.items()}
    t=ts(query_time) if query_time else ts('2026-06-01T00:00:00+00:00')
    for fid in list(ids):
        for e in eng.dag.get_outgoing_edges(fid,t):
            ids.add(e.target_id)
    return {ids_to_key[i] for i in ids if i in ids_to_key}

# ---------- TheHypoKosh output extraction ----------
def hypo(q, eng, facts, query_time=None, mode='BALANCED', depth=4):
    res=eng.query(q, temporal_context=query_time, depth=depth, reasoning_mode=mode)
    ids_to_key={v.id:k for k,v in facts.items()}
    found={ids_to_key[fid] for fid in res.bundle.fibers.keys() if fid in ids_to_key}
    edges=[]
    for fiber in res.bundle.fibers.values():
        for p in fiber.paths:
            for e in p.edges:
                if e.source_id in ids_to_key and e.target_id in ids_to_key:
                    edges.append((ids_to_key[e.source_id], ids_to_key[e.target_id], e.edge_type.value, e.provenance.origin.value, e.provenance.role.value, e.provenance.promotion_status))
    return found, res, edges

# ---------- Evaluation tasks ----------
def score_set(found, expected, forbidden=()):
    expected=set(expected); forbidden=set(forbidden)
    hit=len(found & expected); fp_forbidden=len(found & forbidden)
    return max(0, hit/len(expected) - 0.25*fp_forbidden) if expected else (1.0 if not found else 0.0)

def main():
    root=Path('/tmp/thehypokosh_bench_cart')
    eng,facts=build_engine(root)
    tasks=[
        dict(id='temporal_feb', q='What remote work policy was true in February?', time='2026-02-15T00:00:00+00:00', expected=['remote_old'], forbidden=['remote_new']),
        dict(id='temporal_may', q='What remote work policy was true in May?', time='2026-05-15T00:00:00+00:00', expected=['remote_new'], forbidden=['remote_old']),
        dict(id='root_cause_primary', q='Why did service X fail? deployment memory leak saturation outage', time='2026-05-10T14:00:00+00:00', expected=['deployment','leak','heap','outage']),
        dict(id='contradiction', q='What evidence contradicts the memory leak saturation conclusion for service X?', time='2026-05-10T14:00:00+00:00', expected=['status_contradiction','heap']),
        dict(id='alternative_path', q='What alternative explanation should be considered for service X outage traffic spike saturation?', time='2026-05-10T14:00:00+00:00', expected=['traffic','heap','outage']),
        dict(id='inferred_vs_discovered', q='Did deployment directly cause outage or is it inferred from a chain?', time='2026-05-10T14:00:00+00:00', expected=['deployment','leak','heap','outage']),
        dict(id='hyperedge_joint', q='Why did checkout fail when feature flag F and schema migration S were both active?', time='2026-05-12T10:00:00+00:00', expected=['flag','schema','checkout_fail']),
        dict(id='no_evidence', q='What caused the banana moonbeam payroll dragon?', time='2026-05-12T10:00:00+00:00', expected=[]),
    ]
    baseline_funcs={
        'KeywordRAG': lambda t: keyword_rag(t['q'],facts,t.get('time')),
        'TemporalRAG': lambda t: temporal_rag(t['q'],facts,t.get('time')),
        'AgentMemory': lambda t: agent_memory(t['q'],facts,t.get('time')),
        'GraphRAG': lambda t: graph_rag(t['q'],facts,eng,t.get('time')),
        'SelfRAG_like': lambda t: self_rag_like(t['q'],facts,t.get('time')),
        'ReAct_like': lambda t: react_like(t['q'],facts,eng,t.get('time')),
    }
    details=[]
    totals={name:0.0 for name in baseline_funcs}
    totals['TheHypoKosh']=0.0
    feature_scores=Counter()
    feature_total=Counter()
    for t in tasks:
        row={'id':t['id'], 'query':t['q'], 'expected':t['expected']}
        for name,fn in baseline_funcs.items():
            found=fn(t)
            sc=score_set(found,t['expected'],t.get('forbidden',[]))
            row[name]={'found':sorted(found),'score':round(sc,3)}
            totals[name]+=sc
        found,res,edges=hypo(t['q'],eng,facts,t.get('time'))
        if t['id']=='no_evidence':
            sc=1.0 if res.stability.status=='no_evidence' and res.stability.abstain else 0.0
        else:
            sc=score_set(found,t['expected'],t.get('forbidden',[]))
        row['TheHypoKosh']={'found':sorted(found),'score':round(sc,3),'stability':res.stability.status,'abstain':res.stability.abstain,'edges':edges[:12]}
        totals['TheHypoKosh']+=sc
        # feature checks
        if t['id']=='inferred_vs_discovered':
            has_inferred_compressed=any(e[0]=='deployment' and e[1]=='outage' and e[3]=='INFERRED' and e[4]=='COMPRESSED' for e in edges)
            has_mechanistic=all(any(a==x and b==y and role in ('MECHANISTIC','CAUSAL') for a,b,typ,orig,role,prom in edges) for x,y in [('deployment','leak'),('leak','heap'),('heap','outage')])
            feature_scores['provenance_inferred_compressed']+=1 if has_inferred_compressed else 0; feature_total['provenance_inferred_compressed']+=1
            feature_scores['mechanistic_chain_preserved']+=1 if has_mechanistic else 0; feature_total['mechanistic_chain_preserved']+=1
        if t['id']=='hyperedge_joint':
            has_joint=any(e[2]=='CAUSES' and 'he.' in ''.join([str(x) for x in e]) for e in edges) # synthetic does not expose he id in tuple, weaker below
            found_all={'flag','schema','checkout_fail'}.issubset(found)
            feature_scores['hyperedge_joint_sources']+=1 if found_all else 0; feature_total['hyperedge_joint_sources']+=1
        if t['id']=='no_evidence':
            feature_scores['no_evidence_abstain']+=1 if (res.stability.status=='no_evidence' and res.stability.abstain) else 0; feature_total['no_evidence_abstain']+=1
        details.append(row)
    avg={k:round(v/len(tasks),3) for k,v in totals.items()}
    feat={k: f"{feature_scores[k]}/{feature_total[k]}" for k in feature_total}
    out={'benchmark':'temporal_causal_provenance_v0','tasks':len(tasks),'average_scores':avg,'feature_checks':feat,'details':details}
    Path('reports/benchmarks').mkdir(parents=True,exist_ok=True)
    Path('reports/benchmarks/thehypokosh_comparative_benchmark_v0.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    # markdown
    lines=['# TheHypoKosh Comparative Benchmark v0','', 'This is a deterministic, synthetic benchmark over temporal-causal-provenance tasks. It compares representative baselines, not all published implementations.', '', '## Average scores', '', '| System | Avg score |','|---|---:|']
    for k,v in sorted(avg.items(), key=lambda kv:-kv[1]): lines.append(f'| {k} | {v:.3f} |')
    lines += ['', '## Feature checks','']
    for k,v in feat.items(): lines.append(f'- {k}: {v}')
    lines += ['', '## Per task','']
    for d in details:
        lines.append(f"### {d['id']}")
        lines.append(f"Expected: `{d['expected']}`")
        for k in list(baseline_funcs)+['TheHypoKosh']:
            lines.append(f"- {k}: score={d[k]['score']} found={d[k]['found']}")
        lines.append('')
    Path('reports/benchmarks/thehypokosh_comparative_benchmark_v0.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'average_scores':avg,'feature_checks':feat},indent=2))

if __name__=='__main__': main()
