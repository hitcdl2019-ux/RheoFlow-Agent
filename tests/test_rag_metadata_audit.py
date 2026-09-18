from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "rag_audit", ROOT / "scripts" / "audit_rag_metadata.py"
)
rag_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rag_audit)


class Document:
    def __init__(self, metadata):
        self.metadata = metadata


def test_audit_reports_missing_and_cross_channel_metadata():
    valid = Document({
        "channel": "v10-foundation", "version": "v10", "distribution": "foundation",
        "case_name": "cavity", "case_domain": "incompressible",
        "case_category": "cavity", "case_solver": "icoFoam",
    })
    polluted = Document({
        "channel": "v9-rheotool", "version": "v9", "distribution": "foundation+rheotool",
        "case_name": "bad", "case_domain": "rheology", "case_category": "bad",
        "case_solver": "rheoFoam",
    })
    result = rag_audit.audit_documents(
        [valid, polluted], "v10-foundation", "v10", "openfoam_tutorials_structure"
    )
    assert result["channel_version_mismatches"] == 1


def test_audit_detects_content_version_pollution():
    document = Document({
        "channel": "v10-foundation", "version": "v10", "distribution": "foundation",
        "command": "blockMesh", "help_text": "Using: OpenFOAM-9",
    })
    result = rag_audit.audit_documents(
        [document], "v10-foundation", "v10", "openfoam_command_help"
    )
    assert result["content_version_mismatches"] == 1
