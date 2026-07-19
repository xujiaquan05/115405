import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import QAView from '../views/QAView.vue'
import CrawlManagementView from '../views/CrawlManagementView.vue'
import HistoryView from '../views/HistoryView.vue'
import LoginView from '../views/LoginView.vue'
import ProfileView from '../views/ProfileView.vue'
import AdminUsersView from '../views/AdminUsersView.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: LoginView
  },
  {
    path: '/profile',
    name: 'Profile',
    component: ProfileView,
    // 帳號資訊只有真正登入的使用者能看，訪客不行。
    meta: { requiresAccount: true }
  },
  {
    path: '/admin/users',
    name: 'AdminUsers',
    component: AdminUsersView,
    // 帳號管理只有 admin 能進。
    meta: { requiresAdmin: true }
  },
  {
    path: '/',
    name: 'Dashboard',
    component: DashboardView
  },
  {
    path: '/qa',
    name: 'QA',
    component: QAView
  },
  {
    path: '/crawl',
    name: 'CrawlManagement',
    component: CrawlManagementView
  },
  {
    path: '/history',
    name: 'History',
    component: HistoryView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 說明：
// 全域路由守衛：
// - 已登入者進 /login 直接導回 Dashboard。
// - 其他頁面需要「已登入」或「訪客模式」，否則導到登入頁。
function readStoredRole() {
  try {
    return JSON.parse(localStorage.getItem('auth_user') || 'null')?.role || ''
  } catch {
    return ''
  }
}

router.beforeEach((to) => {
  const hasToken = Boolean(localStorage.getItem('auth_token'))
  const isGuest = localStorage.getItem('auth_guest') === '1'

  if (to.path === '/login') {
    return hasToken ? { path: '/' } : true
  }

  // 只有 admin 能進的頁面：非 admin 導回首頁。
  if (to.meta.requiresAdmin) {
    if (!hasToken) return { path: '/login' }
    if (readStoredRole() !== 'admin') return { path: '/' }
  }

  // 需要真正帳號的頁面（例如帳號資訊），訪客一律導回登入頁。
  if (to.meta.requiresAccount && !hasToken) {
    return { path: '/login' }
  }

  if (!hasToken && !isGuest) {
    return { path: '/login' }
  }

  return true
})

export default router
