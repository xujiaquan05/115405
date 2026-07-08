# backend/app/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os


# 載入 .env 檔案中的環境變數
load_dotenv()


# 從 .env 讀取 DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")


# 如果 DATABASE_URL 不存在就明確報錯，
# 方便發現 .env 設定不正確。
if DATABASE_URL is None:
    raise ValueError("DATABASE_URL is not set in .env file")


# engine 是連線 PostgreSQL 的主要物件
engine = create_engine(DATABASE_URL)


# SessionLocal 用來在每次 API 呼叫時建立 database session
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# Base 供 models 繼承使用
Base = declarative_base()


def get_db():
    """
    提供 database session 給 FastAPI 的相依函式。

    FastAPI 會在看到以下寫法時呼叫此函式：
    db: Session = Depends(get_db)
    """

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
