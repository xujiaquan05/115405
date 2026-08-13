// frontend/src/composables/useAuth.spec.js

import { beforeEach, describe, expect, it } from "vitest";
import { useAuth } from "./useAuth";

describe("useAuth.updateUser", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("合併新資料到目前使用者，並寫回 localStorage", () => {
    const { state, updateUser } = useAuth();

    updateUser({ id: 1, username: "admin", display_name: "舊名字" });
    updateUser({ display_name: "新名字" }); // 只改顯示名稱，其他保留

    expect(state.user.display_name).toBe("新名字");
    expect(state.user.username).toBe("admin");

    const stored = JSON.parse(localStorage.getItem("auth_user"));
    expect(stored.display_name).toBe("新名字");
    expect(stored.username).toBe("admin");
  });

  it("傳入 null 不會出錯也不改變狀態", () => {
    const { state, updateUser } = useAuth();
    updateUser({ id: 9, display_name: "保留" });

    updateUser(null);

    expect(state.user.display_name).toBe("保留");
  });
});
