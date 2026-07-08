from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

from app.core.database import Base


class Platform(Base):
    __tablename__ = "platforms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100))
    base_url = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    boards = relationship("Board", back_populates="platform")
    articles = relationship("Article", back_populates="platform")


class Board(Base):
    __tablename__ = "boards"

    id = Column(Integer, primary_key=True, index=True)
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=False)

    name = Column(String(100), nullable=False)
    display_name = Column(String(100))
    url = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    platform = relationship("Platform", back_populates="boards")
    articles = relationship("Article", back_populates="board")


class Author(Base):
    __tablename__ = "authors"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())

    articles = relationship("Article", back_populates="author")


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)

    unique_id = Column(String(64), unique=True, nullable=False)

    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=False)
    board_id = Column(Integer, ForeignKey("boards.id"))
    author_id = Column(Integer, ForeignKey("authors.id"))

    title = Column(Text, nullable=False)
    content = Column(Text)
    url = Column(Text)

    push_count = Column(Integer, default=0)

    # Note:
    # sentiment do Gemini chấm theo batch sau khi crawl:
    # positive / neutral / negative.
    # NULL = chưa chấm; khi đó các query sẽ fallback về push_count.
    sentiment = Column(String(20), index=True)

    published_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    platform = relationship("Platform", back_populates="articles")
    board = relationship("Board", back_populates="articles")
    author = relationship("Author", back_populates="articles")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)

    keyword = Column(String(255), nullable=False)
    analysis_type = Column(String(50), nullable=False)

    days = Column(Integer, nullable=False, default=30)

    result_json = Column(JSON, nullable=False)

    expired_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class CrawlLog(Base):
    __tablename__ = "crawl_logs"

    id = Column(Integer, primary_key=True, index=True)

    platform_id = Column(Integer, ForeignKey("platforms.id"))
    board_id = Column(Integer, ForeignKey("boards.id"))

    status = Column(String(50), nullable=False)

    new_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)

    error_message = Column(Text)

    started_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime)

    platform = relationship("Platform")
    board = relationship("Board")