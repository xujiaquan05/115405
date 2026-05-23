import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import QAView from '../views/QAView.vue'
import CrawlManagementView from '../views/CrawlManagementView.vue'
import HistoryView from '../views/HistoryView.vue'

const routes = [
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

export default router
