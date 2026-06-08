from __future__ import annotations

from pathlib import Path

from paper2skill.evaluation.execution.data_manager import prepare_download
from paper2skill.evaluation.execution.run_official_example import evaluate_official_examples


def test_l2_blocked_expected_passes_for_candidate_adapter():
    gold = {"official_examples": [{"example_id": "demo", "execution_mode": "blocked_expected", "expected_run": {"expected_status": "blocked_by_policy"}}]}
    generated = {"adapter_review": {"status": "candidate"}}

    result = evaluate_official_examples(gold, generated)

    assert result["passed"] is True
    assert result["examples"][0]["actual_status"] == "blocked_by_policy"


def test_l2_download_skipped_without_allow_download(tmp_path: Path):
    result = prepare_download({"url": "https://example.test/data.txt", "cache_key": "data.txt"}, allow_download=False, cache_dir=tmp_path)

    assert result["status"] == "skipped"
    assert "allow-download" in result["warnings"][0]


def test_l2_output_validation_failure_is_reported(tmp_path: Path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    run_script = scripts / "run.py"
    run_script.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse",
                "from pathlib import Path",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--manifest', required=True)",
                "parser.add_argument('--out', required=True)",
                "args = parser.parse_args()",
                "Path(args.out).mkdir(parents=True, exist_ok=True)",
            ]
        ),
        encoding="utf-8",
    )
    gold = {
        "official_examples": [
            {
                "example_id": "demo",
                "execution_mode": "smoke",
                "expected_run": {"expected_status": "success"},
                "expected_outputs": [{"name": "result.txt", "required": True}],
            }
        ]
    }
    generated = {"adapter_review": {"status": "verified"}}

    result = evaluate_official_examples(gold, generated, skill_dir=tmp_path, l2_mode="data_smoke")

    assert result["passed"] is False
    assert result["examples"][0]["actual_status"] == "output_validation_failed"


def test_l2_verified_adapter_invokes_generated_run_script(tmp_path: Path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    run_script = scripts / "run.py"
    run_script.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse",
                "from pathlib import Path",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--manifest', required=True)",
                "parser.add_argument('--out', required=True)",
                "args = parser.parse_args()",
                "out = Path(args.out)",
                "out.mkdir(parents=True, exist_ok=True)",
                "(out / 'result.txt').write_text('ok', encoding='utf-8')",
            ]
        ),
        encoding="utf-8",
    )
    validator = scripts / "validate_outputs.py"
    validator.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse",
                "from pathlib import Path",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--result', required=True)",
                "args = parser.parse_args()",
                "raise SystemExit(0 if (Path(args.result) / 'result.txt').exists() else 2)",
            ]
        ),
        encoding="utf-8",
    )
    gold = {
        "official_examples": [
            {
                "example_id": "demo",
                "execution_mode": "smoke",
                "input_manifest": {"inputs": [{"path": "toy.txt"}]},
                "expected_run": {"expected_status": "success"},
                "expected_outputs": [{"name": "result.txt", "path": "result.txt", "required": True}],
            }
        ]
    }
    generated = {"adapter_review": {"status": "verified"}}

    result = evaluate_official_examples(gold, generated, skill_dir=tmp_path, l2_mode="data_smoke")

    example = result["examples"][0]
    assert result["passed"] is True
    assert result["score"] == 100.0
    assert example["actual_status"] == "success"
    assert example["execution_depth"] == "data_smoke"
    assert example["score_reason"] == "data_smoke_success"
    assert example["execution"]["exit_code"] == 0
    assert (tmp_path / ".benchmark" / "l2" / "demo" / "result.txt").exists()


def test_l2_manifest_validation_failure_blocks_success_run(tmp_path: Path):
    gold = {
        "official_examples": [
            {
                "example_id": "demo",
                "execution_mode": "smoke",
                "input_manifest": {"matrix_state": "normalized"},
                "expected_run": {"expected_status": "success"},
            }
        ]
    }
    generated = {
        "adapter_review": {"status": "verified"},
        "io_contract": {"input_contract": {"primary_input": {"matrix_state": "raw_counts"}}},
    }

    result = evaluate_official_examples(gold, generated, skill_dir=tmp_path, l2_mode="data_smoke")

    example = result["examples"][0]
    assert result["passed"] is False
    assert example["actual_status"] == "input_validation_failed"
    assert "raw counts required" in " ".join(example["input_validation"]["errors"])


def test_l2_preflight_policy_block_is_reported_without_running_adapter(tmp_path: Path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    preflight = scripts / "preflight.py"
    preflight.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--manifest', required=True)",
                "parser.add_argument('--out', required=True)",
                "parser.parse_args()",
                "raise SystemExit(2)",
            ]
        ),
        encoding="utf-8",
    )
    run_script = scripts / "run.py"
    run_script.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse",
                "from pathlib import Path",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--manifest', required=True)",
                "parser.add_argument('--out', required=True)",
                "args = parser.parse_args()",
                "(Path(args.out) / 'should_not_exist.txt').write_text('ran', encoding='utf-8')",
            ]
        ),
        encoding="utf-8",
    )
    gold = {
        "official_examples": [
            {
                "example_id": "demo",
                "execution_mode": "smoke",
                "input_manifest": {},
                "expected_run": {"expected_status": "blocked_by_policy_or_success"},
            }
        ]
    }
    generated = {"adapter_review": {"status": "verified"}}

    result = evaluate_official_examples(gold, generated, skill_dir=tmp_path, l2_mode="data_smoke")

    example = result["examples"][0]
    assert result["passed"] is True
    assert example["actual_status"] == "blocked_by_policy"
    assert example["execution"]["preflight"]["exit_code"] == 2
    assert not (tmp_path / ".benchmark" / "l2" / "demo" / "should_not_exist.txt").exists()


def test_l2_reviewed_adapter_overlay_copies_fixture_and_executes(tmp_path: Path):
    case_dir = tmp_path / "case"
    fixture_dir = case_dir / "data" / "official_examples" / "minimal"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "toy.txt").write_text("ok\n", encoding="utf-8")
    (fixture_dir / "reviewed_cli_adapter.py").write_text("def touched():\n    return True\n", encoding="utf-8")
    skill = tmp_path / "skill"
    (skill / "scripts").mkdir(parents=True)
    (skill / "references").mkdir(parents=True)
    run_script = skill / "scripts" / "run.py"
    run_script.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse",
                "from pathlib import Path",
                "ROOT = Path(__file__).resolve().parents[1]",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--manifest', required=True)",
                "parser.add_argument('--out', required=True)",
                "args = parser.parse_args()",
                "out = Path(args.out)",
                "out.mkdir(parents=True, exist_ok=True)",
                "assert (ROOT / '.benchmark/fixtures/toy.txt').exists()",
                "assert (ROOT / 'scripts/adapters/cli_adapter.py').exists()",
                "assert 'verified' in (ROOT / 'references/adapter_spec.yaml').read_text(encoding='utf-8')",
                "(out / 'result.txt').write_text('ok', encoding='utf-8')",
            ]
        ),
        encoding="utf-8",
    )
    gold = {
        "official_examples": [
            {
                "example_id": "demo",
                "execution_mode": "smoke",
                "fixture_files": [{"source": "data/official_examples/minimal/toy.txt", "target": ".benchmark/fixtures/toy.txt"}],
                "reviewed_adapter": {
                    "status": "verified",
                    "adapter_type": "cli",
                    "files": [{"source": "data/official_examples/minimal/reviewed_cli_adapter.py", "target": "scripts/adapters/cli_adapter.py"}],
                    "adapter_spec": {"adapter_type": "cli", "status": "verified"},
                    "adapter_review": {"adapter_type": "cli", "status": "verified", "human_approved": True},
                },
                "input_manifest": {"inputs": {"primary_data": {"path": ".benchmark/fixtures/toy.txt"}, "algorithm": {"mode": "reviewed_smoke"}}},
                "expected_run": {"expected_status": "success"},
                "expected_outputs": [{"name": "result", "path": "result.txt", "required": True}],
            }
        ]
    }
    generated = {"adapter_review": {"status": "candidate"}}

    result = evaluate_official_examples(gold, generated, skill_dir=skill, case_dir=case_dir, l2_mode="data_smoke")

    example = result["examples"][0]
    assert result["passed"] is True
    assert example["adapter_status"] == "verified"
    assert example["actual_status"] == "success"
    assert example["reviewed_adapter"]["status"] == "applied"
    assert example["fixtures"]["status"] == "ready"


def test_l2_default_dry_run_skips_data_smoke_without_side_effects(tmp_path: Path):
    gold = {
        "official_examples": [
            {
                "example_id": "demo",
                "execution_mode": "smoke",
                "download": {"url": "https://example.test/data.txt", "cache_key": "data.txt"},
                "expected_run": {"expected_status": "success"},
            }
        ]
    }
    generated = {"adapter_review": {"status": "verified"}}

    result = evaluate_official_examples(gold, generated, skill_dir=tmp_path)

    example = result["examples"][0]
    assert result["passed"] is False
    assert result["score"] == 25.0
    assert example["actual_status"] == "skipped_by_l2_mode"
    assert example["execution_depth"] == "dry_run_skip"
    assert example["score"] == 0.25
    assert example["score_reason"] == "dry_run_skip_no_example_execution"
    assert example["download"]["status"] == "not_applicable"
    assert example["execution"]["status"] == "not_applicable"
    assert result["l2_summary"]["execution_depth_counts"] == {"dry_run_skip": 1}


def test_l2_data_smoke_requires_explicit_download(tmp_path: Path):
    gold = {
        "official_examples": [
            {
                "example_id": "demo",
                "execution_mode": "smoke",
                "download": {"url": "https://example.test/data.txt", "cache_key": "data.txt"},
                "expected_run": {"expected_status": "success"},
            }
        ]
    }
    generated = {"adapter_review": {"status": "verified"}}

    result = evaluate_official_examples(gold, generated, skill_dir=tmp_path, l2_mode="data_smoke")

    example = result["examples"][0]
    assert result["passed"] is False
    assert example["actual_status"] == "download_required"
    assert "allow-download" in example["download"]["warnings"][0]


def test_l2_live_execute_missing_dependencies_returns_install_request(tmp_path: Path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    preflight = scripts / "preflight.py"
    preflight.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse, json",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--manifest', required=True)",
                "parser.add_argument('--out', required=True)",
                "parser.parse_args()",
                "print(json.dumps({'status':'blocked_dependencies_missing','environment':{'r':{'packages':[{'name':'DESeq2','required':True,'installed':False}]},'executables':[]}}))",
                "raise SystemExit(2)",
            ]
        ),
        encoding="utf-8",
    )
    run_script = scripts / "run.py"
    run_script.write_text("raise SystemExit('should not run')\n", encoding="utf-8")
    gold = {
        "official_examples": [
            {
                "example_id": "demo",
                "execution_mode": "live_execute",
                "input_manifest": {"inputs": {"primary_data": {"path": "input.tsv"}, "algorithm": {"mode": "live"}}},
                "dependencies": {
                    "install_policy": "ask",
                    "preferred_environment": "isolated_conda",
                    "allowed_installers": ["BiocManager"],
                    "required_packages": ["DESeq2"],
                },
                "expected_run": {"expected_status": "success"},
            }
        ]
    }
    generated = {"adapter_review": {"status": "verified"}}

    result = evaluate_official_examples(
        gold,
        generated,
        skill_dir=tmp_path,
        l2_mode="live_execute",
        allow_install="ask",
        install_env="paper2skill-l2-demo",
    )

    example = result["examples"][0]
    assert result["passed"] is False
    assert example["actual_status"] == "install_approval_required"
    assert example["score"] == 0.5
    assert example["execution_depth"] == "install_approval_required"
    request = example["execution"]["install_request"]
    assert request["target_environment"] == "paper2skill-l2-demo"
    assert request["required_packages"] == ["DESeq2"]
    assert request["safety"]["auto_install_performed"] is False
