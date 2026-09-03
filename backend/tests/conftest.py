# backend/tests/conftest.py

"""測試共用設定。

正式環境的 PBKDF2 迭代次數是 600,000（OWASP 建議值），每次雜湊約需
數百毫秒。測試會建立大量帳號，若照正式值跑，整個測試套件會慢上好幾倍，
因此在匯入應用程式之前先把迭代次數調低。

這裡只影響測試；正式執行時環境變數未設定，仍使用 600,000。
"""

import os

os.environ.setdefault("PBKDF2_ITERATIONS", "1000")
