"""Shared calculations for interactive and printable management reporting."""

from __future__ import annotations

from collections import defaultdict
import csv
from datetime import date, datetime, timedelta
from io import StringIO
from statistics import mean, median
from typing import Any
import json


LIFECYCLE_STATUSES = ("in_progress", "submitted", "rejected", "completed")
ACTIVE_CASE_STATES = frozenset({"preparation", "in_progress", "submitted", "rejected"})
STATISTICS_SCHEMA_VERSION = "1.0"


def _as_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _as_date(value: str) -> date:
    return _as_datetime(value).date()


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _shift_month(value: date, months: int) -> date:
    month = value.month - 1 + months
    return value.replace(year=value.year + month // 12, month=month % 12 + 1, day=1)


def resolve_period(preset: str, *, today: date, custom_start: str | None = None, custom_end: str | None = None) -> tuple[date, date, str]:
    """Resolve a saved relative preset into inclusive-start/exclusive-end dates."""
    tomorrow = today + timedelta(days=1)
    if preset == "week":
        start = today - timedelta(days=today.weekday())
        return start, tomorrow, "Week to date"
    if preset == "fortnight":
        start = today - timedelta(days=13)
        return start, tomorrow, "Fortnight to date"
    if preset == "month":
        return _month_start(today), tomorrow, "Month to date"
    if preset == "quarter":
        start_month = ((today.month - 1) // 3) * 3 + 1
        return date(today.year, start_month, 1), tomorrow, "Quarter to date"
    if preset == "six_months":
        return _shift_month(today, -5), tomorrow, "Six months to date"
    if preset == "year":
        return date(today.year, 1, 1), tomorrow, "Year to date"
    if preset == "custom":
        if not custom_start or not custom_end:
            raise ValueError("Custom reports require a start and end date.")
        start, end_inclusive = date.fromisoformat(custom_start), date.fromisoformat(custom_end)
        if start > end_inclusive:
            raise ValueError("Report end date must not be before start date.")
        return start, end_inclusive + timedelta(days=1), f"{start:%d %b %Y} – {end_inclusive:%d %b %Y}"
    raise ValueError("Unknown reporting preset.")


def _bucket_starts(start: date, end: date) -> tuple[list[date], str]:
    days = (end - start).days
    if days <= 14:
        return [start + timedelta(days=offset) for offset in range(days)], "day"
    if days <= 45:
        first = start - timedelta(days=start.weekday())
        starts = []
        current = first
        while current < end:
            starts.append(current)
            current += timedelta(days=7)
        return starts, "week"
    first = _month_start(start)
    starts = []
    current = first
    while current < end:
        starts.append(current)
        current = _shift_month(current, 1)
    return starts, "month"


def _bucket_for(value: date, starts: list[date], granularity: str) -> date:
    if granularity == "day":
        return value
    if granularity == "week":
        return value - timedelta(days=value.weekday())
    return _month_start(value)


def _format_bucket(value: date, granularity: str) -> str:
    if granularity == "day":
        return value.strftime("%d %b")
    if granularity == "week":
        return f"Week of {value:%d %b}"
    return value.strftime("%b %Y")


def _parse_events(facts: dict[str, list[dict]]) -> dict[int, list[dict]]:
    result: dict[int, list[dict]] = defaultdict(list)
    for raw in facts["events"]:
        try:
            task_id = int(raw["entity_id"])
            details = json.loads(raw["details_json"])
            event = {**raw, "details": details, "at": _as_datetime(raw["occurred_at"])}
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        result[task_id].append(event)
    return result


def _assignment_events(task: dict, events: list[dict]) -> list[tuple[datetime, int | None]]:
    assignments: list[tuple[datetime, int | None]] = []
    for event in events:
        if event["event_type"] == "task.created_assigned" and event["actor_user_id"]:
            assignments.append((event["at"], event["actor_user_id"]))
        elif event["event_type"] == "task.lead_assigned":
            investigator_id = event["details"].get("investigator_user_id")
            if isinstance(investigator_id, int):
                assignments.append((event["at"], investigator_id))
        elif event["event_type"] == "task.lead_unassigned":
            assignments.append((event["at"], None))
    if not assignments and task.get("lead_investigator_id") is not None:
        # Current ownership is useful for a current report but is never used to
        # invent ownership before a historical reporting period.
        assignments.append((_as_datetime(task["updated_at"]), task["lead_investigator_id"]))
    return sorted(assignments)


def _owner_at(task: dict, events: list[dict], point: datetime) -> int | None:
    owner = None
    for changed_at, candidate in _assignment_events(task, events):
        if changed_at > point:
            break
        owner = candidate
    return owner


def _state_at(task: dict, events: list[dict], point: datetime) -> str:
    state = "preparation"
    for event in events:
        if event["at"] > point:
            break
        if event["event_type"] == "task.lifecycle_changed":
            candidate = event["details"].get("status")
            if candidate in LIFECYCLE_STATUSES:
                state = candidate
    return state


def _lifecycle_events(events: list[dict], status: str) -> list[dict]:
    return [
        event
        for event in events
        if event["event_type"] == "task.lifecycle_changed" and event["details"].get("status") == status
    ]


def _duration_days(start: datetime, end: datetime) -> float:
    return max(0.0, (end - start).total_seconds() / 86400)


def _percentile_75(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * 0.75
    lower, upper = int(position), min(int(position) + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _task_intersects_period(task: dict, events: list[dict], start: date, end: date) -> bool:
    current = start
    while current < end:
        point = datetime.combine(current, datetime.min.time()) + timedelta(days=1)
        if _state_at(task, events, point) in ACTIVE_CASE_STATES:
            return True
        current += timedelta(days=1)
    return False


def _task_in_scope(task: dict, events: list[dict], start: date, end: date, investigator_id: int | None) -> bool:
    if investigator_id is None:
        return _task_intersects_period(task, events, start, end)
    current = start
    while current < end:
        point = datetime.combine(current, datetime.min.time()) + timedelta(days=1)
        if (
            _owner_at(task, events, point) == investigator_id
            and _state_at(task, events, point) in ACTIVE_CASE_STATES
        ):
            return True
        current += timedelta(days=1)
    return False


def build_management_report(
    facts: dict[str, list[dict]],
    *,
    start: date,
    end: date,
    scope_investigator_id: int | None,
    complexity_mode: str,
    today: date,
) -> dict[str, Any]:
    """Build the single normalised reporting model used by UI and PDF renderers."""
    if complexity_mode not in {"totals", "average"}:
        raise ValueError("Invalid complexity mode.")
    events_by_task = _parse_events(facts)
    tasks = {task["id"]: task for task in facts["tasks"]}
    selected_tasks = {
        task_id
        for task_id, task in tasks.items()
        if _task_in_scope(task, events_by_task[task_id], start, end, scope_investigator_id)
    }
    investigators = {
        investigator["id"]: investigator
        for investigator in facts["investigators"]
    }
    subject_counts: dict[int, int] = defaultdict(int)
    finding_counts: dict[int, int] = defaultdict(int)
    for subject in facts["subjects"]:
        subject_counts[subject["task_id"]] += 1
    for finding in facts["findings"]:
        finding_counts[finding["task_id"]] += 1

    bucket_starts, granularity = _bucket_starts(start, end)
    buckets = {
        value: {
            "bucket_start": value.isoformat(),
            "label": _format_bucket(value, granularity),
            "new_assignments": 0,
            "reassignments": 0,
            "started": 0,
            "submitted": 0,
            "returned": 0,
            "completed": 0,
        }
        for value in bucket_starts
    }
    throughput = {"started": 0, "submitted": 0, "returned": 0, "completed": 0}
    assignment_flow = {"new_assignments": 0, "reassignments": 0, "started": 0}
    for task_id, task_events in events_by_task.items():
        task = tasks[task_id]
        for event in task_events:
            event_date = event["at"].date()
            if not start <= event_date < end:
                continue
            owner = _owner_at(task, task_events, event["at"])
            if scope_investigator_id is not None and owner != scope_investigator_id:
                continue
            bucket = _bucket_for(event_date, bucket_starts, granularity)
            if bucket not in buckets:
                continue
            if event["event_type"] in {"task.created_assigned", "task.lead_assigned"}:
                assigned_to = (
                    event["actor_user_id"]
                    if event["event_type"] == "task.created_assigned"
                    else event["details"].get("investigator_user_id")
                )
                if scope_investigator_id is None or assigned_to == scope_investigator_id:
                    field = (
                        "new_assignments"
                        if event["event_type"] == "task.created_assigned"
                        else "reassignments"
                    )
                    buckets[bucket][field] += 1
                    assignment_flow[field] += 1
                continue
            if event["event_type"] != "task.lifecycle_changed":
                continue
            status = event["details"].get("status")
            label = {
                "in_progress": "started",
                "submitted": "submitted",
                "rejected": "returned",
                "completed": "completed",
            }.get(status)
            if label:
                buckets[bucket][label] += 1
                throughput[label] += 1
                if label == "started":
                    assignment_flow["started"] += 1

    durations: dict[str, list[float]] = defaultdict(list)
    duration_trend_values: dict[str, dict[date, list[float]]] = {
        "Created to Started": defaultdict(list),
        "Started to Submitted": defaultdict(list),
        "Final Submission to Completed": defaultdict(list),
        "Returned to Resubmitted": defaultdict(list),
    }
    task_duration_rows = []
    report_as_of = min(today, end - timedelta(days=1))
    for task_id in selected_tasks:
        task = tasks[task_id]
        task_events = events_by_task[task_id]
        started = _lifecycle_events(task_events, "in_progress")
        submitted = _lifecycle_events(task_events, "submitted")
        returned = _lifecycle_events(task_events, "rejected")
        completed = _lifecycle_events(task_events, "completed")
        created_at = _as_datetime(task["created_at"])
        if started:
            created_to_started = _duration_days(created_at, started[0]["at"])
            durations["Created to Started"].append(created_to_started)
            duration_trend_values["Created to Started"][
                _bucket_for(started[0]["at"].date(), bucket_starts, granularity)
            ].append(created_to_started)
        if started and submitted:
            investigation_duration = _duration_days(started[0]["at"], submitted[0]["at"])
            durations["Started to Submitted"].append(investigation_duration)
            duration_trend_values["Started to Submitted"][
                _bucket_for(submitted[0]["at"].date(), bucket_starts, granularity)
            ].append(investigation_duration)
            investigation_duration_status = "submitted"
        elif started:
            investigation_duration = float((report_as_of - started[0]["at"].date()).days)
            investigation_duration_status = "ongoing"
        else:
            investigation_duration = None
            investigation_duration_status = None
        if submitted and completed:
            final_submission = submitted[-1]
            final_submission_to_completed = _duration_days(final_submission["at"], completed[-1]["at"])
            durations["Final Submission to Completed"].append(final_submission_to_completed)
            duration_trend_values["Final Submission to Completed"][
                _bucket_for(completed[-1]["at"].date(), bucket_starts, granularity)
            ].append(final_submission_to_completed)
        returned_durations = []
        for returned_event in returned:
            resubmission = next(
                (event for event in submitted if event["at"] > returned_event["at"]),
                None,
            )
            if resubmission is None:
                continue
            returned_duration = _duration_days(returned_event["at"], resubmission["at"])
            returned_durations.append(returned_duration)
            durations["Returned to Resubmitted"].append(returned_duration)
            duration_trend_values["Returned to Resubmitted"][
                _bucket_for(resubmission["at"].date(), bucket_starts, granularity)
            ].append(returned_duration)
        task_duration_rows.append(
            {
                "task_id": task_id,
                "task_ref": task["task_ref"],
                "task_name": task["task_name"],
                "subjects": subject_counts[task_id],
                "findings": finding_counts[task_id],
                "investigation_duration": investigation_duration,
                "investigation_duration_status": investigation_duration_status,
                "returned_duration": max(returned_durations, default=None),
                "investigator": task.get("current_investigator_name") or task.get("current_investigator_username") or "Unassigned",
            }
        )
    duration_summary = [
        {
            "interval": interval,
            "average_days": round(mean(values), 1),
            "median_days": round(median(values), 1),
            "task_count": len(values),
        }
        for interval, values in durations.items()
        if values
    ]
    duration_trend = [
        {
            "label": _format_bucket(bucket, granularity),
            **{
                interval: round(median(values), 1) if values else None
                for interval, values_by_bucket in duration_trend_values.items()
                for values in [values_by_bucket.get(bucket, [])]
            },
        }
        for bucket in bucket_starts
    ]

    baseline_end = _month_start(start)
    baseline_start = _shift_month(baseline_end, -6)
    known_investigator_ids = {investigator["id"] for investigator in facts["investigators"]}
    for task_id, task in tasks.items():
        for _, owner in _assignment_events(task, events_by_task[task_id]):
            if owner is not None:
                known_investigator_ids.add(owner)

    workload_history: dict[int, list[tuple[date, int]]] = defaultdict(list)
    preparation_history: dict[int, list[tuple[date, int]]] = defaultdict(list)
    report_workload_daily: dict[int, list[int]] = defaultdict(list)
    report_workload_task_ids: dict[int, set[int]] = defaultdict(set)
    workload_buckets: dict[int, dict[date, list[int]]] = defaultdict(lambda: defaultdict(list))
    subjects_by_task: dict[int, list[dict]] = defaultdict(list)
    findings_by_task: dict[int, list[dict]] = defaultdict(list)
    persona_allocations_by_task: dict[int, list[dict]] = defaultdict(list)
    for subject in facts["subjects"]:
        subjects_by_task[subject["task_id"]].append(subject)
    for finding in facts["findings"]:
        findings_by_task[finding["task_id"]].append(finding)
    for persona in facts["personas"]:
        persona_allocations_by_task[persona["task_id"]].append(persona)
    bucket_end_dates = {
        bucket: min(
            (bucket_starts[index + 1] if index + 1 < len(bucket_starts) else end) - timedelta(days=1),
            report_as_of,
        )
        for index, bucket in enumerate(bucket_starts)
    }
    bucket_at_end = {end_date: bucket for bucket, end_date in bucket_end_dates.items()}
    complexity_trend = {}
    persona_trend = {}
    persona_period_tasks: dict[str, set[int]] = defaultdict(set)
    persona_latest_exposure: dict[str, int] = defaultdict(int)
    contributor_ids: set[int] = set()
    current = baseline_start
    while current < end:
        point = datetime.combine(current, datetime.min.time()) + timedelta(days=1)
        active_by_investigator: dict[int, int] = defaultdict(int)
        preparation_by_investigator: dict[int, int] = defaultdict(int)
        active_task_ids: set[int] = set()
        active_personas: dict[str, set[int]] = defaultdict(set)
        for task_id, task in tasks.items():
            task_events = events_by_task[task_id]
            if _as_datetime(task["created_at"]) > point:
                continue
            deleted_at = task.get("deleted_at")
            if deleted_at and _as_datetime(deleted_at) <= point:
                continue
            owner = _owner_at(task, task_events, point)
            state = _state_at(task, task_events, point)
            if owner is None or state not in ACTIVE_CASE_STATES:
                continue
            if scope_investigator_id is not None and owner != scope_investigator_id:
                continue
            active_by_investigator[owner] += 1
            active_task_ids.add(task_id)
            if state == "preparation":
                preparation_by_investigator[owner] += 1
            contributor_ids.add(owner)
            if current >= start:
                report_workload_task_ids[owner].add(task_id)
                for allocation in persona_allocations_by_task[task_id]:
                    if _as_date(allocation["allocated_at"]) <= current:
                        reference = allocation["persona_reference"]
                        persona_period_tasks[reference].add(task_id)
                        active_personas[reference].add(task_id)
        target_ids = (
            [scope_investigator_id]
            if scope_investigator_id is not None
            else list(known_investigator_ids)
        )
        for investigator_id in target_ids:
            if investigator_id is None:
                continue
            count = active_by_investigator[investigator_id]
            workload_history[investigator_id].append((current, count))
            preparation_history[investigator_id].append(
                (current, preparation_by_investigator[investigator_id])
            )
            if current >= start:
                bucket = _bucket_for(current, bucket_starts, granularity)
                report_workload_daily[investigator_id].append(count)
                workload_buckets[investigator_id][bucket].append(count)
        if current in bucket_at_end:
            bucket = bucket_at_end[current]
            subject_total = sum(
                1
                for task_id in active_task_ids
                for subject in subjects_by_task[task_id]
                if _as_date(subject["created_at"]) <= current
                and (not subject.get("deleted_at") or _as_date(subject["deleted_at"]) > current)
            )
            finding_total = sum(
                1
                for task_id in active_task_ids
                for finding in findings_by_task[task_id]
                if _as_date(finding["created_at"]) <= current
                and (not finding.get("deleted_at") or _as_date(finding["deleted_at"]) > current)
            )
            complexity_trend[bucket] = {
                "task_count": len(active_task_ids),
                "subjects_per_task": round(subject_total / len(active_task_ids), 1) if active_task_ids else None,
                "findings_per_task": round(finding_total / len(active_task_ids), 1) if active_task_ids else None,
            }
            persona_trend[bucket] = {
                reference: len(task_ids)
                for reference, task_ids in active_personas.items()
            }
            if current == report_as_of:
                persona_latest_exposure = {
                    reference: len(task_ids)
                    for reference, task_ids in active_personas.items()
                }
        current += timedelta(days=1)
    workload = [
        {
            "investigator_id": investigator_id,
            "investigator": (
                investigators.get(investigator_id, {}).get("display_name")
                or investigators.get(investigator_id, {}).get("username")
                or f"Former investigator {investigator_id}"
            ),
            "average": round(mean(values), 1) if values else 0,
            "peak": max(values, default=0),
            "distinct_active_tasks": len(report_workload_task_ids[investigator_id]),
            "trend": [
                {
                    "label": buckets[bucket]["label"],
                    "average": round(mean(workload_buckets[investigator_id].get(bucket, [0])), 1),
                    "peak": max(workload_buckets[investigator_id].get(bucket, [0])),
                }
                for bucket in bucket_starts
            ],
        }
        for investigator_id, values in report_workload_daily.items()
    ]
    workload.sort(key=lambda item: item["investigator"].casefold())

    complexity_task_count = len(selected_tasks)
    complexity_subjects = sum(subject_counts[task_id] for task_id in selected_tasks)
    complexity_findings = sum(finding_counts[task_id] for task_id in selected_tasks)
    complexity = {
        "subjects_total": complexity_subjects,
        "findings_total": complexity_findings,
        "task_count": complexity_task_count,
        "subjects_per_task": round(complexity_subjects / complexity_task_count, 1) if complexity_task_count else 0,
        "findings_per_task": round(complexity_findings / complexity_task_count, 1) if complexity_task_count else 0,
    }
    complexity_trend_rows = [
        {
            "label": _format_bucket(bucket, granularity),
            **complexity_trend.get(
                bucket,
                {"task_count": 0, "subjects_per_task": None, "findings_per_task": None},
            ),
        }
        for bucket in bucket_starts
    ]

    personas = set(persona_period_tasks) | set(persona_latest_exposure)
    for values in persona_trend.values():
        personas.update(values)
    persona_usage = [
        {
            "persona": persona,
            "distinct_active_tasks": len(persona_period_tasks[persona]),
            "latest_active_exposure": persona_latest_exposure.get(persona, 0),
        }
        for persona in personas
    ]
    persona_usage.sort(key=lambda item: (-item["latest_active_exposure"], item["persona"]))
    persona_trend_rows = [
        {
            "label": _format_bucket(bucket, granularity),
            **{persona: persona_trend.get(bucket, {}).get(persona, 0) for persona in personas},
        }
        for bucket in bucket_starts
    ]

    report_end_point = datetime.combine(report_as_of, datetime.min.time()) + timedelta(days=1)
    readiness_trend = []
    for bucket in bucket_starts:
        point = datetime.combine(bucket_end_dates[bucket], datetime.min.time()) + timedelta(days=1)
        unassigned = 0
        assigned_not_started = 0
        for task_id, task in tasks.items():
            if _as_datetime(task["created_at"]) > point:
                continue
            deleted_at = task.get("deleted_at")
            if deleted_at and _as_datetime(deleted_at) <= point:
                continue
            if _state_at(task, events_by_task[task_id], point) != "preparation":
                continue
            owner = _owner_at(task, events_by_task[task_id], point)
            if scope_investigator_id is not None and owner != scope_investigator_id:
                continue
            if owner is None:
                unassigned += 1
            else:
                assigned_not_started += 1
        buckets[bucket]["unassigned"] = unassigned
        buckets[bucket]["assigned_not_started"] = assigned_not_started
        readiness_trend.append(
            {
                "bucket_start": bucket.isoformat(),
                "label": _format_bucket(bucket, granularity),
                "unassigned": unassigned,
                "assigned_not_started": assigned_not_started,
            }
        )

    awaiting_start = []
    for task_id, task in tasks.items():
        if _as_datetime(task["created_at"]) > report_end_point:
            continue
        owner = _owner_at(task, events_by_task[task_id], report_end_point)
        if owner is None or (scope_investigator_id is not None and owner != scope_investigator_id):
            continue
        if _state_at(task, events_by_task[task_id], report_end_point) != "preparation":
            continue
        assignment_times = [
            changed_at
            for changed_at, assignee in _assignment_events(task, events_by_task[task_id])
            if assignee == owner and changed_at <= report_end_point
        ]
        assigned_at = max(assignment_times, default=_as_datetime(task["created_at"]))
        awaiting_start.append(
            {
                "task_ref": task["task_ref"],
                "investigator": (
                    investigators.get(owner, {}).get("display_name")
                    or investigators.get(owner, {}).get("username")
                    or f"Former investigator {owner}"
                ),
                "assigned_at": assigned_at.date().isoformat(),
                "awaiting_start_days": max(0, (report_as_of - assigned_at.date()).days),
            }
        )
    awaiting_start.sort(key=lambda row: (-row["awaiting_start_days"], row["task_ref"]))
    assignment_flow["awaiting_start"] = len(awaiting_start)
    assignment_flow["awaiting_start_tasks"] = awaiting_start[:5]
    assignment_flow["unassigned"] = readiness_trend[-1]["unassigned"]
    assignment_flow["assigned_not_started"] = readiness_trend[-1]["assigned_not_started"]
    assignment_flow["preparation_backlog"] = (
        assignment_flow["unassigned"] + assignment_flow["assigned_not_started"]
    )

    difficult_task_candidates: dict[int, dict[str, Any]] = {}
    rankings = (
        ("subjects", "High subject count"),
        ("findings", "High finding count"),
        ("investigation_duration", "Long investigation"),
    )
    for field, reason in rankings:
        eligible_rows = [
            row for row in task_duration_rows
            if row[field] is not None
        ]
        for rank, row in enumerate(
            sorted(eligible_rows, key=lambda item: (-item[field], item["task_ref"]))[:5],
            start=1,
        ):
            candidate = difficult_task_candidates.setdefault(
                row["task_id"],
                {**row, "reasons": [], "best_rank": rank},
            )
            candidate["reasons"].append(reason)
            candidate["best_rank"] = min(candidate["best_rank"], rank)
    difficult_tasks = sorted(
        difficult_task_candidates.values(),
        key=lambda row: (
            -len(row["reasons"]),
            row["best_rank"],
            -row["findings"],
            -row["subjects"],
            -row["investigation_duration"] if row["investigation_duration"] is not None else 0,
            row["task_ref"],
        ),
    )[:5]

    def investigator_name(investigator_id: int) -> str:
        return (
            investigators.get(investigator_id, {}).get("display_name")
            or investigators.get(investigator_id, {}).get("username")
            or f"Former investigator {investigator_id}"
        )

    eligible_ids = set()
    for investigator_id in contributor_ids | ({scope_investigator_id} if scope_investigator_id else set()):
        if investigator_id is None:
            continue
        activity_dates = []
        for task_id, task_events in events_by_task.items():
            for event in task_events:
                owner = _owner_at(tasks[task_id], task_events, event["at"])
                if owner == investigator_id:
                    activity_dates.append(event["at"].date())
        if activity_dates and min(activity_dates) <= baseline_start:
            eligible_ids.add(investigator_id)

    def add_attention(investigator_id: int, area: str, observed: float, baseline_values: list[float], context: str) -> None:
        threshold = _percentile_75(baseline_values)
        if threshold is not None and observed > threshold:
            attention.append(
                {
                    "investigator": investigator_name(investigator_id),
                    "area": area,
                    "current": round(observed, 1),
                    "baseline": round(threshold, 1),
                    "context": context,
                }
            )

    attention = []
    end_point = datetime.combine(end, datetime.min.time())
    for investigator_id in eligible_ids:
        historical_days = [
            count
            for observed_date, count in workload_history.get(investigator_id, [])
            if baseline_start <= observed_date < baseline_end
        ]
        current_values = [
            count
            for observed_date, count in workload_history.get(investigator_id, [])
            if start <= observed_date < end
        ]
        if len(historical_days) < (baseline_end - baseline_start).days or not current_values:
            continue
        add_attention(
            investigator_id,
            "Concurrent workload",
            max(current_values),
            historical_days,
            "Peak active tasks exceeds the personal 75th percentile.",
        )
        baseline_preparation = [
            count
            for observed_date, count in preparation_history.get(investigator_id, [])
            if baseline_start <= observed_date < baseline_end
        ]
        current_preparation = [
            count
            for observed_date, count in preparation_history.get(investigator_id, [])
            if start <= observed_date < end
        ]
        if baseline_preparation and current_preparation:
            add_attention(
                investigator_id,
                "Unstarted assigned tasks",
                max(current_preparation),
                baseline_preparation,
                "Preparation tasks exceed the personal 75th percentile.",
            )

        baseline_subjects: list[float] = []
        baseline_findings: list[float] = []
        current_subjects: list[float] = []
        current_findings: list[float] = []
        baseline_rework: list[float] = []
        current_rework: list[float] = []
        baseline_review_wait: list[float] = []
        current_review_wait: list[float] = []
        for task_id, task in tasks.items():
            task_events = events_by_task[task_id]
            started = _lifecycle_events(task_events, "in_progress")
            submitted = _lifecycle_events(task_events, "submitted")
            returned = _lifecycle_events(task_events, "rejected")
            completed = _lifecycle_events(task_events, "completed")
            if started and _owner_at(task, task_events, started[0]["at"]) == investigator_id:
                if baseline_start <= started[0]["at"].date() < baseline_end:
                    baseline_subjects.append(subject_counts[task_id])
                    baseline_findings.append(finding_counts[task_id])
                if (
                    _owner_at(task, task_events, end_point) == investigator_id
                    and _state_at(task, task_events, end_point) == "in_progress"
                ):
                    current_subjects.append(subject_counts[task_id])
                    current_findings.append(finding_counts[task_id])
            if returned and completed and _owner_at(task, task_events, returned[0]["at"]) == investigator_id:
                duration = _duration_days(returned[0]["at"], completed[-1]["at"])
                if baseline_start <= completed[-1]["at"].date() < baseline_end:
                    baseline_rework.append(duration)
                if start <= completed[-1]["at"].date() < end:
                    current_rework.append(duration)
            for index, submitted_event in enumerate(submitted):
                if _owner_at(task, task_events, submitted_event["at"]) != investigator_id:
                    continue
                next_events = [
                    event for event in task_events
                    if event["at"] > submitted_event["at"]
                    and event["event_type"] == "task.lifecycle_changed"
                    and event["details"].get("status") in {"rejected", "completed"}
                ]
                if next_events and baseline_start <= submitted_event["at"].date() < baseline_end:
                    baseline_review_wait.append(_duration_days(submitted_event["at"], next_events[0]["at"]))
                if (
                    index == len(submitted) - 1
                    and _state_at(task, task_events, end_point) == "submitted"
                    and start <= submitted_event["at"].date() < end
                ):
                    current_review_wait.append(_duration_days(submitted_event["at"], end_point))
        if baseline_subjects and current_subjects:
            add_attention(
                investigator_id,
                "Started task subjects",
                max(current_subjects),
                baseline_subjects,
                "A started task has an unusually high subject count.",
            )
        if baseline_findings and current_findings:
            add_attention(
                investigator_id,
                "Started task findings",
                max(current_findings),
                baseline_findings,
                "A started task has an unusually high finding count.",
            )
        if baseline_rework and current_rework:
            add_attention(
                investigator_id,
                "Returned to Completed duration",
                max(current_rework),
                baseline_rework,
                "A completed task has an extended rework duration.",
            )
        if baseline_review_wait and current_review_wait:
            add_attention(
                investigator_id,
                "Submitted review wait",
                max(current_review_wait),
                baseline_review_wait,
                "A submitted task is waiting longer than the personal 75th percentile.",
            )

    coverage_notice = (
        "Historical workload attribution is limited where a task has no auditable assignment event before the reporting period."
        if any(
            not _assignment_events(task, events_by_task[task_id])
            for task_id, task in tasks.items()
            if _task_intersects_period(task, events_by_task[task_id], start, end)
        )
        else None
    )
    readiness_start = readiness_trend[0]
    readiness_end = readiness_trend[-1]
    readiness_change = (
        readiness_end["unassigned"] + readiness_end["assigned_not_started"]
        - readiness_start["unassigned"]
        - readiness_start["assigned_not_started"]
    )
    rework_rate = (
        round(throughput["returned"] / throughput["submitted"] * 100, 1)
        if throughput["submitted"]
        else None
    )
    executive_summary = [
        {
            "Area": "Delivery",
            "Measure": "Lifecycle movements",
            "Value": (
                f"{throughput['started']} started; {throughput['submitted']} submitted; "
                f"{throughput['completed']} completed"
            ),
            "Context": "Independent lifecycle events recorded during the reporting period.",
        },
        {
            "Area": "Readiness",
            "Measure": "Preparation backlog at period end",
            "Value": (
                f"{assignment_flow['preparation_backlog']} total "
                f"({assignment_flow['unassigned']} unassigned; "
                f"{assignment_flow['assigned_not_started']} assigned but not started)"
            ),
            "Context": (
                "No prior reporting snapshot is available for comparison."
                if len(readiness_trend) == 1
                else "Unchanged across the available reporting snapshots."
                if readiness_change == 0
                else f"{abs(readiness_change)} {'higher' if readiness_change > 0 else 'lower'} "
                "than the first reporting snapshot."
            ),
        },
        {
            "Area": "Rework",
            "Measure": "Returns after submission",
            "Value": (
                f"{throughput['returned']} of {throughput['submitted']} submissions "
                f"({rework_rate:.1f}%)"
                if rework_rate is not None
                else "No submissions recorded"
            ),
            "Context": "Returns are recorded lifecycle events and are not a task-level conversion rate.",
        },
    ]
    return {
        "start": start,
        "end": end,
        "generated_at": datetime.combine(today, datetime.now().time()),
        "bucket_granularity": granularity,
        "buckets": list(buckets.values()),
        "throughput": throughput,
        "assignment_flow": assignment_flow,
        "readiness_trend": readiness_trend,
        "executive_summary": executive_summary,
        "workload": workload,
        "durations": duration_summary,
        "duration_trend": duration_trend,
        "complexity": complexity,
        "complexity_trend": complexity_trend_rows,
        "persona_usage": persona_usage,
        "persona_trend": persona_trend_rows,
        "difficult_tasks": difficult_tasks,
        "manager_attention": attention,
        "coverage_notice": coverage_notice,
    }


def management_statistics_csv(report: dict[str, Any], *, scope_label: str) -> str:
    """Return canonical, non-identifying measures for statistical aggregation."""
    rows: list[dict[str, str | int | float]] = []
    metadata = {
        "schema_version": STATISTICS_SCHEMA_VERSION,
        "generated_at": report["generated_at"].isoformat(timespec="seconds"),
        "scope": scope_label,
        "report_period_start": report["start"].isoformat(),
        "report_period_end": (report["end"] - timedelta(days=1)).isoformat(),
    }

    def add(
        measure: str,
        value: int | float,
        definition: str,
        *,
        bucket: dict[str, Any] | None = None,
        numerator: int | float | str = "",
        denominator: int | float | str = "",
    ) -> None:
        rows.append(
            {
                **metadata,
                "bucket_start": bucket["bucket_start"] if bucket else "",
                "bucket_label": bucket["label"] if bucket else "",
                "measure": measure,
                "value": value,
                "unit": "tasks",
                "numerator": numerator,
                "denominator": denominator,
                "definition": definition,
            }
        )

    for bucket in report["buckets"]:
        for field, definition in (
            ("started", "Tasks entering investigation in the bucket."),
            ("submitted", "Submissions recorded in the bucket."),
            ("returned", "Returned reports recorded in the bucket."),
            ("completed", "Completed tasks recorded in the bucket."),
            ("new_assignments", "Initial investigator assignments recorded in the bucket."),
            ("reassignments", "Lead-investigator reassignments recorded in the bucket."),
        ):
            add(field, bucket[field], definition, bucket=bucket)
    for bucket in report["readiness_trend"]:
        preparation_backlog = bucket["unassigned"] + bucket["assigned_not_started"]
        add(
            "preparation_unassigned",
            bucket["unassigned"],
            "Preparation tasks with no assigned investigator at the bucket end.",
            bucket=bucket,
            numerator=bucket["unassigned"],
            denominator=preparation_backlog,
        )
        add(
            "preparation_assigned_not_started",
            bucket["assigned_not_started"],
            "Preparation tasks assigned to an investigator but not started at the bucket end.",
            bucket=bucket,
            numerator=bucket["assigned_not_started"],
            denominator=preparation_backlog,
        )

    readiness = report["assignment_flow"]
    add(
        "preparation_backlog_end",
        readiness["preparation_backlog"],
        "All preparation tasks at the report end, split between unassigned and assigned but not started.",
    )
    add(
        "preparation_unassigned_end",
        readiness["unassigned"],
        "Preparation tasks with no assigned investigator at the report end.",
        numerator=readiness["unassigned"],
        denominator=readiness["preparation_backlog"],
    )
    add(
        "preparation_assigned_not_started_end",
        readiness["assigned_not_started"],
        "Preparation tasks assigned to an investigator but not started at the report end.",
        numerator=readiness["assigned_not_started"],
        denominator=readiness["preparation_backlog"],
    )

    output = StringIO()
    fieldnames = [
        "schema_version",
        "generated_at",
        "scope",
        "report_period_start",
        "report_period_end",
        "bucket_start",
        "bucket_label",
        "measure",
        "value",
        "unit",
        "numerator",
        "denominator",
        "definition",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
