from __future__ import annotations

from paper2skill.evaluation.compare_adapter_behavior import compare_adapter_behavior
from paper2skill.evaluation.evaluate_case import compare_evidence_expectations


def test_adapter_behavior_candidate_blocks_non_demo_execution():
    gold = {
        "expected_adapter_type": "python_api",
        "expected_initial_status": "candidate",
        "non_demo_run": {"expected_behavior": "blocked_until_reviewed"},
    }
    generated = {
        "adapter_spec": {"adapter_type": "python_api", "status": "candidate"},
        "algorithm_contract": {"environment_contract": {"install_policy_default": "ask", "auto_install_requires_confirmation": True}},
    }

    result = compare_adapter_behavior(gold, generated)

    assert result["metrics"]["adapter_type_accuracy"] == 1.0
    assert result["metrics"]["adapter_status_accuracy"] == 1.0
    assert result["metrics"]["non_demo_block_correctness"] == 1.0
    assert result["metrics"]["install_policy_compliance"] == 1.0


def test_adapter_behavior_accepts_r_package_alias():
    gold = {"expected_adapter_type": "r_script_or_r_package", "expected_initial_status": "candidate"}
    generated = {
        "adapter_spec": {"adapter_type": "r_script", "status": "candidate"},
        "algorithm_contract": {"environment_contract": {"install_policy_default": "ask"}},
    }

    result = compare_adapter_behavior(gold, generated)

    assert result["metrics"]["adapter_type_accuracy"] == 1.0


def test_evidence_expectations_use_full_generated_bundle_not_only_graph():
    gold = {
        "high_priority_sources": ["repo_readme", "setup_or_requirements"],
        "required_claims_with_evidence": ["condition labels required", "Rscript CLI positional arguments"],
    }
    generated = {
        "evidence_graph": {},
        "repo_evidence": {"docs": ["README.md"], "dependency_files": ["requirements.txt"], "cli_commands": [{"positional_arguments": [{"index": 1}]}]},
        "bio_contract": {"bio_contract": {"metadata_requirements": {"condition_key": {"value": "condition"}}}},
    }

    result = compare_evidence_expectations(gold, generated)

    assert result["metrics"]["source_recall"] == 1.0
    assert result["metrics"]["claim_recall"] == 1.0
