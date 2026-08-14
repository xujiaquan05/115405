// frontend/src/components/SentimentBar.spec.js

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SentimentBar from "./SentimentBar.vue";

describe("SentimentBar", () => {
  it("loading 時顯示三條 skeleton", () => {
    const wrapper = mount(SentimentBar, { props: { loading: true } });
    expect(wrapper.findAll(".compact-row-skeleton")).toHaveLength(3);
  });

  it("顯示情緒百分比與圓餅圖", () => {
    const wrapper = mount(SentimentBar, {
      props: { sentiment: { positive: 60, neutral: 30, negative: 10 } },
    });

    const text = wrapper.text();
    expect(text).toContain("正面");
    expect(text).toContain("60%");
    expect(text).toContain("10%");

    // 有資料時圓餅圖用 conic-gradient 呈現比例
    expect(wrapper.find(".sentiment-pie").attributes("style")).toContain("conic-gradient");
  });

  it("沒有資料時圖例三項都顯示 0%", () => {
    const wrapper = mount(SentimentBar, { props: { sentiment: {} } });
    const legendText = wrapper.find(".sentiment-pie-legend").text();
    expect((legendText.match(/0%/g) || []).length).toBe(3);
  });
});
