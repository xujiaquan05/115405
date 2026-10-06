"""比較人工（或第二個模型）標註與系統的 Gemini 標註。

輸出混淆矩陣、各類 precision/recall/F1、整體一致率與 Cohen's kappa。

為什麼要看 kappa 而不只看一致率？
三類標籤就算兩邊亂猜也會有三成左右對上，一致率 70% 聽起來很高，
其實可能只比亂猜好一點。kappa 把「碰巧對上」的部分扣掉。

為什麼還要加權回推？
樣本是分層抽的（每類等量），negative 在樣本裡佔三分之一、母體只佔 7.5%，
而 negative 正好是最弱的一類。直接看樣本一致率會低估整體表現。
"""
import json
import os
import pathlib
import sys

from dotenv import load_dotenv

BACKEND = pathlib.Path(__file__).resolve().parents[1]
EVAL = BACKEND.parent / "docs/manual-work/sentiment-eval"
LABELS = ("positive", "neutral", "negative")
ZH = {"positive": "正面", "neutral": "中性", "negative": "負面"}


def load_labels(path: pathlib.Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        article_id, label = line.split()
        if label not in LABELS:
            raise ValueError(f"標籤不合法：{line}")
        out[article_id] = label
    return out


def population_shares() -> tuple[dict[str, float], int]:
    load_dotenv(BACKEND / ".env")
    from sqlalchemy import create_engine, text

    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        counts = dict(conn.execute(text(
            "SELECT sentiment, count(*) FROM articles "
            "WHERE sentiment IN ('positive','neutral','negative') GROUP BY 1"
        )).fetchall())

    total = sum(counts.values())
    return {label: counts.get(label, 0) / total for label in LABELS}, total


def main(mine_file: str) -> None:
    mine = load_labels(EVAL / mine_file)
    ai = json.loads((EVAL / "answer_key.json").read_text(encoding="utf-8"))
    ids = [i for i in mine if i in ai]
    n = len(ids)

    matrix = {row: {col: 0 for col in LABELS} for row in LABELS}
    for i in ids:
        matrix[mine[i]][ai[i]] += 1

    agree = sum(matrix[label][label] for label in LABELS)

    print(f"樣本數：{n}\n")
    print("混淆矩陣（列＝標註者，欄＝系統 Gemini）")
    print(f"{'':10}" + "".join(f"{ZH[c]:>8}" for c in LABELS) + f"{'小計':>8}")
    for row in LABELS:
        total_row = sum(matrix[row].values())
        print(f"{ZH[row]:<10}" + "".join(f"{matrix[row][c]:>8}" for c in LABELS)
              + f"{total_row:>8}")
    print(f"{'小計':<10}"
          + "".join(f"{sum(matrix[r][c] for r in LABELS):>8}" for c in LABELS)
          + f"{n:>8}")

    po = agree / n
    pe = sum(
        (sum(matrix[label].values()) / n) * (sum(matrix[r][label] for r in LABELS) / n)
        for label in LABELS
    )
    print(f"\n樣本一致率：{agree}/{n} = {po * 100:.1f}%")
    print(f"隨機一致的期望值：{pe * 100:.1f}%")
    print(f"Cohen's kappa：{(po - pe) / (1 - pe):.3f}")

    print("\n各類表現（以標註者的標籤為準）")
    print(f"{'類別':<8}{'precision':>12}{'recall':>10}{'F1':>8}{'標註數':>8}")
    for label in LABELS:
        tp = matrix[label][label]
        predicted = sum(matrix[r][label] for r in LABELS)
        actual = sum(matrix[label].values())
        precision = tp / predicted if predicted else 0.0
        recall = tp / actual if actual else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        print(f"{ZH[label]:<8}{precision:>12.3f}{recall:>10.3f}{f1:>8.3f}{actual:>8}")

    shares, pop_total = population_shares()
    weighted = 0.0
    print("\n回推母體（依系統標籤在資料庫中的實際比例加權）")
    print(f"{'系統標籤':<10}{'母體佔比':>10}{'本樣本同意率':>14}")
    for label in LABELS:
        column = sum(matrix[r][label] for r in LABELS)
        agree_rate = matrix[label][label] / column if column else 0.0
        weighted += shares[label] * agree_rate
        print(f"{ZH[label]:<10}{shares[label] * 100:>9.1f}%{agree_rate * 100:>13.1f}%")
    print(f"\n加權後估計：系統給出的標籤約 {weighted * 100:.1f}% 與標註者一致"
          f"（母體 {pop_total} 篇已評分文章）")

    print("\n不一致的案例")
    for i in ids:
        if mine[i] != ai[i]:
            print(f"  id={i:<6} 標註者={ZH[mine[i]]}  系統={ZH[ai[i]]}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "claude_labels.txt")
