// frontend/src/composables/useWebSocket.js

import { reactive } from "vue";

const WS_BASE_URL = "ws://localhost:8000";

const state = reactive({
  connected: false,
  reconnecting: false,
  errorMessage: "",
  statsVersion: 0,

  crawler: {
    active: false,
    board: "",
    progress: 0,
    currentPage: 0,
    totalPages: 0,
    crawledCount: 0,
    newCount: 0,
    skippedCount: 0,
    status: "idle",
  },

  notifications: [],
});

let socket = null;
let reconnectTimer = null;
let shouldReconnect = true;

function addNotification(type, message) {
  state.notifications.unshift({
    id: Date.now() + Math.random(),
    type,
    message,
    createdAt: new Date().toLocaleTimeString(),
  });

  state.notifications = state.notifications.slice(0, 5);
}

function applyMessage(event) {
  if (event.type === "connected") {
    state.connected = true;
    state.reconnecting = false;
    state.errorMessage = "";
    return;
  }

  if (event.type === "crawler_started") {
    state.crawler.active = true;
    state.crawler.board = event.board || "";
    state.crawler.progress = 0;
    state.crawler.currentPage = 0;
    state.crawler.totalPages = event.pages || 0;
    state.crawler.crawledCount = 0;
    state.crawler.newCount = 0;
    state.crawler.skippedCount = 0;
    state.crawler.status = "running";
    addNotification("info", `Crawler started: ${event.board}`);
    return;
  }

  if (event.type === "crawler_progress") {
    state.crawler.active = true;
    state.crawler.board = event.board || state.crawler.board;
    state.crawler.progress = event.progress || 0;
    state.crawler.currentPage = event.current_page || 0;
    state.crawler.totalPages = event.total_pages || 0;
    state.crawler.crawledCount = event.crawled_count || 0;
    state.crawler.status = "running";
    return;
  }

  if (event.type === "crawler_completed") {
    state.crawler.active = false;
    state.crawler.progress = 100;
    state.crawler.newCount = event.new_count || 0;
    state.crawler.skippedCount = event.skipped_count || 0;
    state.crawler.status = "completed";
    addNotification(
      "success",
      `Crawler completed: ${event.new_count || 0} new, ${event.skipped_count || 0} skipped`
    );
    return;
  }

  if (event.type === "crawler_failed") {
    state.crawler.active = false;
    state.crawler.status = "failed";
    state.errorMessage = event.error || "Crawler failed";
    addNotification("error", state.errorMessage);
    return;
  }

  if (event.type === "stats_updated") {
    state.statsVersion += 1;
  }
}

function scheduleReconnect() {
  if (!shouldReconnect || reconnectTimer) return;

  state.reconnecting = true;

  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, 3000);
}

function connect() {
  if (socket && [WebSocket.OPEN, WebSocket.CONNECTING].includes(socket.readyState)) {
    return;
  }

  shouldReconnect = true;
  socket = new WebSocket(`${WS_BASE_URL}/ws/dashboard`);

  socket.onopen = () => {
    state.connected = true;
    state.reconnecting = false;
    state.errorMessage = "";
  };

  socket.onmessage = (message) => {
    try {
      applyMessage(JSON.parse(message.data));
    } catch (error) {
      console.error(error);
    }
  };

  socket.onerror = () => {
    state.connected = false;
    state.errorMessage = "WebSocket connection error";
  };

  socket.onclose = () => {
    state.connected = false;
    scheduleReconnect();
  };
}

function disconnect() {
  shouldReconnect = false;

  if (reconnectTimer) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  if (socket) {
    socket.close();
    socket = null;
  }
}

export function useWebSocket() {
  return {
    state,
    connect,
    disconnect,
  };
}
