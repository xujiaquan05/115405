import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import QAView from '../views/QAView.vue'
import CrawlManagementView from '../views/CrawlManagementView.vue'
import HistoryView from '../views/HistoryView.vue'
import LoginView from '../views/LoginView.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: LoginView
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
router.beforeEach((to) => {
  const hasToken = Boolean(localStorage.getItem('auth_token'))
  const isGuest = localStorage.getItem('auth_guest') === '1'

  if (to.path === '/login') {
    return hasToken ? { path: '/' } : true
  }

  if (!hasToken && !isGuest) {
    return { path: '/login' }
  }

  return true
})

export default router
