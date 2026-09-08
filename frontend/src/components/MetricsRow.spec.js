// frontend/src/components/MetricsRow.spec.js

import { mount } from "@vue/test-utils";

import MetricsRow from "./MetricsRow.vue";

describe("MetricsRow", () => {
  const overview = { total_articles: 128, avg_push_count: 6.4, growth_rate: -12.5 };
  const sentiment = { negative: 18.2 };

  it("顯示總覽數字", () => {
    const wrapper = mount(MetricsRow, { props: { overview, sentiment } });
    const text = wrapper.text();

    expect(text).toContain("128");
    expect(text).toContain("6.4");
  });

  it("成長率為負也要照實顯示，不可被當成沒有值", () => {
    const wrapper = mount(MetricsRow, { props: { overview, sentiment } });

    expect(wrapper.text()).toContain("-12.5%");
  });

  it("缺欄位時以 0 呈現，而不是 undefined", () => {
    const wrapper = mount(MetricsRow, { props: { overview: {}, sentiment: {} } });
    const text = wrapper.text();

    expect(text).not.toContain("undefined");
    expect(text).not.toContain("NaN");
    expect(text).toContain("0");
  });

  it("載入中顯示 skeleton 而不是數字", () => {
    const wrapper = mount(MetricsRow, { props: { overview, sentiment, loading: true } });

    expect(wrapper.findAll(".skeleton").length).toBeGreaterThan(0);
    expect(wrapper.find(".metric-value").exists()).toBe(false);
  });
});
