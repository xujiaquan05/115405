// frontend/src/utils/password.js

// 依「長度」與「字元多樣性」評估新密碼強度：弱 / 中 / 強。
// 回傳 { level: 0-3, label, cls } 供進度條與文字標籤使用。
export function passwordStrength(password) {
  const p = password || "";
  if (!p) return { level: 0, label: "", cls: "" };

  let score = 0;
  if (p.length >= 6) score += 1;
  if (p.length >= 10) score += 1;
  if (/[A-Za-z]/.test(p) && /\d/.test(p)) score += 1; // 同時有英文與數字
  if (/[^A-Za-z0-9]/.test(p)) score += 1; // 含特殊符號

  if (score <= 1) return { level: 1, label: "弱", cls: "weak" };
  if (score === 2) return { level: 2, label: "中", cls: "medium" };
  return { level: 3, label: "強", cls: "strong" };
}
