from __future__ import annotations

from paper2skill.miners.dependency_miner import mine_dependencies, parse_optional_pyproject_dependencies


def test_dependency_miner_reads_python_and_r_files():
    py_deps = mine_dependencies("tests/fixtures/toy_python_algorithm")
    r_deps = mine_dependencies("tests/fixtures/toy_r_algorithm", ["tests/fixtures/toy_r_algorithm/examples/demo.R"])
    assert "pyproject.toml" in " ".join(py_deps["dependency_files"])
    assert "DESCRIPTION" in " ".join(r_deps["dependency_files"])
    assert "stats" not in r_deps["r"]


def test_optional_pyproject_dependencies_are_recorded_not_required(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "optional-demo"
version = "0.1.0"
dependencies = ["numpy"]

[project.optional-dependencies]
dev = ["pytest", "sphinx"]
gpu = ["cupy"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    deps = mine_dependencies(tmp_path)
    assert deps["python"] == ["numpy"]
    assert deps["python_optional"] == {"dev": ["pytest", "sphinx"], "gpu": ["cupy"]}
    assert parse_optional_pyproject_dependencies(pyproject)["dev"] == ["pytest", "sphinx"]


def test_requirements_direct_references_preserve_full_spec(tmp_path):
    requirements = tmp_path / "requirements.txt"
    direct_ref = "localpkg @ file:///tmp/private/localpkg"
    requirements.write_text(
        "\n".join(
            [
                "# comment",
                direct_ref,
                'scanpy[leiden]>=1.10; python_version >= "3.10"',
                "-r other-requirements.txt",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    deps = mine_dependencies(tmp_path)
    assert direct_ref in deps["python"]
    assert 'scanpy[leiden]>=1.10; python_version >= "3.10"' in deps["python"]
    assert "-r other-requirements.txt" not in deps["python"]


def test_requirements_records_required_optional_and_ignored_entries(tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "\n".join(
            [
                'scikit-learn==1.4.0; python_version >= "3.10"',
                "localpkg @ file:///tmp/private/localpkg",
                "-c constraints.txt",
                "-e .",
                "./local_checkout",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    deps = mine_dependencies(tmp_path)
    assert deps["python"] == ['localpkg @ file:///tmp/private/localpkg', 'scikit-learn==1.4.0; python_version >= "3.10"']
    assert deps["python_records"][0]["required"] is True
    assert deps["python_records"][0]["category"] == "runtime"
    assert "constraints.txt" in " ".join(item["value"] for item in deps["ignored"])
    assert "-e ." in " ".join(item["value"] for item in deps["ignored"])
    assert "./local_checkout" in " ".join(item["value"] for item in deps["ignored"])


def test_poetry_dev_groups_are_optional_not_required(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[tool.poetry.dependencies]
python = "^3.10"
scanpy = "^1.10"

[tool.poetry.group.dev.dependencies]
pytest = "^8"
ruff = "^0.6"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    deps = mine_dependencies(tmp_path)
    assert deps["python"] == ["scanpy"]
    assert deps["optional"]["python"]["poetry:dev"] == ["pytest", "ruff"]


def test_r_suggests_and_renv_lock_are_recorded_not_required(tmp_path):
    (tmp_path / "DESCRIPTION").write_text(
        """
Package: demo
Imports:
    Seurat,
    Matrix
Suggests:
    testthat,
    knitr
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "renv.lock").write_text(
        """
{
  "Packages": {
    "dplyr": {"Version": "1.1.4"},
    "ggplot2": {"Version": "3.5.1"}
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    deps = mine_dependencies(tmp_path)
    assert deps["r"] == ["Matrix", "Seurat"]
    assert deps["optional"]["r"]["DESCRIPTION:Suggests"] == ["knitr", "testthat"]
    assert deps["optional"]["r"]["renv.lock"] == ["dplyr", "ggplot2"]


def test_environment_yml_setup_cfg_and_description_system_requirements(tmp_path):
    (tmp_path / "environment.yml").write_text(
        """
name: demo
dependencies:
  - python=3.11
  - numpy
  - pip:
      - scanpy>=1.10
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "setup.cfg").write_text(
        """
[options]
install_requires =
    anndata>=0.10
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "DESCRIPTION").write_text(
        """
Package: demo
Imports:
    DESeq2
SystemRequirements: libxml2, hdf5
Remotes: user/custompkg
""".strip()
        + "\n",
        encoding="utf-8",
    )
    deps = mine_dependencies(tmp_path)
    assert "scanpy>=1.10" in deps["python"]
    assert "anndata>=0.10" in deps["python"]
    assert deps["conda_records"][0]["name"] == "numpy"
    assert deps["r_records"][0]["source"] == "Bioconductor_or_unknown"
    assert {"value": "libxml2", "source": "DESCRIPTION", "required": True, "install": "plan_only"} in deps["system_requirements"]
    assert deps["external_resources"][0]["name"] == "user/custompkg"
