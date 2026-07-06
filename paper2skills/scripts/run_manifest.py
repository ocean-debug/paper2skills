"""Final run manifest with file-level provenance for build outputs."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from common import now_utc
from constants import BUILDER_VERSION, SCHEMA_VERSION


ROOT_ARTIFACT_SUFFIXES = {".yaml", ".jsonl", ".json", ".md", ".svg"}
ALLOWED_RECORD_ROLES = {"run_artifact", "child_skill_file", "retained_process_artifact"}
EXCLUDED_MANIFEST_FILES = {"run_manifest.yaml", "artifact_validation.yaml"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path, root: Path, role: str) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(root)).replace("\\", "/"),
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def root_artifact_files(out: Path) -> list[Path]:
    return sorted(
        path
        for path in out.iterdir()
        if path.is_file() and path.suffix.lower() in ROOT_ARTIFACT_SUFFIXES and path.name not in EXCLUDED_MANIFEST_FILES
    )


def child_skill_files(out: Path) -> list[Path]:
    child_root = out / "child_skill"
    if not child_root.exists():
        return []
    return sorted(path for path in child_root.rglob("*") if path.is_file())


def active_retention_dir(out: Path, publish_manifest: dict[str, Any] | None) -> Path | None:
    retention_path = str((publish_manifest or {}).get("output_retention_path") or "")
    if not retention_path:
        return None
    path = out / retention_path
    if not path.suffix:
        return None
    directory = path.parent
    if path.name != "output_retention.yaml":
        return None
    if directory.resolve(strict=False) == out.resolve(strict=False):
        return None
    if not is_within(path, out) or not path.exists() or not path.is_file():
        return None
    if is_within(directory, out) and directory.exists() and directory.is_dir():
        return directory
    return None


def retained_process_dirs(out: Path, publish_manifest: dict[str, Any] | None = None) -> list[Path]:
    retention_path = str((publish_manifest or {}).get("output_retention_path") or "")
    active = active_retention_dir(out, publish_manifest)
    if active is not None:
        return [active]
    return []


def retained_process_files(out: Path, publish_manifest: dict[str, Any] | None = None) -> list[Path]:
    files = []
    for directory in retained_process_dirs(out, publish_manifest):
        for path in directory.rglob("*"):
            if path.is_file() and path.name not in EXCLUDED_MANIFEST_FILES:
                files.append(path)
    return sorted(files)


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def build_run_manifest(request: dict[str, Any], out: Path, publish_manifest: dict[str, Any]) -> dict[str, Any]:
    artifact_records = [file_record(path, out, "run_artifact") for path in root_artifact_files(out)]
    child_records = [file_record(path, out, "child_skill_file") for path in child_skill_files(out)]
    retained_records = [file_record(path, out, "retained_process_artifact") for path in retained_process_files(out, publish_manifest)]
    all_records = artifact_records + child_records + retained_records
    return {
        "schema_version": SCHEMA_VERSION,
        "builder_version": BUILDER_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "output_dir": ".",
        "publish_status": publish_manifest.get("status"),
        "publish_manifest_path": "publish_manifest.yaml",
        "artifact_count": len(artifact_records),
        "child_skill_file_count": len(child_records),
        "retained_process_artifact_count": len(retained_records),
        "file_count": len(all_records),
        "files": all_records,
        "policy": [
            "Run manifest records generated artifacts and public child-skill files only.",
            "Downloaded sources, copied local source material, execution traces, and caches remain governed by source and execution artifacts.",
            "Retained process artifacts are hash-checked from the retention directory, excluding run_manifest.yaml and artifact_validation.yaml to avoid cyclic validation hashes.",
            "Hashes support remote validation, release review, and rollback without embedding long source excerpts.",
        ],
    }


def add_finding(findings: list[dict[str, Any]], severity: str, code: str, path: str, message: str) -> None:
    findings.append({"severity": severity, "code": code, "path": path, "message": message})


def verify_run_manifest(run_dir: Path, run_manifest: dict[str, Any], publish_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    files = run_manifest.get("files", [])
    if not files:
        add_finding(findings, "error", "missing_file_records", "run_manifest.yaml", "No file records were found.")
    retention_path = str((publish_manifest or {}).get("output_retention_path") or "")
    if active_retention_dir(run_dir, publish_manifest) is None:
        add_finding(
            findings,
            "error",
            "invalid_output_retention_path",
            "publish_manifest.yaml",
            "publish_manifest.output_retention_path must point to an existing output_retention.yaml file inside a retention directory.",
        )
    expected_paths = {
        str(path.relative_to(run_dir)).replace("\\", "/")
        for path in root_artifact_files(run_dir) + child_skill_files(run_dir) + retained_process_files(run_dir, publish_manifest)
    }
    recorded_paths: set[str] = set()
    for record in files:
        rel = str(record.get("path") or "")
        role = str(record.get("role") or "")
        expected_hash = str(record.get("sha256") or "")
        expected_bytes = record.get("bytes")
        if not rel:
            add_finding(findings, "error", "missing_path", "run_manifest.yaml", "A file record is missing path.")
            continue
        if rel in recorded_paths:
            add_finding(findings, "error", "duplicate_file_record", rel, "Run manifest records the same file more than once.")
        recorded_paths.add(rel)
        if role not in ALLOWED_RECORD_ROLES:
            add_finding(findings, "error", "invalid_record_role", rel, "File record role must be run_artifact, child_skill_file, or retained_process_artifact.")
        if not expected_hash:
            add_finding(findings, "error", "missing_sha256", rel, "File record is missing SHA-256.")
        if expected_bytes is None:
            add_finding(findings, "error", "missing_byte_size", rel, "File record is missing byte size.")
        if rel == "run_manifest.yaml":
            add_finding(findings, "error", "manifest_records_itself", rel, "Run manifest must not record itself.")
        path = run_dir / rel
        if not is_within(path, run_dir):
            add_finding(findings, "error", "recorded_file_outside_run_dir", rel, "Recorded path resolves outside the run directory.")
            continue
        if not path.exists():
            add_finding(findings, "error", "missing_file", rel, "Recorded file does not exist.")
            continue
        if not path.is_file():
            add_finding(findings, "error", "not_a_file", rel, "Recorded path is not a file.")
            continue
        actual_bytes = path.stat().st_size
        if expected_bytes is not None and actual_bytes != expected_bytes:
            add_finding(
                findings,
                "error",
                "byte_size_mismatch",
                rel,
                f"Expected {expected_bytes} bytes, observed {actual_bytes}.",
            )
        actual_hash = sha256_file(path)
        if expected_hash and actual_hash != expected_hash:
            add_finding(
                findings,
                "error",
                "sha256_mismatch",
                rel,
                "Recorded SHA-256 does not match current file content.",
            )
    missing_records = sorted(expected_paths.difference(recorded_paths))
    for rel in missing_records:
        add_finding(findings, "error", "unrecorded_generated_file", rel, "Generated root artifact or child-skill file is not recorded in run_manifest.yaml.")
    extra_records = sorted(recorded_paths.difference(expected_paths))
    for rel in extra_records:
        if rel != "run_manifest.yaml":
            role = next((str(record.get("role") or "") for record in files if str(record.get("path") or "") == rel), "")
            if role == "retained_process_artifact":
                add_finding(findings, "error", "retained_record_outside_manifest_scope", rel, "Recorded retained-process file is outside the manifest-selected retention scope.")
            else:
                add_finding(findings, "warning", "recorded_file_outside_manifest_scope", rel, "Recorded file is outside the generated artifact and child-skill manifest scope.")
    if run_manifest.get("file_count") != len(files):
        add_finding(findings, "error", "file_count_mismatch", "run_manifest.yaml", "file_count must match the number of file records.")
    has_errors = any(finding.get("severity") == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "status": "fail" if has_errors else "pass",
        "file_count": len(files),
        "expected_file_count": len(expected_paths),
        "recorded_file_count": len(recorded_paths),
        "missing_record_count": len(missing_records),
        "extra_record_count": len(extra_records),
        "findings": findings,
    }
