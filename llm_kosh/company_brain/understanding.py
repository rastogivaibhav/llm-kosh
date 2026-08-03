"""Deterministic session and episode understanding over reference-first evidence.

The first implementation deliberately targets JSON Lines conversation/event
exports.  It stores compact normalized summaries and native locators, never a
second copy of the registered source artifact.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from llm_kosh.core.utils import now_iso

from .models import (
    AccessPolicy,
    EpisodeInput,
    EvidenceReference,
    MemoryInput,
    NormalizedEventInput,
    Principal,
    SessionInput,
)
from .store import CompanyBrainStore


PIPELINE_VERSION = "session-episode-v1"
MAX_LINE_BYTES = 1_048_576
MAX_EVENT_SUMMARY = 2_000
DEFAULT_MAX_EVENTS = 100_000
EPISODE_GAP_SECONDS = 45 * 60

_GOAL_VERBS = re.compile(
    r"\b(build|create|implement|fix|debug|investigate|analyse|analyze|design|"
    r"migrate|refactor|deploy|test|review|update|add|remove|write|plan)\b",
    re.IGNORECASE,
)
_COMPLETION = re.compile(
    r"\b(completed|complete|implemented|fixed|resolved|deployed|done|"
    r"tests? passed|passing|successful|success)\b",
    re.IGNORECASE,
)
_BLOCKED = re.compile(r"\b(blocked|cannot proceed|can't proceed|waiting for|unavailable)\b", re.I)
_ABANDONED = re.compile(r"\b(abandoned|cancelled|canceled|rolled back|rollback)\b", re.I)
_SECRET_VALUE = re.compile(
    r"(?i)\b(api[_ -]?key|password|passwd|secret|access[_ -]?token|bearer)\b"
    r"(\s*[:=]\s*|\s+)([^\s,;]{4,})"
)
_TOKEN = re.compile(r"[A-Za-z0-9_]+")


def _clean_text(value: Any) -> str:
    """Flatten common message shapes into a bounded, redacted summary."""
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    elif isinstance(value, (int, float, bool)):
        text = str(value)
    elif isinstance(value, list):
        text = " ".join(filter(None, (_clean_text(item) for item in value)))
    elif isinstance(value, dict):
        preferred = []
        for key in ("text", "content", "message", "summary", "description", "subject", "output"):
            if key in value:
                preferred.append(_clean_text(value[key]))
        text = " ".join(filter(None, preferred))
        if not text:
            text = " ".join(
                f"{key}: {_clean_text(item)}"
                for key, item in list(value.items())[:12]
                if key.lower() not in {"password", "secret", "token", "api_key", "apikey"}
            )
    else:
        text = str(value)
    text = _SECRET_VALUE.sub(lambda match: f"{match.group(1)}: [REDACTED]", text)
    return " ".join(text.split())[:MAX_EVENT_SUMMARY]


def _first(record: Dict[str, Any], *paths: str) -> Any:
    for path in paths:
        value: Any = record
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                value = None
                break
            value = value[part]
        if value not in (None, "", [], {}):
            return value
    return None


def _event_type(record: Dict[str, Any], role: str) -> str:
    native = str(_first(record, "event_type", "type", "kind") or "").lower()
    if role in {"system", "developer"}:
        return "system"
    mappings = (
        (("tool_result", "function_result", "tool_output"), "tool_result"),
        (("tool_call", "function_call"), "tool_call"),
        (("file_change", "patch", "file_edit"), "file_change"),
        (("document_change", "document_edit"), "document_change"),
        (("ticket", "issue_change"), "ticket_change"),
        (("commit",), "commit"),
        (("handoff", "subagent"), "handoff"),
        (("checkpoint",), "checkpoint"),
    )
    for needles, canonical in mappings:
        if any(needle in native for needle in needles):
            return canonical
    if role in {"user", "assistant", "agent", "human"} or _first(record, "content", "message", "text"):
        return "message"
    return "other"


def _actor_type(role: str, event_type: str) -> str:
    if role in {"user", "human"}:
        return "person"
    if event_type in {"tool_call", "tool_result"} or role == "tool":
        return "tool"
    if role in {"system", "developer"}:
        return "system"
    return "agent"


def _projects(record: Dict[str, Any], explicit: str) -> List[str]:
    values: List[str] = []
    if explicit:
        values.append(explicit)
    for path in ("project_id", "project", "repo", "repository", "workspace", "cwd"):
        value = _first(record, path)
        if isinstance(value, str) and value.strip():
            candidate = value.strip().replace("\\", "/").rstrip("/").split("/")[-1]
            if candidate and candidate not in values:
                values.append(candidate[:180])
    return values


def _timestamp(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds /= 1000
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        except (OverflowError, OSError, ValueError):
            return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError:
        return text[:80]


def _event_summary(record: Dict[str, Any]) -> str:
    value = _first(
        record, "content", "message.content", "message.text", "message", "text",
        "summary", "payload", "output", "description",
    )
    return _clean_text(value or record)


def _safe_structural_summary(
    record: Dict[str, Any], event_type: str, extracted: str,
) -> str:
    """Avoid persisting system instructions, tool arguments, or raw tool output."""
    if event_type == "system":
        return f"System instruction event ({len(extracted)} derived characters omitted)"
    if event_type == "tool_call":
        name = _first(record, "name", "tool", "function.name", "message.name")
        return f"Tool invocation: {_clean_text(name)[:160] or 'unnamed tool'}"
    if event_type == "tool_result":
        lower = extracted.lower()
        if re.search(r"\b(tests? passed|passing|success|succeeded)\b", lower):
            outcome = "success reported"
        elif re.search(r"\b(failed|failure|error|exception)\b", lower):
            outcome = "failure reported"
        else:
            outcome = "result recorded"
        return f"Tool result: {outcome} ({len(extracted)} derived characters omitted)"
    return extracted


def normalize_jsonl(
    store: CompanyBrainStore,
    evidence_id: str,
    principal: Principal,
    *,
    source_type: str = "session_jsonl",
    session_native_id: str = "",
    project_id: str = "",
    max_events: int = DEFAULT_MAX_EVENTS,
) -> Dict[str, Any]:
    """Stream and normalize a JSONL artifact without mutating the store."""
    metadata = store.inspect_evidence(evidence_id, principal, strong=True)
    artifact_type = metadata["artifact_type"]
    if artifact_type not in {"structured_data", "chat", "transcript", "plain_text"}:
        raise ValueError(
            "Session understanding currently accepts JSONL structured_data, chat, "
            "transcript, or plain_text evidence"
        )
    path = store.resolve_evidence_path(evidence_id, principal)
    policy = AccessPolicy.from_dict(metadata["access_policy"])
    output: List[Dict[str, Any]] = []
    malformed = 0
    overlong = 0
    blank = 0
    line_number = 0
    with path.open("rb") as handle:
        while True:
            if len(output) >= max(1, min(max_events, DEFAULT_MAX_EVENTS)):
                break
            raw_line = handle.readline(MAX_LINE_BYTES + 1)
            if not raw_line:
                break
            line_number += 1
            if not raw_line.strip():
                blank += 1
                continue
            if len(raw_line) > MAX_LINE_BYTES:
                # Drain the remainder in bounded chunks without retaining it.
                while raw_line and not raw_line.endswith(b"\n"):
                    raw_line = handle.readline(MAX_LINE_BYTES + 1)
                overlong += 1
                continue
            try:
                record = json.loads(raw_line.decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                malformed += 1
                continue
            if not isinstance(record, dict):
                malformed += 1
                continue
            native_id = str(_first(record, "id", "event_id", "uuid", "message.id") or line_number)
            native_session = str(
                session_native_id
                or _first(record, "session_id", "sessionId", "conversation_id", "thread_id")
                or evidence_id
            )
            role = str(_first(record, "role", "message.role", "actor.role") or "").lower()
            event_type = _event_type(record, role)
            occurred_at = _timestamp(
                _first(record, "occurred_at", "timestamp", "created_at", "time", "message.timestamp")
            )
            summary = _safe_structural_summary(
                record, event_type, _event_summary(record),
            )
            source_native = f"{native_session}:{native_id}"
            event_id = store.event_id_for(
                principal.tenant_id, source_type, source_native, evidence_id,
            )
            item = NormalizedEventInput(
                tenant_id=principal.tenant_id,
                source_type=source_type,
                source_native_id=source_native,
                session_native_id=native_session,
                evidence_id=evidence_id,
                native_locator={"line": line_number, "source_native_id": native_id},
                summary=summary,
                event_type=event_type,
                actor_type=_actor_type(role, event_type),
                actor_id=str(_first(record, "actor_id", "user_id", "author.id", "actor.id") or role),
                role=role,
                occurred_at=occurred_at,
                project_candidates=_projects(record, project_id),
                entities=[],
                classification=metadata["classification"],
                access_policy=policy,
                ingestion_run_id=PIPELINE_VERSION,
            )
            output.append({**item.__dict__, "event_id": event_id, "line": line_number})
    final_metadata = store.inspect_evidence(evidence_id, principal, strong=True)
    if final_metadata["availability"]["status"] != "available":
        raise OSError(
            "Evidence changed or became unavailable while the normalization graph was reading it"
        )
    return {
        "evidence": final_metadata,
        "events": output,
        "metrics": {
            "events": len(output), "malformed_lines": malformed,
            "overlong_lines": overlong, "blank_lines": blank,
        },
    }


def _parse_time(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN.findall(text) if len(token) > 2}


def _goal_changed(goal: str, event: Dict[str, Any], episode_size: int) -> bool:
    if episode_size < 3 or event.get("role") not in {"user", "human"}:
        return False
    summary = event.get("summary", "")
    if not _GOAL_VERBS.search(summary):
        return False
    old, new = _tokens(goal), _tokens(summary)
    return bool(old and new and len(old & new) / max(1, len(new)) < 0.18)


def _phase(event: Dict[str, Any]) -> str:
    text = event.get("summary", "").lower()
    if event.get("event_type") in {"commit", "file_change", "document_change"}:
        return "implement"
    if re.search(r"\b(test|pytest|coverage|validate|verify|check)\b", text):
        return "test"
    if re.search(r"\b(plan|design|spec|approach|architecture)\b", text):
        return "plan"
    if re.search(r"\b(review|revise|change|adjust|feedback)\b", text):
        return "revise"
    if _COMPLETION.search(text):
        return "conclude"
    if re.search(r"\b(understand|inspect|investigate|analyse|analyze|why)\b", text):
        return "understand"
    return "work"


def _semantic_title(goal: str) -> str:
    cleaned = re.sub(r"^(please|can you|could you|i need you to|we need to)\s+", "", goal, flags=re.I)
    words = cleaned.strip(" .:-").split()
    title = " ".join(words[:12]) or "Understand session activity"
    return title[0].upper() + title[1:180]


def _episode_status(events: Sequence[Dict[str, Any]]) -> str:
    tail = " ".join(event.get("summary", "") for event in events[-4:])
    if _ABANDONED.search(tail):
        return "abandoned"
    if _BLOCKED.search(tail):
        return "blocked"
    if _COMPLETION.search(tail):
        return "completed"
    return "partial"


def _episode_from_events(
    store: CompanyBrainStore,
    events: Sequence[Dict[str, Any]],
    session_id: str,
    boundary_signals: Sequence[str],
    pipeline_version: str,
) -> EpisodeInput:
    goal_event = next(
        (event for event in events if event.get("role") in {"user", "human"} and event.get("summary")),
        events[0],
    )
    goal = goal_event.get("summary") or "Understand session activity"
    outcome_event = next(
        (
            event for event in reversed(events)
            if event.get("summary") and event.get("role") not in {"user", "human", "system", "developer"}
        ),
        events[-1],
    )
    projects = [project for event in events for project in event.get("project_candidates", []) if project]
    project = Counter(projects).most_common(1)[0][0] if projects else ""
    participants = sorted({
        event.get("actor_id") or event.get("role")
        for event in events if event.get("actor_id") or event.get("role")
    })
    phases = {event["event_id"]: _phase(event) for event in events}
    source_native = ":".join((
        pipeline_version, session_id, events[0]["source_native_id"], events[-1]["source_native_id"],
    ))
    return EpisodeInput(
        tenant_id=events[0]["tenant_id"],
        title=_semantic_title(goal),
        goal=goal[:2_000],
        project_id=project,
        participants=participants,
        started_at=events[0].get("occurred_at", ""),
        ended_at=events[-1].get("occurred_at", ""),
        status=_episode_status(events),
        outcome_summary=outcome_event.get("summary", "")[:500],
        session_ids=[session_id],
        evidence_ids=sorted({event["evidence_id"] for event in events}),
        event_ids=[event["event_id"] for event in events],
        phase_summary={
            "counts": dict(Counter(phases.values())), "event_phases": phases,
        },
        boundary_signals=list(boundary_signals),
        confidence=0.85 if boundary_signals else 0.75,
        classification=events[0]["classification"],
        access_policy=events[0]["access_policy"],
        source_native_id=source_native,
    )


def segment_events(
    store: CompanyBrainStore,
    events: Sequence[Dict[str, Any]],
    *,
    gap_seconds: int = EPISODE_GAP_SECONDS,
    pipeline_version: str = PIPELINE_VERSION,
) -> List[EpisodeInput]:
    """Create deterministic episodes from normalized events."""
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for event in events:
        native_session = event["session_native_id"]
        grouped[native_session].append(event)
    episodes: List[EpisodeInput] = []
    for native_session, session_events in grouped.items():
        session_events.sort(key=lambda item: (item.get("occurred_at") or "9999", item["line"]))
        session_id = store.session_id_for(
            session_events[0]["tenant_id"], session_events[0]["source_type"], native_session,
        )
        current: List[Dict[str, Any]] = []
        start_signals: List[str] = []
        for event in session_events:
            signals: List[str] = []
            if current:
                prior_time, current_time = _parse_time(current[-1].get("occurred_at", "")), _parse_time(event.get("occurred_at", ""))
                if prior_time and current_time and (current_time - prior_time).total_seconds() > gap_seconds:
                    signals.append("time_gap")
                prior_projects = set(current[-1].get("project_candidates", []))
                new_projects = set(event.get("project_candidates", []))
                if prior_projects and new_projects and not prior_projects.intersection(new_projects):
                    signals.append("project_change")
                goal = next(
                    (item.get("summary", "") for item in current if item.get("role") in {"user", "human"}),
                    current[0].get("summary", ""),
                )
                if _goal_changed(goal, event, len(current)):
                    signals.append("goal_change")
                if current[-1].get("event_type") == "handoff":
                    signals.append("handoff")
                if _COMPLETION.search(current[-1].get("summary", "")) and event.get("role") in {"user", "human"}:
                    signals.append("post_completion_request")
            if signals and current:
                episodes.append(_episode_from_events(
                    store, current, session_id, start_signals + signals, pipeline_version,
                ))
                current = []
                start_signals = signals
            current.append(event)
        if current:
            episodes.append(_episode_from_events(
                store, current, session_id, start_signals, pipeline_version,
            ))
    return episodes


def _sentences(text: str) -> Iterable[str]:
    for value in re.split(r"(?<=[.!?])\s+|[\r\n]+", text):
        cleaned = " ".join(value.split()).strip(" -*")
        if 10 <= len(cleaned) <= 1_000:
            yield cleaned


def _candidate_type(sentence: str, event: Dict[str, Any]) -> Optional[str]:
    lower = sentence.lower()
    if re.search(r"\b(decided|chose|selected|decision is|we will use|will use)\b", lower):
        return "decision"
    if re.search(r"\b(must|required|cannot|can't|never|constraint)\b", lower):
        return "constraint"
    if re.search(r"\b(todo|need to|plan to|will implement|next step|pending)\b", lower):
        return "task"
    if _COMPLETION.search(lower):
        return "outcome"
    if event.get("role") in {"user", "human"} and sentence.endswith("?"):
        return "question"
    return None


def extract_candidates(
    store: CompanyBrainStore,
    episode_id: str,
    episode: EpisodeInput,
    events: Sequence[Dict[str, Any]],
    run_id: str,
    *,
    persist: bool,
) -> List[Dict[str, Any]]:
    """Extract conservative, evidence-linked candidate memories."""
    candidates: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str]] = set()
    entity_ids: List[str] = []
    if persist and episode.project_id:
        entity_ids.append(store.upsert_entity(
            tenant_id=episode.tenant_id,
            entity_type="project",
            canonical_name=episode.project_id,
            classification=episode.classification,
            access_policy=episode.access_policy,
        ))
    for event in events:
        if event.get("event_type") in {"system", "tool_call"}:
            continue
        if event.get("event_type") == "tool_result" and len(event.get("summary", "")) > 500:
            continue
        for sentence in _sentences(event.get("summary", "")):
            memory_type = _candidate_type(sentence, event)
            key = (memory_type or "", sentence.lower())
            if not memory_type or key in seen:
                continue
            seen.add(key)
            title = _semantic_title(sentence)
            locator = json.dumps(event["native_locator"], sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(f"{memory_type}\x1f{sentence}".encode("utf-8")).hexdigest()[:16]
            source_native_id = (
                f"understanding:{PIPELINE_VERSION}:{episode_id}:{event['event_id']}:"
                f"{memory_type}:{digest}"
            )
            candidate = {
                "memory_type": memory_type,
                "title": title,
                "statement": sentence,
                "event_id": event["event_id"],
                "evidence_id": event["evidence_id"],
                "segment_id": event.get("segment_id", ""),
                "source_native_id": source_native_id,
                "confidence": 0.78 if memory_type in {"decision", "constraint", "outcome"} else 0.68,
            }
            if persist:
                memory_id = store.add_memory(MemoryInput(
                    tenant_id=episode.tenant_id,
                    memory_type=memory_type,
                    title=title,
                    statement=sentence,
                    rationale=f"Extracted from episode: {episode.title}",
                    project_id=episode.project_id,
                    entity_ids=entity_ids,
                    lifecycle="candidate",
                    confidence=candidate["confidence"],
                    importance=0.5,
                    observed_at=event.get("occurred_at", ""),
                    classification=episode.classification,
                    access_policy=episode.access_policy,
                    evidence=[EvidenceReference(
                        evidence_id=event["evidence_id"],
                        segment_id=event.get("segment_id", ""),
                        locator=locator,
                        support="direct",
                        quote=sentence[:2_000],
                    )],
                    extractor={
                        "kind": "deterministic_episode_extractor",
                        "version": PIPELINE_VERSION,
                        "episode_id": episode_id,
                        "event_id": event["event_id"],
                    },
                    source_native_id=source_native_id,
                ))
                store.link_episode_memory(episode_id, memory_id, event["event_id"], run_id)
                candidate["memory_id"] = memory_id
            candidates.append(candidate)
    return candidates


def understand_evidence(
    store: CompanyBrainStore,
    evidence_id: str,
    principal: Principal,
    *,
    dry_run: bool = False,
    source_type: str = "session_jsonl",
    session_native_id: str = "",
    project_id: str = "",
    max_events: int = DEFAULT_MAX_EVENTS,
) -> Dict[str, Any]:
    """Execute normalization -> sessions -> episodes -> candidate memories."""
    started_at = now_iso()
    normalized = normalize_jsonl(
        store, evidence_id, principal, source_type=source_type,
        session_native_id=session_native_id, project_id=project_id,
        max_events=max_events,
    )
    events = normalized["events"]
    metadata = normalized["evidence"]
    run_seed = "\x1f".join((
        principal.tenant_id, evidence_id, PIPELINE_VERSION, metadata["content_hash"], str(int(dry_run)),
    ))
    run_id = "xrun_" + hashlib.sha256(run_seed.encode("utf-8")).hexdigest()[:24]
    sessions: List[Dict[str, Any]] = []
    episodes: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []
    try:
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for event in events:
            grouped[event["session_native_id"]].append(event)
        for native_session, session_events in grouped.items():
            session_events.sort(key=lambda item: (item.get("occurred_at") or "9999", item["line"]))
            projects = [value for event in session_events for value in event["project_candidates"]]
            selected_project = Counter(projects).most_common(1)[0][0] if projects else ""
            participants = sorted({
                event.get("actor_id") or event.get("role")
                for event in session_events if event.get("actor_id") or event.get("role")
            })
            status = _episode_status(session_events)
            session_input = SessionInput(
                tenant_id=principal.tenant_id,
                source_type=source_type,
                source_native_id=native_session,
                title=_semantic_title(next(
                    (event["summary"] for event in session_events if event.get("role") in {"user", "human"} and event["summary"]),
                    f"Session {native_session}",
                )),
                project_id=selected_project,
                participants=participants,
                started_at=session_events[0].get("occurred_at", ""),
                ended_at=session_events[-1].get("occurred_at", ""),
                status=status,
                evidence_ids=[evidence_id],
                event_count=len(session_events),
                classification=metadata["classification"],
                access_policy=AccessPolicy.from_dict(metadata["access_policy"]),
                metadata={"pipeline_version": PIPELINE_VERSION},
            )
            canonical_id = store.session_id_for(principal.tenant_id, source_type, native_session)
            if not dry_run:
                canonical_id = store.upsert_session(session_input)
                for event in session_events:
                    item = NormalizedEventInput(**{
                        key: event[key] for key in NormalizedEventInput.__dataclass_fields__
                    })
                    event["event_id"] = store.add_normalized_event(item)
                # Resolve the deterministic segments created by event persistence.
                persisted = store.list_session_events(canonical_id, principal)
                persisted_by_id = {value["event_id"]: value for value in persisted}
                for event in session_events:
                    event["segment_id"] = persisted_by_id[event["event_id"]]["segment_id"]
            sessions.append({
                "session_id": canonical_id, "source_native_id": native_session,
                "title": session_input.title, "status": session_input.status,
                "event_count": len(session_events), "project_id": selected_project,
            })
        episode_inputs = segment_events(store, events)
        event_map = {event["event_id"]: event for event in events}
        for episode_input in episode_inputs:
            predicted_seed = episode_input.source_native_id or "\x1f".join(episode_input.event_ids)
            episode_id = "ep_" + hashlib.sha256(
                f"{episode_input.tenant_id}\x1f{predicted_seed}".encode("utf-8")
            ).hexdigest()[:24]
            if not dry_run:
                episode_input = EpisodeInput(**{
                    **episode_input.__dict__, "extraction_run_id": run_id,
                })
                episode_id = store.add_episode(episode_input)
            episode_events = [event_map[event_id] for event_id in episode_input.event_ids]
            extracted = extract_candidates(
                store, episode_id, episode_input, episode_events, run_id, persist=not dry_run,
            )
            candidates.extend(extracted)
            episodes.append({
                "episode_id": episode_id, "title": episode_input.title,
                "goal": episode_input.goal, "status": episode_input.status,
                "project_id": episode_input.project_id,
                "event_count": len(episode_input.event_ids),
                "boundary_signals": episode_input.boundary_signals,
                "candidate_count": len(extracted),
            })
        metrics = {
            **normalized["metrics"], "sessions": len(sessions),
            "episodes": len(episodes), "candidate_memories": len(candidates),
        }
        if not dry_run:
            store.record_extraction_run(
                run_id=run_id, tenant_id=principal.tenant_id, evidence_id=evidence_id,
                pipeline_version=PIPELINE_VERSION, status="completed", dry_run=False,
                input_hash=metadata["content_hash"], metrics=metrics, started_at=started_at,
            )
            store.set_checkpoint("session-jsonl", evidence_id, {
                "pipeline_version": PIPELINE_VERSION,
                "content_hash": metadata["content_hash"],
                "last_line": max((event["line"] for event in events), default=0),
                "run_id": run_id,
            })
        return {
            "run_id": run_id, "pipeline_version": PIPELINE_VERSION,
            "dry_run": dry_run, "evidence_id": evidence_id,
            "metrics": metrics, "sessions": sessions,
            "episodes": episodes, "candidates": candidates,
            "checkpoint_advanced": not dry_run,
        }
    except Exception as exc:
        if not dry_run:
            store.record_extraction_run(
                run_id=run_id, tenant_id=principal.tenant_id, evidence_id=evidence_id,
                pipeline_version=PIPELINE_VERSION, status="failed", dry_run=False,
                input_hash=metadata["content_hash"], metrics=normalized["metrics"],
                error=str(exc), started_at=started_at,
            )
        raise
