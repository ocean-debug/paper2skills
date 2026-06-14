from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from paper2skill.common import slugify


DATA_EXTENSIONS = {
    ".h5ad",
    ".h5",
    ".hdf5",
    ".loom",
    ".rds",
    ".rda",
    ".mtx",
    ".csv",
    ".tsv",
    ".txt",
    ".fastq",
    ".fq",
    ".bam",
    ".sam",
    ".bed",
    ".gtf",
    ".gff",
    ".vcf",
}

DOC_HOST_HINTS = {
    "readthedocs",
    "docs.",
    "documentation",
    "pytorch.org/get-started",
    "conda.io",
}

SELECTION_POLICY = (
    "official test/minimal data > package dataset > official script > official "
    "notebook > README quickstart > full large tutorial > paper narrative only"
)


def build_tutorial_catalog(
    tutorial_trace: dict[str, Any],
    adapter_spec: dict[str, Any],
    repo_evidence: dict[str, Any],
    classification: dict[str, Any],
    archetype: dict[str, Any],
    *,
    user_data_urls: list[str] | None = None,
) -> dict[str, Any]:
    examples = []
    seen: set[str] = set()
    tutorials = [tutorial for tutorial in tutorial_trace.get("tutorials", []) or [] if isinstance(tutorial, dict)]
    valid_user_data_urls = explicit_data_urls(user_data_urls or [])
    matched_user_data_urls: set[str] = set()
    allow_unmatched_user_urls = len(tutorials) == 1
    for index, tutorial in enumerate(tutorials, start=1):
        if not isinstance(tutorial, dict):
            continue
        text = "\n".join(_flatten_strings(tutorial))
        matched_urls = user_data_urls_for_tutorial(text, valid_user_data_urls, allow_unmatched=allow_unmatched_user_urls)
        matched_user_data_urls.update(matched_urls)
        item = catalog_item(
            tutorial,
            index=index,
            adapter_spec=adapter_spec,
            archetype=archetype,
            user_data_urls=matched_urls,
        )
        if item["example_id"] in seen:
            item["example_id"] = f"{item['example_id']}_{index:03d}"
            item["tutorial_id"] = item["example_id"]
        seen.add(item["example_id"])
        examples.append(item)
    if not examples:
        examples.append(placeholder_item(adapter_spec, archetype))
    examples.sort(key=lambda item: (item["rank"], item["example_id"]))
    for index, item in enumerate(examples):
        item["is_default"] = index == 0
    unmatched_data_urls = [
        {"type": "url", "url": url, "filename": filename_from_url(url), "reason": "not_referenced_by_tutorial_text"}
        for url in valid_user_data_urls
        if url not in matched_user_data_urls
    ]
    return {
        "schema_version": 2,
        "selection_policy": SELECTION_POLICY,
        "default_example_id": examples[0]["example_id"],
        "examples": examples,
        "unmatched_data_urls": unmatched_data_urls,
        "warnings": [f"{len(unmatched_data_urls)} explicit data URL(s) were not matched to any tutorial example."] if unmatched_data_urls else [],
        "adapter_status_values": ["dry_run_only", "verified"],
        "maturity_levels": ["L1", "L2", "L3", "L4"],
        "notes": [
            "Adapter verification is per example; one verified example does not verify other examples.",
            "Static inference can only produce dry_run_only adapters.",
        ],
        "repo_package_type": repo_evidence.get("package_type"),
        "language": classification.get("language"),
        "archetype": archetype,
    }


def catalog_item(
    tutorial: dict[str, Any],
    *,
    index: int,
    adapter_spec: dict[str, Any],
    archetype: dict[str, Any],
    user_data_urls: list[str],
) -> dict[str, Any]:
    path = str(tutorial.get("path") or f"tutorial_{index}")
    text = "\n".join(_flatten_strings(tutorial))
    data_sources = data_sources_from_text(text, user_data_urls)
    data_kind = infer_data_kind(path, text, data_sources)
    entrypoint_type = infer_entrypoint_type(path, text, archetype.get("adapter_type"))
    risk_flags = infer_risk_flags(path, text, data_kind)
    rank = rank_candidate(data_kind, entrypoint_type, path, text)
    example_id = example_id_from_path(path, fallback_index=index)
    output_contract = output_contract_from_adapter(adapter_spec)
    adapter = adapter_for_example(adapter_spec, archetype)
    return {
        "tutorial_id": example_id,
        "example_id": example_id,
        "is_default": False,
        "source": path,
        "source_type": source_type_for_path(path),
        "officialness": "official" if source_type_for_path(path) in {"tutorial", "notebook", "script"} else "derived",
        "runnable_status": "candidate" if entrypoint_type != "paper_narrative" else "blocked",
        "data_kind": data_kind,
        "entrypoint_type": entrypoint_type,
        "inputs": {"data_sources": data_sources, "manifest_required": True},
        "data_sources": data_sources,
        "outputs": output_contract.get("required_files", []),
        "bio_claims": bio_claims_from_text(text),
        "risk_flags": risk_flags,
        "selected_adapter": adapter,
        "adapter": adapter,
        "output_contract": output_contract,
        "verification": {"status": "not_run"},
        "maturity": "L1",
        "rank": rank,
        "scenario": scenario_from_kind(data_kind, entrypoint_type),
        "priority": rank,
        "source_excerpt": text[:2000],
        "caveats": ["Tutorial/example is not verified until run trace and output validation pass."],
    }


def placeholder_item(adapter_spec: dict[str, Any], archetype: dict[str, Any]) -> dict[str, Any]:
    adapter = adapter_for_example(adapter_spec, archetype)
    return {
        "tutorial_id": "contract_only",
        "example_id": "contract_only",
        "is_default": True,
        "source": "not_confirmed",
        "source_type": "generated",
        "officialness": "derived",
        "runnable_status": "blocked",
        "data_kind": "none",
        "entrypoint_type": "paper_narrative",
        "inputs": {"data_sources": [], "manifest_required": True},
        "data_sources": [],
        "outputs": [],
        "bio_claims": [],
        "risk_flags": ["no_explicit_tutorial"],
        "selected_adapter": adapter,
        "adapter": adapter,
        "output_contract": output_contract_from_adapter(adapter_spec),
        "verification": {"status": "not_run"},
        "maturity": "L1",
        "rank": 1000,
        "scenario": "contract_only",
        "priority": 1000,
        "source_excerpt": "",
        "caveats": ["No explicit runnable tutorial/example was mined."],
    }


def adapter_for_example(adapter_spec: dict[str, Any], archetype: dict[str, Any]) -> dict[str, Any]:
    return {
        "adapter_type": adapter_spec.get("adapter_type"),
        "archetype": archetype.get("archetype"),
        "status": adapter_spec.get("status", "dry_run_only"),
        "entrypoint": adapter_spec.get("entrypoint"),
        "command": adapter_spec.get("command"),
        "official_command": adapter_spec.get("official_command"),
        "official_script": adapter_spec.get("official_script"),
        "module": adapter_spec.get("module"),
        "function": adapter_spec.get("function"),
        "input_binding": adapter_spec.get("input_binding") or archetype.get("interface", {}).get("input_binding"),
        "run_command_or_api": adapter_spec.get("run_command_or_api") or archetype.get("interface", {}).get("run_command_or_api"),
    }


def output_contract_from_adapter(adapter_spec: dict[str, Any]) -> dict[str, Any]:
    expected = list(adapter_spec.get("expected_outputs") or [])
    if not expected:
        expected = ["results/summary.json"]
    return {
        "required_files": expected,
        "json": {"results/summary.json": {"required_keys": ["status"]}},
        "tables": {},
        "nonempty": expected,
        "log_must_not_contain": ["Traceback", "Error:", "fatal error", "segmentation fault"],
    }


def data_sources_from_text(text: str, user_data_urls: list[str]) -> list[dict[str, str]]:
    urls = [*extract_data_urls(text), *[url for url in user_data_urls if is_explicit_data_url(url)]]
    return [{"type": "url", "url": url, "filename": filename_from_url(url)} for url in sorted(dict.fromkeys(urls))]


def explicit_data_urls(urls: list[str]) -> list[str]:
    values = []
    for url in urls:
        value = str(url or "").strip()
        if is_explicit_data_url(value):
            values.append(value)
    return sorted(dict.fromkeys(values))


def user_data_urls_for_tutorial(text: str, urls: list[str], *, allow_unmatched: bool = False) -> list[str]:
    explicit_urls = explicit_data_urls(urls)
    if not explicit_urls:
        return []
    if allow_unmatched:
        return explicit_urls
    lowered = text.lower()
    matched = []
    for url in explicit_urls:
        tokens = data_url_match_tokens(url)
        if any(token and token in lowered for token in tokens):
            matched.append(url)
    return matched


def data_url_match_tokens(url: str) -> set[str]:
    filename = filename_from_url(url)
    tokens = {str(url).strip().lower()}
    suffix = Path(filename).suffix.lower()
    if suffix in DATA_EXTENSIONS:
        tokens.add(filename.lower())
        stem = Path(filename).stem.lower()
        if len(stem) >= 3:
            tokens.add(stem)
    return tokens


def extract_data_urls(text: str) -> list[str]:
    pattern = re.compile(r"https?://[^\s'\"),]+(?:\?[^\s'\"),]+)?")
    return [url for match in pattern.finditer(text) if (url := clean_data_url(match.group(0))) is not None]


def clean_data_url(value: str) -> str | None:
    url = value.rstrip("`].\\*")
    if not is_data_url(url):
        return None
    return url


def is_data_url(url: str) -> bool:
    lowered = url.lower()
    if "#egg=" in lowered or "git+" in lowered:
        return False
    if any(hint in lowered for hint in DOC_HOST_HINTS):
        return False
    if lowered.endswith((".**", ".*", ".md", ".html", "/locally", "/locally/")):
        return False
    suffix = Path(lowered.split("?", 1)[0]).suffix
    return suffix in DATA_EXTENSIONS


def is_explicit_data_url(url: str) -> bool:
    lowered = str(url or "").strip().lower()
    if not lowered:
        return False
    if "#egg=" in lowered or "git+" in lowered:
        return False
    if lowered.endswith((".**", ".*", ".md", ".html", "/locally", "/locally/")):
        return False
    return True


def infer_data_kind(path: str, text: str, data_sources: list[dict[str, str]]) -> str:
    lowered = f"{path}\n{text}".lower()
    if "large dataset" in lowered or "full dataset" in lowered:
        return "large"
    if "test data" in lowered or "/tests/" in lowered or "tests/data" in lowered:
        return "official_minimal"
    if "pbmc" in lowered or "package dataset" in lowered or "datasets." in lowered or "data(" in lowered:
        return "package_dataset"
    if data_sources:
        return "official_example"
    if any(token in lowered for token in ["toy", "small", "minimal", "demo"]):
        return "toy"
    return "none"


def infer_entrypoint_type(path: str, text: str, adapter_type: str | None) -> str:
    lowered = f"{path}\n{text}".lower()
    if path.lower().endswith((".ipynb", ".rmd", ".qmd")):
        return "notebook"
    if path.lower().endswith((".py", ".r", ".sh")):
        return "script"
    if any(token in lowered for token in ["snakemake", "nextflow", "cwltool", "wdl"]):
        return "workflow_engine"
    if any(token in lowered for token in ["docker run", "singularity exec", "apptainer exec"]):
        return "container"
    if adapter_type in {"python_api", "r_script"} and any(token in lowered for token in ["import ", "library(", "::", ".fit", "fit_transform"]):
        return "api"
    if adapter_type == "cli" or re.search(r"^\s*[$>]?\s*[a-z0-9_.-]+\s+[-\w]", text, flags=re.I | re.M):
        return "cli"
    return "paper_narrative"


def infer_risk_flags(path: str, text: str, data_kind: str) -> list[str]:
    lowered = f"{path}\n{text}".lower()
    risks: list[str] = []
    if any(token in lowered for token in ["pip install", "conda install", "biocmanager::install", "install.packages"]):
        risks.append("install")
    if "http://" in lowered or "https://" in lowered:
        risks.append("download")
    if data_kind == "large":
        risks.append("large_data")
    if any(token in lowered for token in ["cuda", "gpu", "faiss-gpu"]):
        risks.append("gpu")
    if path.lower().endswith((".ipynb", ".rmd", ".qmd")):
        risks.append("notebook_side_effects")
    return sorted(dict.fromkeys(risks))


def rank_candidate(data_kind: str, entrypoint_type: str, path: str, text: str) -> int:
    data_rank = {
        "official_minimal": 0,
        "toy": 5,
        "package_dataset": 10,
        "official_example": 20,
        "none": 60,
        "large": 90,
    }.get(data_kind, 70)
    entry_rank = {
        "script": 0,
        "api": 5,
        "cli": 10,
        "workflow_engine": 15,
        "notebook": 25,
        "container": 35,
        "paper_narrative": 80,
    }.get(entrypoint_type, 50)
    lowered = f"{path}\n{text}".lower()
    if "quickstart" in lowered or "getting started" in lowered:
        entry_rank -= 3
    return max(0, data_rank + entry_rank)


def bio_claims_from_text(text: str) -> list[dict[str, str]]:
    lowered = text.lower()
    claims = []
    for token, value in [
        ("scrna", "scRNA-seq"),
        ("single-cell", "scRNA-seq"),
        ("rna-seq", "bulk RNA-seq"),
        ("spatial", "spatial"),
        ("atac", "ATAC"),
        ("proteomics", "proteomics"),
        ("metabolomics", "metabolomics"),
    ]:
        if token in lowered:
            claims.append({"field": "modality", "value": value, "claim_type": "official_tutorial"})
            break
    for token, value in [("raw counts", "raw_counts"), ("log1p", "log1p"), ("normalized", "normalized"), ("batch-corrected", "batch_corrected")]:
        if token in lowered:
            claims.append({"field": "matrix_state", "value": value, "claim_type": "official_tutorial"})
    return claims


def source_type_for_path(path: str) -> str:
    lowered = path.lower()
    if lowered.endswith((".ipynb", ".rmd", ".qmd")):
        return "notebook"
    if lowered.endswith((".py", ".r", ".sh")):
        return "script"
    if "readme" in lowered or "docs" in lowered:
        return "tutorial"
    return "tutorial"


def scenario_from_kind(data_kind: str, entrypoint_type: str) -> str:
    if data_kind == "official_minimal":
        return "official_test_data"
    if data_kind == "package_dataset":
        return "package_dataset"
    if entrypoint_type == "notebook":
        return "notebook_demo"
    if entrypoint_type == "paper_narrative":
        return "contract_only"
    return "tutorial_demo"


def filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    tail = unquote(parsed.path.rstrip("/").split("/")[-1])
    if Path(tail).suffix.lower() in DATA_EXTENSIONS:
        return tail
    for values in parse_qs(parsed.query).values():
        for value in values:
            candidate = unquote(value).rstrip("/").split("/")[-1]
            if Path(candidate).suffix.lower() in DATA_EXTENSIONS:
                return candidate
    return tail or "downloaded_example_data"


def example_id_from_path(path: str, *, fallback_index: int) -> str:
    name = Path(path).stem if path and path != "not_confirmed" else f"official_example_{fallback_index:03d}"
    value = slugify(name, default=f"official-example-{fallback_index:03d}").replace("-", "_")
    return value or f"official_example_{fallback_index:03d}"


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
