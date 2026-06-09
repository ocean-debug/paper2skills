from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run(manifest: dict, out: Path) -> dict:
    repo_dir = ROOT / ".benchmark" / "live_sources" / "translational_regulation"
    if not repo_dir.exists():
        completed = subprocess.run(["git", "clone", "--depth", "1", "https://github.com/SGDDNB/translational_regulation", str(repo_dir)], text=True, capture_output=True, check=False, timeout=600)
        if completed.returncode != 0:
            return {"status": "blocked", "adapter_type": "cli", "message": "deltaTE repo clone failed", "stderr": completed.stderr[-2000:]}
    sample = repo_dir / "sample_data"
    if not sample.exists():
        return {"status": "blocked", "adapter_type": "cli", "message": "sample_data directory not found in deltaTE repo"}
    work = out / "live_deltaTE"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(sample, work)
    existing_results = work / "Results"
    if existing_results.exists():
        shutil.rmtree(existing_results)
    script = repo_dir / "DTEG.R"
    ribo = next(work.glob("*ribo*"), None) or next(work.glob("*Ribo*"), None)
    rna = next(work.glob("*rna*"), None) or next(work.glob("*RNA*"), None)
    info = next(work.glob("*sample*"), None) or next(work.glob("*Sample*"), None)
    if not ribo or not rna or not info:
        return {"status": "blocked", "adapter_type": "cli", "message": "could not identify sample_data ribo/rna/sample_info files"}
    completed = subprocess.run(["Rscript", "--vanilla", str(script), str(ribo), str(rna), str(info), "1"], cwd=work, text=True, capture_output=True, check=False, timeout=1200)
    if completed.returncode != 0:
        return {"status": "blocked", "adapter_type": "cli", "message": "deltaTE live Rscript failed", "stdout": completed.stdout[-2000:], "stderr": completed.stderr[-2000:]}
    results_src = work / "Results"
    results_dst = out / "Results"
    if results_dst.exists():
        shutil.rmtree(results_dst)
    if results_src.exists():
        shutil.copytree(results_src, results_dst)
    summary = out / "results"
    summary.mkdir(parents=True, exist_ok=True)
    (summary / "summary.json").write_text(json.dumps({"status": "pass", "workdir": str(work)}, indent=2) + "\n", encoding="utf-8")
    return {"status": "pass", "adapter_type": "cli", "outputs": ["Results", "results/summary.json"]}
