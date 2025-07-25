<template>
  <div class="space-y-6">
    <!-- Заголовок -->
    <div class="bg-white rounded-lg shadow p-6">
      <h1 class="text-3xl font-bold text-gray-900">Добро пожаловать в VHM24R</h1>
      <p class="mt-2 text-gray-600">Система управления заказами</p>
    </div>

    <!-- Быстрая статистика -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="flex-shrink-0">
            <div class="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
              <span class="text-white text-sm">📦</span>
            </div>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-500">Всего заказов</p>
            <p class="text-2xl font-semibold text-gray-900">{{ stats.totalOrders }}</p>
          </div>
        </div>
      </div>

      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="flex-shrink-0">
            <div class="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
              <span class="text-white text-sm">📁</span>
            </div>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-500">Файлов загружено</p>
            <p class="text-2xl font-semibold text-gray-900">{{ stats.totalFiles }}</p>
          </div>
        </div>
      </div>

      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="flex-shrink-0">
            <div class="w-8 h-8 bg-yellow-500 rounded-full flex items-center justify-center">
              <span class="text-white text-sm">🔄</span>
            </div>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-500">Обновлено сегодня</p>
            <p class="text-2xl font-semibold text-gray-900">{{ stats.updatedToday }}</p>
          </div>
        </div>
      </div>

      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="flex-shrink-0">
            <div class="w-8 h-8 bg-purple-500 rounded-full flex items-center justify-center">
              <span class="text-white text-sm">💰</span>
            </div>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-500">Выручка за месяц</p>
            <p class="text-2xl font-semibold text-gray-900">{{ formatCurrency(stats.monthlyRevenue) }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Быстрые действия -->
    <div class="bg-white rounded-lg shadow p-6">
      <h2 class="text-xl font-bold mb-4">Быстрые действия</h2>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <router-link 
          to="/upload" 
          class="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <div class="flex-shrink-0">
            <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <span class="text-blue-600 text-xl">📤</span>
            </div>
          </div>
          <div class="ml-4">
            <h3 class="text-sm font-medium text-gray-900">Загрузить файлы</h3>
            <p class="text-xs text-gray-500">Загрузите новые данные заказов</p>
          </div>
        </router-link>

        <router-link 
          to="/orders" 
          class="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <div class="flex-shrink-0">
            <div class="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <span class="text-green-600 text-xl">📋</span>
            </div>
          </div>
          <div class="ml-4">
            <h3 class="text-sm font-medium text-gray-900">Просмотр заказов</h3>
            <p class="text-xs text-gray-500">Управление и фильтрация заказов</p>
          </div>
        </router-link>

        <router-link 
          to="/analytics" 
          class="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <div class="flex-shrink-0">
            <div class="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <span class="text-purple-600 text-xl">📊</span>
            </div>
          </div>
          <div class="ml-4">
            <h3 class="text-sm font-medium text-gray-900">Аналитика</h3>
            <p class="text-xs text-gray-500">Отчеты и статистика</p>
          </div>
        </router-link>
      </div>
    </div>

    <!-- Последние изменения -->
    <div class="bg-white rounded-lg shadow p-6">
      <h2 class="text-xl font-bold mb-4">Последние изменения</h2>
      <div class="space-y-3">
        <div v-for="change in recentChanges" :key="change.id" class="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
          <div class="flex-shrink-0">
            <span :class="getChangeIcon(change.type)">{{ getChangeEmoji(change.type) }}</span>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-gray-900">{{ change.description }}</p>
            <p class="text-xs text-gray-500">{{ formatDateTime(change.timestamp) }}</p>
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
  name: 'Dashboard',
  setup() {
    const stats = ref({
      totalOrders: 0,
      totalFiles: 0,
      updatedToday: 0,
      monthlyRevenue: 0
    })

    const recentChanges = ref([])

    const loadDashboardData = async () => {
      try {
        // Загружаем статистику
        const statsResponse = await api.get('/dashboard/stats')
        stats.value = statsResponse.data

        // Загружаем последние изменения
        const changesResponse = await api.get('/dashboard/recent-changes')
        recentChanges.value = changesResponse.data
      } catch (error) {
        console.error('Error loading dashboard data:', error)
        // Заглушка с тестовыми данными
        stats.value = {
          totalOrders: 1250,
          totalFiles: 45,
          updatedToday: 23,
          monthlyRevenue: 2500000
        }

        recentChanges.value = [
          {
            id: 1,
            type: 'new',
            description: 'Добавлено 15 новых заказов из файла orders_2025.csv',
            timestamp: new Date(Date.now() - 30 * 60 * 1000)
          },
          {
            id: 2,
            type: 'updated',
            description: 'Обновлены данные по 8 заказам',
            timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000)
          },
          {
            id: 3,
            type: 'filled',
            description: 'Заполнены пустые поля в 12 заказах',
            timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000)
          }
        ]
      }
    }

    const formatCurrency = (amount) => {
      if (!amount) return '0 ₸'
      return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'UZS'
      }).format(amount)
    }

    const formatDateTime = (datetime) => {
      if (!datetime) return '-'
      return new Date(datetime).toLocaleString('ru-RU')
    }

    const getChangeIcon = (type) => {
      const classes = {
        'new': 'w-6 h-6 bg-green-100 rounded-full flex items-center justify-center',
        'updated': 'w-6 h-6 bg-orange-100 rounded-full flex items-center justify-center',
        'filled': 'w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center',
        'changed': 'w-6 h-6 bg-yellow-100 rounded-full flex items-center justify-center'
      }
      return classes[type] || classes['new']
    }

    const getChangeEmoji = (type) => {
      const emojis = {
        'new': '🟩',
        'updated': '🟧',
        'filled': '🟦',
        'changed': '🔸'
      }
      return emojis[type] || '📝'
    }

    onMounted(() => {
      loadDashboardData()
    })

    return {
      stats,
      recentChanges,
      formatCurrency,
      formatDateTime,
      getChangeIcon,
      getChangeEmoji
    }
  }
}
</script>
