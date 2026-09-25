# backend/tests/test_startup_schema_consistency.py

"""startup 的手動 ALTER TABLE 不可以加回模型已經沒有的欄位。

實際發生過的問題：
遷移 e4f70c2a9d18 刪掉了 `analysis_results.user_id`（個人分析歷史搬走後它就沒人讀寫了），
`alembic upgrade head` 也確實刪成功了。但 startup 裡有一行
`ALTER TABLE analysis_results ADD COLUMN IF NOT EXISTS user_id INTEGER`，
於是後端下一次啟動就把它加了回來——遷移看起來成功，重啟一次就復原。

這類錯誤不會有任何徵兆：沒有例外、沒有警告，只有欄位默默復活。
因此改用測試把「同一件事有兩個來源」這個結構性問題擋下來。
"""

import re
from pathlib import Path

import pytest

from app.core.database import Base
from app.models import database_models  # noqa: F401  匯入以註冊所有資料表

STARTUP_SOURCE = Path(__file__).resolve().parent.parent / "app" / "core" / "startup.py"

ADD_COLUMN = re.compile(
    r"ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)",
    re.IGNORECASE,
)

CREATE_INDEX = re.compile(
    r"CREATE\s+INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?\w+\s+ON\s+(\w+)\s*\((\w+)",
    re.IGNORECASE,
)


def _source() -> str:
    return STARTUP_SOURCE.read_text(encoding="utf-8")


def _added_columns() -> list[tuple[str, str]]:
    return [(table.lower(), column.lower()) for table, column in ADD_COLUMN.findall(_source())]


class TestStartupOnlyAddsColumnsTheModelsDeclare:
    def test_the_statements_are_still_there_to_check(self):
        # 這些 ALTER 若有一天整批移除，上面的正規表示式就會默默什麼都比對不到，
        # 於是本檔所有測試變成永遠通過卻什麼也沒驗證。
        assert _added_columns(), "startup 沒有任何 ADD COLUMN，請確認本測試是否還需要"

    @pytest.mark.parametrize("table,column", _added_columns())
    def test_added_column_exists_in_the_model(self, table, column):
        assert table in Base.metadata.tables, f"startup 對不存在的資料表 {table} 加欄位"

        declared = {name.lower() for name in Base.metadata.tables[table].columns.keys()}

        assert column in declared, (
            f"startup 會建立 {table}.{column}，但模型裡沒有這個欄位。"
            "若它是被遷移刪掉的，請一併從 startup 移除，否則每次啟動都會加回來。"
        )


class TestStartupOnlyIndexesColumnsThatExist:
    def test_indexed_columns_exist_in_the_model(self):
        source = _source()

        # 迴圈形式的 CREATE INDEX（f-string 內的表名是變數）另外處理：
        # 取出迴圈列出的資料表名稱，逐一確認欄位存在。
        loop_tables = re.search(
            r'for table in \(([^)]*)\):\s*\n\s*connection\.execute\(text\(\s*\n\s*f"CREATE INDEX[^"]*ON \{table\} \((\w+)\)',
            source,
        )

        if loop_tables is None:
            pytest.skip("startup 的索引建立方式已改變，請更新本測試")

        tables = re.findall(r'"(\w+)"', loop_tables.group(1))
        column = loop_tables.group(2).lower()

        assert tables, "迴圈中沒有列出任何資料表"

        for table in tables:
            declared = {name.lower() for name in Base.metadata.tables[table].columns.keys()}
            assert column in declared, f"startup 會對 {table}.{column} 建索引，但模型沒有這個欄位"
