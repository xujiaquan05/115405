import { flushPromises, mount } from "@vue/test-utils";
import { ref } from "vue";
import HistoryView from "./HistoryView.vue";

const authenticated = ref(false);
const { get } = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock("../composables/useAuth", () => ({
  useAuth: () => ({ isAuthenticated: authenticated }),
}));
vi.mock("../services/api.js", () => ({ default: { get } }));

beforeEach(() => {
  localStorage.clear();
  authenticated.value = false;
  get.mockReset();
});

it("shows a login explanation without requesting private history for guests", async () => {
  const wrapper = mount(HistoryView);
  await flushPromises();
  expect(get).not.toHaveBeenCalled();
  expect(wrapper.find(".error-message").text()).toContain("請先登入");
  wrapper.unmount();
});

it("loads personal history for signed-in users", async () => {
  authenticated.value = true;
  get.mockResolvedValue({ data: { data: { records: [] } } });
  const wrapper = mount(HistoryView);
  await flushPromises();
  expect(get).toHaveBeenCalledWith("/api/analysis/history", { params: { limit: 80 } });
  expect(wrapper.find(".error-message").exists()).toBe(false);
  wrapper.unmount();
});
