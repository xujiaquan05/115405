// frontend/src/utils/password.spec.js

import { MIN_PASSWORD_LENGTH, passwordStrength } from "./password";

describe("passwordStrength", () => {
  it("空字串回傳 level 0", () => {
    expect(passwordStrength("")).toEqual({ level: 0, label: "", cls: "" });
    expect(passwordStrength(undefined)).toEqual({ level: 0, label: "", cls: "" });
  });

  it("未達最低長度 → 弱，並提示長度", () => {
    const result = passwordStrength("abc1!");

    expect(result.cls).toBe("weak");
    expect(result.label).toBe(`至少 ${MIN_PASSWORD_LENGTH} 個字元`);
  });

  // 這兩類後端會直接擋下，畫面不能顯示成可用的強度，
  // 否則使用者按了送出才被拒絕。
  it("常見密碼一律標成最弱", () => {
    for (const weak of ["admin123", "password", "12345678"]) {
      expect(passwordStrength(weak).cls).toBe("weak");
      expect(passwordStrength(weak).label).toBe("太容易被猜中");
    }
  });

  it("字元過於重複 → 最弱", () => {
    expect(passwordStrength("aaaaaaaaaa").label).toBe("太容易被猜中");
    expect(passwordStrength("abababababab").label).toBe("太容易被猜中");
  });

  it("剛好達長度但只有英文 → 弱", () => {
    expect(passwordStrength("abcdefgh").cls).toBe("weak");
  });

  it("達長度 + 英數混合 → 中", () => {
    const result = passwordStrength("abcdefg1");

    expect(result.level).toBe(2);
    expect(result.label).toBe("中");
  });

  it("夠長 + 英數 + 特殊符號 → 強", () => {
    const result = passwordStrength("Abcd1234!@");

    expect(result.level).toBe(3);
    expect(result.cls).toBe("strong");
  });
});
