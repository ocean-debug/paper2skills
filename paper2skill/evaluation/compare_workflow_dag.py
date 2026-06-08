from __future__ import annotations

from collections import Counter
from typing import Any

from paper2skill.evaluation.load_gold import evaluation_result, finish_result, normalize_token


def compare_workflow_dag(gold: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    result = evaluation_result("workflow_dag")
    generated_dag = generated.get("workflow_dag") or {}
    gold_nodes = gold.get("nodes") or []
    generated_nodes = generated_dag.get("nodes") or []
    gold_types = [canonical_step_type(node.get("type")) for node in gold_nodes if node.get("type")]
    generated_types = [canonical_step_type(node.get("type")) for node in generated_nodes if node.get("type")]
    node_recall = multiset_recall(gold_types, generated_types)
    missing_types = missing_multiset(gold_types, generated_types)
    result["missing_items"].extend(f"workflow_node_type:{item}" for item in missing_types)

    gold_edges = parse_gold_edges(gold)
    generated_edges = parse_generated_edges(generated_dag)
    edge_recall = edge_type_recall(gold_edges, generated_edges, gold_nodes, generated_nodes)
    object_state_accuracy = compare_object_states(gold_nodes, generated_nodes)
    return finish_result(
        result,
        {
            "workflow_node_recall": node_recall,
            "workflow_edge_recall": edge_recall,
            "step_type_accuracy": node_recall,
            "object_state_accuracy": object_state_accuracy,
        },
    )


def multiset_recall(expected: list[str], observed: list[str]) -> float:
    if not expected:
        return 1.0
    expected_counts = Counter(expected)
    observed_counts = Counter(observed)
    matched = sum(min(count, observed_counts[item]) for item, count in expected_counts.items())
    return matched / len(expected)


def missing_multiset(expected: list[str], observed: list[str]) -> list[str]:
    expected_counts = Counter(expected)
    observed_counts = Counter(observed)
    missing = []
    for item, count in expected_counts.items():
        missing.extend([item] * max(0, count - observed_counts[item]))
    return sorted(missing)


def parse_gold_edges(gold: dict[str, Any]) -> list[tuple[str, str]]:
    result = []
    for item in gold.get("edges") or []:
        if isinstance(item, str) and "->" in item:
            left, right = item.split("->", 1)
            result.append((left.strip(), right.strip()))
        elif isinstance(item, dict):
            left = item.get("from") or item.get("source")
            right = item.get("to") or item.get("target")
            if left and right:
                result.append((str(left), str(right)))
    return result


def parse_generated_edges(dag: dict[str, Any]) -> list[tuple[str, str]]:
    result = []
    for item in dag.get("edges") or []:
        left = item.get("from") or item.get("source")
        right = item.get("to") or item.get("target")
        if left and right:
            result.append((str(left), str(right)))
    return result


def edge_type_recall(gold_edges: list[tuple[str, str]], generated_edges: list[tuple[str, str]], gold_nodes: list[dict[str, Any]], generated_nodes: list[dict[str, Any]]) -> float:
    if not gold_edges:
        return 1.0
    gold_type_by_id = {str(node.get("id") or node.get("step_id")): canonical_step_type(node.get("type")) for node in gold_nodes}
    generated_type_by_id = {str(node.get("id") or node.get("step_id")): canonical_step_type(node.get("type")) for node in generated_nodes}
    expected = {(gold_type_by_id.get(left, left), gold_type_by_id.get(right, right)) for left, right in gold_edges}
    observed = {(generated_type_by_id.get(left, left), generated_type_by_id.get(right, right)) for left, right in generated_edges}
    if not observed and generated_nodes:
        observed = set(zip([canonical_step_type(node.get("type")) for node in generated_nodes], [canonical_step_type(node.get("type")) for node in generated_nodes[1:]]))
    return len(expected & observed) / len(expected)


def compare_object_states(gold_nodes: list[dict[str, Any]], generated_nodes: list[dict[str, Any]]) -> float:
    expected = []
    for node in gold_nodes:
        for key in ["expected_state_after", "expected_state"]:
            state = node.get(key)
            if isinstance(state, dict):
                expected.extend((state_key, state_value) for state_key, state_value in state.items())
    if not expected:
        return 1.0
    observed = []
    for node in generated_nodes:
        for state in (node.get("object_state_after") or {}).values():
            if isinstance(state, dict):
                observed.extend((key, value) for key, value in state.items())
    observed_norm = {(normalize_token(key), normalize_token(value)) for key, value in observed}
    matched = sum(1 for key, value in expected if (normalize_token(key), normalize_token(value)) in observed_norm)
    return matched / len(expected)


def canonical_step_type(value: Any) -> str:
    token = normalize_token(value)
    aliases = {
        "model_training": "model_training_or_scoring",
        "model_training_or_embedding": "model_training_or_scoring",
        "prediction": "model_training_or_scoring",
        "differential_expression": "statistical_analysis",
        "visualization": "output_extraction",
        "save_output": "output_extraction",
        "filtering": "input_validation",
        "qc": "input_validation",
    }
    return aliases.get(token, token)
