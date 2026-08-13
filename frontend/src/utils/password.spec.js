// frontend/src/utils/password.spec.js

import { passwordStrength } from "./password";

describe("passwordStrength", () => {
  it("空字串回傳 level 0", () => {
    expect(passwordStrength("")).toEqual({ level: 0, label: "", cls: "" });
    expect(passwordStrength(undefined)).toEqual({ level: 0, label: "", cls: "" });
  });

  it("太短或單一類型 → 弱", () => {
    expect(passwordStrength("abc").cls).toBe("weak"); // 長度 < 6
    expect(passwordStrength("abcdef").cls).toBe("weak"); // 6 碼但只有英文
  });

  it("有長度 + 英數混合 → 中", () => {
    const result = passwordStrength("abcde1"); // 長度6 + 英數
    expect(result.level).toBe(2);
    expect(result.label).toBe("中");
  });

  it("夠長 + 英數 + 特殊符號 → 強", () => {
    const result = passwordStrength("Abcd1234!@"); // 長度10 + 英數 + 特殊
    expect(result.level).toBe(3);
    expect(result.cls).toBe("strong");
  });
});
