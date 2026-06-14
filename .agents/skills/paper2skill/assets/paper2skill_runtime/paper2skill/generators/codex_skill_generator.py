from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import shutil
from typing import Any

import jinja2
import yaml

from paper2skill.collectors.path_sanitizer import REDACTED_LOCAL_PATH, public_data
from paper2skill.collectors.paper_collector import collect_paper
from paper2skill.collectors.repo_collector import collect_repo
from paper2skill.collectors.tutorial_collector import collect_tutorials
from paper2skill.compiler import build_empty_run_trace
from paper2skill.compiler import build_tutorial_catalog as build_generic_tutorial_catalog
from paper2skill.compiler import evaluate_maturity, infer_algorithm_archetype, normalize_bio_contract_evidence
from paper2skill.common import PROJECT_ROOT, ensure_dir, slugify, write_json, write_text, write_yaml
from paper2skill.evidence.evidence_graph import build_evidence_graph
from paper2skill.env_rebuilder.canonical_env import CANONICAL_ENV_RELATIVE_PATH
from paper2skill.env_rebuilder.routes import DEFAULT_BIOCONDA_CHANNELS, package_key, route_python_packages, route_r_packages
from paper2skill.inference.classify_algorithm import classify_algorithm
from paper2skill.inference.infer_bio_contract import infer_bio_contract
from paper2skill.inference.infer_environment import infer_environment_spec
from paper2skill.inference.infer_io_contract import infer_io_contract
from paper2skill.inference.infer_parameters import infer_parameters
from paper2skill.inference.infer_workflow import infer_workflow
from paper2skill.miners.api_miner import mine_api
from paper2skill.miners.dependency_miner import mine_dependencies
from paper2skill.miners.tutorial_miner import mine_repo_tutorials, mine_tutorials
from paper2skill.runtime.env_manager import inspect_environment
from paper2skill.runtime.install_planner import build_install_plan, render_install_plan_markdown
from paper2skill.validators.adapter_review import adapter_review_matches, missing_explicit_adapter_mapping


TEMPLATE_ROOT = PROJECT_ROOT / "paper2skill" / "templates" / "codex_skill"
EXECUTABLE_ADAPTER_STATUSES = {"verified"}
ADAPTER_STATUSES = {"dry_run_only", "verified"}
DEFAULT_EXAMPLE_ID = "official_example_001"
SOURCE_SNAPSHOT_MAX_FILE_BYTES = 5 * 1024 * 1024
SOURCE_SNAPSHOT_SKIP_PARTS = {
    ".git",
    ".github",
    "__pycache__",
    ".pytest_cache",
    ".paper2skill",
    "build",
    "dist",
}


@dataclass
class ResolvedInputs:
    paper_result: dict[str, Any] | None
    repo_result: dict[str, Any] | None
    repo_path: Path | None
    explicit_tutorials: list[Path]
    selected_tutorials: list[Path]
    source_manifest: dict[str, Any]
    warnings: list[str]


def example_inputs(example: str) -> dict[str, Any]:
    fixtures = PROJECT_ROOT / "examples"
    if example == "toy_python":
        root = fixtures / "toy_python_algorithm"
        return {
            "skill_name": "toy-python-skill",
            "algorithm_name": "Toy Python Algorithm",
            "task": "demo_table_summary",
            "paper": str(root / "paper.md"),
            "repo": str(root),
            "tutorials": [str(root / "examples" / "demo.py"), str(fixtures / "toy_notebook.ipynb")],
            "language": "python",
            "maturity_level": "L2",
        }
    if example == "toy_r":
        root = fixtures / "toy_r_algorithm"
        return {
            "skill_name": "toy-r-skill",
            "algorithm_name": "Toy R Algorithm",
            "task": "demo_table_summary",
            "paper": str(root / "paper.md"),
            "repo": str(root),
            "tutorials": [str(root / "examples" / "demo.R"), str(fixtures / "toy_script.R")],
            "language": "r",
            "maturity_level": "L2",
        }
    raise ValueError(f"unknown example: {example}")


def resolve_inputs(
    *,
    paper: str | None,
    repo: str | None,
    tutorials: list[str],
    paper_url: str | None,
    paper_title: str | None,
    repo_ref: str,
    skip_repo_clone: bool,
    tutorial_filter: str | None,
    collection_dir: str | Path | None,
    skill_name: str,
) -> ResolvedInputs:
    base = Path.cwd().resolve()
    work_dir = Path(collection_dir).resolve() if collection_dir else (base / ".paper2skill-resolve" / skill_name)
    warnings: list[str] = []
    paper_result = collect_paper(paper, paper_url, paper_title, base)
    repo_result = collect_repo(repo, repo_ref, base, work_dir=work_dir, skip_clone=skip_repo_clone) if repo else None
    if repo_result and (repo_result.get("manifest") or {}).get("clone_status") == "skipped":
        warnings.append("remote repo clone was skipped; repo-dependent mining was not executed")
    repo_path = Path(repo_result["resolved_path"]) if repo_result and repo_result.get("resolved_path") and Path(repo_result["resolved_path"]).exists() else None
    explicit_tutorials = resolve_tutorial_paths(tutorials, repo_path)
    selected_tutorials = explicit_tutorials
    tutorial_result = collect_tutorials([str(path) for path in explicit_tutorials], base_dir=repo_path or base)
    source_manifest = {
        "base_dir": REDACTED_LOCAL_PATH,
        "paper": paper_result,
        "repo": repo_result or {"url": None, "local_path": None, "resolved_path": None, "ref": repo_ref, "exists": False, "manifest": None, "index": {"files": []}},
        "tutorial": tutorial_result,
        "options": {
            "target": "codex_skill",
            "allow_network": False,
            "install_policy": "ask",
            "maturity_target": "L1",
            "repo_ref": repo_ref,
            "skip_repo_clone": skip_repo_clone,
            "tutorial_filter": tutorial_filter,
        },
    }
    return ResolvedInputs(paper_result, repo_result, repo_path, explicit_tutorials, selected_tutorials, source_manifest, warnings)


def resolve_tutorial_paths(tutorials: list[str], repo_path: Path | None) -> list[Path]:
    resolved = []
    for value in tutorials:
        path = Path(value)
        if path.exists():
            resolved.append(path.resolve())
            continue
        if repo_path and (repo_path / value).exists():
            resolved.append((repo_path / value).resolve())
            continue
        resolved.append(path)
    return resolved


def public_resolved_inputs(resolved: ResolvedInputs) -> dict[str, Any]:
    data = asdict(resolved)
    data["repo_path"] = str(resolved.repo_path) if resolved.repo_path else None
    data["explicit_tutorials"] = [str(path) for path in resolved.explicit_tutorials]
    data["selected_tutorials"] = [str(path) for path in resolved.selected_tutorials]
    return public_data(data, PROJECT_ROOT)


def infer_adapter_type(repo_evidence: dict[str, Any], tutorial_trace: dict[str, Any], classification: dict[str, str]) -> str:
    if repo_evidence.get("workflow_engines"):
        return "workflow_engine"
    if official_rscript_command(tutorial_trace):
        return "r_script"
    if repo_evidence.get("package_type") == "r_package" or classification.get("language") == "r":
        return "r_script"
    if repo_evidence.get("entrypoints") or repo_evidence.get("cli_commands"):
        return "cli"
    tutorials = tutorial_trace.get("tutorials", [])
    if tutorials and has_notebook_tutorial(tutorials):
        return "notebook"
    python_package = str(repo_evidence.get("package_type", "")).startswith("python_")
    if (classification.get("language") == "python" or python_package) and (safe_python_api_functions(repo_evidence) or repo_evidence.get("classes") or has_installable_python_package_source(repo_evidence)):
        return "python_api"
    if tutorials and all(trace.get("language") == "python" for trace in tutorials) and not safe_python_api_functions(repo_evidence):
        return "notebook"
    return "demo_only"


def has_installable_python_package_source(repo_evidence: dict[str, Any]) -> bool:
    if not str(repo_evidence.get("package_type", "")).startswith("python_"):
        return False
    ignored_roots = {"docs", "doc", "examples", "example", "notebooks", "notebook", "tests", "test"}
    for value in repo_evidence.get("tutorials", []) or []:
        path = str(value).replace("\\", "/")
        parts = [part for part in path.split("/") if part]
        if not path.endswith(".py") or path == "setup.py" or not parts:
            continue
        if parts[0].lower() in ignored_roots:
            continue
        return True
    return False


def has_notebook_tutorial(tutorials: list[dict[str, Any]]) -> bool:
    for trace in tutorials:
        path = str(trace.get("path") or "").lower()
        if path.endswith(".ipynb") or trace.get("execution_policy"):
            return True
    return False


def load_adapter_review(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    review_path = Path(path)
    if not review_path.exists():
        return None
    data = yaml.safe_load(review_path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else None


def default_adapter_review(spec: dict[str, Any]) -> dict[str, Any]:
    default_caveats = list(spec.get("caveats", []) or [])
    if spec.get("status") not in EXECUTABLE_ADAPTER_STATUSES:
        default_caveats = ["Generated adapters start as dry_run_only until run_trace and output validation pass", *default_caveats]
    return {
        "adapter_type": spec.get("adapter_type"),
        "status": spec.get("status"),
        "entrypoint": spec.get("entrypoint"),
        "command": spec.get("command"),
        "module": spec.get("module"),
        "function": spec.get("function"),
        "verification": {"status": "not_run"},
        "expected_outputs": list(spec.get("expected_outputs", []) or []),
        "evidence": list(spec.get("evidence", []) or []),
        "caveats": default_caveats,
    }


def apply_adapter_review(spec: dict[str, Any], review: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if not review:
        return spec, default_adapter_review(spec)
    review_data = {**default_adapter_review(spec), **review}
    requested_status = review_data.get("status")
    if requested_status not in ADAPTER_STATUSES:
        reviewed_spec = dict(spec)
        reviewed_spec["status"] = "dry_run_only"
        reviewed_spec["caveats"] = list(spec.get("caveats", []) or []) + ["adapter_review.yaml requested an invalid status"]
        review_data["status"] = "dry_run_only"
        return reviewed_spec, review_data
    if requested_status == "verified":
        if missing := missing_explicit_adapter_mapping(spec, review):
            reviewed_spec = dict(spec)
            reviewed_spec["status"] = "dry_run_only"
            reviewed_spec["caveats"] = list(spec.get("caveats", []) or []) + [f"adapter_review.yaml must provide explicit adapter mapping: {', '.join(missing)}"]
            review_data["status"] = "dry_run_only"
            return reviewed_spec, review_data
        if not adapter_review_matches(spec, review):
            reviewed_spec = dict(spec)
            reviewed_spec["status"] = "dry_run_only"
            reviewed_spec["caveats"] = list(spec.get("caveats", []) or []) + ["adapter_review.yaml mapping does not match the inferred adapter"]
            review_data["status"] = "dry_run_only"
            return reviewed_spec, review_data
        if not adapter_review_has_verified_evidence(review_data):
            reviewed_spec = dict(spec)
            reviewed_spec["status"] = "dry_run_only"
            reviewed_spec["caveats"] = list(spec.get("caveats", []) or []) + ["verified status requires run_trace evidence with passing output_validation"]
            review_data["status"] = "dry_run_only"
            return reviewed_spec, review_data
    reviewed_spec = dict(spec)
    for key in ["adapter_type", "entrypoint", "command", "module", "function"]:
        if key in review_data:
            reviewed_spec[key] = review_data.get(key)
    reviewed_spec["status"] = requested_status
    reviewed_spec["evidence"] = sorted(dict.fromkeys((spec.get("evidence", []) or []) + (review_data.get("evidence", []) or [])))
    reviewed_spec["caveats"] = list(review_data.get("caveats", []) or reviewed_spec.get("caveats", []) or [])
    return reviewed_spec, review_data


def adapter_review_has_ready_evidence(review: dict[str, Any]) -> bool:
    verification = review.get("verification") if isinstance(review.get("verification"), dict) else {}
    dry_run = review.get("dry_run") if isinstance(review.get("dry_run"), dict) else {}
    return verification.get("status") == "pass" or dry_run.get("status") == "pass"


def adapter_review_has_verified_evidence(review: dict[str, Any]) -> bool:
    verification = review.get("verification") if isinstance(review.get("verification"), dict) else {}
    output_validation = verification.get("output_validation") if isinstance(verification.get("output_validation"), dict) else {}
    evidence = [str(item).lower() for item in review.get("evidence", []) or []]
    has_run_trace = verification.get("source") == "run_trace" or "run_trace" in evidence or bool(verification.get("run_trace"))
    return has_run_trace and adapter_review_has_ready_evidence(review) and output_validation.get("status") == "pass" and bool(review.get("expected_outputs"))


def build_adapter_spec(
    adapter_type: str,
    repo_evidence: dict[str, Any],
    tutorial_trace: dict[str, Any],
) -> dict[str, Any]:
    spec = {
        "adapter_type": adapter_type,
        "status": "dry_run_only",
        "entrypoint": None,
        "command": None,
        "module": None,
        "function": None,
        "evidence": [],
        "caveats": [],
    }
    if adapter_type == "demo_only":
        spec["status"] = "dry_run_only"
        spec["caveats"] = ["No real algorithm adapter was inferred; generated skill is dry-run only until a verification-capable adapter is produced"]
        return spec
    if adapter_type == "python_api":
        candidate = select_python_api_candidate(repo_evidence)
        if candidate:
            module = candidate.get("public_module") or candidate.get("module")
            function = candidate.get("name")
            spec.update(
                {
                    "entrypoint": f"{module}:{function}",
                    "module": module,
                    "function": function,
                    "evidence": [candidate.get("path", "api_miner")],
                    "caveats": ["Python API adapter remains dry_run_only until run_trace and output validation pass"],
                }
            )
            return spec
        if repo_evidence.get("classes"):
            spec["caveats"] = ["Python class-based API evidence was found, but no safe module-level runner function was inferred; adapter remains dry_run_only"]
        else:
            spec["caveats"] = ["Python package/API evidence was found, but no safe importable function was inferred; adapter remains dry_run_only"]
        return spec
    if adapter_type == "cli":
        entrypoint = first_item(repo_evidence.get("entrypoints", [])) or first_item(repo_evidence.get("cli_commands", []))
        command = None
        target = None
        if entrypoint:
            command = entrypoint.get("command") or entrypoint.get("name")
            target = entrypoint.get("target") or entrypoint.get("path")
        spec.update(
            {
                "entrypoint": target,
                "command": command,
                "evidence": [entrypoint.get("source")] if entrypoint else [],
                "caveats": ["CLI command remains dry_run_only until run_trace and output validation pass"],
            }
        )
        return spec
    if adapter_type == "workflow_engine":
        engine = first_item(repo_evidence.get("workflow_engines", []))
        spec.update(
            {
                "entrypoint": engine.get("engine") if engine else None,
                "command": engine.get("engine") if engine else None,
                "evidence": engine.get("files", []) if engine else [],
                "caveats": ["Workflow engine execution remains dry_run_only until run_trace and output validation pass"],
            }
        )
        return spec
    if adapter_type == "r_script":
        official = official_rscript_command(tutorial_trace)
        if official:
            spec.update(
                {
                    "status": "dry_run_only",
                    "entrypoint": "scripts/adapters/official_rscript_adapter.py",
                    "command": ["python", "scripts/adapters/official_rscript_adapter.py", "{manifest}", "{out}"],
                    "evidence": official.get("evidence", []),
                    "official_command": official.get("command"),
                    "official_script": official.get("script"),
                    "expected_outputs": ["results/summary.json"],
                    "caveats": [
                        "Official Rscript command pattern is detected but remains dry_run_only until output validation passes",
                        "Biological interpretation still requires full output validation by the child skill",
                    ],
                }
            )
            return spec
        spec["caveats"] = ["R script adapter requires verifiable function or script wiring"]
        return spec
    if adapter_type == "notebook":
        spec.update(
            {
                "entrypoint": "scripts/adapters/notebook_adapter.py",
                "command": ["python", "scripts/adapters/notebook_adapter.py", "{manifest}", "{out}", "{example_id}"],
                "expected_outputs": ["results/summary.json"],
                "caveats": ["Notebook smoke adapter executes a filtered official notebook path and remains dry_run_only until run_trace and output validation pass"],
            }
        )
        return spec
    spec["status"] = "dry_run_only"
    spec["caveats"] = ["Unsupported adapter type"]
    return spec


def apply_adapter_interface(spec: dict[str, Any], archetype: dict[str, Any]) -> dict[str, Any]:
    """Attach the generic Paper2Skill adapter interface without changing safety state."""
    interface = dict(archetype.get("interface") or {})
    enriched = dict(interface)
    enriched.update(spec)
    enriched["adapter_type"] = spec.get("adapter_type") or interface.get("adapter_type")
    enriched["archetype"] = archetype.get("archetype")
    enriched["install_contract"] = spec.get("install_contract") or interface.get("install_contract") or {"install_policy": "ask"}
    enriched["input_binding"] = spec.get("input_binding") or interface.get("input_binding") or {"status": "not_confirmed", "manifest_required": True}
    enriched["run_command_or_api"] = spec.get("run_command_or_api") or interface.get("run_command_or_api")
    enriched["expected_outputs"] = list(spec.get("expected_outputs") or interface.get("expected_outputs") or [])
    enriched["verification"] = spec.get("verification") or interface.get("verification") or {"status": "not_run", "source": "static_inference"}
    enriched["status"] = spec.get("status") or "dry_run_only"
    return enriched


def select_python_api_candidate(repo_evidence: dict[str, Any]) -> dict[str, Any] | None:
    functions = safe_python_api_functions(repo_evidence)
    if not functions:
        return None
    candidate = sorted(functions, key=score_python_api_candidate)[0]
    if repo_evidence.get("classes") and score_python_api_candidate(candidate)[0] >= 20:
        return None
    return candidate


def safe_python_api_functions(repo_evidence: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in repo_evidence.get("api_functions", []) if is_safe_python_api_function(item)]


def is_safe_python_api_function(item: dict[str, Any]) -> bool:
    module = str(item.get("public_module") or item.get("module") or "")
    name = str(item.get("name") or "")
    path = str(item.get("path") or "").replace("\\", "/")
    args = list(item.get("args") or [])
    parts = [part.lower() for part in path.split("/") if part]
    if not module or not name or path == "setup.py":
        return False
    if name.startswith("_") or name in {"readme", "get_version", "setup", "main", "commandargs", "lazy_import", "set_verbose_mode"}:
        return False
    if args and str(args[0]) in {"self", "cls"}:
        return False
    if parts and parts[0] in {"tests", "test", "docs", "doc", "examples", "example", "notebooks", "notebook"}:
        return False
    if parts and parts[-1] == "__init__.py" and name not in {"summarize", "run", "fit_transform", "predict", "transform", "fit", "train", "analyze", "process", "evaluate"}:
        return False
    if path.endswith("/setup.py") or "/tests/" in f"/{path}" or "/test/" in f"/{path}":
        return False
    return True


def score_python_api_candidate(item: dict[str, Any]) -> tuple[int, str, str]:
    name = str(item.get("name") or "").lower()
    path = str(item.get("path") or "").replace("\\", "/").lower()
    priority_names = {
        "summarize": 0,
        "run": 1,
        "fit_transform": 2,
        "predict": 3,
        "transform": 4,
        "fit": 5,
        "train": 6,
        "analyze": 7,
        "process": 8,
        "evaluate": 9,
    }
    score = priority_names.get(name, 20)
    if any(token in path for token in ["/utils", "/plot", "/benchmark", "/simulation"]):
        score += 10
    return (score, path, name)


def first_item(values: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    return values[0] if values else None


def official_rscript_command(tutorial_trace: dict[str, Any]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for tutorial in tutorial_trace.get("tutorials", []) or []:
        path = str(tutorial.get("path") or "tutorial")
        for item in _flatten_strings(tutorial):
            for match in re.finditer(r"\bRscript(?:\s+--vanilla)?\s+([A-Za-z0-9_./-]+\.R)(?:\s+[^\n`$]*)?", item):
                command = match.group(0).strip()
                script = match.group(1).split("/")[-1]
                candidates.append({"command": command, "script": script, "evidence": [f"{path}:official_rscript_command"]})
    if not candidates:
        return None
    def score(item: dict[str, Any]) -> tuple[int, str]:
        command = str(item.get("command") or "").lower()
        score_value = 0
        if "arg1" in command or "arg2" in command:
            score_value += 5
        if re.search(r"\b[a-z0-9_./-]+\.(txt|tsv|csv|rds)\b", command):
            score_value -= 2
        if "goi" in command:
            score_value += 3
        return (score_value, command)

    return sorted(candidates, key=score)[0]


def notebook_execution_policy(tutorial_trace: dict[str, Any]) -> dict[str, Any]:
    combined = {
        "will_execute": False,
        "reason": "static_analysis_only",
        "notebooks": [],
        "shell_magics": [],
        "line_magics": [],
        "cell_magics": [],
        "parameter_cells": [],
        "large_outputs": [],
        "risks": [],
    }
    risks: set[str] = set()
    for tutorial in tutorial_trace.get("tutorials", []):
        policy = tutorial.get("execution_policy")
        if not policy:
            continue
        path = tutorial.get("path")
        combined["notebooks"].append(path)
        for key in ["shell_magics", "line_magics", "cell_magics", "large_outputs"]:
            for item in policy.get(key, []) or []:
                record = dict(item)
                record["notebook"] = path
                combined[key].append(record)
        for cell in policy.get("parameter_cells", []) or []:
            combined["parameter_cells"].append({"notebook": path, "cell": cell})
        risks.update(policy.get("risks", []) or [])
    combined["risks"] = sorted(risks)
    return combined


def build_context(
    *,
    skill_name: str | None = None,
    algorithm_name: str | None = None,
    task: str = "algorithm_execution",
    paper: str | None = None,
    repo: str | None = None,
    tutorials: list[str] | None = None,
    paper_url: str | None = None,
    paper_title: str | None = None,
    maturity_level: str = "L1",
    language: str | None = None,
    repo_ref: str = "main",
    skip_repo_clone: bool = False,
    no_execute_tutorials: bool = True,
    strict_evidence: bool = False,
    tutorial_filter: str | None = None,
    adapter_review: str | Path | None = None,
    example_data_urls: list[str] | None = None,
    collection_dir: str | Path | None = None,
) -> dict[str, Any]:
    skill_name = slugify(skill_name or algorithm_name or "generated-skill")
    algorithm_name = algorithm_name or skill_name.replace("-", " ").title()
    tutorials = tutorials or []
    resolved = resolve_inputs(
        paper=paper,
        repo=repo,
        tutorials=tutorials,
        paper_url=paper_url,
        paper_title=paper_title,
        repo_ref=repo_ref,
        skip_repo_clone=skip_repo_clone,
        tutorial_filter=tutorial_filter,
        collection_dir=collection_dir,
        skill_name=skill_name,
    )
    source_manifest = resolved.source_manifest
    tutorial_paths = [str(path) for path in resolved.selected_tutorials]
    if tutorial_paths:
        tutorial_trace = mine_tutorials(tutorial_paths, base_dir=resolved.repo_path if resolved.repo_path else None)
        if resolved.repo_path and not tutorials:
            repo_tutorial_trace = mine_repo_tutorials(resolved.repo_path, tutorial_filter=tutorial_filter)
            tutorial_trace["tutorial_candidates"] = repo_tutorial_trace.get("tutorial_candidates", [])
            tutorial_trace["tutorial_scanner_report"] = repo_tutorial_trace.get("tutorial_scanner_report", {})
        else:
            tutorial_trace["tutorial_candidates"] = []
            tutorial_trace["tutorial_scanner_report"] = {"total": len(tutorial_paths), "included": len(tutorial_paths), "filter": tutorial_filter}
    elif resolved.repo_path:
        tutorial_trace = mine_repo_tutorials(resolved.repo_path, tutorial_filter=tutorial_filter)
    else:
        tutorial_trace = {"tutorials": [], "workflow_steps": [], "steps": [], "tutorial_candidates": [], "tutorial_scanner_report": {"total": 0, "included": 0, "filter": tutorial_filter}}
    tutorial_trace["tutorial_execution_status"] = "not_executed_by_policy" if no_execute_tutorials else "not_executed"
    dependency_evidence = mine_dependencies(resolved.repo_path, tutorial_paths)
    repo_evidence = mine_api(resolved.repo_path)
    classification = classify_algorithm(repo_evidence, tutorial_trace)
    if language:
        classification["language"] = language
        classification["execution_mode"] = "python_api" if language == "python" else "r_script"
    adapter_type = infer_adapter_type(repo_evidence, tutorial_trace, classification)
    adapter_spec = build_adapter_spec(
        adapter_type,
        repo_evidence,
        tutorial_trace,
    )
    algorithm_archetype = infer_algorithm_archetype(repo_evidence, tutorial_trace, classification, adapter_type)
    adapter_spec = apply_adapter_interface(adapter_spec, algorithm_archetype)
    adapter_spec, adapter_review_data = apply_adapter_review(adapter_spec, load_adapter_review(adapter_review))
    examples_catalog = build_generic_tutorial_catalog(
        tutorial_trace,
        adapter_spec,
        repo_evidence,
        classification,
        algorithm_archetype,
        user_data_urls=example_data_urls or [],
    )
    environment_spec = infer_environment_spec(dependency_evidence, classification["language"])
    if classification["language"] == "python" and not environment_spec["python"]["packages"]:
        environment_spec["python"]["packages"] = []
    if classification["language"] == "r":
        environment_spec["r"]["required"] = True
    environment_report = inspect_environment(environment_spec)
    install_plan = build_install_plan(environment_report, environment_spec)
    parameters = infer_parameters(tutorial_trace)
    workflow = infer_workflow(tutorial_trace)
    paper_sections = (((source_manifest.get("paper") or {}).get("parsed_document") or {}).get("sections") or [])
    bio_contract = normalize_bio_contract_evidence(infer_bio_contract(tutorial_trace, paper_sections, dependency_evidence, strict_evidence=strict_evidence))
    io_contract = infer_io_contract(tutorial_trace, bio_contract)
    run_trace = build_empty_run_trace(example_id=examples_catalog.get("default_example_id"))
    maturity = evaluate_maturity(adapter_spec, examples_catalog, run_trace)
    algorithm_contract = {
        "algorithm": {
            "name": algorithm_name,
            "task": task,
            "domain": classification["domain"],
            "modality": "not_confirmed",
            "language": classification["language"],
            "execution_mode": classification["execution_mode"],
            "archetype": algorithm_archetype["archetype"],
            "adapter_type": adapter_type,
            "adapter_status": adapter_spec["status"],
            "maturity_level": maturity["level"],
        },
        **io_contract,
        "environment_contract": {
            "install_policy_default": "ask",
            "preflight_required": True,
            "auto_install_requires_confirmation": True,
        },
        "maturity": maturity,
    }
    evidence_report = {
        "evidence_priority": ["tutorial", "docs", "api", "dependency_files", "paper_methods", "paper_abstract", "readme"],
        "sources": source_manifest,
        "claims": _claims_from_context(algorithm_contract, workflow),
    }
    evidence_graph = build_evidence_graph(
        paper_evidence=source_manifest.get("paper"),
        tutorial_trace=tutorial_trace,
        dependency_evidence=dependency_evidence,
        bio_contract=bio_contract,
        algorithm_contract=algorithm_contract,
    )
    return {
        "skill_name": skill_name,
        "algorithm_name": algorithm_name,
        "task": task,
        "language": classification["language"],
        "maturity_level": maturity["level"],
        "source_manifest": source_manifest,
        "resolved_inputs": public_resolved_inputs(resolved),
        "paper_evidence": _paper_evidence(source_manifest),
        "repo_evidence": repo_evidence,
        "dependency_evidence": dependency_evidence,
        "tutorial_trace": tutorial_trace,
        "workflow": workflow,
        "parameters": parameters,
        "algorithm_archetype": algorithm_archetype,
        "environment_spec": environment_spec,
        "environment_report": environment_report,
        "install_plan": install_plan,
        "install_plan_markdown": render_install_plan_markdown(install_plan),
        "adapter_spec": adapter_spec,
        "adapter_review": adapter_review_data,
        "examples_catalog": examples_catalog,
        "tutorial_catalog": examples_catalog,
        "run_trace": run_trace,
        "maturity": maturity,
        "notebook_execution_policy": notebook_execution_policy(tutorial_trace),
        "algorithm_contract": algorithm_contract,
        "bio_contract": bio_contract,
        "evidence_graph": evidence_graph,
        "evidence_report": evidence_report,
        "input_sources": {
            "paper": paper,
            "repo": repo,
            "repo_ref": repo_ref,
            "skip_repo_clone": skip_repo_clone,
            "no_execute_tutorials": no_execute_tutorials,
            "strict_evidence": strict_evidence,
            "tutorial_filter": tutorial_filter,
            "adapter_review": str(adapter_review) if adapter_review else None,
            "example_data_urls": example_data_urls or [],
        },
        "warnings": resolved.warnings,
        "demo_data": _demo_data_for_language(classification["language"]),
    }


def generate_skill(context: dict[str, Any], out_dir: str | Path) -> Path:
    root = ensure_dir(Path(out_dir))
    env = _jinja_env()
    public_context = _public_context(context)
    template_targets = {
        "SKILL.md.j2": "SKILL.md",
        "scripts/preflight.py.j2": "scripts/preflight.py",
        "scripts/env_manager.py.j2": "scripts/env_manager.py",
        "scripts/run_in_env.sh.j2": "scripts/run_in_env.sh",
        "scripts/plan.py.j2": "scripts/plan.py",
        "scripts/run.py.j2": "scripts/run.py",
        "scripts/validate_outputs.py.j2": "scripts/validate_outputs.py",
        "scripts/adapters/__init__.py.j2": "scripts/adapters/__init__.py",
        "scripts/adapters/command_adapter.py.j2": "scripts/adapters/command_adapter.py",
        "scripts/adapters/python_api_adapter.py.j2": "scripts/adapters/python_api_adapter.py",
        "scripts/adapters/cli_adapter.py.j2": "scripts/adapters/cli_adapter.py",
        "scripts/adapters/notebook_adapter.py.j2": "scripts/adapters/notebook_adapter.py",
        "scripts/adapters/official_rscript_adapter.py.j2": "scripts/adapters/official_rscript_adapter.py",
        "scripts/adapters/workflow_engine_adapter.py.j2": "scripts/adapters/workflow_engine_adapter.py",
        "scripts/adapters/r_script_adapter.py.j2": "scripts/adapters/r_script_adapter.py",
        "scripts/adapters/r_script_adapter.R.j2": "scripts/adapters/r_script_adapter.R",
        "references/evidence_report.md.j2": "references/evidence_report.md",
        "references/paper_summary.md.j2": "references/paper_summary.md",
        "references/repo_summary.md.j2": "references/repo_summary.md",
        "references/api_reference.md.j2": "references/api_reference.md",
        "references/tutorial_trace.md.j2": "references/tutorial_trace.md",
        "assets/input_manifest_template.yaml.j2": "assets/input_manifest_template.yaml",
        "assets/config_template.yaml.j2": "assets/config_template.yaml",
        "agents/openai.yaml.j2": "agents/openai.yaml",
    }
    for template_name, rel_target in template_targets.items():
        content = env.get_template(template_name).render(**public_context)
        write_text(root / rel_target, content)
    write_json(root / "references" / "tutorial_trace.json", public_context["tutorial_trace"])
    write_json(root / "references" / "workflow_dag.json", public_context["workflow"].get("workflow_dag", {"nodes": [], "edges": []}))
    write_json(root / "references" / "tutorial_candidates.json", public_context["tutorial_trace"].get("tutorial_candidates", []))
    write_json(root / "references" / "tutorial_scanner_report.json", public_context["tutorial_trace"].get("tutorial_scanner_report", {}))
    write_json(root / "references" / "environment_report.json", _public_environment_report(context["environment_report"]))
    write_json(root / "references" / "source_manifest.json", public_context["source_manifest"])
    write_json(root / "references" / "paper_evidence.json", public_context["paper_evidence"])
    write_json(root / "references" / "repo_evidence.json", public_context["repo_evidence"])
    write_yaml(root / "references" / "algorithm_contract.yaml", public_context["algorithm_contract"])
    write_yaml(root / "references" / "adapter_spec.yaml", public_context["adapter_spec"])
    write_yaml(root / "references" / "adapter_review.yaml", public_context["adapter_review"])
    write_yaml(root / "references" / "examples_catalog.yaml", public_context["examples_catalog"])
    write_yaml(root / "references" / "tutorial_catalog.yaml", public_context["tutorial_catalog"])
    write_yaml(root / "references" / "maturity.yaml", public_context["maturity"])
    write_yaml(root / "references" / "environment_spec.yaml", public_context["environment_spec"])
    write_json(root / "references" / "notebook_execution_policy.json", public_context["notebook_execution_policy"])
    write_yaml(root / "references" / "bio_contract.yaml", public_context["bio_contract"])
    write_yaml(root / "references" / "io_contract.yaml", {"input_contract": public_context["algorithm_contract"].get("input_contract"), "output_contract": public_context["algorithm_contract"].get("output_contract")})
    write_json(root / "references" / "evidence_graph.json", public_context["evidence_graph"])
    write_compiler_artifacts(root, public_context)
    write_optional_collection_outputs(public_context, root)
    write_json(root / "references" / "build_report.json", public_data(build_report(context), PROJECT_ROOT))
    write_text(root / "references" / "install_plan.md", public_context["install_plan_markdown"])
    write_text(root / "assets" / "environment_spec.yaml", json.dumps(public_context["environment_spec"], indent=2) + "\n")
    write_text(root / "assets" / "demo_input_manifest.yaml", json.dumps(public_data(_demo_manifest(context), PROJECT_ROOT), indent=2) + "\n")
    write_text(root / "assets" / "official_attempt_manifest.yaml", yaml.safe_dump(public_context["input_manifest_template"], sort_keys=False, allow_unicode=True))
    canonical_env, normalization_report = _canonical_environment(public_context)
    pip_segment = normalization_report.get("pip_segment") or []
    write_text(root / "assets" / "requirements.txt", ("\n".join(pip_segment) + "\n") if pip_segment else "")
    write_text(root / "assets" / "environment.yml", yaml.safe_dump(canonical_env, sort_keys=False))
    write_text(root / CANONICAL_ENV_RELATIVE_PATH, yaml.safe_dump(canonical_env, sort_keys=False))
    write_json(root / "assets" / "env" / "normalization_report.json", normalization_report)
    write_text(root / "assets" / "renv.lock.placeholder", "{}\n")
    write_text(root / "assets" / "demo_input.csv", context["demo_data"])
    write_source_snapshot(context, root)
    return root


def write_compiler_artifacts(root: Path, public_context: dict[str, Any]) -> None:
    contracts = root / "references" / "contracts"
    write_yaml(contracts / "algorithm_contract.yaml", public_context["algorithm_contract"])
    write_yaml(contracts / "adapter_contract.yaml", public_context["adapter_spec"])
    write_yaml(contracts / "bio_contract.yaml", public_context["bio_contract"])
    write_yaml(contracts / "environment_contract.yaml", public_context["environment_spec"])
    write_yaml(
        contracts / "io_contract.yaml",
        {
            "input_contract": public_context["algorithm_contract"].get("input_contract"),
            "output_contract": public_context["algorithm_contract"].get("output_contract"),
        },
    )
    write_yaml(root / "references" / "tutorial_catalog.yaml", public_context["tutorial_catalog"])
    write_yaml(root / "references" / "maturity.yaml", public_context["maturity"])
    write_json(root / "references" / "run_trace.template.json", public_context["run_trace"])
    write_text(root / "references" / "evidence_summary.md", evidence_summary_markdown(public_context))
    debug = root / "debug" / "evidence"
    write_json(debug / "source_manifest.json", public_context["source_manifest"])
    write_json(debug / "tutorial_trace.json", public_context["tutorial_trace"])
    write_json(debug / "workflow_dag.json", public_context["workflow"].get("workflow_dag", {"nodes": [], "edges": []}))
    write_json(debug / "evidence_graph.json", public_context["evidence_graph"])


def write_source_snapshot(context: dict[str, Any], root: Path) -> None:
    adapter_spec = context.get("adapter_spec") or {}
    repo_path = (((context.get("source_manifest") or {}).get("repo") or {}).get("resolved_path"))
    if not repo_path:
        return
    source_root = Path(repo_path)
    if not source_root.exists():
        return
    dest = root / "sources" / "repo"
    if dest.exists():
        shutil.rmtree(dest)
    ensure_dir(dest)
    copied: set[str] = set()
    for rel in source_snapshot_relative_paths(context, source_root):
        copy_repo_item(source_root, dest, rel, copied)
    for item in source_root.iterdir():
        if item.name.startswith(".") or item.name in {"__pycache__", ".pytest_cache", "tests", "docs", "examples", "data"}:
            continue
        target = dest / item.name
        if item.is_dir() and (item / "__init__.py").exists():
            copy_repo_item(source_root, dest, item.relative_to(source_root), copied)
        elif item.is_file() and (item.suffix == ".py" or item.name in {"pyproject.toml", "setup.py", "setup.cfg"}):
            copy_repo_item(source_root, dest, item.relative_to(source_root), copied)


def source_snapshot_relative_paths(context: dict[str, Any], source_root: Path) -> list[Path]:
    paths: list[Path] = []
    examples = ((context.get("examples_catalog") or {}).get("examples") or [])
    for example in examples:
        if isinstance(example, dict):
            paths.extend(_repo_relative_candidates(example.get("source"), source_root))
    for tutorial in (context.get("tutorial_trace") or {}).get("tutorials", []) or []:
        if not isinstance(tutorial, dict):
            continue
        paths.extend(_repo_relative_candidates(tutorial.get("path"), source_root))
        for key in ["file_reads", "source_files"]:
            for value in tutorial.get(key, []) or []:
                paths.extend(_repo_relative_candidates(value, source_root))
        paths.extend(_repo_relative_values(tutorial.get("parameters"), source_root))
        for step in tutorial.get("steps", []) or tutorial.get("workflow_steps", []) or []:
            if not isinstance(step, dict):
                continue
            for key in ["read_files", "inputs"]:
                for value in step.get(key, []) or []:
                    paths.extend(_repo_relative_candidates(value, source_root))
            paths.extend(_repo_relative_values(step.get("parameters"), source_root))
    repo_index = ((((context.get("source_manifest") or {}).get("repo") or {}).get("index") or {}).get("files") or [])
    tutorial_dirs = {path.parent for path in paths if path.parent != Path(".")}
    for item in repo_index:
        rel = Path(str(item.get("path") or ""))
        if rel.parent in tutorial_dirs and item.get("category") in {"source", "tutorial_candidate"}:
            paths.append(rel)
    return sorted(dict.fromkeys(path for path in paths if path.parts))


def _repo_relative_candidates(value: Any, source_root: Path) -> list[Path]:
    if not isinstance(value, str) or not value or value == REDACTED_LOCAL_PATH:
        return []
    raw = Path(value)
    candidates: list[Path] = []
    try:
        if raw.is_absolute():
            candidates.append(raw.resolve().relative_to(source_root.resolve()))
        else:
            candidates.append(raw)
    except (OSError, ValueError):
        pass
    return [candidate for candidate in candidates if safe_repo_relative_path(candidate)]


def _repo_relative_values(value: Any, source_root: Path) -> list[Path]:
    paths: list[Path] = []
    if isinstance(value, dict):
        for item in value.values():
            paths.extend(_repo_relative_values(item, source_root))
    elif isinstance(value, list):
        for item in value:
            paths.extend(_repo_relative_values(item, source_root))
    elif isinstance(value, str):
        for candidate in _repo_relative_candidates(value, source_root):
            if (source_root / candidate).exists():
                paths.append(candidate)
    return paths


def safe_repo_relative_path(path: Path) -> bool:
    return not path.is_absolute() and ".." not in path.parts and not any(part in SOURCE_SNAPSHOT_SKIP_PARTS or part.startswith(".") for part in path.parts)


def copy_repo_item(source_root: Path, dest: Path, rel: Path, copied: set[str]) -> None:
    if not safe_repo_relative_path(rel):
        return
    key = rel.as_posix()
    if key in copied:
        return
    source = source_root / rel
    target = dest / rel
    if source.is_dir():
        if not (source / "__init__.py").exists():
            return
        shutil.copytree(
            source,
            target,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
        )
        copied.add(key)
    elif source.is_file() and source.stat().st_size <= SOURCE_SNAPSHOT_MAX_FILE_BYTES:
        ensure_dir(target.parent)
        shutil.copyfile(source, target)
        copied.add(key)


def write_optional_collection_outputs(public_context: dict[str, Any], root: Path) -> None:
    paper = (public_context.get("source_manifest") or {}).get("paper") or {}
    parsed = paper.get("parsed_document") or {}
    if parsed:
        write_text(root / "references" / "paper.md", parsed.get("markdown", ""))
        write_json(
            root / "references" / "paper_sections.json",
            {
                "source_path": parsed.get("source_path"),
                "parser_name": parsed.get("parser_name"),
                "sections": [
                    {
                        "section_id": section.get("section_id"),
                        "title": section.get("title"),
                        "level": section.get("level"),
                        "start_line": section.get("start_line"),
                        "end_line": section.get("end_line"),
                        "char_count": len(section.get("text", "")),
                    }
                    for section in parsed.get("sections", [])
                ],
                "warnings": parsed.get("warnings", []),
            },
        )
        write_json(
            root / "references" / "paper_parser_report.json",
            {
                "source_path": parsed.get("source_path"),
                "source_type": parsed.get("source_type"),
                "parser_name": parsed.get("parser_name"),
                "warnings": parsed.get("warnings", []),
            },
        )
    repo = (public_context.get("source_manifest") or {}).get("repo") or {}
    write_json(root / "references" / "repo_manifest.json", repo.get("manifest"))
    write_json(root / "references" / "repo_index.json", repo.get("index", {"files": []}))


def build_report(context: dict[str, Any]) -> dict[str, Any]:
    sources = context.get("input_sources", {})
    missing = {}
    warnings = list(context.get("warnings", []))
    if not sources.get("paper"):
        missing["paper"] = "not provided"
    if not sources.get("repo"):
        missing["repo"] = "not provided"
    if sources.get("no_execute_tutorials", True):
        warnings.append("tutorial_execution_status=not_executed_by_policy")
    unresolved = [
        decision
        for decision in (context.get("evidence_graph") or {}).get("decisions", [])
        if (decision.get("decision") or {}).get("status") == "unresolved"
    ]
    if unresolved:
        warnings.append("unresolved evidence conflicts present")
    return {
        "status": "built_with_warnings" if warnings else "built",
        "missing_inputs": missing,
        "options": sources,
        "warnings": sorted(dict.fromkeys(warnings)),
        "tutorial_execution_status": (context.get("tutorial_trace") or {}).get("tutorial_execution_status", "not_executed_by_policy"),
        "unresolved_conflicts": unresolved,
    }


def plan_outputs(context: dict[str, Any], out_dir: str | Path) -> Path:
    root = ensure_dir(Path(out_dir))
    public_context = _public_context(context)
    write_yaml(root / "execution_plan.yaml", execution_plan(public_context))
    write_yaml(root / "tutorial_catalog.yaml", public_context["tutorial_catalog"])
    write_yaml(root / "maturity.yaml", public_context["maturity"])
    write_json(root / "evidence_claims.json", evidence_claims(public_context))
    write_json(root / "blocked_items.json", blocked_items(public_context))
    write_json(root / "source_manifest.json", public_context["source_manifest"])
    write_json(root / "paper_evidence.json", public_context["paper_evidence"])
    write_json(root / "repo_evidence.json", public_context["repo_evidence"])
    write_json(root / "tutorial_trace.json", public_context["tutorial_trace"])
    write_json(root / "workflow_dag.json", public_context["workflow"].get("workflow_dag", {"nodes": [], "edges": []}))
    write_yaml(root / "adapter_spec.preview.yaml", public_context["adapter_spec"])
    write_yaml(root / "adapter_review.preview.yaml", public_context["adapter_review"])
    write_yaml(root / "examples_catalog.preview.yaml", public_context["examples_catalog"])
    write_yaml(root / "tutorial_catalog.preview.yaml", public_context["tutorial_catalog"])
    write_json(root / "notebook_execution_policy.json", public_context["notebook_execution_policy"])
    write_yaml(root / "algorithm_contract.preview.yaml", public_context["algorithm_contract"])
    write_yaml(root / "bio_contract.preview.yaml", public_context["bio_contract"])
    write_json(root / "environment_report.json", _public_environment_report(context["environment_report"]))
    write_text(root / "build_plan.md", _build_plan_markdown(public_context))
    return root


def execution_plan(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "pipeline": [
            "collect_sources",
            "normalize_evidence",
            "build_tutorial_graph",
            "rank_execution_candidates",
            "run_candidate",
            "synthesize_contracts",
            "promote_skill",
            "evaluate_maturity",
        ],
        "algorithm": context["algorithm_contract"].get("algorithm", {}),
        "default_example_id": context["tutorial_catalog"].get("default_example_id"),
        "selected_candidate": selected_candidate(context["tutorial_catalog"]),
        "adapter": context["adapter_spec"],
        "maturity": context["maturity"],
        "run_gate": {
            "requires_explicit_confirmation": True,
            "verified_requires_run_trace": True,
            "static_inference_status": "dry_run_only",
        },
    }


def selected_candidate(catalog: dict[str, Any]) -> dict[str, Any]:
    default_id = catalog.get("default_example_id")
    for item in catalog.get("examples", []) or []:
        if isinstance(item, dict) and item.get("example_id") == default_id:
            return item
    return {}


def evidence_claims(context: dict[str, Any]) -> list[dict[str, Any]]:
    claims = list(((context.get("evidence_report") or {}).get("claims") or []))
    claims.append(
        {
            "claim": f"Algorithm archetype is {context.get('algorithm_archetype', {}).get('archetype')}",
            "evidence_id": "repo_or_tutorial_execution_shape",
            "source_type": "inferred",
            "claim_type": "inferred",
            "confidence": context.get("algorithm_archetype", {}).get("confidence", "low"),
        }
    )
    return claims


def blocked_items(context: dict[str, Any]) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    adapter = context.get("adapter_spec") or {}
    maturity = context.get("maturity") or {}
    if maturity.get("level") == "L1":
        blocks.append({"code": "contract_only_maturity", "message": "L1 skills can preflight and plan but require run trace promotion before real execution."})
    if adapter.get("status") != "verified":
        blocks.append({"code": "verified_adapter_missing", "message": "Run trace and output validation are required before real execution."})
    selected = selected_candidate(context.get("tutorial_catalog") or {})
    if selected.get("runnable_status") == "blocked":
        blocks.append({"code": "runnable_tutorial_missing", "message": "No runnable official tutorial/example was confirmed."})
    for risk in selected.get("risk_flags", []) or []:
        if risk in {"install", "download", "large_data", "notebook_side_effects"}:
            blocks.append({"code": f"review_required:{risk}", "message": f"{risk} requires explicit review before execution."})
    return {"blocked": bool(blocks), "items": blocks}


def evidence_summary_markdown(context: dict[str, Any]) -> str:
    algorithm = context["algorithm_contract"].get("algorithm", {})
    selected = selected_candidate(context.get("tutorial_catalog") or {})
    lines = [
        f"# Evidence Summary for {algorithm.get('name', context.get('algorithm_name', 'generated skill'))}",
        "",
        f"- Archetype: `{algorithm.get('archetype', 'not_confirmed')}`",
        f"- Adapter status: `{algorithm.get('adapter_status', 'dry_run_only')}`",
        f"- Maturity: `{(context.get('maturity') or {}).get('level', 'L1')}`",
        f"- Default example: `{selected.get('example_id', 'not_confirmed')}`",
        f"- Default data kind: `{selected.get('data_kind', 'not_confirmed')}`",
        "",
        "Verified execution requires a passing run trace and output validation. Static evidence remains contract-only.",
        "",
    ]
    return "\n".join(lines)


def _jinja_env() -> jinja2.Environment:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATE_ROOT)), autoescape=False, keep_trailing_newline=True)
    env.filters["to_nice_json"] = lambda value: json.dumps(value, indent=2, ensure_ascii=False)
    env.filters["to_nice_yaml"] = lambda value: yaml.safe_dump(value, sort_keys=False, allow_unicode=True)
    return env


def _paper_evidence(source_manifest: dict[str, Any]) -> dict[str, Any]:
    paper = source_manifest.get("paper", {})
    return {
        "paper": {
            "title": paper.get("title") or "not_confirmed",
            "doi": "not_confirmed",
            "year": "not_confirmed",
            "authors": "not_confirmed",
            "official_code": source_manifest.get("repo", {}).get("url") or source_manifest.get("repo", {}).get("local_path") or "not_confirmed",
            "official_data": "not_confirmed",
            "method_purpose": "not_confirmed",
            "algorithm_type": "not_confirmed",
            "input_data": "not_confirmed",
            "output_data": "not_confirmed",
            "core_steps": "not_confirmed",
            "key_parameters": "not_confirmed",
            "benchmark_datasets": "not_confirmed",
            "evaluation_metrics": "not_confirmed",
            "limitations": "not_confirmed",
        },
        "note": "Paper semantic extraction is delegated to Codex or ClaudeCode; CLI records available local text and source metadata.",
    }


def _public_context(context: dict[str, Any]) -> dict[str, Any]:
    clean = public_data(context, PROJECT_ROOT)
    clean["environment_report"] = _public_environment_report(context["environment_report"], PROJECT_ROOT)
    clean["input_manifest_template"] = _official_attempt_manifest(clean)
    return clean


def build_examples_catalog(
    tutorial_trace: dict[str, Any],
    adapter_spec: dict[str, Any],
    repo_evidence: dict[str, Any],
    classification: dict[str, Any],
    *,
    user_data_urls: list[str] | None = None,
) -> dict[str, Any]:
    examples: list[dict[str, Any]] = []
    seen: set[str] = set()
    user_data_urls = user_data_urls or []
    for index, tutorial in enumerate(tutorial_trace.get("tutorials", []) or [], start=1):
        if not isinstance(tutorial, dict):
            continue
        path = str(tutorial.get("path") or f"tutorial_{index}")
        text = "\n".join(_flatten_strings(tutorial))
        urls = sorted(dict.fromkeys([*extract_data_urls(text), *user_data_urls_for_tutorial(text, user_data_urls)]))
        scenario = classify_example_scenario(path, text)
        example_id = example_id_from_path(path, fallback_index=index)
        if example_id in seen:
            example_id = f"{example_id}_{index:03d}"
        seen.add(example_id)
        examples.append(
            {
                "example_id": example_id,
                "is_default": not examples,
                "source": path,
                "source_type": "notebook" if path.lower().endswith(".ipynb") else "tutorial",
                "source_excerpt": text[:2000],
                "scenario": scenario,
                "priority": example_priority(scenario, path, text),
                "data_sources": [{"type": "url", "url": url, "filename": filename_from_url(url)} for url in urls],
                "adapter": {
                    "adapter_type": adapter_spec.get("adapter_type"),
                    "status": adapter_spec.get("status", "dry_run_only"),
                    "entrypoint": adapter_spec.get("entrypoint"),
                    "command": adapter_spec.get("command"),
                    "official_command": adapter_spec.get("official_command"),
                    "official_script": adapter_spec.get("official_script"),
                    "module": adapter_spec.get("module"),
                    "function": adapter_spec.get("function"),
                },
                "output_contract": default_output_contract(adapter_spec),
                "verification": {"status": "not_run"},
                "caveats": ["Tutorial demo context is the primary evidence for this example; paper context is background only."],
            }
        )
    if not examples:
        examples.append(
            {
                "example_id": DEFAULT_EXAMPLE_ID,
                "is_default": True,
                "source": "not_confirmed",
                "source_type": "generated",
                "scenario": "quickstart",
                "priority": 100,
                "data_sources": [{"type": "manifest", "path": "assets/official_attempt_manifest.yaml"}],
                "adapter": {
                    "adapter_type": adapter_spec.get("adapter_type"),
                    "status": adapter_spec.get("status", "dry_run_only"),
                    "entrypoint": adapter_spec.get("entrypoint"),
                    "command": adapter_spec.get("command"),
                    "official_command": adapter_spec.get("official_command"),
                    "official_script": adapter_spec.get("official_script"),
                    "module": adapter_spec.get("module"),
                    "function": adapter_spec.get("function"),
                },
                "output_contract": default_output_contract(adapter_spec),
                "verification": {"status": "not_run"},
                "caveats": ["No explicit tutorial example was mined; this is a generated dry-run placeholder."],
            }
        )
    examples.sort(key=lambda item: (item.get("priority", 100), str(item.get("example_id"))))
    for index, item in enumerate(examples):
        item["is_default"] = index == 0
    return {
        "schema_version": 1,
        "selection_policy": "official small/test data > quickstart > package dataset > notebook demo > full tutorial",
        "default_example_id": examples[0]["example_id"],
        "examples": examples,
        "adapter_status_values": ["dry_run_only", "verified"],
        "notes": ["Adapter verification is per example; one verified example does not verify other examples."],
        "repo_package_type": repo_evidence.get("package_type"),
        "language": classification.get("language"),
    }


def extract_data_urls(text: str) -> list[str]:
    pattern = re.compile(r"https?://[^\s'\"),]+(?:\?[^\s'\"),]+)?")
    return [url for match in pattern.finditer(text) if (url := clean_data_url(match.group(0))) is not None]


def user_data_urls_for_tutorial(text: str, urls: list[str]) -> list[str]:
    if not urls:
        return []
    if len(urls) == 1:
        return urls
    lowered = text.lower()
    matched = []
    for url in urls:
        filename = filename_from_url(url)
        stem = Path(filename).stem.lower()
        tokens = {url.lower(), filename.lower(), stem}
        if any(token and token in lowered for token in tokens):
            matched.append(url)
    return matched


def clean_data_url(value: str) -> str | None:
    url = value.rstrip("`].\\")
    lowered = url.lower()
    if "#egg=" in lowered or "git+" in lowered:
        return None
    if "github.com" in lowered and not re.search(r"\.(h5ad|rds|rda|csv|tsv|txt)(?:\?|$)", lowered):
        return None
    return url


def filename_from_url(url: str) -> str:
    lowered = url.lower()
    if "pancreas.h5ad" in lowered:
        return "pancreas.h5ad"
    if "train_kang" in lowered or "1r87vhollq6pxaydmyyd89zg90ejofylk" in lowered:
        return "train_kang.h5ad"
    tail = url.split("?", 1)[0].rstrip("/").split("/")[-1]
    return tail or "downloaded_example_data"


def example_id_from_path(path: str, *, fallback_index: int) -> str:
    name = Path(path).stem if path and path != "not_confirmed" else f"official_example_{fallback_index:03d}"
    value = slugify(name, default=f"official-example-{fallback_index:03d}").replace("-", "_")
    return value or f"official_example_{fallback_index:03d}"


def classify_example_scenario(path: str, text: str) -> str:
    lowered = f"{path}\n{text}".lower()
    if "test data" in lowered or "/tests/" in lowered or "tests/data" in lowered:
        return "official_test_data"
    if "batch" in lowered and ("removal" in lowered or "correction" in lowered):
        return "batch_removal"
    if "perturb" in lowered or "stimulated" in lowered:
        return "perturbation_prediction"
    if "quickstart" in lowered or "getting started" in lowered:
        return "quickstart"
    if path.lower().endswith(".ipynb"):
        return "notebook_demo"
    return "tutorial_demo"


def example_priority(scenario: str, path: str, text: str) -> int:
    lowered = f"{path}\n{text}".lower()
    if scenario == "official_test_data":
        return 0
    if "small" in lowered or "toy" in lowered or "minimal" in lowered:
        return 5
    if scenario == "quickstart":
        return 10
    if "package" in lowered and "data(" in lowered:
        return 20
    if scenario in {"batch_removal", "perturbation_prediction"}:
        return 30
    if scenario == "notebook_demo":
        return 40
    return 50


def default_output_contract(adapter_spec: dict[str, Any]) -> dict[str, Any]:
    expected = list(adapter_spec.get("expected_outputs") or [])
    if not expected:
        expected = ["results/summary.json"]
    return {
        "required_files": expected,
        "json": {
            "results/summary.json": {
                "required_keys": ["status"],
            }
        },
        "tables": {},
        "nonempty": expected,
        "log_must_not_contain": ["Traceback", "Error:", "fatal error", "segmentation fault"],
    }


def _public_environment_report(report: dict[str, Any], base_dir: Path = PROJECT_ROOT) -> dict[str, Any]:
    clean = json.loads(json.dumps(public_data(report, base_dir)))
    python = clean.get("python")
    if isinstance(python, dict) and python.get("executable"):
        python["executable"] = REDACTED_LOCAL_PATH
    r = clean.get("r")
    if isinstance(r, dict) and r.get("rscript"):
        r["rscript"] = REDACTED_LOCAL_PATH
    for item in clean.get("executables", []) or []:
        if isinstance(item, dict) and item.get("path"):
            item["path"] = REDACTED_LOCAL_PATH
    return clean


def _claims_from_context(contract: dict[str, Any], workflow: dict[str, Any]) -> list[dict[str, Any]]:
    claims = [
        {
            "claim": f"Algorithm language is {contract['algorithm']['language']}",
            "evidence_id": "repo_or_tutorial_language",
            "source_type": "api_or_tutorial",
            "confidence": "medium",
        }
    ]
    for step in workflow.get("steps", []):
        claims.append(
            {
                "claim": f"Workflow includes {step.get('name')}",
                "evidence_id": step.get("evidence_id", "not_confirmed"),
                "source_type": step.get("source_type", "tutorial"),
                "confidence": step.get("confidence", "medium"),
            }
        )
    return claims


def _demo_manifest(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "inputs": {
            "primary_data": {"path": "assets/demo_input.csv", "format": "csv", "exists": True},
            "metadata": {"sample_key": "sample", "condition_key": "condition"},
            "algorithm": {"mode": "demo", "parameters": context["parameters"] or {"summary_column": "value"}},
        },
        "environment": {
            "preferred_manager": "conda",
            "environment_name": f"{context['skill_name']}-env",
            "install_policy": "ask",
        },
    }


def _official_attempt_manifest(context: dict[str, Any]) -> dict[str, Any]:
    primary_contract = _contract_primary_data(context)
    bio = _bio_contract_body(context)
    data_source = _official_data_source(context, _contract_value(primary_contract.get("format")) or "csv")
    primary_data = {
        "path": data_source["path"],
        "format": _contract_value(primary_contract.get("format")) or data_source["format"],
        "exists": data_source["exists"],
        "source": data_source["source"],
        "matrix_state": _manifest_matrix_state(primary_contract, bio),
    }
    for key, value in data_source.items():
        if key not in {"path", "format", "exists", "source"} and value is not None:
            primary_data[key] = value
    organism = _manifest_organism(primary_contract, bio)
    primary_data.update(organism)
    modalities = _paired_modality_inputs(primary_contract, bio)
    if modalities:
        primary_data["modalities"] = modalities
    return {
        "inputs": {
            "primary_data": primary_data,
            "metadata": _manifest_metadata(primary_contract, bio),
            "external_resources": {
                "official_tutorials": _official_tutorial_paths(context),
                "note": "Contract-aware official example attempt. Generated adapters remain dry_run_only until run_trace and output validation pass.",
            },
            "algorithm": {"mode": "official_example_attempt", "parameters": context.get("parameters") or {}},
        },
        "environment": {
            "preferred_manager": "conda",
            "environment_name": f"{context.get('skill_name', 'generated-skill')}-env",
            "install_policy": "ask",
        },
    }


def _contract_primary_data(context: dict[str, Any]) -> dict[str, Any]:
    algorithm_contract = context.get("algorithm_contract") or {}
    return ((((algorithm_contract.get("input_contract") or {}).get("required") or {}).get("primary_data") or {}))


def _bio_contract_body(context: dict[str, Any]) -> dict[str, Any]:
    bio_contract = context.get("bio_contract") or {}
    return bio_contract.get("bio_contract") if isinstance(bio_contract.get("bio_contract"), dict) else bio_contract


def _contract_value(field: Any) -> Any | None:
    value = field.get("value") if isinstance(field, dict) else field
    if isinstance(field, dict) and field.get("confidence") == "low":
        return None
    if value is None:
        return None
    if isinstance(value, str) and _is_unconfirmed(value):
        return None
    return value


def _is_unconfirmed(value: Any) -> bool:
    return _normalize_token(value) in {"", "unknown", "not_confirmed", "none", "null", "na", "n_a"}


def _normalize_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_flatten_strings(item))
        return result
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_flatten_strings(item))
        return result
    if value is None:
        return []
    return [str(value)]


def _manifest_matrix_state(primary_contract: dict[str, Any], bio: dict[str, Any]) -> str:
    matrix = bio.get("input_matrix_state") or {}
    if _contract_value(matrix.get("raw_counts_required")) is True:
        return "raw_counts"
    if _contract_value(matrix.get("preprocessed_required")) is True:
        return "preprocessed"
    value = _contract_value(primary_contract.get("matrix_state"))
    return str(value) if value is not None else "unknown"


def _manifest_organism(primary_contract: dict[str, Any], bio: dict[str, Any]) -> dict[str, str]:
    primary_organism = primary_contract.get("organism") or {}
    bio_organism = bio.get("organism") or {}
    fields = {
        "species": _contract_value(primary_organism.get("species")) or _contract_value(bio_organism.get("species_supported")),
        "genome_build": _contract_value(primary_organism.get("genome_build")) or _contract_value(bio_organism.get("genome_build")),
        "gene_id_type": _contract_value(primary_organism.get("gene_id_type")) or _contract_value(bio_organism.get("gene_id_type")),
    }
    return {key: str(value) for key, value in fields.items() if value is not None}


def _manifest_metadata(primary_contract: dict[str, Any], bio: dict[str, Any]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    sources = [primary_contract.get("metadata_keys") or {}, bio.get("metadata_requirements") or {}]
    modality_key = _primary_modality_key(bio)
    modality_contracts = bio.get("modality_contracts") or {}
    if modality_key and isinstance(modality_contracts.get(modality_key), dict):
        sources.append((modality_contracts[modality_key].get("metadata") or {}))
    for source in sources:
        if not isinstance(source, dict):
            continue
        for logical_key, spec in source.items():
            value = _contract_value(spec)
            if value is not None:
                metadata[str(logical_key)] = str(value)
    return metadata


def _primary_modality_key(bio: dict[str, Any]) -> str | None:
    value = _contract_value(((bio.get("modality") or {}).get("primary") or {}))
    if value is None:
        return None
    token = _normalize_token(value)
    if "ribo" in token and "rna" in token:
        return "ribo_rna_seq"
    if "perturb" in token:
        return "perturb_seq"
    if "scrna" in token or "single_cell" in token:
        return "scrna_seq"
    if "bulk" in token and "rna" in token:
        return "bulk_rna_seq"
    if "spatial" in token:
        return "spatial"
    return None


def _paired_modality_inputs(primary_contract: dict[str, Any], bio: dict[str, Any]) -> dict[str, dict[str, Any]]:
    modality = _contract_value(((bio.get("modality") or {}).get("primary") or {}))
    token = _normalize_token(modality) if modality is not None else ""
    if not ("ribo" in token and "rna" in token):
        return {}
    matrix_state = _manifest_matrix_state(primary_contract, bio)
    return {
        "ribo": {"path": "assets/ribo_counts.txt", "format": "count_matrix", "exists": False, "matrix_state": matrix_state},
        "rna": {"path": "assets/rna_counts.txt", "format": "count_matrix", "exists": False, "matrix_state": matrix_state},
    }


def _official_data_source(context: dict[str, Any], expected_format: str) -> dict[str, Any]:
    example_source = _official_data_source_from_examples(context, expected_format)
    if example_source:
        return example_source
    text_items = _flatten_strings(context.get("tutorial_trace") or {})
    text = "\n".join(text_items)
    lower = text.lower()
    fmt = _normalize_token(expected_format)
    if "sc_sim" in lower:
        return {"path": "package:Augur/sc_sim", "format": expected_format, "exists": False, "source": "package_dataset", "dataset_name": "sc_sim", "package": "Augur"}
    if "pbmc3k_processed" in lower:
        return {"path": "scanpy.datasets.pbmc3k_processed()", "format": expected_format, "exists": False, "source": "package_dataset", "dataset_name": "pbmc3k_processed", "package": "scanpy"}
    match = _first_tutorial_data_file(text_items, fmt)
    if match:
        return {"path": match, "format": expected_format, "exists": False, "source": "tutorial_reference"}
    extension = {
        "h5ad": "h5ad",
        "anndata_object": "h5ad",
        "rds": "rds",
        "count_matrix": "txt",
        "tabular_count_matrix": "txt",
        "csv": "csv",
        "tsv": "tsv",
    }.get(fmt, "dat")
    return {"path": f"assets/official_input.{extension}", "format": expected_format, "exists": False, "source": "user_provided_or_tutorial_dataset"}


def _official_data_source_from_examples(context: dict[str, Any], expected_format: str) -> dict[str, Any] | None:
    catalog = context.get("examples_catalog") or {}
    examples = catalog.get("examples") if isinstance(catalog.get("examples"), list) else []
    default_id = catalog.get("default_example_id")
    selected = next((item for item in examples if isinstance(item, dict) and item.get("example_id") == default_id), None)
    if selected is None and examples:
        selected = examples[0] if isinstance(examples[0], dict) else None
    if not selected:
        return None
    data_sources = catalog_data_sources(selected)
    candidates = [item for item in data_sources if isinstance(item, dict) and item.get("type") == "url" and item.get("url")]
    if not candidates:
        return None
    expected_ext = _expected_data_extension(expected_format)
    source = sorted(candidates, key=lambda item: _score_data_source(item, selected, expected_ext))[0]
    filename = str(source.get("filename") or filename_from_url(str(source.get("url"))))
    return {
        "path": f"assets/data/{filename}",
        "format": _format_from_filename(filename, expected_format),
        "exists": False,
        "source": "remote_url",
        "url": str(source.get("url")),
        "filename": filename,
        "example_id": selected.get("example_id"),
    }


def catalog_data_sources(example: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    inputs = example.get("inputs") if isinstance(example.get("inputs"), dict) else {}
    for value in [example.get("data_sources"), inputs.get("data_sources")]:
        if isinstance(value, list):
            sources.extend(item for item in value if isinstance(item, dict))
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for source in sources:
        key = (str(source.get("type") or ""), str(source.get("url") or ""), str(source.get("path") or source.get("filename") or ""))
        deduped[key] = source
    return list(deduped.values())


def _expected_data_extension(expected_format: str) -> str:
    return {
        "h5ad": "h5ad",
        "anndata_object": "h5ad",
        "rds": "rds",
        "count_matrix": "txt",
        "tabular_count_matrix": "txt",
        "csv": "csv",
        "tsv": "tsv",
    }.get(_normalize_token(expected_format), "")


def _format_from_filename(filename: str, fallback: str) -> str:
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix == "h5ad":
        return "h5ad"
    if suffix in {"rds", "rda", "csv", "tsv", "txt"}:
        return suffix
    return fallback


def _score_data_source(item: dict[str, Any], example: dict[str, Any], expected_ext: str) -> tuple[int, str]:
    filename = str(item.get("filename") or filename_from_url(str(item.get("url") or ""))).lower()
    example_text = " ".join(
        str(example.get(key) or "")
        for key in ["source", "source_excerpt", "scenario"]
    ).lower()
    score = 20
    if expected_ext and filename.endswith(f".{expected_ext}"):
        score -= 10
    if filename and filename in example_text:
        score -= 5
    if "github.com" in str(item.get("url") or "").lower() and "#egg=" in str(item.get("url") or "").lower():
        score += 100
    return (score, filename)


def _first_tutorial_data_file(text_items: list[str], expected_format: str) -> str | None:
    extensions = {
        "h5ad": ["h5ad"],
        "anndata_object": ["h5ad"],
        "rds": ["rds", "rda"],
        "count_matrix": ["txt", "tsv", "csv"],
        "tabular_count_matrix": ["txt", "tsv", "csv"],
        "csv": ["csv"],
        "tsv": ["tsv"],
    }.get(expected_format, ["h5ad", "rds", "rda", "txt", "tsv", "csv"])
    pattern = re.compile(r"[\w./-]+\.(" + "|".join(re.escape(ext) for ext in extensions) + r")\b", re.I)
    for item in text_items:
        match = pattern.search(item)
        if match:
            return match.group(0).strip("\"'`")
    return None


def _official_tutorial_paths(context: dict[str, Any]) -> list[str]:
    tutorials = ((context.get("tutorial_trace") or {}).get("tutorials") or [])
    return [str(item.get("path")) for item in tutorials if isinstance(item, dict) and item.get("path")]


def _demo_data_for_language(language: str) -> str:
    return "sample,condition,value\ns1,control,1\ns2,treatment,2\ns3,treatment,3\n"


def _python_specs(environment_spec: dict[str, Any]) -> list[str]:
    specs = []
    for item in environment_spec.get("python", {}).get("packages", []):
        required = item.get("required", True) if isinstance(item, dict) else True
        category = item.get("category") if isinstance(item, dict) else None
        if required or category == "self_package":
            specs.append(item["spec"] if isinstance(item, dict) else str(item))
    return specs


def _r_specs(environment_spec: dict[str, Any]) -> list[str]:
    specs = []
    for item in environment_spec.get("r", {}).get("packages", []):
        required = item.get("required", True) if isinstance(item, dict) else True
        if required:
            specs.append(item["name"] if isinstance(item, dict) else str(item))
    return specs


def _conda_environment(context: dict[str, Any]) -> str:
    env, _report = _canonical_environment(context)
    return yaml.safe_dump(env, sort_keys=False)


def _canonical_environment(context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    env_spec = context["environment_spec"]
    python_specs = _python_specs(env_spec)
    routed = route_python_packages(python_specs)
    r_specs = _r_specs(env_spec)
    r_routed = route_r_packages(r_specs)
    deps: list[Any] = ["python=3.10", "pip", "pyyaml", "uv"]
    if env_spec.get("r", {}).get("required"):
        deps.append("r-base")
    for item in (env_spec.get("conda") or {}).get("packages") or []:
        package = item.get("package") if isinstance(item, dict) else item
        if package:
            deps.append(str(package))
    deps.extend(routed["conda"])
    deps.extend(r_routed["conda_packages"])
    special_pip_segment: list[str] = []
    for route in routed.get("special") or []:
        if route.get("manual_approval_required"):
            continue
        deps.extend(route.get("conda_packages") or [])
        special_pip_segment.extend(str(item) for item in route.get("pip_packages") or [])
    deps = _dedupe_conda_dependencies(deps)
    pip_segment = sorted(dict.fromkeys([*routed["uv"], *special_pip_segment]))
    environment_deps: list[Any] = list(deps)
    if pip_segment:
        environment_deps.append({"pip": pip_segment})
    channels = list(DEFAULT_BIOCONDA_CHANNELS)
    if any(str(item).split("=", 1)[0].lower() in {"pytorch", "cpuonly", "torchvision", "torchaudio"} for item in deps):
        channels = ["pytorch", *[channel for channel in channels if channel != "pytorch"]]
    env = {
        "name": f"{context['skill_name']}-env",
        "channels": channels,
        "dependencies": environment_deps,
    }
    report = {
        "status": "derived",
        "upstream": "generated_environment_spec",
        "canonical_path": CANONICAL_ENV_RELATIVE_PATH,
        "route_migrations": routed.get("migrations") or [],
        "special_routes": routed.get("special") or [],
        "additive_dependencies": r_routed.get("routes") or [],
        "manual_blocks": [*(routed.get("manual") or []), *(r_routed.get("manual") or [])],
        "pip_segment": pip_segment,
        "conflicts": [],
        "channel_priority": "strict",
        "patch_policy": "additive_or_route_migration",
    }
    return env, report


def _dedupe_conda_dependencies(dependencies: list[Any]) -> list[str]:
    selected: dict[str, str] = {}
    for item in dependencies:
        dep = str(item).strip()
        if not dep:
            continue
        key = package_key(dep)
        previous = selected.get(key)
        if previous is None or (_has_version_constraint(dep) and not _has_version_constraint(previous)):
            selected[key] = dep
    return sorted(selected.values())


def _has_version_constraint(dependency: str) -> bool:
    return any(operator in dependency for operator in ["==", ">=", "<=", "~=", "!=", "="])


def _build_plan_markdown(context: dict[str, Any]) -> str:
    lines = [f"# Build Plan for {context['algorithm_name']}", ""]
    lines.append(f"- Skill name: `{context['skill_name']}`")
    lines.append(f"- Language: `{context['language']}`")
    lines.append(f"- Maturity level: `{context.get('maturity', {}).get('level', context['maturity_level'])}`")
    lines.append(f"- Algorithm archetype: `{context.get('algorithm_archetype', {}).get('archetype', 'unknown')}`")
    lines.append(f"- Default example: `{context.get('tutorial_catalog', {}).get('default_example_id', 'not_confirmed')}`")
    lines.append("- Evidence priority: tutorial, docs, API, dependency files, paper, README")
    lines.append("")
    lines.append("## Workflow Steps")
    for step in context["workflow"].get("steps", []):
        lines.append(f"- `{step['id']}` from `{step['evidence_id']}`")
    if not context["workflow"].get("steps"):
        lines.append("- No tutorial workflow steps confirmed.")
    return "\n".join(lines) + "\n"
