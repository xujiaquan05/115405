// frontend/src/composables/useDashboard.spec.js

import { useDashboard } from "./useDashboard.js";

const get = vi.fn();
const post = vi.fn();
vi.mock("../services/api.js", () => ({
  default: {
    get: (...args) => get(...args),
    post: (...args) => post(...args),
  },
}));

const BOARDS = [
  { platform: "ptt", board: "facelift", label: "醫美", article_count: 9110 },
  { platform: "dcard", board: "facelift", label: "醫美", article_count: 20 },
  { platform: "dcard", board: "makeup", label: "美妝", article_count: 8 },
];

describe("useDashboard 平台篩選", () => {
  let dashboard;

  beforeEach(() => {
    vi.clearAllMocks();
    dashboard = useDashboard();
    dashboard.state.availableBoards = BOARDS;
    dashboard.state.selectedBoards = [];
    // 平台篩選只在已搜尋過關鍵字後才重新查詢。
    dashboard.state.keyword = "醫美";
    dashboard.state.hasSearched = true;
    // searchDashboard 會打 API，這裡讓它安靜地成功。
    get.mockResolvedValue({ data: { data: {} } });
  });

  it("fetchAvailableBoards 會把看板清單存進 state", async () => {
    get.mockResolvedValueOnce({ data: { data: { boards: BOARDS } } });

    await dashboard.fetchAvailableBoards();

    expect(get).toHaveBeenCalledWith("/api/dashboard/boards");
    expect(dashboard.state.availableBoards).toHaveLength(3);
  });

  // PTT 與 Dcard 都有 facelift：只送看板名稱會把兩個平台的文章混在一起，
  // 因此必須送出「平台:看板」。
  it("依平台篩選時送出「平台:看板」而非純看板名稱", async () => {
    await dashboard.filterByPlatform("dcard");

    expect(dashboard.state.selectedBoards).toEqual(["dcard:facelift", "dcard:makeup"]);
  });

  it("傳入空值代表全部平台，清空選取", async () => {
    dashboard.state.selectedBoards = ["dcard:facelift"];

    await dashboard.filterByPlatform("");

    expect(dashboard.state.selectedBoards).toEqual([]);
  });

  it("篩選後會重新查詢儀表板", async () => {
    await dashboard.filterByPlatform("ptt");

    expect(get).toHaveBeenCalled();
  });
});

describe("useDashboard 匯出權限提示", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => vi.restoreAllMocks());

  it("未登入時提示登入", async () => {
    get.mockRejectedValueOnce({ response: { status: 401 } });
    const dashboard = useDashboard();
    await dashboard.exportArticles();
    expect(dashboard.state.errorMessage).toBe("請先登入後匯出報表。");
  });

  it("讀取 blob 中的方案限制訊息", async () => {
    const data = new Blob([], { type: "application/json" });
    data.text = async () => JSON.stringify({ detail: "免費版未包含匯出報表功能" });
    get.mockRejectedValueOnce({ response: { status: 403, data } });
    const dashboard = useDashboard();
    await dashboard.exportArticles();
    expect(dashboard.state.errorMessage).toBe("免費版未包含匯出報表功能");
  });

  it("非 JSON 錯誤內容仍顯示可讀提示", async () => {
    const data = new Blob([]);
    data.text = async () => "service unavailable";
    get.mockRejectedValueOnce({ response: { status: 503, data } });
    const dashboard = useDashboard();
    await dashboard.exportArticles();
    expect(dashboard.state.errorMessage).toBe("Excel 匯出失敗，請稍後再試。");
  });
});

describe("useDashboard 開啟時不自動查詢", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useDashboard().resetDashboard();
  });

  it("重設後沒有預設關鍵字，也尚未搜尋", () => {
    const { state } = useDashboard();
    expect(state.keyword).toBe("");
    expect(state.hasSearched).toBe(false);
    expect(state.dashboardData).toBeNull();
  });

  it("沒有關鍵字時按搜尋不會呼叫 API", async () => {
    const dashboard = useDashboard();
    await dashboard.searchDashboard();
    expect(get).not.toHaveBeenCalled();
    expect(dashboard.state.errorMessage).toBe("請先輸入至少一個關鍵字再搜尋。");
  });

  it("尚未搜尋時切換平台只記住選擇，不查詢", async () => {
    const dashboard = useDashboard();
    dashboard.state.availableBoards = BOARDS;
    await dashboard.filterByPlatform("ptt");
    expect(dashboard.state.selectedBoards).toEqual(["ptt:facelift"]);
    expect(get).not.toHaveBeenCalled();
  });

  it("輸入關鍵字後搜尋才會查詢", async () => {
    get.mockResolvedValue({ data: { data: {} } });
    const dashboard = useDashboard();
    dashboard.state.keyword = "玻尿酸";
    await dashboard.searchDashboard({ createConversation: false });
    expect(dashboard.state.hasSearched).toBe(true);
    expect(get).toHaveBeenCalledWith("/api/dashboard/full", expect.anything());
  });
});
