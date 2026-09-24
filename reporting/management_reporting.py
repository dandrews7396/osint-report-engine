"""Shared calculations for interactive and printable management reporting."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean, median
from typing import Any
import json


LIFECYCLE_STATUSES = ("in_progress", "submitted", "rejected", "completed")
ACTIVE_CASE_STATES = frozenset({"preparation", "in_progress", "submitted", "rejected"})


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
    if days <= 92:
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
            case_id = int(raw["entity_id"])
            details = json.loads(raw["details_json"])
            event = {**raw, "details": details, "at": _as_datetime(raw["occurred_at"])}
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        result[case_id].append(event)
    return result


def _assignment_events(case: dict, events: list[dict]) -> list[tuple[datetime, int | None]]:
    assignments: list[tuple[datetime, int | None]] = []
    for event in events:
        if event["event_type"] == "case.created_assigned" and event["actor_user_id"]:
            assignments.append((event["at"], event["actor_user_id"]))
        elif event["event_type"] == "case.lead_assigned":
            investigator_id = event["details"].get("investigator_user_id")
            if isinstance(investigator_id, int):
                assignments.append((event["at"], investigator_id))
        elif event["event_type"] == "case.lead_unassigned":
            assignments.append((event["at"], None))
    if not assignments and case.get("lead_investigator_id") is not None:
        # Current ownership is useful for a current report but is never used to
        # invent ownership before a historical reporting period.
        assignments.append((_as_datetime(case["updated_at"]), case["lead_investigator_id"]))
    return sorted(assignments)


def _owner_at(case: dict, events: list[dict], point: datetime) -> int | None:
    owner = None
    for changed_at, candidate in _assignment_events(case, events):
        if changed_at > point:
            break
        owner = candidate
    return owner


def _state_at(case: dict, events: list[dict], point: datetime) -> str:
    state = "preparation"
    for event in events:
        if event["at"] > point:
            break
        if event["event_type"] == "case.lifecycle_changed":
            candidate = event["details"].get("status")
            if candidate in LIFECYCLE_STATUSES:
                state = candidate
    return state


def _lifecycle_events(events: list[dict], status: str) -> list[dict]:
    return [
        event
        for event in events
        if event["event_type"] == "case.lifecycle_changed" and event["details"].get("status") == status
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


def _case_intersects_period(case: dict, events: list[dict], start: date, end: date) -> bool:
    current = start
    while current < end:
        point = datetime.combine(current, datetime.min.time()) + timedelta(days=1)
        if _state_at(case, events, point) in ACTIVE_CASE_STATES:
            return True
        current += timedelta(days=1)
    return False


def _case_in_scope(case: dict, events: list[dict], start: date, end: date, investigator_id: int | None) -> bool:
    if investigator_id is None:
        return _case_intersects_period(case, events, start, end)
    current = start
    while current < end:
        point = datetime.combine(current, datetime.min.time()) + timedelta(days=1)
        if (
            _owner_at(case, events, point) == investigator_id
            and _state_at(case, events, point) in ACTIVE_CASE_STATES
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
    events_by_case = _parse_events(facts)
    cases = {case["id"]: case for case in facts["cases"]}
    selected_cases = {
        case_id
        for case_id, case in cases.items()
        if _case_in_scope(case, events_by_case[case_id], start, end, scope_investigator_id)
    }
    investigators = {
        investigator["id"]: investigator
        for investigator in facts["investigators"]
    }
    subject_counts: dict[int, int] = defaultdict(int)
    finding_counts: dict[int, int] = defaultdict(int)
    for subject in facts["subjects"]:
        subject_counts[subject["case_id"]] += 1
    for finding in facts["findings"]:
        finding_counts[finding["case_id"]] += 1

    bucket_starts, granularity = _bucket_starts(start, end)
    buckets = {
        value: {
            "label": _format_bucket(value, granularity),
            "assigned": 0,
            "started": 0,
            "submitted": 0,
            "returned": 0,
            "completed": 0,
        }
        for value in bucket_starts
    }
    throughput = {"started": 0, "submitted": 0, "returned": 0, "completed": 0}
    for case_id, case_events in events_by_case.items():
        case = cases[case_id]
        for event in case_events:
            event_date = event["at"].date()
            if not start <= event_date < end:
                continue
            owner = _owner_at(case, case_events, event["at"])
            if scope_investigator_id is not None and owner != scope_investigator_id:
                continue
            bucket = _bucket_for(event_date, bucket_starts, granularity)
            if bucket not in buckets:
                continue
            if event["event_type"] in {"case.created_assigned", "case.lead_assigned"}:
                assigned_to = (
                    event["actor_user_id"]
                    if event["event_type"] == "case.created_assigned"
                    else event["details"].get("investigator_user_id")
                )
                if scope_investigator_id is None or assigned_to == scope_investigator_id:
                    buckets[bucket]["assigned"] += 1
                continue
            if event["event_type"] != "case.lifecycle_changed":
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

    durations: dict[str, list[float]] = defaultdict(list)
    case_duration_rows = []
    for case_id in selected_cases:
        case = cases[case_id]
        case_events = events_by_case[case_id]
        started = _lifecycle_events(case_events, "in_progress")
        submitted = _lifecycle_events(case_events, "submitted")
        returned = _lifecycle_events(case_events, "rejected")
        completed = _lifecycle_events(case_events, "completed")
        created_at = _as_datetime(case["created_at"])
        if started:
            durations["Created to Started"].append(_duration_days(created_at, started[0]["at"]))
        if started and submitted:
            investigation_duration = _duration_days(started[0]["at"], submitted[0]["at"])
            durations["Investigation Duration"].append(investigation_duration)
        else:
            investigation_duration = None
        if submitted and completed:
            durations["Submitted to Completed"].append(_duration_days(submitted[0]["at"], completed[-1]["at"]))
        if returned and completed:
            returned_duration = _duration_days(returned[0]["at"], completed[-1]["at"])
            durations["Returned to Completed"].append(returned_duration)
        else:
            returned_duration = None
        case_duration_rows.append(
            {
                "case_id": case_id,
                "case_ref": case["case_ref"],
                "case_name": case["case_name"],
                "subjects": subject_counts[case_id],
                "findings": finding_counts[case_id],
                "investigation_duration": investigation_duration,
                "returned_duration": returned_duration,
                "investigator": case.get("current_investigator_name") or case.get("current_investigator_username") or "Unassigned",
            }
        )
    duration_summary = [
        {
            "interval": interval,
            "average_days": round(mean(values), 1),
            "median_days": round(median(values), 1),
            "case_count": len(values),
        }
        for interval, values in durations.items()
        if values
    ]

    baseline_end = _month_start(start)
    baseline_start = _shift_month(baseline_end, -6)
    known_investigator_ids = {investigator["id"] for investigator in facts["investigators"]}
    for case_id, case in cases.items():
        for _, owner in _assignment_events(case, events_by_case[case_id]):
            if owner is not None:
                known_investigator_ids.add(owner)

    workload_history: dict[int, list[tuple[date, int]]] = defaultdict(list)
    preparation_history: dict[int, list[tuple[date, int]]] = defaultdict(list)
    report_workload_daily: dict[int, list[int]] = defaultdict(list)
    workload_buckets: dict[int, dict[date, list[int]]] = defaultdict(lambda: defaultdict(list))
    contributor_ids: set[int] = set()
    current = baseline_start
    while current < end:
        point = datetime.combine(current, datetime.min.time()) + timedelta(days=1)
        active_by_investigator: dict[int, int] = defaultdict(int)
        preparation_by_investigator: dict[int, int] = defaultdict(int)
        for case_id, case in cases.items():
            case_events = events_by_case[case_id]
            owner = _owner_at(case, case_events, point)
            state = _state_at(case, case_events, point)
            if owner is None or state not in ACTIVE_CASE_STATES:
                continue
            active_by_investigator[owner] += 1
            if state == "preparation":
                preparation_by_investigator[owner] += 1
            contributor_ids.add(owner)
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

    complexity_case_count = len(selected_cases)
    complexity = {
        "mode": complexity_mode,
        "subjects": sum(subject_counts[case_id] for case_id in selected_cases),
        "findings": sum(finding_counts[case_id] for case_id in selected_cases),
        "case_count": complexity_case_count,
    }
    if complexity_mode == "average" and complexity_case_count:
        complexity["subjects"] = round(complexity["subjects"] / complexity_case_count, 1)
        complexity["findings"] = round(complexity["findings"] / complexity_case_count, 1)

    personas: dict[str, set[int]] = defaultdict(set)
    for persona in facts["personas"]:
        case_id = persona["case_id"]
        if case_id in selected_cases and _case_intersects_period(cases[case_id], events_by_case[case_id], start, end):
            personas[persona["persona_reference"]].add(case_id)
    persona_usage = [
        {"persona": persona, "active_investigations": len(case_ids)}
        for persona, case_ids in personas.items()
    ]
    persona_usage.sort(key=lambda item: (-item["active_investigations"], item["persona"]))

    difficult_cases = {
        "subjects": sorted(case_duration_rows, key=lambda row: (-row["subjects"], row["case_ref"]))[:5],
        "findings": sorted(case_duration_rows, key=lambda row: (-row["findings"], row["case_ref"]))[:5],
        "durations": sorted(
            [row for row in case_duration_rows if row["investigation_duration"] is not None],
            key=lambda row: (-row["investigation_duration"], row["case_ref"]),
        )[:5],
    }

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
        for case_id, case_events in events_by_case.items():
            for event in case_events:
                owner = _owner_at(cases[case_id], case_events, event["at"])
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
            "Peak active cases exceeds the personal 75th percentile.",
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
                "Unstarted assigned cases",
                max(current_preparation),
                baseline_preparation,
                "Preparation cases exceed the personal 75th percentile.",
            )

        baseline_subjects: list[float] = []
        baseline_findings: list[float] = []
        current_subjects: list[float] = []
        current_findings: list[float] = []
        baseline_rework: list[float] = []
        current_rework: list[float] = []
        baseline_review_wait: list[float] = []
        current_review_wait: list[float] = []
        for case_id, case in cases.items():
            case_events = events_by_case[case_id]
            started = _lifecycle_events(case_events, "in_progress")
            submitted = _lifecycle_events(case_events, "submitted")
            returned = _lifecycle_events(case_events, "rejected")
            completed = _lifecycle_events(case_events, "completed")
            if started and _owner_at(case, case_events, started[0]["at"]) == investigator_id:
                if baseline_start <= started[0]["at"].date() < baseline_end:
                    baseline_subjects.append(subject_counts[case_id])
                    baseline_findings.append(finding_counts[case_id])
                if (
                    _owner_at(case, case_events, end_point) == investigator_id
                    and _state_at(case, case_events, end_point) == "in_progress"
                ):
                    current_subjects.append(subject_counts[case_id])
                    current_findings.append(finding_counts[case_id])
            if returned and completed and _owner_at(case, case_events, returned[0]["at"]) == investigator_id:
                duration = _duration_days(returned[0]["at"], completed[-1]["at"])
                if baseline_start <= completed[-1]["at"].date() < baseline_end:
                    baseline_rework.append(duration)
                if start <= completed[-1]["at"].date() < end:
                    current_rework.append(duration)
            for index, submitted_event in enumerate(submitted):
                if _owner_at(case, case_events, submitted_event["at"]) != investigator_id:
                    continue
                next_events = [
                    event for event in case_events
                    if event["at"] > submitted_event["at"]
                    and event["event_type"] == "case.lifecycle_changed"
                    and event["details"].get("status") in {"rejected", "completed"}
                ]
                if next_events and baseline_start <= submitted_event["at"].date() < baseline_end:
                    baseline_review_wait.append(_duration_days(submitted_event["at"], next_events[0]["at"]))
                if (
                    index == len(submitted) - 1
                    and _state_at(case, case_events, end_point) == "submitted"
                    and start <= submitted_event["at"].date() < end
                ):
                    current_review_wait.append(_duration_days(submitted_event["at"], end_point))
        if baseline_subjects and current_subjects:
            add_attention(
                investigator_id,
                "Started case subjects",
                max(current_subjects),
                baseline_subjects,
                "A started case has an unusually high subject count.",
            )
        if baseline_findings and current_findings:
            add_attention(
                investigator_id,
                "Started case findings",
                max(current_findings),
                baseline_findings,
                "A started case has an unusually high finding count.",
            )
        if baseline_rework and current_rework:
            add_attention(
                investigator_id,
                "Returned to Completed duration",
                max(current_rework),
                baseline_rework,
                "A completed case has an extended rework duration.",
            )
        if baseline_review_wait and current_review_wait:
            add_attention(
                investigator_id,
                "Submitted review wait",
                max(current_review_wait),
                baseline_review_wait,
                "A submitted case is waiting longer than the personal 75th percentile.",
            )

    coverage_notice = (
        "Historical workload attribution is limited where a case has no auditable assignment event before the reporting period."
        if any(
            not _assignment_events(case, events_by_case[case_id])
            for case_id, case in cases.items()
            if _case_intersects_period(case, events_by_case[case_id], start, end)
        )
        else None
    )
    return {
        "start": start,
        "end": end,
        "generated_at": datetime.combine(today, datetime.now().time()),
        "bucket_granularity": granularity,
        "buckets": list(buckets.values()),
        "throughput": throughput,
        "workload": workload,
        "durations": duration_summary,
        "complexity": complexity,
        "persona_usage": persona_usage,
        "difficult_cases": difficult_cases,
        "manager_attention": attention,
        "coverage_notice": coverage_notice,
    }
