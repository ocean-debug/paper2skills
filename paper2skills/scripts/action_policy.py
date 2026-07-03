"""Shared release-action status policy for build gates."""

from __future__ import annotations

from typing import Any


CREATE_NEW = "create_new"
UPDATE_EXISTING = "update_existing"
REUSE_EXISTING = "reuse_existing"

VALID_ACTIONS = {CREATE_NEW, UPDATE_EXISTING, REUSE_EXISTING}


def normalize_action(discovery_decision: Any, fallback: Any = None) -> str:
    """Map Discovery decisions to release actions."""
    value = str(fallback or "").strip()
    if value in VALID_ACTIONS:
        return value
    decision = str(discovery_decision or "create").strip()
    if decision == "reuse":
        return REUSE_EXISTING
    if decision == "update":
        return UPDATE_EXISTING
    return CREATE_NEW


def expected_publish_statuses(action: Any) -> set[str]:
    if action == REUSE_EXISTING:
        return {"reuse_ready"}
    return {"publishable"}


def expected_install_statuses(action: Any) -> set[str]:
    if action == REUSE_EXISTING:
        return {"not_applicable"}
    return {"pass"}


def is_publish_status_acceptable(action: Any, status: Any) -> bool:
    return str(status) in expected_publish_statuses(action)


def is_install_status_acceptable(action: Any, status: Any) -> bool:
    return str(status) in expected_install_statuses(action)
