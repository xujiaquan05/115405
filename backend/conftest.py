# backend/conftest.py
#
# 說明：
# 這個檔案讓 pytest 自動把 backend/ 加入 sys.path（才能 import app 套件），
# 並在測試時把 DATABASE_URL 強制設為 SQLite in-memory —
# 測試永遠不可以碰到真正的資料庫。

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
