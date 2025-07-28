<template>
  <div class="admin-panel">
    <div class="bg-white rounded-lg shadow p-6">
      <h2 class="text-2xl font-bold text-gray-800 mb-6">Панель администратора</h2>
      
      <!-- Статистика -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div class="bg-blue-50 p-4 rounded-lg">
          <h3 class="text-lg font-semibold text-blue-800">Всего пользователей</h3>
          <p class="text-3xl font-bold text-blue-600">{{ stats.totalUsers }}</p>
        </div>
        <div class="bg-yellow-50 p-4 rounded-lg">
          <h3 class="text-lg font-semibold text-yellow-800">Ожидают одобрения</h3>
          <p class="text-3xl font-bold text-yellow-600">{{ stats.pendingUsers }}</p>
        </div>
        <div class="bg-green-50 p-4 rounded-lg">
          <h3 class="text-lg font-semibold text-green-800">Активных пользователей</h3>
          <p class="text-3xl font-bold text-green-600">{{ stats.activeUsers }}</p>
        </div>
      </div>

      <!-- Пользователи, ожидающие одобрения -->
      <div class="mb-8">
        <h3 class="text-xl font-semibold text-gray-800 mb-4">Пользователи, ожидающие одобрения</h3>
        
        <div v-if="loading" class="text-center py-4">
          <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p class="mt-2 text-gray-600">Загрузка...</p>
        </div>

        <div v-else-if="pendingUsers.length === 0" class="text-center py-8 text-gray-500">
          Нет пользователей, ожидающих одобрения
        </div>

        <div v-else class="space-y-4">
          <div
            v-for="user in pendingUsers"
            :key="user.id"
            class="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
          >
            <div class="flex items-center space-x-4">
              <div class="w-10 h-10 bg-gray-300 rounded-full flex items-center justify-center">
                <span class="text-sm font-medium text-gray-700">
                  {{ user.first_name ? user.first_name[0] : user.username[0] }}
                </span>
              </div>
              <div>
                <p class="font-medium text-gray-900">
                  {{ user.first_name || user.username }}
                </p>
                <p class="text-sm text-gray-500">@{{ user.username }}</p>
                <p class="text-xs text-gray-400">
                  Telegram ID: {{ user.telegram_id }}
                </p>
              </div>
            </div>
            
            <div class="flex space-x-2">
              <button
                @click="approveUser(user.id)"
                :disabled="processingUsers.includes(user.id)"
                class="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
              >
                <span v-if="processingUsers.includes(user.id)">Обработка...</span>
                <span v-else>Одобрить</span>
              </button>
              <button
                @click="rejectUser(user.id)"
                :disabled="processingUsers.includes(user.id)"
                class="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
              >
                Отклонить
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Системная информация -->
      <div class="border-t pt-6">
        <h3 class="text-xl font-semibold text-gray-800 mb-4">Системная информация</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="bg-gray-50 p-4 rounded-lg">
            <h4 class="font-medium text-gray-700 mb-2">Статус системы</h4>
            <div class="flex items-center space-x-2">
              <div class="w-3 h-3 bg-green-500 rounded-full"></div>
              <span class="text-sm text-gray-600">Система работает нормально</span>
            </div>
          </div>
          <div class="bg-gray-50 p-4 rounded-lg">
            <h4 class="font-medium text-gray-700 mb-2">Версия</h4>
            <span class="text-sm text-gray-600">VHM24R v1.0.0</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import api from '../services/api'

export default {
  name: 'AdminPanel',
  setup() {
    const pendingUsers = ref([])
    const loading = ref(true)
    const processingUsers = ref([])
    const stats = ref({
      totalUsers: 0,
      pendingUsers: 0,
      activeUsers: 0
    })

    const loadPendingUsers = async () => {
      try {
        loading.value = true
        const response = await api.get('/users/pending')
        pendingUsers.value = response.data || []
        
        // Обновляем статистику
        stats.value.pendingUsers = pendingUsers.value.length
        
        if (window.notify) {
          window.notify('Список пользователей обновлен', 'success')
        }
      } catch (error) {
        console.error('Ошибка загрузки пользователей:', error)
        if (window.notify) {
          window.notify('Ошибка загрузки пользователей', 'error')
        }
      } finally {
        loading.value = false
      }
    }

    const approveUser = async (userId) => {
      try {
        processingUsers.value.push(userId)
        
        await api.post(`/users/${userId}/approve`)
        
        // Удаляем пользователя из списка ожидающих
        pendingUsers.value = pendingUsers.value.filter(user => user.id !== userId)
        stats.value.pendingUsers = pendingUsers.value.length
        stats.value.activeUsers += 1
        
        if (window.notify) {
          window.notify('Пользователь успешно одобрен', 'success')
        }
      } catch (error) {
        console.error('Ошибка одобрения пользователя:', error)
        if (window.notify) {
          window.notify('Ошибка одобрения пользователя', 'error')
        }
      } finally {
        processingUsers.value = processingUsers.value.filter(id => id !== userId)
      }
    }

    const rejectUser = async (userId) => {
      try {
        processingUsers.value.push(userId)
        
        // В данной реализации просто удаляем из списка
        // В реальном приложении здесь должен быть API вызов для отклонения
        pendingUsers.value = pendingUsers.value.filter(user => user.id !== userId)
        stats.value.pendingUsers = pendingUsers.value.length
        
        if (window.notify) {
          window.notify('Пользователь отклонен', 'info')
        }
      } catch (error) {
        console.error('Ошибка отклонения пользователя:', error)
        if (window.notify) {
          window.notify('Ошибка отклонения пользователя', 'error')
        }
      } finally {
        processingUsers.value = processingUsers.value.filter(id => id !== userId)
      }
    }

    const loadStats = async () => {
      try {
        // В реальном приложении здесь должен быть API вызов для получения статистики
        // Пока используем заглушку
        stats.value = {
          totalUsers: 15,
          pendingUsers: pendingUsers.value.length,
          activeUsers: 12
        }
      } catch (error) {
        console.error('Ошибка загрузки статистики:', error)
      }
    }

    onMounted(async () => {
      await loadPendingUsers()
      await loadStats()
    })

    return {
      pendingUsers,
      loading,
      processingUsers,
      stats,
      approveUser,
      rejectUser,
      loadPendingUsers
    }
  }
}
</script>

<style scoped>
.admin-panel {
  max-width: 1200px;
  margin: 0 auto;
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
