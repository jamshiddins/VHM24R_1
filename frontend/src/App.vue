<template>
  <div id="app" class="min-h-screen bg-gray-100">
    <!-- Навигация -->
    <nav v-if="isAuthenticated" class="bg-white shadow-lg">
      <div class="max-w-7xl mx-auto px-4">
        <div class="flex justify-between h-16">
          <div class="flex items-center space-x-8">
            <h1 class="text-xl font-bold text-gray-800">VHM24R</h1>
            <router-link to="/" class="nav-link">Главная</router-link>
            <router-link to="/orders" class="nav-link">Заказы</router-link>
            <router-link to="/upload" class="nav-link">Загрузка</router-link>
            <router-link to="/analytics" class="nav-link">Аналитика</router-link>
            <router-link v-if="user.role === 'admin'" to="/admin" class="nav-link">Админ</router-link>
          </div>
          <div class="flex items-center space-x-4">
            <span class="text-sm text-gray-600">{{ user.username }}</span>
            <button @click="logout" class="btn-secondary">Выйти</button>
          </div>
        </div>
      </div>
    </nav>

    <!-- Основной контент -->
    <main class="max-w-7xl mx-auto py-6 px-4">
      <router-view />
    </main>

    <!-- Уведомления -->
    <div v-if="notifications.length" class="fixed top-4 right-4 z-50">
      <div
        v-for="notification in notifications"
        :key="notification.id"
        class="notification"
        :class="notification.type"
      >
        {{ notification.message }}
        <button @click="removeNotification(notification.id)" class="ml-2 text-white">×</button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from './services/api'

export default {
  name: 'App',
  setup() {
    const router = useRouter()
    const user = ref(JSON.parse(localStorage.getItem('user') || '{}'))
    const notifications = ref([])

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

    // WebSocket подключение
    const connectWebSocket = () => {
      if (!isAuthenticated.value) return

      const ws = new WebSocket('ws://localhost:8000/ws/session')
      
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
      logout,
      addNotification,
      removeNotification
    }
  }
}
</script>
