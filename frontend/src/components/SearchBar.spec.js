// frontend/src/components/SearchBar.spec.js

import { mount } from "@vue/test-utils";
import { reactive } from "vue";

// useDashboard 是共享的模組級狀態，測試中換成可控的替身。
const dashboardState = reactive({
  keyword: "",
  days: 30,
  selectedBoards: [],
  availableBoards: [],
  loadingDashboard: false,
  hotKeywords: [],
});

const searchDashboard = vi.fn();
const fetchAvailableBoards = vi.fn();
const filterByPlatform = vi.fn();

vi.mock("../composables/useDashboard.js", () => ({
  useDashboard: () => ({
    state: dashboardState,
    searchDashboard,
    fetchAvailableBoards,
    filterByPlatform,
  }),
  TARGET_BOARDS: [],
}));

import SearchBar from "./SearchBar.vue";

const BOARDS = [
  { platform: "ptt", board: "facelift", label: "醫美", article_count: 9110 },
  { platform: "dcard", board: "facelift", label: "醫美", article_count: 20 },
  { platform: "mobile01", board: "371", label: "彩妝保養", article_count: 27 },
];

function chips(wrapper) {
  return wrapper.findAll(".platform-chip").map((c) => ({
    text: c.text().split("\n")[0].trim(),
    active: c.classes("active"),
  }));
}

describe("SearchBar 平台篩選", () => {
  beforeEach(() => {
    dashboardState.availableBoards = BOARDS;
    dashboardState.selectedBoards = [];
    vi.clearAllMocks();
  });

  it("依看板清單推導出平台按鈕，並加總各平台文章數", () => {
    const wrapper = mount(SearchBar);
    const labels = chips(wrapper).map((c) => c.text);

    expect(labels).toContain("全部");
    expect(labels.some((l) => l.startsWith("PTT"))).toBe(true);
    expect(wrapper.text()).toContain("9110");
  });

  it("沒有選看板時「全部」為選取狀態", () => {
    const wrapper = mount(SearchBar);

    expect(chips(wrapper).find((c) => c.text === "全部").active).toBe(true);
  });

  // 迴歸測試：selectedBoards 改成「平台:看板」格式後，
  // 判斷目前平台的程式仍在比對純看板名稱，導致永遠只有「全部」亮著。
  it("選了某平台時只有該平台亮起", () => {
    dashboardState.selectedBoards = ["mobile01:371"];
    const wrapper = mount(SearchBar);

    const active = chips(wrapper).filter((c) => c.active).map((c) => c.text);

    expect(active).toHaveLength(1);
    expect(active[0]).toContain("Mobile01");
  });

  it("PTT 與 Dcard 都有 facelift，仍要能分辨是哪一個平台", () => {
    dashboardState.selectedBoards = ["dcard:facelift"];
    const wrapper = mount(SearchBar);

    const active = chips(wrapper).filter((c) => c.active).map((c) => c.text);

    expect(active[0]).toContain("Dcard");
    expect(active[0]).not.toContain("PTT");
  });

  it("點平台按鈕會帶著平台名稱呼叫篩選", async () => {
    const wrapper = mount(SearchBar);
    const mobile01 = wrapper.findAll(".platform-chip").find((c) => c.text().includes("Mobile01"));

    await mobile01.trigger("click");

    expect(filterByPlatform).toHaveBeenCalledWith("mobile01");
  });

  it("只有一個平台時不顯示篩選列（沒得比就不佔版面）", () => {
    dashboardState.availableBoards = [BOARDS[0]];
    const wrapper = mount(SearchBar);

    expect(wrapper.findAll(".platform-chip")).toHaveLength(0);
  });
});
