// frontend/src/utils/password.js

// 規則必須與後端 password_policy.py 一致，否則畫面顯示「強」卻被伺服器擋下。
export const MIN_PASSWORD_LENGTH = 8;

// 後端封鎖清單的常見密碼（含本系統的預設密碼）。
const COMMON_PASSWORDS = new Set([
  "admin123", "password", "password1", "password123", "12345678",
  "123456789", "1234567890", "qwerty123", "abc12345", "iloveyou",
  "admin1234", "letmein1", "welcome1", "sunshine", "princess",
  "football", "baseball", "trustno1", "starwars", "passw0rd",
  "qwertyuiop", "1qaz2wsx", "zaq12wsx", "asdfghjkl", "11111111",
]);

// 整串只有一兩種字元（aaaaaaaa、abababab）。
function tooRepetitive(password) {
  return new Set(password).size <= 2;
}

// 依「長度」與「字元多樣性」評估新密碼強度：弱 / 中 / 強。
// 回傳 { level: 0-3, label, cls } 供進度條與文字標籤使用。
export function passwordStrength(password) {
  const p = password || "";
  if (!p) return { level: 0, label: "", cls: "" };

  // 這兩種一定會被後端擋下，直接標成最弱，不要讓使用者以為可以用。
  if (COMMON_PASSWORDS.has(p.toLowerCase()) || tooRepetitive(p)) {
    return { level: 1, label: "太容易被猜中", cls: "weak" };
  }

  if (p.length < MIN_PASSWORD_LENGTH) {
    return { level: 1, label: `至少 ${MIN_PASSWORD_LENGTH} 個字元`, cls: "weak" };
  }

  let score = 1;
  if (p.length >= 12) score += 1;
  if (/[A-Za-z]/.test(p) && /\d/.test(p)) score += 1; // 同時有英文與數字
  if (/[^A-Za-z0-9]/.test(p)) score += 1; // 含特殊符號

  if (score <= 1) return { level: 1, label: "弱", cls: "weak" };
  if (score === 2) return { level: 2, label: "中", cls: "medium" };
  return { level: 3, label: "強", cls: "strong" };
}
