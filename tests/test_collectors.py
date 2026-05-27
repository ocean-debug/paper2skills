from __future__ import annotations

from pathlib import Path

from paper2skill.collectors.path_sanitizer import REDACTED_LOCAL_PATH, public_data
from paper2skill.collectors.source_manifest import build_source_manifest


def test_source_manifest_records_local_inputs():
    fixture = Path("tests/fixtures/toy_python_algorithm")
    manifest = build_source_manifest(
        paper=str(fixture / "paper.md"),
        repo=str(fixture),
        tutorials=[str(fixture / "examples" / "demo.py")],
    )
    assert manifest["paper"]["exists"] is True
    assert manifest["repo"]["exists"] is True
    assert manifest["tutorial"]["paths"][0]["exists"] is True
    assert manifest["options"]["install_policy"] == "ask"
    assert manifest["base_dir"] == REDACTED_LOCAL_PATH
    assert manifest["paper"]["path"] == "tests/fixtures/toy_python_algorithm/paper.md"
    assert manifest["repo"]["local_path"] == "tests/fixtures/toy_python_algorithm"
    assert manifest["tutorial"]["paths"][0]["path"] == "tests/fixtures/toy_python_algorithm/examples/demo.py"


def test_source_manifest_redacts_paths_outside_base(tmp_path: Path):
    paper = tmp_path / "paper.md"
    paper.write_text("# private paper\n", encoding="utf-8")
    manifest = build_source_manifest(
        paper=str(paper),
        repo=str(tmp_path),
        tutorials=[str(paper)],
        base_dir=Path("tests/fixtures/toy_python_algorithm"),
    )
    assert manifest["paper"]["path"] == REDACTED_LOCAL_PATH
    assert manifest["repo"]["local_path"] == REDACTED_LOCAL_PATH
    assert manifest["tutorial"]["paths"][0]["path"] == REDACTED_LOCAL_PATH


def test_public_data_redacts_embedded_absolute_paths_without_rewriting_urls(tmp_path: Path):
    data = {
        "/tmp/private/key.csv": "keyed value",
        "code": 'input_path = "/tmp/private/data.csv"',
        "quoted_spaces": 'read_csv("/tmp/private dir/input file.csv")',
        "file_url": "localpkg @ file:///tmp/private/localpkg",
        "win": r"C:\Private\alice\sample.tsv",
        "url": "https://example.org/files/data.csv",
        "nested": ["prefix /tmp/private/out.tsv suffix"],
    }
    public = public_data(data, tmp_path)
    assert "/tmp/private" not in str(public)
    assert r"C:\Private\alice" not in str(public)
    assert "key.csv" in public
    assert "data.csv" in public["code"]
    assert "/tmp/private dir" not in public["quoted_spaces"]
    assert "input file.csv" in public["quoted_spaces"]
    assert "file:///tmp/private" not in public["file_url"]
    assert public["file_url"] == "localpkg @ localpkg"
    assert public["win"] == "sample.tsv"
    assert public["url"] == "https://example.org/files/data.csv"
