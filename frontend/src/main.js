import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

// Компоненты
import Dashboard from './components/Dashboard.vue'
import OrderList from './components/OrderList.vue'
import FileUpload from './components/FileUpload.vue'
import Analytics from './components/Analytics.vue'
import Login from './components/Login.vue'
import AdminPanel from './components/AdminPanel.vue'

// Роутер
const routes = [
  { path: '/', component: Dashboard, meta: { requiresAuth: true } },
  { path: '/orders', component: OrderList, meta: { requiresAuth: true } },
  { path: '/upload', component: FileUpload, meta: { requiresAuth: true } },
  { path: '/analytics', component: Analytics, meta: { requiresAuth: true } },
  { path: '/admin', component: AdminPanel, meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/login', component: Login },
  { path: '/auth/telegram', component: Login, props: route => ({ token: route.query.token, uid: route.query.uid }) },
  { path: '/auth/session/:token', component: Login, props: route => ({ sessionToken: route.params.token }) },
  { path: '/auth/admin/:token', component: Login, props: route => ({ adminToken: route.params.token }) },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Глобальная проверка авторизации
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.meta.requiresAdmin && user.role !== 'admin') {
    next('/')
  } else {
    next()
  }
})

createApp(App).use(router).mount('#app')
