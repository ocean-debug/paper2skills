from __future__ import annotations

import os
import json
import subprocess
import sys
import importlib.util
from pathlib import Path


def test_generated_toy_python_skill_smoke(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    build = subprocess.run(
        [sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    validate = subprocess.run(
        [sys.executable, "-m", "paper2skill.cli", "validate", "--skill", str(out)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert validate.returncode == 0, validate.stdout + validate.stderr
    test = subprocess.run(
        [sys.executable, "-m", "paper2skill.cli", "test", "--skill", str(out), "--mode", "all"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert test.returncode == 0, test.stdout + test.stderr


def test_generated_skill_runs_with_regular_yaml_manifest(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    subprocess.run([sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)], check=True)
    manifest = out / "yaml_manifest.yaml"
    manifest.write_text(
        """
inputs:
  primary_data:
    path: assets/demo_input.csv
    format: csv
    exists: true
  metadata:
    sample_key: sample
    condition_key: condition
  algorithm:
    mode: demo
    parameters:
      summary_column: value
environment:
  preferred_manager: conda
  environment_name: toy-python-skill-env
  install_policy: ask
""".strip()
        + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(out / "scripts" / "run.py"), "--manifest", str(manifest), "--out", str(out / "yaml-result")],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (out / "yaml-result" / "result.json").exists()


def test_generated_plan_accepts_regular_yaml_manifest(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    subprocess.run([sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)], check=True)
    manifest = out / "yaml_manifest.yaml"
    manifest.write_text(
        """
inputs:
  primary_data:
    path: assets/demo_input.csv
    format: csv
    exists: true
  metadata:
    sample_key: sample
    condition_key: condition
  algorithm:
    mode: demo
    parameters:
      summary_column: value
environment:
  preferred_manager: conda
  environment_name: toy-python-skill-env
  install_policy: ask
""".strip()
        + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(out / "scripts" / "plan.py"), "--manifest", str(manifest), "--out", str(out / "yaml-plan-result")],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (out / "yaml-plan-result" / "workflow" / "plan.json").exists()


def test_generated_preflight_accepts_regular_yaml_manifest(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    subprocess.run([sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)], check=True)
    manifest = out / "yaml_manifest.yaml"
    manifest.write_text(
        """
inputs:
  primary_data:
    path: assets/demo_input.csv
    format: csv
    exists: true
  metadata:
    sample_key: sample
    condition_key: condition
  algorithm:
    mode: demo
    parameters:
      summary_column: value
environment:
  preferred_manager: conda
  environment_name: toy-python-skill-env
  install_policy: ask
""".strip()
        + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(out / "scripts" / "preflight.py"), "--manifest", str(manifest), "--out", str(out / "yaml-result")],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_generated_yaml_loader_has_stdlib_fallback_for_lists(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    subprocess.run([sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)], check=True)
    spec = importlib.util.spec_from_file_location("generated_env_manager", out / "scripts" / "env_manager.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.yaml = None
    parsed = module.parse_simple_yaml(
        """
inputs:
  algorithm:
    mode: demo
    parameters:
      targets:
        - STAT3
        - JUN
""".strip()
    )
    assert parsed["inputs"]["algorithm"]["parameters"]["targets"] == ["STAT3", "JUN"]


def test_generated_env_manager_direct_reference_import_probe(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    subprocess.run([sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)], check=True)
    spec = importlib.util.spec_from_file_location("generated_env_manager_direct_ref", out / "scripts" / "env_manager.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    direct_ref = "localpkg @ file:///tmp/private/localpkg"
    report = module.probe_python([{"spec": direct_ref, "required": True}])
    assert module.import_name_from_spec(direct_ref) == "localpkg"
    assert report["packages"][0]["name"] == direct_ref
    assert report["packages"][0]["import_name"] == "localpkg"


def test_generated_run_preserves_preflight_failure_status(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    subprocess.run([sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)], check=True)
    manifest = out / "bad_manifest.yaml"
    missing_input = tmp_path / "private" / "missing.csv"
    manifest.write_text(
        f"""
inputs:
  primary_data:
    path: {missing_input}
    format: csv
    exists: true
  algorithm:
    mode: demo
""".strip()
        + "\n",
        encoding="utf-8",
    )
    result_dir = out / "bad-result"
    result = subprocess.run(
        [sys.executable, str(out / "scripts" / "run.py"), "--manifest", str(manifest), "--out", str(result_dir)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    result_json = (result_dir / "result.json").read_text(encoding="utf-8")
    assert "blocked_input_invalid" in result_json
    public_outputs = [
        result.stdout,
        result.stderr,
        result_json,
        (result_dir / "qc" / "input_validation.json").read_text(encoding="utf-8"),
        (result_dir / "qc" / "qc_summary.json").read_text(encoding="utf-8"),
    ]
    combined = "\n".join(public_outputs)
    assert str(missing_input) not in combined
    assert str(tmp_path) not in combined


def test_generated_env_manager_does_not_execute_install_commands_through_shell(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    subprocess.run([sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)], check=True)
    env_manager = (out / "scripts" / "env_manager.py").read_text(encoding="utf-8")
    assert "shell=True" not in env_manager
    assert "run_install_strategy" in env_manager
    assert "PyYAML is required" not in env_manager
    assert "parse_simple_yaml" in env_manager


def test_generated_conda_env_strategy_is_not_current_env(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    subprocess.run([sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)], check=True)
    env_manager = (out / "scripts" / "env_manager.py").read_text(encoding="utf-8")
    assert 'if strategy == "current_env"' in env_manager
    assert 'elif strategy == "conda_env"' in env_manager
    assert "install_conda_env(python_specs, r_packages, spec)" in env_manager


def test_generated_conda_env_includes_r_base_for_r_packages(tmp_path: Path):
    out = tmp_path / "toy-r-skill"
    subprocess.run([sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_r", "--out", str(out)], check=True)
    env_manager = (out / "scripts" / "env_manager.py").read_text(encoding="utf-8")
    assert 'create_args.append("r-base")' in env_manager
    assert "conda run" in env_manager
    environment_yml = (out / "assets" / "environment.yml").read_text(encoding="utf-8")
    assert "r-base" in environment_yml


def test_generated_env_manager_plan_redacts_absolute_environment_name(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    subprocess.run([sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)], check=True)
    spec = tmp_path / "environment_spec.json"
    private_env = "/tmp/private-env/conda"
    spec.write_text(
        json.dumps(
            {
                "install_policy": "never",
                "environment_name": private_env,
                "python": {"packages": [{"name": "paper2skill_missing_pkg_zz"}]},
                "r": {"required": False, "packages": []},
                "executables": [],
            }
        ),
        encoding="utf-8",
    )
    result_dir = out / "env-plan-result"
    result = subprocess.run(
        [sys.executable, str(out / "scripts" / "env_manager.py"), "plan", "--spec", str(spec), "--out", str(result_dir)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    public_text = "\n".join(
        [
            result.stdout,
            (result_dir / "qc" / "install_plan.json").read_text(encoding="utf-8"),
            (result_dir / "references" / "install_plan.md").read_text(encoding="utf-8"),
        ]
    )
    assert private_env not in public_text
    assert "conda" in public_text


def test_generated_preflight_install_plan_uses_environment_spec_name(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    subprocess.run([sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)], check=True)
    custom_env = "custom-preflight-env"
    missing_pkg = "paper2skill_missing_pkg_zz"
    (out / "assets" / "environment_spec.yaml").write_text(
        json.dumps(
            {
                "install_policy": "never",
                "environment_name": custom_env,
                "python": {"packages": [{"spec": missing_pkg, "required": True}]},
                "r": {"required": False, "packages": []},
                "executables": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PAPER2SKILL_FORCE_MISSING_PACKAGES"] = missing_pkg
    result_dir = out / "preflight-custom-env-result"
    result = subprocess.run(
        [
            sys.executable,
            str(out / "scripts" / "preflight.py"),
            "--manifest",
            str(out / "assets" / "demo_input_manifest.yaml"),
            "--out",
            str(result_dir),
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert result.returncode == 2
    public_text = "\n".join(
        [
            result.stdout,
            (result_dir / "qc" / "install_plan.json").read_text(encoding="utf-8"),
            (result_dir / "references" / "install_plan.md").read_text(encoding="utf-8"),
        ]
    )
    assert custom_env in public_text
    assert "toy-python-skill-env" not in public_text


def test_generated_env_manager_public_report_recursively_redacts_local_paths(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    subprocess.run([sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)], check=True)
    spec = importlib.util.spec_from_file_location("generated_env_manager_public_report", out / "scripts" / "env_manager.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    private_prefix = "/tmp/private-env"
    report = {
        "status": "blocked_dependencies_missing",
        "python": {
            "executable": f"{private_prefix}/bin/python",
            "packages": [
                {
                    "name": f"localpkg @ file://{private_prefix}/localpkg",
                    "import_name": f"{private_prefix}/imports/localpkg.py",
                    "installed": False,
                    "required": True,
                }
            ],
            f"{private_prefix}/key.csv": "keyed value",
        },
        "r": {
            "required": True,
            "rscript_available": True,
            "rscript": f"{private_prefix}/bin/Rscript",
            "packages": [],
        },
        "executables": [
            {
                "name": "tool",
                "path": f"{private_prefix}/bin/tool",
                "available": True,
                "required": True,
            }
        ],
        "notes": {
            "quoted": f'read_csv("{private_prefix}/data with spaces/input.csv")',
            "windows": r"C:\Private\alice\sample.tsv",
            "url": "https://example.org/files/data.csv",
        },
    }
    public = module.public_environment_report(report)
    public_text = json.dumps(public, sort_keys=True)
    assert private_prefix not in public_text
    assert f"file://{private_prefix}" not in public_text
    assert r"C:\Private\alice" not in public_text
    assert public["python"]["executable"] == "<redacted-local-path>"
    assert public["r"]["rscript"] == "<redacted-local-path>"
    assert public["executables"][0]["path"] == "<redacted-local-path>"
    assert "localpkg @ localpkg" in public_text
    assert "key.csv" in public["python"]
    assert "input.csv" in public["notes"]["quoted"]
    assert public["notes"]["windows"] == "sample.tsv"
    assert public["notes"]["url"] == "https://example.org/files/data.csv"


def test_generated_env_manager_never_policy_blocks_confirmed_install(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    subprocess.run([sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)], check=True)
    spec = tmp_path / "never_spec.json"
    spec.write_text(
        json.dumps(
            {
                "install_policy": "never",
                "python": {"packages": [{"spec": "paper2skill_missing_pkg_zz", "required": True}]},
                "r": {"required": False, "packages": []},
                "executables": [],
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PAPER2SKILL_FORCE_MISSING_PACKAGES"] = "paper2skill_missing_pkg_zz"
    result = subprocess.run(
        [
            sys.executable,
            str(out / "scripts" / "env_manager.py"),
            "install",
            "--spec",
            str(spec),
            "--strategy",
            "current_env",
            "--confirm",
            "yes",
            "--out",
            str(out / "never-install-result"),
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert result.returncode == 2
    assert "effective install policy is never" in result.stderr
    assert (out / "never-install-result" / "qc" / "install_plan.json").exists()


def test_generated_runtime_outputs_redact_absolute_paths(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    subprocess.run([sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)], check=True)
    manifest = tmp_path / "external_manifest.yaml"
    absolute_input = (out / "assets" / "demo_input.csv").resolve()
    private_posix_path = "/tmp/paper2skill-private/output.tsv"
    quoted_space_path = 'read_csv("/tmp/private dir/input file.csv")'
    private_windows_path = r"C:\Private\alice\sample.tsv"
    public_url = "https://example.org/files/data.csv"
    manifest.write_text(
        f"""
inputs:
  primary_data:
    path: {absolute_input}
    format: csv
    exists: true
  algorithm:
    mode: demo
    parameters:
      private_posix_path: {private_posix_path}
      /tmp/paper2skill-private/key.csv: keyed value
      quoted_space_path: '{quoted_space_path}'
      private_windows_path: '{private_windows_path}'
      public_url: {public_url}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    result_dir = out / "absolute-path-result"
    result = subprocess.run(
        [sys.executable, str(out / "scripts" / "run.py"), "--manifest", str(manifest.resolve()), "--out", str(result_dir)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((result_dir / "qc" / "environment_report.json").read_text(encoding="utf-8"))
    assert report["python"]["executable"] == "<redacted-local-path>"
    if report["r"].get("rscript"):
        assert report["r"]["rscript"] == "<redacted-local-path>"
    history = (result_dir / "reproducibility" / "command_history.sh").read_text(encoding="utf-8")
    assert str(manifest.resolve()) not in history
    assert "external_manifest.yaml" in history
    result_text = (result_dir / "result.json").read_text(encoding="utf-8")
    plan_text = (result_dir / "workflow" / "plan.json").read_text(encoding="utf-8")
    params_text = (result_dir / "parameters" / "resolved_parameters.json").read_text(encoding="utf-8")
    markers = {
        str(tmp_path),
        str(tmp_path).replace("\\", "/"),
        str(absolute_input),
        str(absolute_input).replace("\\", "/"),
        private_posix_path,
        "/tmp/private dir",
        private_windows_path,
        sys.executable,
        sys.executable.replace("\\", "/"),
        "/home/",
        "\\Users\\",
    }
    leaks = [marker for marker in markers if marker and marker in result_text + history + plan_text + params_text + json.dumps(report)]
    assert leaks == []
    assert "input file.csv" in params_text
    assert "key.csv" in params_text
    assert public_url in params_text


def test_generated_plan_redacts_manifest_absolute_paths(tmp_path: Path):
    out = tmp_path / "toy-python-skill"
    subprocess.run([sys.executable, "-m", "paper2skill.cli", "build", "--example", "toy_python", "--out", str(out)], check=True)
    private_posix_path = "/tmp/paper2skill-private/input.csv"
    private_windows_path = r"C:\Private\alice\sample.tsv"
    manifest = tmp_path / "plan_manifest.yaml"
    manifest.write_text(
        f"""
inputs:
  primary_data:
    path: {private_posix_path}
    format: csv
    exists: false
  metadata:
    private_windows_path: '{private_windows_path}'
  algorithm:
    mode: demo
    parameters:
      private_posix_path: {private_posix_path}
      private_windows_path: '{private_windows_path}'
""".strip()
        + "\n",
        encoding="utf-8",
    )
    result_dir = out / "absolute-plan-result"
    result = subprocess.run(
        [sys.executable, str(out / "scripts" / "plan.py"), "--manifest", str(manifest.resolve()), "--out", str(result_dir)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    plan_text = (result_dir / "workflow" / "plan.json").read_text(encoding="utf-8")
    assert private_posix_path not in plan_text
    assert private_windows_path not in plan_text
    assert "input.csv" in plan_text
    assert "sample.tsv" in plan_text
