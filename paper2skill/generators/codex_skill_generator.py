from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jinja2
import yaml

from paper2skill.collectors.path_sanitizer import REDACTED_LOCAL_PATH, public_data
from paper2skill.collectors.paper_collector import collect_paper
from paper2skill.collectors.repo_collector import collect_repo
from paper2skill.collectors.source_manifest import build_source_manifest
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
) -> dict[str, Any]:
    skill_name = slugify(skill_name or algorithm_name or "generated-skill")
    algorithm_name = algorithm_name or skill_name.replace("-", " ").title()
    tutorials = tutorials or []
    source_manifest = build_source_manifest(paper, repo, tutorials, paper_url, paper_title, repo_ref=repo_ref)
    if tutorials:
        tutorial_trace = mine_tutorials(tutorials)
    elif repo and Path(repo).exists():
        tutorial_trace = mine_repo_tutorials(repo)
    else:
        tutorial_trace = {"tutorials": [], "workflow_steps": [], "steps": [], "tutorial_candidates": [], "tutorial_scanner_report": {"total": 0, "included": 0}}
    dependency_evidence = mine_dependencies(repo, tutorials)
    repo_evidence = mine_api(repo)
    classification = classify_algorithm(repo_evidence, tutorial_trace)
    if language:
        classification["language"] = language
        classification["execution_mode"] = "python_api" if language == "python" else "r_script"
    environment_spec = infer_environment_spec(dependency_evidence, classification["language"])
    if classification["language"] == "python" and not environment_spec["python"]["packages"]:
        environment_spec["python"]["packages"] = []
    if classification["language"] == "r":
        environment_spec["r"]["required"] = True
    environment_report = inspect_environment(environment_spec)
    install_plan = build_install_plan(environment_report, environment_spec)
    io_contract = infer_io_contract(tutorial_trace)
    parameters = infer_parameters(tutorial_trace)
    workflow = infer_workflow(tutorial_trace)
    algorithm_contract = {
        "algorithm": {
            "name": algorithm_name,
            "task": task,
            "domain": classification["domain"],
            "modality": "not_confirmed",
            "language": classification["language"],
            "execution_mode": classification["execution_mode"],
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
    paper_sections = (((source_manifest.get("paper") or {}).get("parsed_document") or {}).get("sections") or [])
    bio_contract = infer_bio_contract(tutorial_trace, paper_sections, dependency_evidence)
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
        },
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
    write_optional_collection_outputs(context, root)
    write_json(root / "references" / "build_report.json", public_data(build_report(context), PROJECT_ROOT))
    write_text(root / "references" / "install_plan.md", public_context["install_plan_markdown"])
    write_text(root / "assets" / "environment_spec.yaml", json.dumps(public_context["environment_spec"], indent=2) + "\n")
    write_text(root / "assets" / "demo_input_manifest.yaml", json.dumps(public_data(_demo_manifest(context), PROJECT_ROOT), indent=2) + "\n")
    write_text(root / "assets" / "requirements.txt", "\n".join(_python_specs(public_context["environment_spec"])) + "\n")
    write_text(root / "assets" / "environment.yml", _conda_environment(public_context))
    write_text(root / "assets" / "renv.lock.placeholder", "{}\n")
    write_text(root / "assets" / "demo_input.csv", context["demo_data"])
    return root


def write_optional_collection_outputs(context: dict[str, Any], root: Path) -> None:
    sources = context.get("input_sources", {})
    if sources.get("paper"):
        collect_paper(sources["paper"], out_dir=root)
    if sources.get("repo"):
        repo_result = collect_repo(sources["repo"], ref=sources.get("repo_ref"), work_dir=root, skip_clone=sources.get("skip_repo_clone", False))
        write_json(root / "references" / "repo_manifest.json", public_data(repo_result.get("manifest"), root))
        write_json(root / "references" / "repo_index.json", public_data(repo_result.get("index"), root))


def build_report(context: dict[str, Any]) -> dict[str, Any]:
    sources = context.get("input_sources", {})
    missing = {}
    if not sources.get("paper"):
        missing["paper"] = "not provided"
    if not sources.get("repo"):
        missing["repo"] = "not provided"
    return {"status": "built", "missing_inputs": missing, "options": sources}


def plan_outputs(context: dict[str, Any], out_dir: str | Path) -> Path:
    root = ensure_dir(Path(out_dir))
    public_context = _public_context(context)
    write_json(root / "source_manifest.json", public_context["source_manifest"])
    write_json(root / "paper_evidence.json", public_context["paper_evidence"])
    write_json(root / "repo_evidence.json", public_context["repo_evidence"])
    write_json(root / "tutorial_trace.json", public_context["tutorial_trace"])
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
