from __future__ import annotations

from paper2skill.evaluation.compare_dependencies import compare_dependencies


def test_dependency_recall_precision_and_language_metrics():
    gold = {
        "language": {"python": True, "r": False},
        "python_required": ["scanpy", "anndata"],
        "python_optional": ["torch"],
    }
    generated = {
        "environment_spec": {
            "python": {"packages": [{"name": "scanpy", "spec": "scanpy>=1.10"}]},
            "r": {"required": False, "packages": []},
            "optional_dependencies": {"python": {"gpu": ["torch"]}, "r": {}},
        }
    }

    result = compare_dependencies(gold, generated)

    assert result["metrics"]["required_dependency_recall"] == 0.5
    assert result["metrics"]["optional_dependency_recall"] == 1.0
    assert result["metrics"]["dependency_recall"] == 2 / 3
    assert result["metrics"]["language_detection_accuracy"] == 1.0
    assert "required:anndata" in result["missing_items"]


def test_dependency_recall_includes_executable_requirements():
    gold = {"language": {"python": False, "r": True}, "r_required": ["DESeq2"], "system_or_cli": ["Rscript"]}
    generated = {
        "environment_spec": {
            "r": {"required": True, "packages": [{"name": "DESeq2"}]},
            "executables": [{"name": "Rscript", "required": True}],
        }
    }

    result = compare_dependencies(gold, generated)

    assert result["metrics"]["required_dependency_recall"] == 1.0


def test_dependency_compare_counts_required_false_packages_as_observed_optional():
    gold = {"python_required": ["cell-gears"], "r_optional_or_object_support": ["stats"]}
    generated = {
        "environment_spec": {
            "python": {"packages": [{"name": "cell-gears", "spec": "cell-gears", "required": False}]},
            "r": {"required": False, "packages": []},
            "optional_dependencies": {},
            "optional": {},
        }
    }

    result = compare_dependencies(gold, generated)

    assert result["metrics"]["required_dependency_recall"] == 1.0
    assert result["metrics"]["optional_dependency_recall"] == 1.0
