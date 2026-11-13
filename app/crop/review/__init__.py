"""Preview Review Workflow Package (Phase 1.2.2.6 & Phase 1.2.2.7).

Provides structured Pydantic review models, SQLite review session persistence,
decision state transition guards, immutable audit trails, and document status aggregation.
"""

from app.crop.review.db import (
    CURRENT_SCHEMA_VERSION,
    DEFAULT_DATA_DIR,
    DEFAULT_REVIEW_DB_PATH,
    backup_database,
    get_schema_version,
    init_database,
    restore_database,
)
from app.crop.review.enums import (
    DocumentReviewStatus,
    ReviewDecisionState,
    ReviewEventType,
)
from app.crop.review.models import (
    DocumentReviewSummary,
    PageReviewRecord,
    ReviewDecision,
    ReviewHistory,
    ReviewHistoryEntry,
    ReviewSession,
)
from app.crop.review.repository import (
    DuplicateSessionError,
    ReviewRepository,
    SQLiteReviewRepository,
)
from app.crop.review.workflow import (
    InvalidStateTransitionError,
    PageNotFoundError,
    PreviewReviewWorkflow,
    SessionNotFoundError,
)

__all__ = [
    # Enums
    "ReviewDecisionState",
    "DocumentReviewStatus",
    "ReviewEventType",
    # Models
    "ReviewDecision",
    "ReviewHistoryEntry",
    "ReviewHistory",
    "PageReviewRecord",
    "DocumentReviewSummary",
    "ReviewSession",
    # Workflow & Exceptions
    "PreviewReviewWorkflow",
    "InvalidStateTransitionError",
    "SessionNotFoundError",
    "PageNotFoundError",
    "DuplicateSessionError",
    # Persistence & Database
    "ReviewRepository",
    "SQLiteReviewRepository",
    "init_database",
    "get_schema_version",
    "backup_database",
    "restore_database",
    "CURRENT_SCHEMA_VERSION",
    "DEFAULT_DATA_DIR",
    "DEFAULT_REVIEW_DB_PATH",
]


