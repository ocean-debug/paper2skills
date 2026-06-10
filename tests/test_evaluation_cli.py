from __future__ import annotations

from pathlib import Path
import json

import yaml

from paper2skill.evaluation.evaluate_case import evaluate_case, main
from paper2skill.evaluation.summarize_benchmark import format_l2_status, main as summarize_main


def write_case(root: Path) -> Path:
    case = root / "case"
    gold = case / "gold"
    gold.mkdir(parents=True)
    files = {
        "case_metadata.yaml": {"case_id": "case", "tool_name": "Demo", "paper_title": "Paper", "paper_url": "https://example.test/paper", "repo_url": "https://example.test/repo", "tutorial_urls": [{"id": "main", "url": "https://example.test"}], "primary_language": "Python", "expected_adapter_type": "python_api", "expected_initial_adapter_status": "candidate"},
        "source_collection.yaml": {},
        "dependency_contract.yaml": {},
        "tutorial_selection.yaml": {},
        "workflow_dag.yaml": {},
        "io_contract.yaml": {},
        "bio_contract.yaml": {},
        "adapter_behavior.yaml": {},
        "evidence_expectations.yaml": {},
        "metrics.yaml": {},
        "level0_skill_package.yaml": {},
        "level2_official_examples.yaml": {},
        "level3_new_data.yaml": {},
        "level4_agentic_tasks.yaml": {},
    }
    for name, data in files.items():
        (gold / name).write_text(yaml.safe_dump(data), encoding="utf-8")
    (case / "case.md").write_text("# case\n", encoding="utf-8")
    return case


def test_evaluate_case_cli_handles_missing_generated_without_traceback(tmp_path: Path):
    case = write_case(tmp_path)
    out = tmp_path / "evaluation.json"

    exit_code = main(["--case", str(case), "--generated", str(tmp_path / "missing_skill"), "--levels", "L0,L1", "--out", str(out)])

    assert exit_code == 0
    assert out.is_file()
    assert "missing generated" in out.read_text(encoding="utf-8")


def test_evaluate_case_supports_all_levels_with_empty_optional_gold(tmp_path: Path):
    case = write_case(tmp_path)

    result = evaluate_case(case, tmp_path / "missing_skill", levels=["L0", "L1", "L2", "L3", "L4"])

    assert result["levels"] == ["L0", "L1", "L2", "L3", "L4"]
    assert set(result["score_by_level"]) == {"L0", "L1", "L2", "L3", "L4"}
    assert "execution_safety_plan" in result["level_results"]["L1"]["category_scores"]
    assert "generated_skill_validation" not in result["level_results"]["L1"]["category_scores"]


def test_summarize_benchmark_cli_writes_markdown_and_json(tmp_path: Path):
    evaluation = tmp_path / "evaluation.json"
    evaluation.write_text(
        json.dumps(
            {
                "case_id": "case",
                "score": 91.5,
                "grade": "strong",
                "passed": True,
                "score_by_level": {"L0": 100, "L1": 80, "L2": 100, "L3": 100, "L4": 100},
                "score_by_component": {"L1.source_collection": 80},
                "level_results": {
                    "L2": {
                        "evaluators": {
                            "official_example_execution": {
                                "l2_summary": {
                                    "example_count": 1,
                                    "status_counts": {"success": 1},
                                    "execution_depth_counts": {"data_smoke": 1},
                                }
                            }
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    markdown_out = tmp_path / "summary.md"
    json_out = tmp_path / "summary.json"

    exit_code = summarize_main(["--results", str(evaluation), "--out", str(markdown_out), "--json-out", str(json_out)])

    assert exit_code == 0
    markdown = markdown_out.read_text(encoding="utf-8")
    assert "Average score: 91.50" in markdown
    assert "L2 Status" in markdown
    assert "data_smoke_not_live 1" in markdown
    summary = json.loads(json_out.read_text(encoding="utf-8"))
    assert summary["case_count"] == 1
    assert summary["average_score"] == 91.5
    assert summary["cases"][0]["l2_summary"]["execution_depth_counts"] == {"data_smoke": 1}


def test_l2_summary_distinguishes_smoke_fallback_from_live_success():
    result = {
        "level_results": {
            "L2": {
                "evaluators": {
                    "official_example_execution": {
                        "l2_summary": {
                            "status_counts": {"success": 1},
                            "execution_depth_counts": {"data_smoke": 1},
                            "score_reasons": {"data_smoke_success_is_not_live_execute": 1},
                        }
                    }
                }
            }
        }
    }

    status = format_l2_status(result)

    assert "smoke_only_when_live_requested 1" in status
    assert "live_execute success" not in status
    assert "data_smoke success" not in status


def test_l2_summary_reports_missing_live_gold():
    result = {
        "level_results": {
            "L2": {
                "evaluators": {
                    "official_example_execution": {
                        "l2_summary": {
                            "status_counts": {"missing_live_official_example_gold": 1},
                            "execution_depth_counts": {},
                            "score_reasons": {"missing_live_official_example_gold": 1},
                        }
                    }
                }
            }
        }
    }

    status = format_l2_status(result)

    assert "missing_live_gold 1" in status


def test_l2_summary_reports_missing_official_gold_for_diagnostic_mode():
    result = {
        "level_results": {
            "L2": {
                "evaluators": {
                    "official_example_execution": {
                        "l2_summary": {
                            "status_counts": {"missing_official_example_gold": 1},
                            "execution_depth_counts": {},
                            "score_reasons": {"missing_official_example_gold": 1},
                        }
                    }
                }
            }
        }
    }

    status = format_l2_status(result)

    assert "missing_official_gold 1" in status
