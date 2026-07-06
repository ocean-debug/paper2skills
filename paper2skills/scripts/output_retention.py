"""Post-build retention, cleanup, and generation-process documentation."""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path
from typing import Any

from artifact_validator import POST_CLEANUP_ARTIFACTS, REQUIRED_TOP_LEVEL_ARTIFACTS
from common import ensure_dir, load_data, md_table, now_utc, read_text, write_data, write_text
from constants import SCHEMA_VERSION


ROOT_ARTIFACT_SUFFIXES = {".yaml", ".jsonl", ".json", ".md", ".svg"}
TEXT_RETENTION_SUFFIXES = {".yaml", ".yml", ".json", ".jsonl", ".md", ".txt", ".svg"}
PROCESS_DIRS = ["sources", ".source_cache"]
EXTRA_GENERATED_ROOT_FILES = {
    "review_log.jsonl",
    "review_iterations.jsonl",
    "review_evolution_plot.svg",
    "review_iteration_log.md",
    "acceptance_handoff.md",
    "run_scorecard.md",
}
GENERATED_ROOT_ARTIFACT_NAMES = (
    {f"{name}.yaml" for name in REQUIRED_TOP_LEVEL_ARTIFACTS + POST_CLEANUP_ARTIFACTS}
    | EXTRA_GENERATED_ROOT_FILES
)
RESERVED_RETENTION_DIRS = {
    "child_skill",
    "final_skill",
    "sources",
    ".source_cache",
    "source_cache",
} | GENERATED_ROOT_ARTIFACT_NAMES
FINAL_ROOT_ARTIFACTS = {"publish_manifest.yaml", "run_manifest.yaml"}
EXCLUDED_RETAINED_ARTIFACTS = {"run_manifest.yaml", "artifact_validation.yaml"}
LOCAL_URI_RE = re.compile("file://" + r"/[^\s)\"']+")
PATH_SEPARATOR_RE = r"(?:/|" + re.escape(chr(92)) + ")"
WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:" + PATH_SEPARATOR_RE + r"[^\s)\"']+")
POSIX_LOCAL_PATH_RE = re.compile(r"(?<!:)\/(?:home|Users|tmp)\/[^\s)\"']+")
UNC_PATH_RE = re.compile(re.escape(chr(92) * 2) + r"[^\s)\"']+")
SENSITIVE_REQUEST_KEY_RE = re.compile(
    r"(host|hostname|server|node|queue|partition|environment|conda|activation|workdir|work_dir|output_dir|path|dir|token|secret|password)",
    re.IGNORECASE,
)


def safe_component(value: Any, default: str) -> str:
    text = str(value or default).strip().replace("\\", "/").split("/")[-1]
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in text).strip("._")
    return cleaned or default


def reserved_retention_component(name: str) -> bool:
    return name in RESERVED_RETENTION_DIRS or Path(name).suffix.lower() in ROOT_ARTIFACT_SUFFIXES


def planned_output_retention(request: dict[str, Any]) -> dict[str, str]:
    retention_dir_name = safe_component(request.get("retained_process_artifacts_dir"), "iteration_versions")
    if reserved_retention_component(retention_dir_name):
        retention_dir_name = "iteration_versions"
    process_doc_name = safe_component(request.get("generation_process_doc"), "generation_process.md")
    if (
        process_doc_name in FINAL_ROOT_ARTIFACTS
        or process_doc_name in RESERVED_RETENTION_DIRS
        or process_doc_name in GENERATED_ROOT_ARTIFACT_NAMES
        or Path(process_doc_name).suffix.lower() != ".md"
        or process_doc_name == retention_dir_name
    ):
        process_doc_name = "generation_process.md"
    return {
        "retention_dir": retention_dir_name,
        "generation_process_doc": process_doc_name,
        "output_retention_path": f"{retention_dir_name}/output_retention.yaml",
    }


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def source_cache_cleanup_path(request: dict[str, Any], out: Path) -> Path | None:
    if not bool(request.get("reuse_fetched_sources", True)):
        return None
    requested = Path(str(request.get("source_cache_dir") or out / ".source_cache")).expanduser()
    if is_within(requested, out):
        return requested
    return out / ".source_cache"


def protected_cleanup_dir(path: Path, out: Path, retention_dir: Path) -> bool:
    protected_roots = [out / "child_skill", out / "final_skill", retention_dir]
    resolved = path.resolve(strict=False)
    for root in protected_roots:
        root_resolved = root.resolve(strict=False)
        if resolved == root_resolved or is_within(resolved, root_resolved):
            return True
    return False


def retention_safe_text(text: str, out: Path) -> str:
    replacements = {
        str(out.resolve(strict=False)).replace("\\", "/"): "<run_dir>",
        str(out.resolve(strict=False)): "<run_dir>",
        str(out).replace("\\", "/"): "<run_dir>",
        str(out): "<run_dir>",
    }
    safe = text
    for needle, replacement in replacements.items():
        if needle:
            safe = safe.replace(needle, replacement)
    safe = LOCAL_URI_RE.sub("local_source_material:<redacted>", safe)
    safe = WINDOWS_PATH_RE.sub("<local_path>", safe)
    safe = POSIX_LOCAL_PATH_RE.sub("<local_path>", safe)
    safe = UNC_PATH_RE.sub("<local_path>", safe)
    return safe


def redact_sensitive_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact_sensitive_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_sensitive_value(item) for item in value]
    if isinstance(value, str):
        return "<redacted>" if value else value
    return value


def retention_safe_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if SENSITIVE_REQUEST_KEY_RE.search(key_text):
                redacted[key] = redact_sensitive_value(item)
            else:
                redacted[key] = retention_safe_value(item)
        return redacted
    if isinstance(value, list):
        return [retention_safe_value(item) for item in value]
    if isinstance(value, str):
        return retention_safe_text(value, Path("."))
    return value


def copy_retained_artifact(src: Path, dest: Path, out: Path) -> None:
    ensure_dir(dest.parent)
    if src.name == "request.yaml":
        try:
            write_data(dest, retention_safe_value(load_data(src)))
            return
        except Exception:
            pass
    if src.suffix.lower() in TEXT_RETENTION_SUFFIXES:
        write_text(dest, retention_safe_text(read_text(src), out))
    else:
        shutil.copy2(src, dest)


def root_artifact_candidates(out: Path) -> list[Path]:
    return sorted(
        path
        for path in out.iterdir()
        if path.is_file()
        and path.suffix.lower() in ROOT_ARTIFACT_SUFFIXES
        and path.name not in EXCLUDED_RETAINED_ARTIFACTS
    )


def copy_iteration_artifacts(out: Path, retention_dir: Path) -> list[dict[str, Any]]:
    records = []
    ensure_dir(retention_dir)
    for src in root_artifact_candidates(out):
        name = rel(src, out)
        dest = retention_dir / name
        copy_retained_artifact(src, dest, out)
        records.append(
            {
                "path": name,
                "retained": True,
                "retained_path": rel(dest, out),
                "bytes": dest.stat().st_size,
                "sha256": sha256_file(dest),
            }
        )
    return records


def protected_root_artifacts(request: dict[str, Any]) -> set[str]:
    plan = planned_output_retention(request)
    return FINAL_ROOT_ARTIFACTS | {plan["generation_process_doc"]}


def run_artifact_paths(out: Path, run_manifest: dict[str, Any], protected_names: set[str]) -> list[Path]:
    paths = []
    for record in run_manifest.get("files", []):
        if record.get("role") != "run_artifact":
            continue
        rel_path = str(record.get("path") or "")
        if rel_path in protected_names:
            continue
        path = out / rel_path
        if path.exists() and is_within(path, out):
            paths.append(path)
    manifest_path = out / "run_manifest.yaml"
    if manifest_path.exists() and manifest_path.name not in protected_names:
        paths.append(manifest_path)
    return sorted(set(paths))


def delete_paths(paths: list[Path], out: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    deleted = []
    failed = []
    for path in sorted(set(paths), key=lambda item: len(item.parts), reverse=True):
        if not is_within(path, out) or path == out:
            failed.append({"path": str(path), "reason": "outside_output_dir"})
            continue
        if not path.exists():
            continue
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            deleted.append({"path": rel(path, out)})
        except OSError as exc:
            failed.append({"path": rel(path, out), "reason": str(exc)})
    return deleted, failed


def task_rows(task_catalog: dict[str, Any]) -> list[list[str]]:
    rows = []
    for task in task_catalog.get("tasks", []):
        rows.append(
            [
                f"`{task.get('task_type')}`",
                str(task.get("verification_status") or "unknown"),
                ", ".join(str(ref) for ref in task.get("evidence_refs", [])[:4]) or "none",
            ]
        )
    return rows


def review_rows(review_result: dict[str, Any]) -> list[list[str]]:
    rows = []
    for item in review_result.get("iterations", []):
        gate = next((state for state in item.get("states", []) if state.get("role") == "gate"), {})
        rows.append(
            [
                str(item.get("iteration")),
                str(item.get("score_ratio")),
                str(item.get("blocking")),
                str(gate.get("reason") or "unknown"),
            ]
        )
    return rows


def final_child_skill_path(out: Path) -> str:
    child_root = out / "child_skill"
    if not child_root.exists():
        return "child_skill"
    children = sorted(path for path in child_root.iterdir() if path.is_dir())
    if len(children) == 1:
        return rel(children[0], out)
    return rel(child_root, out)


def render_generation_process_md(
    request: dict[str, Any],
    task_catalog: dict[str, Any],
    review_result: dict[str, Any],
    publish_gate: dict[str, Any],
    retention_report: dict[str, Any],
) -> str:
    retained_rows = [
        [record["path"], record.get("retained_path", "missing")]
        for record in retention_report.get("retained_iteration_artifacts", [])
        if record.get("retained")
    ]
    deleted_rows = [[record["path"]] for record in retention_report.get("deleted_process_artifacts", [])[:80]]
    failed_rows = [[record["path"], record["reason"]] for record in retention_report.get("cleanup_failures", [])]
    task_table = md_table(["task_type", "verification", "evidence"], task_rows(task_catalog))
    review_table = md_table(["iteration", "score_ratio", "blocking", "gate"], review_rows(review_result))
    retained_table = md_table(["artifact", "retained path"], retained_rows) if retained_rows else "No iteration artifacts were retained."
    deleted_table = md_table(["deleted path"], deleted_rows) if deleted_rows else "No process artifacts were deleted."
    failed_text = "\n\n## Cleanup Failures\n\n" + md_table(["path", "reason"], failed_rows) if failed_rows else ""
    return f"""# Generation Process

Package: `{request.get('package_name')}`
Method: `{request.get('method_name') or request.get('package_name')}`
Created: `{retention_report.get('created_at')}`

## Final Outputs

- Final child skill: `{retention_report.get('final_child_skill_path')}`
- Iteration/version artifacts: `{retention_report.get('retention_dir')}`
- Cleanup enabled: `{retention_report.get('cleanup_enabled')}`
- Publish gate status: `{publish_gate.get('status')}`
- Recommended action: `{publish_gate.get('recommended_action')}`

## First-Principles Build Chain

1. Ground official sources without executing package code.
2. Partition evidence-backed capabilities into `task_type` entries inside one child skill.
3. Render contracts, refusal boundaries, validation rules, troubleshooting, and evidence references.
4. Run the agent-driven paper2skills review loop over draft artifacts.
5. Promote the selected child-skill candidate and retain only final skill plus iteration/version evidence.

## Task Types

{task_table}

## Review Iterations

{review_table}

## Retained Iteration Artifacts

{retained_table}

## Deleted Process Artifacts

{deleted_table}
{failed_text}
"""


def refresh_retained_artifacts(out: Path, retention_report: dict[str, Any], artifact_names: list[str]) -> dict[str, Any]:
    """Copy finalized root entry artifacts into the retained process directory."""
    retention_dir = out / str(retention_report.get("retention_dir") or "iteration_versions")
    if not is_within(retention_dir, out):
        failures = retention_report.setdefault("cleanup_failures", [])
        failures.append(
            {
                "path": str(retention_report.get("retention_dir") or "iteration_versions"),
                "reason": "retention_dir_resolves_outside_output_dir",
            }
        )
        retention_report["cleanup_failure_count"] = len(failures)
        retention_report["status"] = "fail"
        return retention_report
    ensure_dir(retention_dir)
    records = retention_report.setdefault("retained_iteration_artifacts", [])
    by_path = {record.get("path"): record for record in records if isinstance(record, dict)}
    refreshed = []
    for name in artifact_names:
        src = out / name
        if not src.exists() or not src.is_file():
            continue
        dest = retention_dir / name
        ensure_dir(dest.parent)
        copy_retained_artifact(src, dest, out)
        record = by_path.get(name)
        if record is None:
            record = {"path": name}
            records.append(record)
            by_path[name] = record
        record.update(
            {
                "retained": True,
                "retained_path": rel(dest, out),
                "bytes": dest.stat().st_size,
                "sha256": sha256_file(dest),
                "finalized": True,
            }
        )
        refreshed.append(name)
    retention_report["retained_iteration_artifact_count"] = sum(1 for record in records if record.get("retained"))
    retention_report["finalized_retained_artifacts"] = refreshed
    write_data(retention_dir / "output_retention.yaml", retention_report)
    return retention_report


def refresh_generation_process_doc(
    request: dict[str, Any],
    out: Path,
    task_catalog: dict[str, Any],
    review_result: dict[str, Any],
    publish_gate: dict[str, Any],
    retention_report: dict[str, Any],
) -> dict[str, Any]:
    """Rewrite the public process document after the final retention refresh."""
    process_doc_name = str(retention_report.get("generation_process_doc") or "generation_process.md")
    write_text(out / process_doc_name, render_generation_process_md(request, task_catalog, review_result, publish_gate, retention_report))
    return refresh_retained_artifacts(out, retention_report, [process_doc_name])


def build_output_retention(
    request: dict[str, Any],
    out: Path,
    run_manifest: dict[str, Any],
    task_catalog: dict[str, Any],
    review_result: dict[str, Any],
    publish_gate: dict[str, Any],
) -> dict[str, Any]:
    """Retain final child skill plus version artifacts and optionally remove process files."""
    cleanup_enabled = bool(request.get("cleanup_process_files", True))
    retention_plan = planned_output_retention(request)
    retention_dir_name = retention_plan["retention_dir"]
    process_doc_name = retention_plan["generation_process_doc"]
    retention_dir = out / retention_dir_name
    retention_dir_failure: dict[str, Any] | None = None
    if retention_dir.exists() or retention_dir.is_symlink():
        if not is_within(retention_dir, out):
            retention_dir_failure = {
                "path": retention_dir_name,
                "reason": "retention_dir_resolves_outside_output_dir",
            }
        elif retention_dir.is_symlink():
            retention_dir.unlink()
        elif retention_dir.is_dir():
            shutil.rmtree(retention_dir)
        else:
            retention_dir.unlink()
    retained = [] if retention_dir_failure else copy_iteration_artifacts(out, retention_dir)
    candidates = []
    candidate_failures: list[dict[str, Any]] = []
    if not retention_dir_failure:
        candidates = run_artifact_paths(out, run_manifest, protected_root_artifacts(request))
        cache_path = source_cache_cleanup_path(request, out)
        for dirname in PROCESS_DIRS:
            path = out / dirname
            if path.exists() and is_within(path, out):
                candidates.append(path)
        if cache_path and cache_path.exists() and is_within(cache_path, out):
            if protected_cleanup_dir(cache_path, out, retention_dir):
                candidate_failures.append(
                    {
                        "path": rel(cache_path, out),
                        "reason": "source_cache_dir_overlaps_protected_output",
                    }
                )
            else:
                candidates.append(cache_path)
    deleted: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    if retention_dir_failure:
        failures.append(retention_dir_failure)
    failures.extend(candidate_failures)
    if cleanup_enabled and not retention_dir_failure:
        deleted, cleanup_failures = delete_paths(candidates, out)
        failures.extend(cleanup_failures)
    findings = []
    if not cleanup_enabled:
        findings.append(
            {
                "severity": "error",
                "code": "cleanup_disabled_leaves_raw_root_artifacts",
                "message": "cleanup_process_files=false leaves raw root artifacts in place, so publish must remain blocked.",
            }
        )
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if failures or findings else "pass",
        "cleanup_enabled": cleanup_enabled,
        "output_dir": ".",
        "final_child_skill_path": final_child_skill_path(out),
        "retention_dir": rel(retention_dir, out),
        "generation_process_doc": process_doc_name,
        "retained_iteration_artifact_count": sum(1 for record in retained if record.get("retained")),
        "deleted_process_artifact_count": len(deleted),
        "cleanup_failure_count": len(failures),
        "retained_iteration_artifacts": retained,
        "deleted_process_artifacts": deleted,
        "cleanup_failures": failures,
        "findings": findings,
        "policy": [
            "Keep the final child skill under child_skill/.",
            "Keep final root entry artifacts so publish and manifest verification paths remain valid.",
            "Keep selected iteration and candidate-version artifacts under the retention directory.",
            "Delete only builder-generated process artifacts recorded by run_manifest plus builder source/cache directories.",
            "Do not delete unknown user files that are outside the generated run manifest.",
        ],
    }
    if not retention_dir_failure:
        write_data(retention_dir / "output_retention.yaml", report)
    write_text(out / process_doc_name, render_generation_process_md(request, task_catalog, review_result, publish_gate, report))
    return report
