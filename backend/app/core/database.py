# backend/app/database.py

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

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


def close_transaction(db) -> None:
    """結束目前交易，把連線還給連線池。

    給「接下來要做很久、而且完全不碰資料庫的事」使用（例如爬一個看板，
    可能要好幾分鐘）。SQLAlchemy 在第一次查詢時就會開啟交易，
    而且要等到 commit / rollback 才結束——中間就算只是讀取也一樣。

    不主動結束的話，在 PostgreSQL 會看到 idle in transaction：
    一條連線被佔著不放，autovacuum 也無法回收那段期間的舊資料列
    （實際量測過一次爬取讓交易開了 18 分鐘）。
    """
    db.commit()


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
