from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from main import enforce_intake_receipt  # noqa: E402
from services.intake import issue_receipt  # noqa: E402


def test_main_rejects_missing_intake_receipt(tmp_path, monkeypatch):
    monkeypatch.delenv("FOAMAGENT_DEV_ALLOW_UNSTAMPED", raising=False)
    req = tmp_path / "user_requirement.txt"
    req.write_text("水在管道中的稳态压降 geometry pipe diameter=0.001 length=0.1 inlet velocity=0.001 nu=1e-6 rho=1000 property source: literature_typical source reference: standard water properties at 20C user approved", encoding="utf-8")
    with pytest.raises(ValueError, match="INTAKE_RECEIPT_MISSING"):
        enforce_intake_receipt(str(req))


def test_main_accepts_matching_intake_receipt(tmp_path, monkeypatch):
    monkeypatch.delenv("FOAMAGENT_DEV_ALLOW_UNSTAMPED", raising=False)
    req = tmp_path / "user_requirement.txt"
    req.write_text("水在管道中的稳态压降 geometry pipe diameter=0.001 length=0.1 inlet velocity=0.001 nu=1e-6 rho=1000 property source: literature_typical source reference: standard water properties at 20C user approved", encoding="utf-8")
    issue_receipt(req)
    receipt = enforce_intake_receipt(str(req))
    assert receipt["target_preview"]["solver"] == "simpleFoam"


def test_dev_unstamped_override_is_explicitly_audited(tmp_path, monkeypatch):
    monkeypatch.setenv("FOAMAGENT_DEV_ALLOW_UNSTAMPED", "1")
    req = tmp_path / "user_requirement.txt"
    req.write_text("anything", encoding="utf-8")
    receipt = enforce_intake_receipt(str(req))
    assert receipt == {"unstamped_override": True}
