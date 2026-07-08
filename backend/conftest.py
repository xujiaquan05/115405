# backend/conftest.py
#
# Note:
# File này giúp pytest tự thêm thư mục backend/ vào sys.path
# (để import được package app), và ép DATABASE_URL về SQLite in-memory
# khi chạy test — test không bao giờ được đụng vào database thật.

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
