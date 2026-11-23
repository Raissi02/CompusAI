"""Add document chunks for passage-level retrieval."""

from alembic import op

revision = "0002_document_chunks"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.models import DocumentChunk

    DocumentChunk.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    from app.models import DocumentChunk

    DocumentChunk.__table__.drop(bind=op.get_bind(), checkfirst=True)
