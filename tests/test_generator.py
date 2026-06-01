from __future__ import annotations

from pathlib import Path

from paper2skill.common import PROJECT_ROOT
from paper2skill.generators.codex_skill_generator import build_context, example_inputs, generate_skill, plan_outputs
from paper2skill.validators.skill_validator import validate_skill


def test_generator_creates_complete_toy_python_skill(tmp_path: Path):
    context = build_context(**example_inputs("toy_python"))
    out = generate_skill(context, tmp_path / "toy-python-skill")
    result = validate_skill(out)
    assert result["status"] == "pass", result
    assert (out / "references" / "algorithm_contract.yaml").exists()
    assert (out / "references" / "bio_contract.yaml").exists()


def test_generator_creates_toy_r_skill(tmp_path: Path):
    context = build_context(**example_inputs("toy_r"))
    out = generate_skill(context, tmp_path / "toy-r-skill")
    result = validate_skill(out)
    assert result["status"] == "pass", result
    assert (out / "assets" / "environment_spec.yaml").exists()


def test_generated_public_files_do_not_include_absolute_paths(tmp_path: Path):
    context = build_context(**example_inputs("toy_python"))
    out = generate_skill(context, tmp_path / "toy-python-skill")
    assert_no_absolute_path_markers(out)


def test_generated_dependency_assets_redact_local_file_urls(tmp_path: Path):
    context = build_context(**example_inputs("toy_python"))
    private_dep = "localpkg @ file:///tmp/paper2skill-private/localpkg"
    context["environment_spec"]["python"]["packages"] = [{"spec": private_dep, "required": True}]
    context["environment_report"]["python"]["packages"] = [{"name": private_dep, "import_name": "localpkg", "installed": False, "required": True}]
    out = generate_skill(context, tmp_path / "toy-python-skill")
    plan = plan_outputs(context, tmp_path / "plan")
    public_text = "\n".join(
        [
            (out / "assets" / "requirements.txt").read_text(encoding="utf-8"),
            (out / "assets" / "environment.yml").read_text(encoding="utf-8"),
            (out / "assets" / "environment_spec.yaml").read_text(encoding="utf-8"),
            (out / "references" / "environment_report.json").read_text(encoding="utf-8"),
            (plan / "environment_report.json").read_text(encoding="utf-8"),
        ]
    )
    assert "file:///tmp/paper2skill-private" not in public_text
    assert "/tmp/paper2skill-private" not in public_text
    assert "localpkg" in public_text


def test_generated_environment_yml_uses_pip_section_for_python_specs(tmp_path: Path):
    context = build_context(**example_inputs("toy_python"))
    context["environment_spec"]["python"]["packages"] = [{"spec": "scikit-learn==1.4.0", "required": True}]
    out = generate_skill(context, tmp_path / "toy-python-skill")
    environment_yml = (out / "assets" / "environment.yml").read_text(encoding="utf-8")
    requirements_txt = (out / "assets" / "requirements.txt").read_text(encoding="utf-8")
    assert "- pip:" in environment_yml
    assert "  - scikit-learn==1.4.0" in environment_yml
    assert "scikit-learn==1.4.0" in requirements_txt


def test_plan_outputs_do_not_include_absolute_paths(tmp_path: Path):
    context = build_context(**example_inputs("toy_python"))
    out = plan_outputs(context, tmp_path / "plan")
    assert_no_absolute_path_markers(out)


def assert_no_absolute_path_markers(root: Path) -> None:
    markers = {
        str(PROJECT_ROOT),
        str(PROJECT_ROOT).replace("\\", "/"),
        "/home/",
        "\\Users\\",
        "C:\\",
        "D:\\",
    }
    leaks = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in markers:
            if marker and marker in text:
                leaks.append(f"{path.relative_to(root)} contains {marker}")
    assert leaks == []
