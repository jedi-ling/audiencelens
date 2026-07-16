import json

import pytest

from tools.benchmark_scaffold import init_case


def test_init_case_creates_isolated_templates_and_manifest(tmp_path):
    result = init_case(str(tmp_path), "studio-001", "Test Game")
    case_dir = tmp_path / "studio-001"
    assert result["case_id"] == "studio-001"
    assert (case_dir / "reference.json").exists()
    assert (case_dir / "audiencelens.json").exists()
    assert (case_dir / "single-prompt.json").exists()
    assert (case_dir / "expert-quick.json").exists()
    reference = json.loads((case_dir / "reference.json").read_text(encoding="utf-8"))
    assert reference["collected_after_candidates_frozen"] is False
    manifest = json.loads((tmp_path / "benchmark-suite.json").read_text(encoding="utf-8"))
    assert manifest["cases"][0]["id"] == "studio-001"


def test_init_case_appends_without_rewriting_previous_case(tmp_path):
    init_case(str(tmp_path), "studio-001")
    first = (tmp_path / "studio-001" / "reference.json").read_text(encoding="utf-8")
    init_case(str(tmp_path), "studio-002")
    assert (tmp_path / "studio-001" / "reference.json").read_text(encoding="utf-8") == first
    manifest = json.loads((tmp_path / "benchmark-suite.json").read_text(encoding="utf-8"))
    assert [row["id"] for row in manifest["cases"]] == ["studio-001", "studio-002"]


def test_init_case_refuses_overwrite_and_path_traversal(tmp_path):
    init_case(str(tmp_path), "studio-001")
    with pytest.raises(FileExistsError):
        init_case(str(tmp_path), "studio-001")
    with pytest.raises(ValueError):
        init_case(str(tmp_path), "../escape")
