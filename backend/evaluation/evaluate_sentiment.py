# backend/evaluation/evaluate_sentiment.py

"""情緒分析模型的成效評估。

為什麼需要這支程式？
系統宣稱「AI 情緒分析」，但如果沒有量化指標，就無法回答
「模型到底判得多準」。這裡以人工標註的樣本為基準（ground truth），
計算 accuracy、各類別的 precision / recall / F1，以及混淆矩陣。

樣本設計（見 sample.json 的 set 欄位）：
- random：從已評分文章中隨機抽樣，用來估計「整體正確率」。
- negative_boost：額外抽樣模型判為 negative 的文章。
  負面樣本在隨機抽樣中太少（約 8%），F1 會非常不穩定，
  因此補抽以取得可靠的 negative precision。
  注意：補抽會改變類別比例，所以「整體 accuracy」只用 random 子集計算，
  才不會被人為放大的負面比例扭曲。

執行：python evaluation/evaluate_sentiment.py
"""

import json
from collections import Counter, defaultdict
from pathlib import Path


LABELS = ["positive", "neutral", "negative"]
SAMPLE_PATH = Path(__file__).with_name("sample.json")


def load_labeled() -> list[dict]:
    items = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    return [i for i in items if i.get("gold_label")]


def confusion_matrix(items: list[dict]) -> dict:
    matrix = {gold: Counter() for gold in LABELS}

    for item in items:
        matrix[item["gold_label"]][item["model_label"]] += 1

    return matrix


def per_class_metrics(items: list[dict]) -> dict:
    """各類別的 precision / recall / F1。

    precision：模型說是某類別的，有多少真的是（避免誤報）。
    recall：真的屬於某類別的，模型抓到多少（避免漏報）。
    輿情場景通常更在意 negative 的 recall —— 漏掉負面聲量的代價最大。
    """
    stats = {}

    for label in LABELS:
        tp = sum(1 for i in items if i["model_label"] == label and i["gold_label"] == label)
        fp = sum(1 for i in items if i["model_label"] == label and i["gold_label"] != label)
        fn = sum(1 for i in items if i["model_label"] != label and i["gold_label"] == label)

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

        stats[label] = {
            "support": tp + fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
        }

    return stats


def accuracy(items: list[dict]) -> float:
    if not items:
        return 0.0

    correct = sum(1 for i in items if i["model_label"] == i["gold_label"])
    return correct / len(items)


def error_examples(items: list[dict], limit: int = 5) -> list[dict]:
    wrong = [i for i in items if i["model_label"] != i["gold_label"]]
    return [
        {"title": i["title"][:40], "gold": i["gold_label"], "model": i["model_label"]}
        for i in wrong[:limit]
    ]


def main() -> None:
    items = load_labeled()
    random_only = [i for i in items if i.get("set") == "random"]

    print(f"樣本總數：{len(items)}（隨機 {len(random_only)}、負面補抽 {len(items) - len(random_only)}）")
    print()

    # 整體正確率只看隨機子集，補抽樣本會扭曲類別比例。
    print(f"整體正確率（僅隨機子集 n={len(random_only)}）：{accuracy(random_only):.1%}")
    print()

    print("各類別成效（含補抽樣本，讓 negative 的統計更穩定）：")
    print(f"{'類別':<10}{'樣本數':>7}{'precision':>12}{'recall':>9}{'F1':>8}")
    for label, m in per_class_metrics(items).items():
        print(f"{label:<10}{m['support']:>7}{m['precision']:>12}{m['recall']:>9}{m['f1']:>8}")
    print()

    print("混淆矩陣（列＝人工標註，欄＝模型判斷）：")
    matrix = confusion_matrix(items)
    print(f"{'':<12}" + "".join(f"{l:>10}" for l in LABELS))
    for gold in LABELS:
        row = "".join(f"{matrix[gold][pred]:>10}" for pred in LABELS)
        print(f"{gold:<12}{row}")
    print()

    print("判錯的例子：")
    for e in error_examples(items):
        print(f"  人工={e['gold']:<9} 模型={e['model']:<9} {e['title']}")


if __name__ == "__main__":
    main()
