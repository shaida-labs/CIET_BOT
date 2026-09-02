from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.models import AdminInvitation, AdminUser, HandoffTicket, IngestionJob, PasswordResetToken


def test_migration_history_has_a_single_head_and_required_revisions() -> None:
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "migrations"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["0006_handoff_tickets"]
    revisions = {revision.revision for revision in script.walk_revisions()}
    assert {
        "0001_initial",
        "0002_hardening",
        "0003_search_indexes",
        "0004_session_job_integrity",
        "0005_admin_account_recovery",
        "0006_handoff_tickets",
    } <= revisions


def test_model_schema_invariants_are_declared() -> None:
    assert "session_version" in AdminUser.__table__.c
    assert any(constraint.name == "uq_ingestion_jobs_document_id" for constraint in IngestionJob.__table__.constraints)
    assert PasswordResetToken.__table__.c.token_hash.unique
    assert AdminInvitation.__table__.c.token_hash.unique
    assert HandoffTicket.__table__.c.contact_consent.default.arg is False
