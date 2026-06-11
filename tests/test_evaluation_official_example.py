from __future__ import annotations

import json
import subprocess
from pathlib import Path

import paper2skill.evaluation.execution.run_official_example as official_example
from paper2skill.evaluation.execution.data_manager import prepare_download
from paper2skill.evaluation.execution.run_official_example import evaluate_official_examples
from paper2skill.evaluation.execution.run_official_example import run_repair_attempts
from paper2skill.evaluation.execution.run_official_example import safe_repair_plan


def test_l2_policy_block_is_diagnostic_not_l2_success():
    gold = {"official_examples": [{"example_id": "demo", "execution_mode": "blocked_expected", "expected_run": {"expected_status": "blocked_by_policy"}}]}
    generated = {"adapter_review": {"status": "candidate"}}

    result = evaluate_official_examples(gold, generated, l2_mode="dry_run")

    assert result["passed"] is False
    assert result["examples"][0]["actual_status"] == "blocked_by_policy"
    assert result["examples"][0]["score_reason"] == "expected_policy_block_is_l4_not_l2"
    assert result["examples"][0]["execution_passed"] is False


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
    assert result["passed"] is False
    assert result["score"] == 0.0
    assert example["passed"] is False
    assert example["execution_passed"] is True
    assert example["actual_status"] == "success"
    assert example["execution_depth"] == "data_smoke"
    assert example["score_reason"] == "diagnostic_data_smoke_success_not_benchmark_scoring"
    assert example["diagnostic_only"] is True
    assert result["l2_summary"]["diagnostic_only"] is True
    assert result["l2_summary"]["benchmark_policy"] == "diagnostic_only"
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
    assert result["passed"] is False
    assert example["actual_status"] == "blocked_by_policy"
    assert example["score_reason"] == "expected_policy_block_is_l4_not_l2"
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
    assert result["passed"] is False
    assert example["adapter_status"] == "verified"
    assert example["actual_status"] == "success"
    assert example["diagnostic_only"] is True
    assert example["reviewed_adapter"]["status"] == "applied"
    assert example["fixtures"]["status"] == "ready"


def test_l2_default_benchmark_requires_live_execute_gold(tmp_path: Path):
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

    assert result["passed"] is False
    assert result["score"] == 0.0
    assert "level2_official_examples.live_execute" in result["missing_items"]
    assert result["l2_summary"]["status_counts"] == {"missing_live_official_example_gold": 1}
    assert result["l2_summary"]["benchmark_policy"] == "live_execute_required"


def test_l2_empty_gold_is_not_scored_as_success(tmp_path: Path):
    result = evaluate_official_examples({}, {"adapter_review": {"status": "verified"}}, skill_dir=tmp_path)

    assert result["passed"] is False
    assert result["score"] == 0.0
    assert "level2_official_examples.official_examples" in result["missing_items"]
    assert result["l2_summary"]["score_reasons"] == {"missing_live_official_example_gold": 1}


def test_l2_empty_gold_in_diagnostic_mode_is_still_zero_score(tmp_path: Path):
    result = evaluate_official_examples({}, {"adapter_review": {"status": "verified"}}, skill_dir=tmp_path, l2_mode="data_smoke")

    assert result["passed"] is False
    assert result["score"] == 0.0
    assert result["diagnostic_only"] is True
    assert result["l2_summary"]["benchmark_policy"] == "diagnostic_only"
    assert result["l2_summary"]["score_reasons"] == {"missing_official_example_gold": 1}


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
    assert example["score"] == 0.0
    assert example["execution_depth"] == "install_approval_required"
    request = example["execution"]["install_request"]
    assert request["target_environment"] == "paper2skill-l2-demo"
    assert request["required_packages"] == ["DESeq2"]
    assert request["safety"]["auto_install_performed"] is False


def test_l2_live_execute_selects_live_entries_only(tmp_path: Path):
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
                "(out / 'live.txt').write_text('ok', encoding='utf-8')",
            ]
        ),
        encoding="utf-8",
    )
    gold = {
        "official_examples": [
            {
                "example_id": "smoke",
                "execution_mode": "smoke",
                "expected_run": {"expected_status": "success"},
                "expected_outputs": [{"name": "smoke.txt", "path": "smoke.txt", "required": True}],
            },
            {
                "example_id": "live",
                "execution_mode": "live_execute",
                "expected_run": {"expected_status": "success"},
                "expected_outputs": [{"name": "live.txt", "path": "live.txt", "required": True}],
            },
        ]
    }
    generated = {"adapter_review": {"status": "verified"}}

    result = evaluate_official_examples(gold, generated, skill_dir=tmp_path, l2_mode="live_execute")

    assert result["passed"] is True
    assert len(result["examples"]) == 1
    assert result["examples"][0]["example_id"] == "live"
    assert result["examples"][0]["execution_depth"] == "live_execute"
    assert result["examples"][0]["passed"] is True
    assert result["examples"][0]["execution_passed"] is True


def test_l2_live_request_requires_live_gold_instead_of_smoke_fallback(tmp_path: Path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "run.py").write_text(
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
                "(out / 'smoke.txt').write_text('ok', encoding='utf-8')",
            ]
        ),
        encoding="utf-8",
    )
    gold = {
        "official_examples": [
            {
                "example_id": "smoke_only",
                "execution_mode": "smoke",
                "expected_run": {"expected_status": "success"},
                "expected_outputs": [{"name": "smoke", "path": "smoke.txt", "required": True}],
            }
        ]
    }
    generated = {"adapter_review": {"status": "verified"}}

    result = evaluate_official_examples(gold, generated, skill_dir=tmp_path, l2_mode="live_execute")

    assert result["passed"] is False
    assert result["score"] == 0.0
    assert "level2_official_examples.live_execute" in result["missing_items"]
    assert result["l2_summary"]["score_reasons"] == {"missing_live_official_example_gold": 1}


def test_l2_live_execute_approved_install_uses_conda_env_runner(tmp_path: Path, monkeypatch):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "preflight.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    (scripts / "run.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    (scripts / "validate_outputs.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    seen_commands = []

    def fake_install(*args, **kwargs):
        return {"status": "executed", "execution_results": [{"kind": "conda_env_create", "exit_code": 0, "skipped": True}]}

    def fake_run(command, **kwargs):
        seen_commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(official_example, "install_approved_dependencies", fake_install)
    monkeypatch.setattr(official_example.subprocess, "run", fake_run)
    gold = {
        "official_examples": [
            {
                "example_id": "live",
                "execution_mode": "live_execute",
                "dependencies": {"allowed_installers": ["conda", "pip"], "conda": ["numpy"], "pip": ["scanpy"]},
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
        allow_install="approved",
        install_env="p2s_l2_case_demo",
        create_conda_env=True,
    )

    assert result["passed"] is True
    assert seen_commands
    assert all(command[:5] == ["conda", "run", "-n", "p2s_l2_case_demo", "python"] for command in seen_commands)
    assert result["examples"][0]["execution"]["install_report"]["status"] == "executed"


def test_l2_live_execute_approved_install_reports_remaining_missing_dependencies(tmp_path: Path, monkeypatch):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "preflight.py").write_text("raise SystemExit(2)\n", encoding="utf-8")
    (scripts / "run.py").write_text("raise SystemExit('should not run')\n", encoding="utf-8")

    def fake_install(*args, **kwargs):
        return {"status": "executed", "execution_results": [{"kind": "python_packages", "exit_code": 0}]}

    def fake_run(command, **kwargs):
        stdout = (
            '{"status":"blocked_dependencies_missing",'
            '"environment":{"python":{"packages":[{"name":"scanpy","required":true,"installed":false}]},'
            '"r":{"packages":[]},"executables":[]}}'
        )
        return subprocess.CompletedProcess(command, 2, stdout=stdout, stderr="")

    monkeypatch.setattr(official_example, "install_approved_dependencies", fake_install)
    monkeypatch.setattr(official_example.subprocess, "run", fake_run)
    gold = {
        "official_examples": [
            {
                "example_id": "live",
                "execution_mode": "live_execute",
                "dependencies": {"allowed_installers": ["pip"], "pip": ["scanpy"]},
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
        allow_install="approved",
        install_env="p2s_l2_case_demo",
    )

    example = result["examples"][0]
    assert result["passed"] is False
    assert example["actual_status"] == "dependencies_missing_after_install"
    assert example["execution"]["missing_dependencies"]["missing_python_packages"] == ["scanpy"]


def test_l2_live_execute_can_use_bio_env_rebuilder(tmp_path: Path, monkeypatch):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "preflight.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    (scripts / "run.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    seen_plan = {}
    seen_commands = []

    def fake_apply(plan, *, yes):
        seen_plan.update(plan)
        return {"status": "executed", "manager": plan["manager"], "execution_results": [{"kind": "uv_venv_create", "exit_code": 0}], "auto_install_performed": True}

    def fake_run(command, **kwargs):
        seen_commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(official_example, "apply_bio_install_plan", fake_apply)
    monkeypatch.setattr(official_example.subprocess, "run", fake_run)
    gold = {
        "official_examples": [
            {
                "example_id": "live",
                "execution_mode": "live_execute",
                "dependencies": {"allowed_installers": ["pip"], "pip": ["paper-only"]},
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
        allow_install="approved",
        install_env="p2s_l2_case_demo",
        env_rebuilder="bio",
        export_lock=True,
    )

    assert result["passed"] is True
    assert seen_plan["manager"] == "uv"
    assert seen_plan["torch_backend"] == "auto"
    assert seen_plan["resolved_env_path"] == str(tmp_path / ".benchmark" / "envs" / "p2s_l2_case_demo")
    assert seen_commands
    expected_python = tmp_path / ".benchmark" / "envs" / "p2s_l2_case_demo"
    assert any(str(command[0]).startswith(str(expected_python)) for command in seen_commands)
    install_report = result["examples"][0]["execution"]["install_report"]
    assert install_report["env_rebuilder"] == "bio"
    assert install_report["resolved_env_path"] == str(expected_python)
    assert install_report["python_executable"].startswith(str(expected_python))
    assert install_report["export_lock_requested"] is True


def test_l2_bio_env_scans_skill_lockfile_for_frozen_restore(tmp_path: Path, monkeypatch):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "preflight.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    (scripts / "run.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    lock_dir = tmp_path / "assets" / "env"
    lock_dir.mkdir(parents=True)
    (lock_dir / "conda-lock.yml").write_text(
        """
metadata:
  platforms:
    - linux-64
  channels:
    - conda-forge
    - bioconda
package:
  - name: python
    platform: linux-64
    manager: conda
    url: https://conda.anaconda.org/conda-forge/linux-64/python.tar.bz2
""".strip()
        + "\n",
        encoding="utf-8",
    )
    seen_plan = {}
    seen_commands = []

    def fake_apply(plan, *, yes):
        seen_plan.update(plan)
        return {"status": "executed", "manager": plan["manager"], "execution_results": [{"kind": command["kind"], "exit_code": 0} for command in plan["commands"]], "auto_install_performed": True}

    def fake_run(command, **kwargs):
        seen_commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(official_example, "apply_bio_install_plan", fake_apply)
    monkeypatch.setattr(official_example.subprocess, "run", fake_run)
    gold = {
        "official_examples": [
            {
                "example_id": "live",
                "execution_mode": "live_execute",
                "dependencies": {"allowed_installers": ["pip"], "pip": ["paper-only"]},
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
        allow_install="approved",
        install_env="p2s_l2_case_demo",
        env_rebuilder="bio",
    )

    assert result["passed"] is True
    assert seen_plan["mode"] == "lockfile_restore"
    assert seen_plan["frozen"] is True
    assert [command["kind"] for command in seen_plan["commands"]] == ["restore_conda_lock", "environment_probe"]
    install_report = result["examples"][0]["execution"]["install_report"]
    assert install_report["plan_source"] == "lockfile_restore"
    assert install_report["install_plan_path"].endswith("install_plan.json")
    assert install_report["env_rebuild_report_path"].endswith("env_rebuild_report.json")
    assert any(item["name"] == "conda-lock.yml" for item in install_report["scanned_artifacts"])


def test_l2_bio_env_scans_source_manifest_repo_lockfile(tmp_path: Path, monkeypatch):
    scripts = tmp_path / "scripts"
    refs = tmp_path / "references"
    scripts.mkdir()
    refs.mkdir()
    (scripts / "preflight.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    (scripts / "run.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    repo = tmp_path / "cloned_repo"
    repo.mkdir()
    (repo / "conda-lock.yml").write_text(
        """
metadata:
  platforms:
    - linux-64
  channels:
    - conda-forge
    - bioconda
package:
  - name: python
    platform: linux-64
    manager: conda
    url: https://conda.anaconda.org/conda-forge/linux-64/python.tar.bz2
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (refs / "source_manifest.json").write_text(json.dumps({"repo": {"resolved_path": str(repo)}}), encoding="utf-8")
    seen_plan = {}

    def fake_apply(plan, *, yes):
        seen_plan.update(plan)
        return {"status": "executed", "manager": plan["manager"], "execution_results": [{"kind": command["kind"], "exit_code": 0} for command in plan["commands"]]}

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(official_example, "apply_bio_install_plan", fake_apply)
    monkeypatch.setattr(official_example.subprocess, "run", fake_run)
    gold = {
        "official_examples": [
            {
                "example_id": "live",
                "execution_mode": "live_execute",
                "dependencies": {"pip": ["paper-only"]},
                "expected_run": {"expected_status": "success"},
            }
        ]
    }

    result = evaluate_official_examples(
        gold,
        {"adapter_review": {"status": "verified"}},
        skill_dir=tmp_path,
        l2_mode="live_execute",
        allow_install="approved",
        install_env="p2s_l2_case_demo",
        env_rebuilder="bio",
    )

    assert result["passed"] is True
    assert seen_plan["mode"] == "lockfile_restore"
    assert seen_plan["allow_install"] == "approved"
    sources = [item["source"] for item in result["examples"][0]["execution"]["install_report"]["scanned_artifacts"]]
    assert str(repo / "conda-lock.yml") in sources


def test_l2_bio_env_torch_cuda_requires_manual_special_route(tmp_path: Path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "preflight.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    (scripts / "run.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    gold = {
        "official_examples": [
            {
                "example_id": "live",
                "execution_mode": "live_execute",
                "dependencies": {"allowed_installers": ["pip"], "pip": ["torch"]},
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
        allow_install="approved",
        install_env="p2s_l2_case_demo",
        env_rebuilder="bio",
        gpu_policy="required",
        torch_backend="cu128",
    )

    example = result["examples"][0]
    assert result["passed"] is False
    assert example["actual_status"] == "install_approval_required"
    commands = example["execution"]["install_report"]["install_plan"]["commands"]
    special = next(command for command in commands if command["kind"] == "manual_special_route")
    assert special["kind"] == "manual_special_route"
    assert special["special_route"]["route"] == "special_torch"


def test_l2_bio_env_github_install_unapproved_is_approval_required(tmp_path: Path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "preflight.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    (scripts / "run.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    gold = {
        "official_examples": [
            {
                "example_id": "live",
                "execution_mode": "live_execute",
                "dependencies": {"allowed_installers": ["conda", "remotes"], "r_github": ["owner/pkg"]},
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
        allow_install="approved",
        install_env="p2s_l2_case_demo",
        env_rebuilder="bio",
        allow_github_install="ask",
    )

    example = result["examples"][0]
    assert result["passed"] is False
    assert example["actual_status"] == "install_approval_required"
    assert example["execution"]["install_report"]["status"] == "approval_required"
    assert example["execution"]["install_report"]["manual_approval_required"] is True
    assert example["execution"]["install_report"]["resolved_env_path"] == str(tmp_path / ".benchmark" / "envs" / "p2s_l2_case_demo")


def test_l2_bio_env_failed_install_records_repair_attempt_and_retries(tmp_path: Path, monkeypatch):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "preflight.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    (scripts / "run.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    calls = []

    def fake_apply(plan, *, yes):
        calls.append(plan)
        if len(calls) == 1:
            return {
                "status": "failed",
                "execution_results": [{"kind": "conda_packages", "exit_code": 1, "stderr": "there is no package called 'DESeq2'"}],
            }
        return {"status": "executed", "execution_results": [{"kind": "conda_packages", "exit_code": 0}]}

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(official_example, "apply_bio_install_plan", fake_apply)
    monkeypatch.setattr(official_example.subprocess, "run", fake_run)
    gold = {
        "official_examples": [
            {
                "example_id": "live",
                "execution_mode": "live_execute",
                "dependencies": {"allowed_installers": ["conda"], "r": ["DESeq2"]},
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
        allow_install="approved",
        install_env="p2s_l2_case_demo",
        env_rebuilder="bio",
        repair_attempts=1,
    )

    report = result["examples"][0]["execution"]["install_report"]
    assert result["passed"] is True
    assert report["status"] == "executed"
    assert report["repair_attempts"][0]["status"] == "retried_safe_repair"
    assert len(calls) == 3
    assert (tmp_path / ".benchmark" / "l2" / "live" / "repair_attempts.json").exists()


def test_safe_repair_plan_limits_repeated_failure_modes_and_requires_known_route():
    diagnosis = {
        "findings": [
            {"failure_mode": "missing_r_package", "package": "DESeq2"},
            {"failure_mode": "missing_r_package", "package": "DESeq2"},
            {"failure_mode": "missing_r_package", "package": "DESeq2"},
            {"failure_mode": "missing_executable", "executable": "unknowncmd"},
        ]
    }
    counts = {}
    plan = safe_repair_plan(diagnosis, {"env": "p2s_l2_case", "manager": "conda"}, failure_mode_counts=counts)

    assert len(plan["commands"]) == 2
    assert all(command["repair_patch_type"] == "additive" for command in plan["commands"])
    assert all("--strict-channel-priority" in command["command"] for command in plan["commands"])
    assert any(item["reason"] == "same failure repair limit exceeded" for item in plan["blocked_repairs"])
    assert any(item.get("executable") == "unknowncmd" for item in plan["blocked_repairs"])


def test_safe_repair_plan_allows_multiple_packages_in_one_repair_round():
    diagnosis = {
        "findings": [
            {"failure_mode": "missing_r_package", "package": "DESeq2"},
            {"failure_mode": "missing_r_package", "package": "ggplot2"},
            {"failure_mode": "missing_executable", "executable": "Rscript"},
        ]
    }
    counts = {}

    plan = safe_repair_plan(diagnosis, {"env": "p2s_l2_case", "manager": "conda"}, failure_mode_counts=counts)

    packages = [package for command in plan["commands"] for package in command["packages"]]
    assert "bioconductor-deseq2" in packages
    assert "r-ggplot2" in packages
    assert "r-base" in packages
    assert not any(item["reason"] == "same failure repair limit exceeded" for item in plan["blocked_repairs"])


def test_frozen_lockfile_probe_failure_is_diagnosed_without_repair(monkeypatch):
    calls = []

    def fake_apply(plan, yes):
        calls.append([command.get("kind") for command in plan.get("commands") or []])
        return {
            "status": "failed",
            "execution_results": [
                {"kind": "environment_probe", "exit_code": 1, "stderr": "executable not found: python"}
            ],
        }

    monkeypatch.setattr("paper2skill.evaluation.execution.run_official_example.apply_bio_install_plan", fake_apply)
    attempts = run_repair_attempts(
        {"status": "failed", "stderr": "executable not found: python"},
        plan={
            "mode": "lockfile_restore",
            "frozen": True,
            "repair_policy": "suggestion_only",
            "commands": [{"kind": "restore_conda_lock"}, {"kind": "environment_probe"}],
        },
        requested_attempts=3,
    )

    assert attempts[0]["status"] == "diagnosed_only_frozen_lockfile"
    assert calls == []


def test_safe_repair_plan_allows_case_gold_allowlist_for_unknown_package():
    diagnosis = {
        "findings": [
            {"failure_mode": "missing_r_package", "package": "knownByGold", "manual_block": True},
        ]
    }

    plan = safe_repair_plan(
        diagnosis,
        {"env": "p2s_l2_case", "manager": "conda", "repair_allowlist": ["r-knownbygold"]},
    )

    assert plan["status"] == "ready"
    assert plan["commands"][0]["packages"] == ["r-knownbygold"]
    assert plan["commands"][0]["repair_filter"] == "case_gold_allowlist"
