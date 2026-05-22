// frontend/src/services/api.js

import axios from "axios";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL
  || (import.meta.env.DEV ? "http://localhost:8000" : "");

const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: 120000,
});

export default api;
