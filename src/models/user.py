"""User model for authentication and authorization."""

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import BaseModel

if TYPE_CHECKING:
    from src.models.audit import AuditLog
    from src.models.bid import BidResponse
    from src.models.document import ProcurementDocument
    from src.models.procurement_tender import ProcurementTender


class UserRole(str, Enum):
    """User role enumeration."""

    BID_MANAGER = "bid_manager"
    ADMIN = "admin"


class User(BaseModel):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    # Core fields
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole),
        nullable=False,
        default=UserRole.BID_MANAGER,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    # Relationships
    procurement_documents: Mapped[list["ProcurementDocument"]] = relationship(
        "ProcurementDocument",
        back_populates="uploaded_by_user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    bid_responses_created: Mapped[list["BidResponse"]] = relationship(
        "BidResponse",
        foreign_keys="BidResponse.created_by",
        back_populates="creator",
        cascade="all, delete-orphan",
        lazy="select",
    )

    bid_responses_reviewed: Mapped[list["BidResponse"]] = relationship(
        "BidResponse",
        foreign_keys="BidResponse.reviewed_by",
        back_populates="reviewer",
        cascade="all, delete-orphan",
        lazy="select",
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    tenders: Mapped[list["ProcurementTender"]] = relationship(
        "ProcurementTender",
        back_populates="creator",
        lazy="select",
    )

    bid_responses_created: Mapped[list["BidResponse"]] = relationship(
        "BidResponse",
        foreign_keys="BidResponse.created_by",
        back_populates="creator",
        lazy="select",
    )

    bid_responses_reviewed: Mapped[list["BidResponse"]] = relationship(
        "BidResponse",
        foreign_keys="BidResponse.reviewed_by",
        back_populates="reviewer",
        lazy="select",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<User(id={self.id}, email={self.email}, role={self.role.value})>"

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == UserRole.ADMIN

    @property
    def is_bid_manager(self) -> bool:
        """Check if user has bid manager role."""
        return self.role == UserRole.BID_MANAGER
