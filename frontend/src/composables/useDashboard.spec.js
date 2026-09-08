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
