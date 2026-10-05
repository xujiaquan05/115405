# backend/tests/conftest.py

"""測試共用設定。

正式環境的 PBKDF2 迭代次數是 600,000（OWASP 建議值），每次雜湊約需
數百毫秒。測試會建立大量帳號，若照正式值跑，整個測試套件會慢上好幾倍，
因此在匯入應用程式之前先把迭代次數調低。

這裡只影響測試；正式執行時環境變數未設定，仍使用 600,000。
"""

import os

os.environ.setdefault("PBKDF2_ITERATIONS", "1000")

# TestClient 透過 http://testserver 呼叫，是明文連線，不會保存 Secure cookie。
# 若讓這裡跟著開發者 .env 的 APP_ENV 走，誰把自己機器改成 production，
# 整套 cookie 相關測試就會在他電腦上紅掉——那是環境差異，不是程式壞了。
# 測試固定用 development；Secure 旗標本身另有 test_deployment_hardening 驗證規則。
# load_dotenv 預設不覆蓋既有環境變數，所以這行先設就贏。
os.environ.setdefault("APP_ENV", "development")
