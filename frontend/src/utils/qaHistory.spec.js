// frontend/src/utils/qaHistory.spec.js

import { toHistory } from "./qaHistory";

describe("toHistory", () => {
  it("略過歡迎詞與空內容，並依角色取對應欄位", () => {
    const messages = [
      { role: "assistant", welcome: true, answer: "歡迎詞" },
      { role: "user", text: "玻尿酸有負評嗎" },
      { role: "assistant", answer: "有一些術後腫脹的抱怨" },
      { role: "assistant", answer: "" }, // 空內容 → 略過
    ];

    expect(toHistory(messages)).toEqual([
      { role: "user", content: "玻尿酸有負評嗎" },
      { role: "assistant", content: "有一些術後腫脹的抱怨" },
    ]);
  });

  it("只保留最近 maxTurns 則", () => {
    const messages = Array.from({ length: 10 }, (_, i) => ({ role: "user", text: `Q${i}` }));
    const result = toHistory(messages, 3);
    expect(result).toHaveLength(3);
    expect(result.map((m) => m.content)).toEqual(["Q7", "Q8", "Q9"]);
  });

  it("空或未定義輸入回傳空陣列", () => {
    expect(toHistory(null)).toEqual([]);
    expect(toHistory(undefined)).toEqual([]);
    expect(toHistory([])).toEqual([]);
  });
});
