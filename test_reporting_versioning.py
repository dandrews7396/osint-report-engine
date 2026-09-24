from pathlib import Path

import pytest

from reporting.versioning import (
    ReportIntegrityError,
    approval_signoff,
    build_versioned_output_path,
    sha256_file,
    verify_file_sha256,
)


class CapturingHTML:
    rendered = []

    def __init__(self, *, string, base_url):
        self.string = string
        self.base_url = base_url
        self.rendered.append(string)

    def write_pdf(self, output_path):
        Path(output_path).write_bytes(b"rendered-pdf")


def test_versioned_path_is_deterministic_and_status_specific():
    path = build_versioned_output_path("reports", "CASE/ 12", 3, status="draft")

    assert path == Path("reports/CASE_12_v0003_draft.pdf")


def test_hash_verification_raises_for_tampered_file():
    report = Path("reporting-hash-test-artifact.pdf")
    try:
        report.write_bytes(b"original")
        digest = sha256_file(report)

        assert verify_file_sha256(report, digest) is True
        report.write_bytes(b"tampered")

        with pytest.raises(ReportIntegrityError, match="SHA-256 mismatch"):
            verify_file_sha256(report, digest)
    finally:
        report.unlink(missing_ok=True)


def test_final_signoff_requires_explicit_approver_and_date():
    signoff = approval_signoff(
        {"approved_by": "M. Approver", "approved_at": "2026-09-22", "title": "Director"}
    )

    assert signoff == {
        "approved_by": "M. Approver",
        "approved_at": "2026-09-22",
        "title": "Director",
        "signature": "",
    }

    with pytest.raises(ValueError, match="approved_by"):
        approval_signoff({"approved_at": "2026-09-22"})


def test_generator_renders_final_approval_and_draft_watermark(monkeypatch):
    import reporting.generator as generator

    monkeypatch.setattr(generator, "HTML", CapturingHTML)
    monkeypatch.setattr(generator.db, "get_case_subjects", lambda _case_id: [])
    monkeypatch.setattr(generator.db, "get_investigators", lambda: [])
    output_directory = Path("reporting-test-artifacts")
    final_path = output_directory / "final.pdf"
    draft_path = output_directory / "draft.pdf"
    case = {
        "id": 1,
        "case_ref": "CASE-42",
        "case_name": "Example",
        "case_type": "Custom OSINT Investigation",
    }
    try:
        generator.generate_report(
            case, {"name": "Client"}, {"name": "Firm"}, [], final_path,
            include_risk_graphs=False, status="final", case_start_date="2026-01-01",
            approval_data={"approved_by": "A. Approver", "approved_at": "2026-01-31"},
        )
        final_html = CapturingHTML.rendered[-1]
        assert "2026-01-01" in final_html
        assert "2026-01-31" in final_html
        assert "A. Approver" in final_html

        generator.generate_report(
            case, {"name": "Client"}, {"name": "Firm"}, [], draft_path,
            include_risk_graphs=False, status="draft",
        )
        assert 'content: "DRAFT"' in CapturingHTML.rendered[-1]
    finally:
        final_path.unlink(missing_ok=True)
        draft_path.unlink(missing_ok=True)
        output_directory.rmdir() if output_directory.exists() else None
