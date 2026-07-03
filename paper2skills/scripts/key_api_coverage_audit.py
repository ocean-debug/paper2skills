"""Audit explicit key API coverage against parsed grounding artifacts."""

from __future__ import annotations

import re
from typing import Any

from common import as_list, now_utc
from constants import SCHEMA_VERSION


def normalize_symbol(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\([^)]*\)$", "", text)
    return re.sub(r"[^A-Za-z0-9_.]+", "", text).lower()


def symbol_variants(value: Any) -> set[str]:
    normalized = normalize_symbol(value)
    if not normalized:
        return set()
    parts = normalized.split(".")
    variants = {normalized, parts[-1]}
    if len(parts) >= 2:
        variants.add(".".join(parts[-2:]))
    return variants


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    symbol: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if symbol:
        item["symbol"] = symbol
    findings.append(item)


def grounded_symbols(api_grounding: dict[str, Any], interface_grounding: dict[str, Any]) -> set[str]:
    symbols: set[str] = set()
    for candidate in api_grounding.get("api_candidates", []):
        symbols.update(symbol_variants(candidate.get("symbol")))
    for interface in interface_grounding.get("interfaces", []):
        for key in ("qualname", "name"):
            symbols.update(symbol_variants(interface.get(key)))
        signature = str(interface.get("signature") or "")
        symbols.update(symbol_variants(signature.split("(", 1)[0]))
    return {symbol for symbol in symbols if symbol}


def requested_key_apis(request: dict[str, Any]) -> list[dict[str, Any]]:
    keys: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in as_list(request.get("api_names")):
        normalized = normalize_symbol(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        keys.append(
            {
                "api_name": str(value),
                "normalized": normalized,
                "variants": sorted(symbol_variants(value)),
            }
        )
    return keys


def build_key_api_coverage_audit(
    request: dict[str, Any],
    api_grounding: dict[str, Any],
    interface_grounding: dict[str, Any],
) -> dict[str, Any]:
    """Return a deterministic coverage audit for explicitly requested APIs."""
    findings: list[dict[str, Any]] = []
    keys = requested_key_apis(request)
    grounded = grounded_symbols(api_grounding, interface_grounding)
    records: list[dict[str, Any]] = []

    for key in keys:
        variants = set(key["variants"])
        matched = sorted(variants.intersection(grounded))
        is_grounded = bool(matched)
        records.append({**key, "grounded": is_grounded, "matched_symbols": matched})
        if not is_grounded:
            add_finding(
                findings,
                "error",
                "requested_key_api_not_grounded",
                "Explicitly requested key API was not found in parsed API or interface grounding.",
                symbol=key["api_name"],
            )

    if not keys:
        add_finding(
            findings,
            "info",
            "no_requested_key_apis",
            "No explicit api_names were provided; key API coverage is informational for this run.",
        )

    grounded_count = sum(1 for record in records if record["grounded"])
    required_count = len(records)
    coverage_ratio = round(grounded_count / required_count, 3) if required_count else 1.0
    has_errors = any(finding["severity"] == "error" for finding in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "fail" if has_errors else "pass",
        "minimum_coverage_ratio": 1.0,
        "coverage_ratio": coverage_ratio,
        "required_key_api_count": required_count,
        "grounded_key_api_count": grounded_count,
        "grounded_symbol_count": len(grounded),
        "records": records,
        "findings": findings,
        "policy": [
            "Explicit build-request api_names are key APIs and must be grounded exactly by parsed API or interface evidence.",
            "Symbol matching uses normalized exact symbol variants, not arbitrary substring matching.",
            "Key API coverage is static grounding only and does not imply execution verification.",
        ],
    }
