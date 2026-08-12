<!-- frontend/src/views/LandingView.vue -->

<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useAuth } from "../composables/useAuth";
import LogoMark from "../components/LogoMark.vue";

const router = useRouter();
const { isAuthenticated, isGuest, enterGuestMode } = useAuth();

let revealObserver = null;

// 說明：
// 進場動畫。元素捲動進畫面時加上 is-visible，觸發淡入上移。
// 若使用者偏好減少動態效果（prefers-reduced-motion），直接全部顯示。
onMounted(() => {
  const elements = document.querySelectorAll(".reveal");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (reduceMotion || !("IntersectionObserver" in window)) {
    elements.forEach((el) => el.classList.add("is-visible"));
    return;
  }

  revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          revealObserver.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15 }
  );

  elements.forEach((el) => revealObserver.observe(el));
});

onBeforeUnmount(() => revealObserver?.disconnect());

function goLogin() {
  router.push("/login");
}

function enterDashboard() {
  // 已登入或已是訪客就直接進系統；否則以訪客身分體驗。
  if (!isAuthenticated.value && !isGuest.value) {
    enterGuestMode();
  }
  router.push("/dashboard");
}

const features = [
  {
    icon: "◫",
    title: "多平台輿情爬蟲",
    desc: "自動爬取 PTT 十大美容看板討論，架構已預留 Dcard、Threads 等平台擴充。",
  },
  {
    icon: "⚗",
    title: "智慧內容過濾",
    desc: "爬取當下即濾除公告、版務等雜訊，只保留與醫美消費相關的真實討論。",
  },
  {
    icon: "☺",
    title: "AI 情緒分析",
    desc: "以 Gemini 逐篇判讀正面 / 中性 / 負面，取代單純以推文數估算的粗略指標。",
  },
  {
    icon: "⌕",
    title: "關鍵字輿情追蹤",
    desc: "輸入療程或品牌關鍵字，即時彙整聲量趨勢、熱門話題與消費者痛點。",
  },
  {
    icon: "✦",
    title: "可執行行銷洞察",
    desc: "以 5W2H1E 拆解每一條建議，讓行銷人員看完就知道做什麼、怎麼做、在哪做。",
  },
  {
    icon: "◈",
    title: "AI 問答助理",
    desc: "用自然語言追問資料，例如「最近玻尿酸有哪些負評」，並附上可點擊的來源。",
  },
];

const steps = [
  { no: "1", title: "爬取資料", desc: "從 PTT 等平台收集最新討論文章。" },
  { no: "2", title: "過濾清洗", desc: "去除雜訊、擷取正文，保留有效內容。" },
  { no: "3", title: "AI 分析", desc: "情緒判讀、關鍵字彙整與趨勢計算。" },
  { no: "4", title: "輸出洞察", desc: "產出圖表、洞察與可執行行銷建議。" },
];

const audiences = [
  { title: "輿情分析師", desc: "快速掌握市場聲量與情緒變化，省去人工翻文章的時間。" },
  { title: "行銷企劃", desc: "從真實討論中找到內容題材與可切入的行銷機會。" },
  { title: "品牌經營者", desc: "即時察覺負評與公關風險，掌握消費者當前的需求。" },
];

const keywords = ["玻尿酸", "音波拉提", "皮秒雷射", "肉毒", "隆鼻", "電波", "術後保養", "醫美診所"];

// 常見問題（FAQ）。以點擊展開的手風琴呈現。
const faqs = [
  {
    q: "系統的資料從哪裡來？",
    a: "目前自動爬取 PTT 十大美容相關看板，以及 Dcard 的醫美、美妝、穿搭看板；架構已預留 Threads 等平台擴充。爬取當下即濾除公告、版務與交易等雜訊，只保留與醫美、時尚消費相關的真實討論。",
  },
  {
    q: "情緒分析是怎麼判讀的？準確嗎？",
    a: "由 Gemini 逐篇判讀正面 / 中性 / 負面，比單純用推文數估算更貼近真實語意。尚未評分的文章會暫以推文數作為過渡指標，每篇的 AI 覆蓋率也會顯示，方便你評估分數可信度。",
  },
  {
    q: "需要登入才能使用嗎？",
    a: "以訪客身分即可瀏覽 Dashboard、關鍵字分析與趨勢圖表。登入後才能執行爬蟲、重新評分等寫入操作；帳號管理、系統設定與看板管理等後台功能則僅限管理員。",
  },
  {
    q: "資料多久更新一次？",
    a: "系統每天固定時間自動爬取、分析並檢查輿情風險；管理員可在「系統管理 → 系統設定」調整執行時間與每個看板的爬取頁數，也能隨時手動觸發爬取。",
  },
  {
    q: "可以追蹤特定品牌或療程嗎？",
    a: "可以。在「輿情監控」新增想追蹤的關鍵字，系統會定期評估其聲量與負面比例，一旦達到警示或危機門檻就主動產生預警，協助你及早掌握公關風險。",
  },
  {
    q: "這是商業產品嗎？資料可以商用嗎？",
    a: "本系統為 115405 學術專題製作，資料僅供研究與分析示範之用。使用時請尊重各來源平台的服務條款與 robots.txt，並以合理頻率爬取。",
  },
];

// 預設全部收合。可同時展開多題：展開某題不會收合其他已展開的題目。
const openFaqs = ref([]);

function isFaqOpen(index) {
  return openFaqs.value.includes(index);
}

function toggleFaq(index) {
  if (openFaqs.value.includes(index)) {
    openFaqs.value = openFaqs.value.filter((i) => i !== index);
  } else {
    openFaqs.value = [...openFaqs.value, index];
  }
}
</script>

<template>
  <div class="landing">

    <!-- 頂部導覽 -->
    <header class="landing-nav">
      <div class="landing-nav-inner">
        <div class="landing-brand">
          <LogoMark :size="42" />
          <div class="landing-brand-text">
            <strong class="landing-wordmark">MeBOD</strong>
            <span class="landing-brand-sub">醫美時尚輿情分析系統</span>
          </div>
        </div>
        <nav class="landing-nav-links">
          <a href="#features">功能特色</a>
          <a href="#flow">運作流程</a>
          <a href="#audience">適用對象</a>
          <a href="#faq">常見問題</a>
          <button class="landing-nav-login" type="button" @click="goLogin">登入系統</button>
        </nav>
      </div>
    </header>

    <!-- Hero -->
    <section class="landing-hero">
      <div class="landing-hero-text">
        <span class="landing-badge hero-in" style="--d: 0ms">AI 驅動的醫美輿情分析</span>
        <h1 class="hero-in" style="--d: 100ms">把網路上的醫美討論<br />變成可行動的行銷洞察</h1>
        <p class="hero-in" style="--d: 200ms">
          自動爬取社群平台的醫美討論，經 AI 過濾與情緒分析後，
          依關鍵字彙整出聲量趨勢、消費者痛點與具體行銷建議，
          協助分析師與行銷人員快速掌握市場需求。
        </p>
        <div class="landing-hero-actions hero-in" style="--d: 300ms">
          <button class="landing-btn-primary" type="button" @click="enterDashboard">立即體驗 Dashboard</button>
          <button class="landing-btn-secondary" type="button" @click="goLogin">登入系統</button>
        </div>
      </div>
      <div class="landing-hero-visual hero-in" style="--d: 250ms" aria-hidden="true">
        <div class="landing-keyword-cloud">
          <span
            v-for="(kw, index) in keywords"
            :key="kw"
            :class="['landing-kw', `kw-${index % 4}`]"
            :style="{ animationDelay: `${index * 0.4}s` }"
          >{{ kw }}</span>
        </div>
      </div>
    </section>

    <!-- 功能特色 -->
    <section id="features" class="landing-section">
      <div class="landing-section-head reveal">
        <h2>功能特色</h2>
        <p>從資料收集到行銷建議，一站式完成醫美輿情分析。</p>
      </div>
      <div class="landing-feature-grid">
        <article
          v-for="(feature, index) in features"
          :key="feature.title"
          class="landing-feature-card reveal"
          :style="{ transitionDelay: `${index * 80}ms` }"
        >
          <div class="landing-feature-head">
            <span class="landing-feature-icon">{{ feature.icon }}</span>
            <h3>{{ feature.title }}</h3>
          </div>
          <p>{{ feature.desc }}</p>
        </article>
      </div>
    </section>

    <!-- 運作流程 -->
    <section id="flow" class="landing-section landing-section-alt">
      <div class="landing-section-head reveal">
        <h2>運作流程</h2>
        <p>四個步驟，把零散的網路討論轉成清楚的分析報告。</p>
      </div>
      <div class="landing-step-row">
        <template v-for="(step, index) in steps" :key="step.no">
          <div class="landing-step reveal" :style="{ transitionDelay: `${index * 120}ms` }">
            <div class="landing-step-head">
              <span class="landing-step-no">{{ step.no }}</span>
              <h3>{{ step.title }}</h3>
            </div>
            <p>{{ step.desc }}</p>
          </div>
          <span v-if="index < steps.length - 1" class="landing-step-arrow" aria-hidden="true">→</span>
        </template>
      </div>
    </section>

    <!-- 適用對象 -->
    <section id="audience" class="landing-section">
      <div class="landing-section-head reveal">
        <h2>適用對象</h2>
        <p>無論你負責分析、行銷或品牌經營，都能更快掌握市場動態。</p>
      </div>
      <div class="landing-audience-grid">
        <article
          v-for="(item, index) in audiences"
          :key="item.title"
          class="landing-audience-card reveal"
          :style="{ transitionDelay: `${index * 100}ms` }"
        >
          <h3>{{ item.title }}</h3>
          <p>{{ item.desc }}</p>
        </article>
      </div>
    </section>

    <!-- 常見問題 -->
    <section id="faq" class="landing-section landing-section-alt">
      <div class="landing-section-head reveal">
        <h2>常見問題</h2>
        <p>關於資料來源、分析方式與使用權限的常見疑問。</p>
      </div>
      <div class="landing-faq-list">
        <article
          v-for="(item, index) in faqs"
          :key="item.q"
          class="landing-faq-item"
          :class="{ open: isFaqOpen(index) }"
        >
          <button
            class="landing-faq-q"
            type="button"
            :aria-expanded="isFaqOpen(index)"
            @click="toggleFaq(index)"
          >
            <span>{{ item.q }}</span>
            <span class="landing-faq-icon" aria-hidden="true"></span>
          </button>
          <div class="landing-faq-a">
            <div class="landing-faq-a-inner">
              <p>{{ item.a }}</p>
            </div>
          </div>
        </article>
      </div>
    </section>

    <!-- CTA -->
    <section class="landing-cta reveal">
      <h2>現在就開始分析醫美市場輿情</h2>
      <p>以訪客身分即可瀏覽 Dashboard，登入後可執行爬蟲與完整功能。</p>
      <div class="landing-hero-actions">
        <button class="landing-btn-primary" type="button" @click="enterDashboard">立即體驗 Dashboard</button>
        <button class="landing-btn-ghost" type="button" @click="goLogin">登入系統</button>
      </div>
    </section>

    <!-- 頁尾 -->
    <footer class="landing-footer">
      <div class="landing-footer-brand">
        <LogoMark :size="36" />
        <div>
          <strong>MeBOD</strong>
          <p>醫美時尚輿情分析系統</p>
        </div>
      </div>
      <p class="landing-footer-note">115405 專題製作 · 資料來源：PTT（Dcard、Threads 規劃中）</p>
    </footer>

  </div>
</template>
