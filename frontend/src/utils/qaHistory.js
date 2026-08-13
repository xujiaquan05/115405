// frontend/src/utils/qaHistory.js

// 把 AI 問答的對話訊息整理成傳給後端的 history：
// - 略過歡迎詞（welcome）與空內容
// - user 取 text、assistant 取 answer
// - 只保留最近 maxTurns 則，避免 prompt 過長
export function toHistory(messages, maxTurns = 6) {
  return (messages || [])
    .filter((message) => !message.welcome)
    .map((message) => ({
      role: message.role === "user" ? "user" : "assistant",
      content: message.role === "user" ? message.text || "" : message.answer || "",
    }))
    .filter((item) => item.content)
    .slice(-maxTurns);
}
