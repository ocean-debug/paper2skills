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
    assert deps["python"] == ["numpy", "optional-demo"]
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


def test_description_bioconductor_metadata_multiline_fields_and_versions(tmp_path):
    (tmp_path / "DESCRIPTION").write_text(
        """
Package: demo
Imports:
    DESeq2 (>= 1.40),
    SummarizedExperiment,
    ggplot2
LinkingTo:
    Rcpp
biocViews:
    RNASeq,
    DifferentialExpression
SystemRequirements:
    libxml2,
    hdf5
Enhances:
    BiocStyle
""".strip()
        + "\n",
        encoding="utf-8",
    )

    deps = mine_dependencies(tmp_path)

    assert deps["r"] == ["DESeq2", "Rcpp", "SummarizedExperiment", "ggplot2"]
    assert deps["optional"]["r"]["DESCRIPTION:Enhances"] == ["BiocStyle"]
    deseq = next(record for record in deps["r_records"] if record["name"] == "DESeq2")
    assert deseq["version_spec"] == ">= 1.40"
    assert deseq["source"] == "Bioconductor_or_unknown"
    assert "RNASeq" in deps["bioconductor"]["biocViews"]
    assert {"value": "hdf5", "source": "DESCRIPTION", "required": True, "install": "plan_only"} in deps["system_requirements"]


def test_rscript_cli_scripts_record_rscript_executable(tmp_path):
    (tmp_path / "run_method.R").write_text(
        """
args <- commandArgs(trailingOnly = TRUE)
print(args)
""".strip()
        + "\n",
        encoding="utf-8",
    )

    deps = mine_dependencies(tmp_path)

    assert deps["executables"] == [{"name": "Rscript", "source": "run_method.R", "required": True, "category": "runtime"}]


def test_namespace_imports_are_required_r_dependencies(tmp_path):
    (tmp_path / "NAMESPACE").write_text(
        """
import(dplyr)
importFrom(SummarizedExperiment, assay)
importFrom(stats, p.adjust)
""".strip()
        + "\n",
        encoding="utf-8",
    )

    deps = mine_dependencies(tmp_path)

    assert deps["r"] == ["SummarizedExperiment", "dplyr"]
    assert {record["evidence"] for record in deps["r_records"]} == {"NAMESPACE:import", "NAMESPACE:importFrom"}


def test_self_package_and_python_import_fallback_are_required_dependencies(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "cell-gears"
version = "0.1.0"
dependencies = []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    package = tmp_path / "src" / "gears"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "model.py").write_text("import torch\nimport anndata as ad\nimport json\nfrom . import local\n", encoding="utf-8")

    deps = mine_dependencies(tmp_path)

    names = {record["name"] for record in deps["python_records"]}
    assert {"cell-gears", "torch", "anndata"} <= names
    assert "json" not in names


def test_markdown_r_dependencies_are_mined_from_readme_code_blocks(tmp_path):
    (tmp_path / "README.md").write_text(
        """
# Usage

```r
library(DESeq2)
res <- apeglm::apeglm(...)
stats::p.adjust(res$pvalue)
```
""".strip()
        + "\n",
        encoding="utf-8",
    )

    deps = mine_dependencies(tmp_path)

    assert "DESeq2" in deps["r"]
    assert "apeglm" in deps["r"]
    assert "stats" not in deps["r"]


def test_install_commands_are_recorded_as_optional_dependency_hints(tmp_path):
    (tmp_path / "README.md").write_text(
        """
# Install

```bash
pip install faiss-gpu scgen[tutorials]
```

```r
BiocManager::install(c("DESeq2", "apeglm"))
install.packages("ggplot2")
```
""".strip()
        + "\n",
        encoding="utf-8",
    )

    deps = mine_dependencies(tmp_path)

    python_names = {record["name"]: record for record in deps["python_records"]}
    r_names = {record["name"]: record for record in deps["r_records"]}
    assert python_names["faiss-gpu"]["required"] is False
    assert python_names["scgen"]["required"] is False
    assert r_names["DESeq2"]["required"] is False
    assert r_names["apeglm"]["source"] == "Bioconductor_or_unknown"
    assert r_names["ggplot2"]["required"] is False


def test_documentation_dependency_hints_are_optional_python_records(tmp_path):
    (tmp_path / "README.md").write_text(
        """
# Acceleration

This method can use PyTorch and FAISS-GPU. AnnData input is supported.
""".strip()
        + "\n",
        encoding="utf-8",
    )

    deps = mine_dependencies(tmp_path)

    records = {record["name"]: record for record in deps["python_records"]}
    assert records["torch"]["required"] is False
    assert records["faiss-gpu"]["required"] is False
    assert records["anndata"]["required"] is False


def test_r_script_qualified_calls_and_apeglm_type_are_dependencies(tmp_path):
    (tmp_path / "DTEG.R").write_text(
        """
library(data.table)
dds <- DESeq2::DESeq(dds)
res <- lfcShrink(dds, coef = 2, type = "apeglm")
stats::p.adjust(res$pvalue)
""".strip()
        + "\n",
        encoding="utf-8",
    )

    deps = mine_dependencies(tmp_path)

    assert "DESeq2" in deps["r"]
    assert "apeglm" in deps["r"]
    assert "data.table" in deps["r"]
    assert "stats" not in deps["r"]
