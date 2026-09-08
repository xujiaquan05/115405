# backend/tests/test_env_example.py

"""確保 .env.example 與程式實際讀取的環境變數保持同步。

為什麼需要自動檢查？
環境變數是隨功能一路長出來的（帳號鎖定、部署環境、各平台爬取開關……），
很容易加了程式卻忘了寫進範例檔。結果是新加入的人照著範例設定，
卻少了像 APP_ENV 這種「沒設就等於關掉安全防護」的變數，而且不會有任何錯誤訊息。

與其靠人記得，不如讓 CI 直接比對。
"""

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
APP_DIR = BACKEND / "app"
ENV_EXAMPLE = BACKEND / ".env.example"

# 這些由測試或工具自行設定，不需要出現在範例檔。
IGNORED = {"PBKDF2_ITERATIONS"}


def env_vars_used_in_code() -> set[str]:
    """掃描程式中所有讀取環境變數的地方。

    涵蓋兩種寫法：os.getenv("X") 以及 settings_service 的 _env_bool("X")。
    """
    pattern = re.compile(r'(?:getenv|_env_bool)\(\s*"([A-Z][A-Z0-9_]*)"')
    found: set[str] = set()

    for path in APP_DIR.rglob("*.py"):
        found |= set(pattern.findall(path.read_text(encoding="utf-8")))

    return found


def env_vars_in_example() -> set[str]:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    return set(re.findall(r"^([A-Z][A-Z0-9_]*)=", text, re.MULTILINE))


class TestEnvExample:
    def test_every_variable_used_in_code_is_documented(self):
        missing = env_vars_used_in_code() - env_vars_in_example() - IGNORED

        assert not missing, (
            "以下環境變數程式會讀取，但 .env.example 沒有列出："
            f"{sorted(missing)}"
        )

    def test_example_does_not_list_unused_variables(self):
        """反向檢查：範例檔留著已經沒人讀的變數，同樣會誤導設定的人。"""
        unused = env_vars_in_example() - env_vars_used_in_code() - IGNORED

        assert not unused, f"以下變數已無程式讀取，請從 .env.example 移除：{sorted(unused)}"

    def test_documents_the_security_critical_ones(self):
        """這幾個沒設定會靜默失去防護，範例檔一定要有。"""
        documented = env_vars_in_example()

        for key in ("APP_ENV", "JWT_SECRET", "ADMIN_PASSWORD"):
            assert key in documented


class TestRequirementsPinned:
    """所有相依都要鎖定版本，否則今天裝到 A 版、下個月裝到 B 版，
    問題無法重現，部署也不可預測。"""

    def test_every_requirement_has_a_version(self):
        for name in ("requirements.txt", "requirements-dev.txt"):
            lines = (BACKEND / name).read_text(encoding="utf-8-sig").splitlines()
            unpinned = [
                line.split("#")[0].strip()
                for line in lines
                if line.strip() and not line.strip().startswith("#") and "==" not in line
            ]

            assert not unpinned, f"{name} 有未鎖定版本的套件：{unpinned}"
