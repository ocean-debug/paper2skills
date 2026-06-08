from __future__ import annotations

from pathlib import Path

from paper2skill.evaluation.run_real_benchmark import load_case_metadata, run_real_benchmark


def write_case(root: Path, case_id: str, repo_url: str = "https://example.test/repo.git") -> Path:
    case_dir = root / case_id
    (case_dir / "gold").mkdir(parents=True)
    (case_dir / "case.md").write_text(
        f"""
# Case

## Basic information

```yaml
case_id: {case_id}
tool_name: DemoTool
paper_title: "Demo paper"
paper_url: "https://example.test/paper"
repo_url: "{repo_url}"
primary_language: Python
```
""".lstrip(),
        encoding="utf-8",
    )
    return case_dir


def test_load_case_metadata_from_case_md(tmp_path: Path):
    case = write_case(tmp_path, "case_demo")

    metadata = load_case_metadata(case)

    assert metadata["case_id"] == "case_demo"
    assert metadata["tool_name"] == "DemoTool"
    assert metadata["paper_title"] == "Demo paper"


def test_runner_builds_and_evaluates_multiple_cases_without_case_md_paper_input(tmp_path: Path):
    cases_root = tmp_path / "cases"
    write_case(cases_root, "case_a")
    write_case(cases_root, "case_b")
    builder_calls = []

    def fake_builder(**kwargs):
        builder_calls.append(kwargs)
        return {"skill_name": kwargs["skill_name"]}

    def fake_generator(_context, out_dir):
        references = Path(out_dir) / "references"
        references.mkdir(parents=True)
        (references / "source_manifest.json").write_text("{}", encoding="utf-8")
        return Path(out_dir)

    def fake_evaluator(case_dir, generated_dir):
        return {"case_id": Path(case_dir).name, "score": 88.0, "grade": "strong", "passed": True, "generated_dir": str(generated_dir), "category_scores": {}}

    result = run_real_benchmark(cases_root=cases_root, out_root=tmp_path / "generated", strict_evidence=True, builder=fake_builder, generator=fake_generator, evaluator=fake_evaluator)

    assert result["case_count"] == 2
    assert result["failed_case_count"] == 0
    assert (tmp_path / "generated" / "benchmark_summary.md").is_file()
    assert all(call["paper_url"] == "https://example.test/paper" for call in builder_calls)
    assert all(call.get("paper") is None for call in builder_calls)
    assert all(call.get("repo_ref") is None for call in builder_calls)
    assert all(call["no_execute_tutorials"] is True for call in builder_calls)
    assert all(call["strict_evidence"] is True for call in builder_calls)


def test_runner_writes_fail_evaluation_when_build_fails(tmp_path: Path):
    cases_root = tmp_path / "cases"
    write_case(cases_root, "case_fail")

    def failing_builder(**_kwargs):
        raise RuntimeError("clone failed")

    result = run_real_benchmark(cases_root=cases_root, out_root=tmp_path / "generated", builder=failing_builder)
    evaluation_path = tmp_path / "generated" / "case_fail" / "evaluation.json"
    text = evaluation_path.read_text(encoding="utf-8")

    assert result["failed_case_count"] == 1
    assert "clone failed" in text
    assert '"passed": false' in text
