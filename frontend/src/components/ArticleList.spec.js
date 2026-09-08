// frontend/src/components/ArticleList.spec.js

import { mount } from "@vue/test-utils";

import ArticleList from "./ArticleList.vue";

// 元件內部使用 useRouter()，測試中以最小替身取代。
const routerStub = { push: vi.fn() };
vi.mock("vue-router", () => ({ useRouter: () => routerStub }));

function makeArticles(count) {
  return Array.from({ length: count }, (_, i) => ({
    id: i + 1,
    title: `文章 ${i + 1}`,
    board: "facelift",
    author: `user${i + 1}`,
    push_count: i * 10,
    published_at: "2026-08-19T06:35:40",
  }));
}

function mountList(props) {
  return mount(ArticleList, { props, global: { stubs: { RouterLink: true } } });
}

describe("ArticleList", () => {
  it("預設只顯示前三篇，避免首屏過長", () => {
    const wrapper = mountList({ articles: makeArticles(10) });
    const text = wrapper.text();

    expect(text).toContain("文章 3");
    expect(text).not.toContain("文章 4");
  });

  it("展開後顯示全部", async () => {
    const wrapper = mountList({ articles: makeArticles(10) });

    const toggle = wrapper.findAll("button").find((b) => /全部|展開|更多/.test(b.text()));
    if (toggle) {
      await toggle.trigger("click");
      expect(wrapper.text()).toContain("文章 10");
    }
  });

  it("空清單不應該壞掉", () => {
    const wrapper = mountList({ articles: [] });

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).not.toContain("undefined");
  });

  it("缺少看板或作者時以 unknown 呈現，不顯示 undefined", () => {
    const wrapper = mountList({ articles: [{ id: 1, title: "無來源", push_count: 0 }] });

    expect(wrapper.text()).not.toContain("undefined");
    expect(wrapper.text()).toContain("unknown");
  });

  it("日期只取到日，沒有日期時顯示 no date", () => {
    const wrapper = mountList({
      articles: [
        { id: 1, title: "有日期", board: "b", author: "a", push_count: 1, published_at: "2026-08-19T06:35:40" },
        { id: 2, title: "沒日期", board: "b", author: "a", push_count: 1 },
      ],
    });
    const text = wrapper.text();

    expect(text).toContain("2026-08-19");
    expect(text).not.toContain("06:35:40");
    expect(text).toContain("no date");
  });
});
