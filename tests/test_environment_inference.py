from __future__ import annotations

from paper2skill.inference.infer_environment import infer_environment_spec


def test_environment_spec_keeps_optional_install_hints_without_making_them_required():
    deps = {
        "python_records": [
            {"spec": "scanpy", "name": "scanpy", "required": True, "category": "runtime"},
            {"spec": "faiss-gpu", "name": "faiss-gpu", "required": False, "category": "install_hint"},
            {"spec": "demo-tool", "name": "demo-tool", "required": False, "category": "self_package"},
        ],
        "r_records": [],
    }

    spec = infer_environment_spec(deps, "python")

    packages = {item["name"]: item for item in spec["python"]["packages"]}
    assert packages["scanpy"]["required"] is True
    assert packages["faiss-gpu"]["required"] is False
    assert packages["demo-tool"]["required"] is False
