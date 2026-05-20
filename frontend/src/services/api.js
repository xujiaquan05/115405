// frontend/src/services/api.js

import axios from "axios";

// Note:
// Tạo một axios instance dùng chung cho toàn frontend.
// Nhờ baseURL, khi gọi API chỉ cần viết "/api/dashboard/full"
// thay vì viết đầy đủ "http://localhost:8000/api/dashboard/full".
const api = axios.create({
  baseURL: "http://localhost:8000",
  timeout: 120000,
});

// Note:
// Export api để composable hoặc component khác có thể dùng.
export default api;
