from __future__ import annotations

from paper2skill.miners.dependency_miner import mine_dependencies, parse_optional_pyproject_dependencies


def test_dependency_miner_reads_python_and_r_files():
    py_deps = mine_dependencies("tests/fixtures/toy_python_algorithm")
    r_deps = mine_dependencies("tests/fixtures/toy_r_algorithm", ["tests/fixtures/toy_r_algorithm/examples/demo.R"])
    assert "pyproject.toml" in " ".join(py_deps["dependency_files"])
    assert "DESCRIPTION" in " ".join(r_deps["dependency_files"])
    assert "stats" in r_deps["r"]


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
