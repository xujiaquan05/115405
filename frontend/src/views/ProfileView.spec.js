// frontend/src/views/ProfileView.spec.js

import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

// 把 api 服務換成假的，避免真的打後端。
vi.mock("../services/api", () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: { user: {} } })),
    patch: vi.fn(() => Promise.resolve({ data: { user: { display_name: "新名字" } } })),
    post: vi.fn(() => Promise.resolve({ data: { message: "ok" } })),
  },
}));

import { useAuth } from "../composables/useAuth";
import ProfileView from "./ProfileView.vue";

function seedUser() {
  useAuth().updateUser({
    id: 1,
    username: "admin",
    display_name: "系統管理員",
    role: "admin",
    is_active: true,
    last_login_at: "2026-08-13T09:30:00",
    created_at: "2026-07-01T10:00:00",
  });
}

describe("ProfileView", () => {
  beforeEach(() => {
    localStorage.clear();
    seedUser();
  });

  it("顯示帳號資訊欄位（角色、狀態、最後登入、建立時間）", () => {
    const wrapper = mount(ProfileView);
    const text = wrapper.text();

    expect(text).toContain("系統管理員");
    expect(text).toContain("@admin");
    expect(text).toContain("啟用中");
    expect(text).toContain("最後登入");
    expect(text).toContain("建立時間");
  });

  it("點編輯 → 出現輸入框；儲存後顯示新名稱", async () => {
    const wrapper = mount(ProfileView);

    // 一開始沒有編輯輸入框
    expect(wrapper.find(".profile-name-edit input").exists()).toBe(false);

    await wrapper.find(".profile-edit-btn").trigger("click");
    const input = wrapper.find(".profile-name-edit input");
    expect(input.exists()).toBe(true);

    await input.setValue("新名字");
    await wrapper.find(".profile-name-save").trigger("click");
    await flushPromises();

    // 儲存成功後回到顯示狀態，且名稱已更新
    expect(wrapper.find(".profile-name-edit input").exists()).toBe(false);
    expect(wrapper.text()).toContain("新名字");
  });

  it("新密碼與舊密碼相同時擋下並提示", async () => {
    const wrapper = mount(ProfileView);
    const inputs = wrapper.findAll(".profile-pw-field input");

    await inputs[0].setValue("samepass");
    await inputs[1].setValue("samepass");
    await inputs[2].setValue("samepass");
    // jsdom 中點 submit 按鈕不一定觸發 form 送出，直接觸發 submit 事件。
    await wrapper.find(".profile-form").trigger("submit");

    expect(wrapper.text()).toContain("新密碼不可與舊密碼相同");
  });
});
