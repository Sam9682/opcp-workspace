"""Forum models for topics and posts"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.security.types import EncryptedString


class Topic(Base):
    """Forum topic model
    
    Validates Requirements 3.1, 3.2:
    - Stores forum discussion topics
    - Associates topics with authors
    - Supports pinning and locking functionality
    """
    __tablename__ = "forum_topics"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # Topic information
    # Encrypted-at-rest when DB field encryption is enabled (detect-on-read).
    # Widened to Text because ciphertext is longer than the plaintext title.
    title: Mapped[str] = mapped_column(
        EncryptedString,
        nullable=False
    )
    
    # Author relationship
    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )
    
    # Topic status flags
    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    is_locked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # Relationships
    author: Mapped["User"] = relationship("User", back_populates="topics")
    posts: Mapped[list["Post"]] = relationship(
        "Post",
        back_populates="topic",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Topic(id={self.id}, title={self.title}, author_id={self.author_id})>"


class Post(Base):
    """Forum post model
    
    Validates Requirements 3.3:
    - Stores forum post content
    - Associates posts with topics and authors
    - Supports content moderation (hiding)
    """
    __tablename__ = "forum_posts"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # Topic relationship
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("forum_topics.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Author relationship
    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )
    
    # Post content
    # Encrypted-at-rest when DB field encryption is enabled (detect-on-read).
    content: Mapped[str] = mapped_column(
        EncryptedString,
        nullable=False
    )
    
    # Moderation flag
    is_hidden: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # Relationships
    topic: Mapped["Topic"] = relationship("Topic", back_populates="posts")
    author: Mapped["User"] = relationship("User", back_populates="posts")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_posts_topic', 'topic_id'),
        Index('idx_posts_author', 'author_id'),
    )
    
    def __repr__(self) -> str:
        return f"<Post(id={self.id}, topic_id={self.topic_id}, author_id={self.author_id})>"
