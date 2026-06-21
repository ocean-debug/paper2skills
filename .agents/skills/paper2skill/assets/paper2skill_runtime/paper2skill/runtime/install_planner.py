from __future__ import annotations

import shlex
from typing import Any


def build_install_plan(report: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    missing_python = [pkg for pkg in report.get("python", {}).get("packages", []) if pkg.get("required") and not pkg.get("installed")]
    missing_r = [pkg for pkg in report.get("r", {}).get("packages", []) if pkg.get("required") and not pkg.get("installed")]
    missing_execs = [item for item in report.get("executables", []) if item.get("required") and not item.get("available")]
    python_specs = [pkg["name"] for pkg in missing_python]
    r_specs = [pkg["name"] for pkg in missing_r]
    env_name = spec.get("environment_name") or spec.get("name") or "paper2skill-generated-env"
    commands = {
        "current_env": [],
        "isolated_env": [],
        "conda_env": [],
        "manual": [],
    }
    if python_specs:
        quoted = " ".join(shlex.quote(spec) for spec in python_specs)
        commands["current_env"].append(f"python -m pip install {quoted}")
        commands["isolated_env"].extend(["python -m venv .venv", ". .venv/bin/activate", f"python -m pip install {quoted}"])
        commands["conda_env"].extend([f"conda create -y -n {env_name} python>=3.10 pip", f"conda run -n {env_name} python -m pip install {quoted}"])
        commands["manual"].append(f"python -m pip install {quoted}")
    if r_specs:
        r_vector = ", ".join(repr(pkg) for pkg in r_specs)
        r_command = f"Rscript -e \"install.packages(c({r_vector}), repos='https://cloud.r-project.org')\""
        commands["current_env"].append(r_command)
        if not commands["conda_env"]:
            commands["conda_env"].append(f"conda create -y -n {env_name} python>=3.10 pip r-base")
        elif "r-base" not in commands["conda_env"][0]:
            commands["conda_env"][0] = f"{commands['conda_env'][0]} r-base"
        commands["conda_env"].append(f"conda run -n {env_name} {r_command}")
        commands["manual"].append(r_command)
    return {
        "status": "blocked" if missing_python or missing_r or missing_execs else "ready",
        "install_policy": report.get("install_policy", "ask"),
        "effective_install_policy": report.get("effective_install_policy", "never"),
        "missing": {
            "python": missing_python,
            "r": missing_r,
            "executables": missing_execs,
        },
        "options": [
            {"id": "A", "label": "install into current environment", "strategy": "current_env", "commands": commands["current_env"]},
            {"id": "B", "label": "create isolated venv", "strategy": "isolated_env", "commands": commands["isolated_env"]},
            {"id": "C", "label": "create conda/mamba environment", "strategy": "conda_env", "commands": commands["conda_env"]},
            {"id": "D", "label": "manual install only", "strategy": "manual", "commands": commands["manual"]},
            {"id": "E", "label": "cancel", "strategy": "cancel", "commands": []},
        ],
        "source_priority": [
            "official docs/tutorial",
            "environment.yml / conda.yml",
            "requirements.txt / pyproject.toml / setup.py",
            "DESCRIPTION / renv.lock",
            "README",
            "fallback inference",
        ],
    }


def render_install_plan_markdown(plan: dict[str, Any]) -> str:
    lines = ["# Install Plan", ""]
    lines.append(f"Status: `{plan['status']}`")
    lines.append(f"Effective install policy: `{plan['effective_install_policy']}`")
    lines.append("")
    for option in plan["options"]:
        lines.append(f"## Option {option['id']}: {option['label']}")
        if option["commands"]:
            lines.append("```bash")
            lines.extend(option["commands"])
            lines.append("```")
        else:
            lines.append("No commands.")
        lines.append("")
    lines.append("Installation must not run unless the user explicitly passes `--confirm yes`.")
    return "\n".join(lines).rstrip() + "\n"
