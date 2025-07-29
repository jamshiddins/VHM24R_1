<template>
  <div id="app" class="min-h-screen bg-gradient-to-br from-gray-900 via-black to-gray-900">
    <!-- Заголовок -->
    <header v-if="isAuthenticated" class="border-b border-gray-800 bg-black/90 backdrop-blur-sm">
      <div class="flex h-16 items-center justify-between px-6">
        <div class="flex items-center space-x-4">
          <div class="w-8 h-8 bg-orange-500 rounded-lg flex items-center justify-center">
            <img src="/logo.svg" alt="Hub" class="w-6 h-6" />
          </div>
          <h1 class="text-xl font-bold text-white">Order Management Hub</h1>
        </div>
        
        <div class="flex items-center space-x-4">
          <div v-if="user" class="flex items-center space-x-2 text-gray-300">
            <span class="text-sm">@{{ user.username }}</span>
            <div class="w-8 h-8 bg-orange-500 rounded-full flex items-center justify-center">
              <span class="text-black text-xs font-bold">
                {{ user.first_name?.[0] || user.username?.[0] || 'U' }}
              </span>
            </div>
          </div>
          <button 
            @click="logout"
            class="inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none text-gray-300 hover:bg-gray-800 hover:text-white h-10 py-2 px-4"
          >
            Выйти
          </button>
        </div>
      </div>
    </header>

    <div v-if="isAuthenticated" class="flex">
      <!-- Боковая панель -->
      <aside class="w-64 border-r border-gray-800 bg-black/50 backdrop-blur-sm">
        <nav class="space-y-2 p-4">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            @click="activeTab = tab.id"
            :class="[
              'w-full flex items-center space-x-3 px-3 py-2 text-left rounded-md transition-colors',
              activeTab === tab.id
                ? 'bg-orange-500 text-black font-medium'
                : 'text-gray-300 hover:bg-gray-800 hover:text-white'
            ]"
          >
            <component :is="tab.icon" :size="20" />
            <span>{{ tab.name }}</span>
          </button>
        </nav>
      </aside>

      <!-- Основной контент -->
      <main class="flex-1 p-6">
        <div v-if="user?.status === 'approved'">
          <!-- Дашборд -->
          <Dashboard v-if="activeTab === 'dashboard'" />
          
          <!-- Заказы -->
          <OrderList v-else-if="activeTab === 'orders'" />
          
          <!-- Загрузка файлов -->
          <FileUpload v-else-if="activeTab === 'upload'" />
          
          <!-- Аналитика -->
          <Analytics v-else-if="activeTab === 'analytics'" />
          
          <!-- Пользователи (только для админа) -->
          <AdminPanel v-else-if="activeTab === 'users' && user?.role === 'admin'" />
          
          <!-- Настройки -->
          <div v-else-if="activeTab === 'settings'" class="flex items-center justify-center h-64">
            <div class="rounded-lg border border-gray-800 bg-gray-900/50 backdrop-blur-sm max-w-md mx-auto">
              <div class="p-6 text-center">
                <div class="w-16 h-16 bg-orange-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                  <SettingsIcon class="w-8 h-8 text-orange-500" />
                </div>
                <h3 class="text-lg font-semibold text-white mb-2">Настройки</h3>
                <p class="text-gray-400">Раздел настроек в разработке</p>
              </div>
            </div>
          </div>
          
          <!-- Заглушка для других разделов -->
          <div v-else class="flex items-center justify-center h-64">
            <div class="rounded-lg border border-gray-800 bg-gray-900/50 backdrop-blur-sm max-w-md mx-auto">
              <div class="p-6 text-center">
                <div class="w-16 h-16 bg-orange-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                  <component :is="getCurrentTabIcon()" class="w-8 h-8 text-orange-500" />
                </div>
                <h3 class="text-lg font-semibold text-white mb-2">{{ getCurrentTabName() }}</h3>
                <p class="text-gray-400">Раздел в разработке</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Ожидание подтверждения -->
        <div v-else-if="user && user.status !== 'approved'" class="flex items-center justify-center h-64">
          <div class="rounded-lg border border-gray-800 bg-gray-900/50 backdrop-blur-sm max-w-md mx-auto">
            <div class="p-6 text-center">
              <div class="w-16 h-16 bg-orange-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <UsersIcon class="w-8 h-8 text-orange-500" />
              </div>
              <h3 class="text-lg font-semibold text-white mb-2">Ожидание подтверждения</h3>
              <p class="text-gray-400">
                Ваша учетная запись ожидает подтверждения администратора.
                Пожалуйста, обратитесь к администратору системы.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>

    <!-- Страница входа -->
    <div v-else class="flex items-center justify-center min-h-screen">
      <router-view />
    </div>

    <!-- Уведомления -->
    <div v-if="notifications.length" class="fixed top-4 right-4 z-50 space-y-2">
      <div
        v-for="notification in notifications"
        :key="notification.id"
        :class="[
          'p-4 rounded-lg shadow-lg text-white font-medium flex items-center justify-between min-w-80',
          getNotificationClass(notification.type)
        ]"
      >
        <div class="flex items-center space-x-2">
          <component :is="getNotificationIcon(notification.type)" class="w-5 h-5" />
          <span>{{ notification.message }}</span>
        </div>
        <button 
          @click="removeNotification(notification.id)" 
          class="ml-4 text-white hover:text-gray-200 transition-colors"
        >
          ×
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { 
  BarChart3, 
  FileText, 
  Upload, 
  Settings as SettingsIcon, 
  Users as UsersIcon,
  CheckCircle,
  AlertCircle,
  Info,
  AlertTriangle
} from 'lucide-vue-next'

// Импорт компонентов
import Dashboard from './components/Dashboard.vue'
import OrderList from './components/OrderList.vue'
import FileUpload from './components/FileUpload.vue'
import Analytics from './components/Analytics.vue'
import AdminPanel from './components/AdminPanel.vue'

export default {
  name: 'App',
  components: {
    Dashboard,
    OrderList,
    FileUpload,
    Analytics,
    AdminPanel,
    BarChart3,
    FileText,
    Upload,
    SettingsIcon,
    UsersIcon,
    CheckCircle,
    AlertCircle,
    Info,
    AlertTriangle
  },
  setup() {
    const router = useRouter()
    const user = ref(JSON.parse(localStorage.getItem('user') || '{}'))
    const notifications = ref([])
    const activeTab = ref('dashboard')

    const tabs = ref([
      { id: 'dashboard', name: 'Дашборд', icon: 'BarChart3' },
      { id: 'orders', name: 'Заказы', icon: 'FileText' },
      { id: 'upload', name: 'Загрузка', icon: 'Upload' },
      { id: 'analytics', name: 'Аналитика', icon: 'BarChart3' },
      { id: 'users', name: 'Пользователи', icon: 'UsersIcon' },
      { id: 'settings', name: 'Настройки', icon: 'SettingsIcon' }
    ])

    const isAuthenticated = computed(() => {
      return localStorage.getItem('token') && user.value.id
    })

    const logout = () => {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      user.value = {}
      router.push('/login')
    }

    const addNotification = (message, type = 'info') => {
      const notification = {
        id: Date.now(),
        message,
        type
      }
      notifications.value.push(notification)
      setTimeout(() => removeNotification(notification.id), 5000)
    }

    const removeNotification = (id) => {
      const index = notifications.value.findIndex(n => n.id === id)
      if (index > -1) {
        notifications.value.splice(index, 1)
      }
    }

    const getNotificationClass = (type) => {
      switch (type) {
        case 'success': return 'bg-green-600'
        case 'error': return 'bg-red-600'
        case 'warning': return 'bg-yellow-600'
        default: return 'bg-blue-600'
      }
    }

    const getNotificationIcon = (type) => {
      switch (type) {
        case 'success': return 'CheckCircle'
        case 'error': return 'AlertCircle'
        case 'warning': return 'AlertTriangle'
        default: return 'Info'
      }
    }

    const getCurrentTabIcon = () => {
      const currentTab = tabs.value.find(tab => tab.id === activeTab.value)
      return currentTab?.icon || 'BarChart3'
    }

    const getCurrentTabName = () => {
      const currentTab = tabs.value.find(tab => tab.id === activeTab.value)
      return currentTab?.name || 'Раздел'
    }

    // WebSocket подключение
    const connectWebSocket = () => {
      if (!isAuthenticated.value) return

      try {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const wsHost = import.meta.env.VITE_API_URL ? 
          import.meta.env.VITE_API_URL.replace('http://', '').replace('https://', '') : 
          window.location.host
        const ws = new WebSocket(`${wsProtocol}//${wsHost}/ws/session`)
        
        ws.onmessage = (event) => {
          const data = JSON.parse(event.data)
          
          if (data.type === 'progress') {
            addNotification(`Обработано ${data.processed_rows} из ${data.total_rows} строк`, 'info')
          } else if (data.type === 'completed') {
            addNotification('Обработка файлов завершена!', 'success')
          } else if (data.type === 'error') {
            addNotification(`Ошибка: ${data.error}`, 'error')
          }
        }

        ws.onerror = () => {
          addNotification('Ошибка подключения к серверу', 'error')
        }
      } catch (error) {
        console.log('WebSocket connection failed:', error)
      }
    }

    onMounted(() => {
      if (isAuthenticated.value) {
        connectWebSocket()
      }
    })

    // Глобальный объект для уведомлений
    window.notify = addNotification

    return {
      user,
      isAuthenticated,
      notifications,
      activeTab,
      tabs,
      logout,
      addNotification,
      removeNotification,
      getNotificationClass,
      getNotificationIcon,
      getCurrentTabIcon,
      getCurrentTabName
    }
  }
}
</script>

<style scoped>
/* Дополнительные стили если нужны */
</style>
