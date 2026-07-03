"""Audit source fetch path, opt-in, and extraction boundaries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


PATH_FIELDS = ("local_path", "extract_path")
HTTP_STATUSES_WITHOUT_FETCH = {"skipped_fetch_disabled"}
UNSAFE_EXTRACT_STATUSES = {"blocked_unsafe_zip_member"}


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    evidence_id: str | None = None,
    path: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if evidence_id:
        item["evidence_id"] = evidence_id
    if path:
        item["path"] = path
    findings.append(item)


def is_http(uri: str) -> bool:
    return uri.startswith("http://") or uri.startswith("https://")


def resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def audit_source_fetch_boundaries(
    request: dict[str, Any],
    source_fetch_report: dict[str, Any],
) -> dict[str, Any]:
    """Return a static audit for source fetch output and opt-in boundaries."""
    findings: list[dict[str, Any]] = []
    output_dir = resolved(request.get("output_dir") or ".")
    allowed_root = output_dir / "sources"
    fetch_enabled = bool(source_fetch_report.get("fetch_enabled"))
    max_fetch_bytes = int(source_fetch_report.get("max_fetch_bytes") or 0)
    path_records: list[dict[str, Any]] = []

    if fetch_enabled and max_fetch_bytes <= 0:
        add_finding(
            findings,
            "error",
            "invalid_max_fetch_bytes",
            "Fetch is enabled but max_fetch_bytes is not a positive integer.",
        )

    for source in source_fetch_report.get("sources", []):
        evidence_id = str(source.get("evidence_id") or "")
        uri = str(source.get("uri") or "")
        status = str(source.get("status") or "")
        if is_http(uri) and not fetch_enabled:
            if status not in HTTP_STATUSES_WITHOUT_FETCH:
                add_finding(
                    findings,
                    "error",
                    "remote_source_fetched_without_opt_in",
                    "Remote HTTP(S) source must not be fetched when fetch_sources is false.",
                    evidence_id=evidence_id,
                )
            for field in PATH_FIELDS:
                if source.get(field):
                    add_finding(
                        findings,
                        "error",
                        "remote_source_has_local_path_without_opt_in",
                        "Remote HTTP(S) source produced a local path even though fetch_sources is false.",
                        evidence_id=evidence_id,
                        path=str(source.get(field)),
                    )

        for field in PATH_FIELDS:
            value = source.get(field)
            if not value:
                continue
            actual = resolved(value)
            within = is_within(actual, allowed_root)
            path_records.append(
                {
                    "evidence_id": evidence_id,
                    "field": field,
                    "path": str(actual),
                    "within_sources_root": within,
                }
            )
            if not within:
                add_finding(
                    findings,
                    "error",
                    "source_material_outside_run_sources_root",
                    "Fetched or registered source material must stay under the run sources directory.",
                    evidence_id=evidence_id,
                    path=str(actual),
                )

        extract = source.get("extract") or {}
        extract_status = str(extract.get("status") or "")
        if extract_status in UNSAFE_EXTRACT_STATUSES:
            add_finding(
                findings,
                "error",
                "unsafe_archive_extraction_blocked",
                "Archive extraction reported an unsafe member and must block publish.",
                evidence_id=evidence_id,
            )
        if extract_status == "skipped_too_many_files":
            add_finding(
                findings,
                "warning",
                "archive_too_many_files",
                "Archive extraction was skipped because it exceeded the file-count safety limit.",
                evidence_id=evidence_id,
            )

    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "fetch_enabled": fetch_enabled,
        "max_fetch_bytes": max_fetch_bytes,
        "output_dir": str(output_dir),
        "allowed_sources_root": str(allowed_root),
        "source_count": len(source_fetch_report.get("sources", [])),
        "path_record_count": len(path_records),
        "path_records": path_records,
        "findings": findings,
        "policy": [
            "Remote source fetching must remain explicit opt-in.",
            "Fetched or locally registered source material must stay under the run sources directory.",
            "Archive extraction safety failures block publish even when source parsing is otherwise non-executing.",
        ],
    }
