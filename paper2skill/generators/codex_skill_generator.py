from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

import jinja2
import yaml

from paper2skill.collectors.path_sanitizer import REDACTED_LOCAL_PATH, public_data
from paper2skill.collectors.paper_collector import collect_paper
from paper2skill.collectors.repo_collector import collect_repo
from paper2skill.collectors.tutorial_collector import collect_tutorials
from paper2skill.common import PROJECT_ROOT, ensure_dir, slugify, write_json, write_text, write_yaml
from paper2skill.evidence.evidence_graph import build_evidence_graph
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


TEMPLATE_ROOT = PROJECT_ROOT / "paper2skill" / "templates" / "codex_skill"


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
    fixtures = PROJECT_ROOT / "tests" / "fixtures"
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
    if repo_evidence.get("entrypoints") or repo_evidence.get("cli_commands"):
        return "cli"
    if repo_evidence.get("workflow_engines"):
        return "workflow_engine"
    if repo_evidence.get("package_type") == "r_package" or classification.get("language") == "r":
        return "r_script"
    tutorials = tutorial_trace.get("tutorials", [])
    if tutorials and all(trace.get("language") == "python" for trace in tutorials) and not repo_evidence.get("api_functions"):
        return "notebook"
    return "demo_only"


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
    bio_contract = infer_bio_contract(tutorial_trace, paper_sections, dependency_evidence, strict_evidence=strict_evidence)
    io_contract = infer_io_contract(tutorial_trace, bio_contract)
    algorithm_contract = {
        "algorithm": {
            "name": algorithm_name,
            "task": task,
            "domain": classification["domain"],
            "modality": "not_confirmed",
            "language": classification["language"],
            "execution_mode": classification["execution_mode"],
            "adapter_type": adapter_type,
            "maturity_level": maturity_level,
        },
        **io_contract,
        "environment_contract": {
            "install_policy_default": "ask",
            "preflight_required": True,
            "auto_install_requires_confirmation": True,
        },
        "maturity": {"level": maturity_level, "status": "demo_executable" if maturity_level == "L2" else "contract_and_preflight"},
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
        "maturity_level": maturity_level,
        "source_manifest": source_manifest,
        "resolved_inputs": public_resolved_inputs(resolved),
        "paper_evidence": _paper_evidence(source_manifest),
        "repo_evidence": repo_evidence,
        "dependency_evidence": dependency_evidence,
        "tutorial_trace": tutorial_trace,
        "workflow": workflow,
        "parameters": parameters,
        "environment_spec": environment_spec,
        "environment_report": environment_report,
        "install_plan": install_plan,
        "install_plan_markdown": render_install_plan_markdown(install_plan),
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
        "scripts/plan.py.j2": "scripts/plan.py",
        "scripts/run.py.j2": "scripts/run.py",
        "scripts/validate_outputs.py.j2": "scripts/validate_outputs.py",
        "scripts/adapters/__init__.py.j2": "scripts/adapters/__init__.py",
        "scripts/adapters/python_api_adapter.py.j2": "scripts/adapters/python_api_adapter.py",
        "scripts/adapters/cli_adapter.py.j2": "scripts/adapters/cli_adapter.py",
        "scripts/adapters/notebook_adapter.py.j2": "scripts/adapters/notebook_adapter.py",
        "scripts/adapters/r_script_adapter.R.j2": "scripts/adapters/r_script_adapter.R",
        "references/evidence_report.md.j2": "references/evidence_report.md",
        "references/paper_summary.md.j2": "references/paper_summary.md",
        "references/repo_summary.md.j2": "references/repo_summary.md",
        "references/api_reference.md.j2": "references/api_reference.md",
        "references/tutorial_trace.md.j2": "references/tutorial_trace.md",
        "assets/input_manifest_template.yaml.j2": "assets/input_manifest_template.yaml",
        "assets/config_template.yaml.j2": "assets/config_template.yaml",
        "agents/openai.yaml.j2": "agents/openai.yaml",
        "tests/test_preflight.py.j2": "tests/test_preflight.py",
        "tests/test_environment.py.j2": "tests/test_environment.py",
        "tests/test_plan.py.j2": "tests/test_plan.py",
        "tests/test_output_contract.py.j2": "tests/test_output_contract.py",
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
    write_yaml(root / "references" / "bio_contract.yaml", public_context["bio_contract"])
    write_yaml(root / "references" / "io_contract.yaml", {"input_contract": public_context["algorithm_contract"].get("input_contract"), "output_contract": public_context["algorithm_contract"].get("output_contract")})
    write_json(root / "references" / "evidence_graph.json", public_context["evidence_graph"])
    write_optional_collection_outputs(public_context, root)
    write_json(root / "references" / "build_report.json", public_data(build_report(context), PROJECT_ROOT))
    write_text(root / "references" / "install_plan.md", public_context["install_plan_markdown"])
    write_text(root / "assets" / "environment_spec.yaml", json.dumps(public_context["environment_spec"], indent=2) + "\n")
    write_text(root / "assets" / "demo_input_manifest.yaml", json.dumps(public_data(_demo_manifest(context), PROJECT_ROOT), indent=2) + "\n")
    write_text(root / "assets" / "requirements.txt", "\n".join(_python_specs(public_context["environment_spec"])) + "\n")
    write_text(root / "assets" / "environment.yml", _conda_environment(public_context))
    write_text(root / "assets" / "renv.lock.placeholder", "{}\n")
    write_text(root / "assets" / "demo_input.csv", context["demo_data"])
    return root


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
    write_json(root / "source_manifest.json", public_context["source_manifest"])
    write_json(root / "paper_evidence.json", public_context["paper_evidence"])
    write_json(root / "repo_evidence.json", public_context["repo_evidence"])
    write_json(root / "tutorial_trace.json", public_context["tutorial_trace"])
    write_json(root / "workflow_dag.json", public_context["workflow"].get("workflow_dag", {"nodes": [], "edges": []}))
    write_yaml(root / "algorithm_contract.preview.yaml", public_context["algorithm_contract"])
    write_json(root / "environment_report.json", _public_environment_report(context["environment_report"]))
    write_text(root / "build_plan.md", _build_plan_markdown(public_context))
    return root


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
    return clean


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


def _demo_data_for_language(language: str) -> str:
    return "sample,condition,value\ns1,control,1\ns2,treatment,2\ns3,treatment,3\n"


def _python_specs(environment_spec: dict[str, Any]) -> list[str]:
    specs = []
    for item in environment_spec.get("python", {}).get("packages", []):
        required = item.get("required", True) if isinstance(item, dict) else True
        if required:
            specs.append(item["spec"] if isinstance(item, dict) else str(item))
    return specs


def _conda_environment(context: dict[str, Any]) -> str:
    deps = ["python>=3.10", "pip"]
    if context["environment_spec"].get("r", {}).get("required"):
        deps.append("r-base")
    python_specs = _python_specs(context["environment_spec"])
    if python_specs:
        deps.append({"pip": python_specs})
    return yaml.safe_dump({"name": f"{context['skill_name']}-env", "channels": ["conda-forge"], "dependencies": deps}, sort_keys=False)


def _build_plan_markdown(context: dict[str, Any]) -> str:
    lines = [f"# Build Plan for {context['algorithm_name']}", ""]
    lines.append(f"- Skill name: `{context['skill_name']}`")
    lines.append(f"- Language: `{context['language']}`")
    lines.append(f"- Maturity target: `{context['maturity_level']}`")
    lines.append("- Evidence priority: tutorial, docs, API, dependency files, paper, README")
    lines.append("")
    lines.append("## Workflow Steps")
    for step in context["workflow"].get("steps", []):
        lines.append(f"- `{step['id']}` from `{step['evidence_id']}`")
    if not context["workflow"].get("steps"):
        lines.append("- No tutorial workflow steps confirmed.")
    return "\n".join(lines) + "\n"
