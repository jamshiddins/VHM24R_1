<template>
  <div class="space-y-6">
    <!-- Заголовок и фильтры -->
    <div class="bg-white rounded-lg shadow p-6">
      <h2 class="text-2xl font-bold mb-4">Аналитика заказов</h2>
      
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">От</label>
          <input
            v-model="filters.date_from"
            type="date"
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">До</label>
          <input
            v-model="filters.date_to"
            type="date"
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Группировка</label>
          <select
            v-model="filters.group_by"
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="day">По дням</option>
            <option value="week">По неделям</option>
            <option value="month">По месяцам</option>
          </select>
        </div>
        <div class="flex items-end">
          <button @click="loadAnalytics" class="btn-primary w-full">
            Обновить
          </button>
        </div>
      </div>
      
      <!-- Быстрые фильтры -->
      <div class="flex flex-wrap gap-2">
        <button
          v-for="preset in quickFilters"
          :key="preset.label"
          @click="applyQuickFilter(preset)"
          class="px-4 py-2 text-sm border rounded-md hover:bg-gray-50"
        >
          {{ preset.label }}
        </button>
      </div>
    </div>

    <!-- Сводная статистика -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="flex-shrink-0">
            <div class="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
              <span class="text-white text-sm">📦</span>
            </div>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-500">Всего заказов</p>
            <p class="text-2xl font-semibold text-gray-900">
              {{ analytics.summary?.total_orders || 0 }}
            </p>
          </div>
        </div>
      </div>
      
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="flex-shrink-0">
            <div class="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
              <span class="text-white text-sm">💰</span>
            </div>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-500">Общая выручка</p>
            <p class="text-2xl font-semibold text-gray-900">
              {{ formatCurrency(analytics.summary?.total_revenue || 0) }}
            </p>
          </div>
        </div>
      </div>
      
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="flex-shrink-0">
            <div class="w-8 h-8 bg-purple-500 rounded-full flex items-center justify-center">
              <span class="text-white text-sm">📊</span>
            </div>
          </div>
          <div class="ml-4">
            <p class="text-sm font-medium text-gray-500">Средний чек</p>
            <p class="text-2xl font-semibold text-gray-900">
              {{ formatCurrency(analytics.summary?.avg_order_value || 0) }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Графики -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- График заказов по времени -->
      <div class="bg-white rounded-lg shadow p-6">
        <h3 class="text-lg font-medium mb-4">Динамика заказов</h3>
        <canvas ref="ordersChart" width="400" height="200"></canvas>
      </div>
      
      <!-- График выручки по времени -->
      <div class="bg-white rounded-lg shadow p-6">
        <h3 class="text-lg font-medium mb-4">Динамика выручки</h3>
        <canvas ref="revenueChart" width="400" height="200"></canvas>
      </div>
      
      <!-- Типы оплаты -->
      <div class="bg-white rounded-lg shadow p-6">
        <h3 class="text-lg font-medium mb-4">Типы оплаты</h3>
        <canvas ref="paymentChart" width="400" height="200"></canvas>
      </div>
      
      <!-- Топ автоматов -->
      <div class="bg-white rounded-lg shadow p-6">
        <h3 class="text-lg font-medium mb-4">Топ автоматов</h3>
        <canvas ref="machinesChart" width="400" height="200"></canvas>
      </div>
    </div>

    <!-- Таблица детализации -->
    <div class="bg-white rounded-lg shadow overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-200">
        <h3 class="text-lg font-medium">Детализация по автоматам</h3>
      </div>
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Автомат
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Заказов
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Выручка
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Средний чек
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200">
            <tr v-for="machine in analytics.top_machines" :key="machine.machine_code">
              <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                {{ machine.machine_code }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ machine.count }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ formatCurrency(machine.total) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ formatCurrency(machine.total / machine.count) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, onMounted, nextTick } from 'vue'
import api from '../services/api'

export default {
  name: 'Analytics',
  setup() {
    const analytics = ref({})
    const loading = ref(false)
    
    const filters = reactive({
      date_from: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      date_to: new Date().toISOString().split('T')[0],
      group_by: 'day'
    })
    
    const quickFilters = [
      { label: 'Сегодня', days: 0 },
      { label: '7 дней', days: 7 },
      { label: '30 дней', days: 30 },
      { label: '90 дней', days: 90 }
    ]
    
    // Ссылки на canvas элементы
    const ordersChart = ref(null)
    const revenueChart = ref(null)
    const paymentChart = ref(null)
    const machinesChart = ref(null)
    
    // Экземпляры графиков
    let ordersChartInstance = null
    let revenueChartInstance = null
    let paymentChartInstance = null
    let machinesChartInstance = null
    
    const loadAnalytics = async () => {
      loading.value = true
      try {
        const response = await api.get('/analytics', { params: filters })
        analytics.value = response.data
        
        await nextTick()
        renderCharts()
        
      } catch (error) {
        window.notify('Ошибка при загрузке аналитики: ' + error.message, 'error')
      } finally {
        loading.value = false
      }
    }
    
    const applyQuickFilter = (filter) => {
      const today = new Date()
      const fromDate = new Date(today)
      fromDate.setDate(fromDate.getDate() - filter.days)
      
      filters.date_from = fromDate.toISOString().split('T')[0]
      filters.date_to = today.toISOString().split('T')[0]
      
      loadAnalytics()
    }
    
    const renderCharts = () => {
      // Простая заглушка для графиков
      // В реальном проекте здесь будет Chart.js
      console.log('Rendering charts with data:', analytics.value)
    }
    
    const formatCurrency = (amount) => {
      if (!amount) return '0 ₸'
      return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'UZS'
      }).format(amount)
    }
    
    onMounted(() => {
      loadAnalytics()
    })
    
    return {
      analytics,
      loading,
      filters,
      quickFilters,
      ordersChart,
      revenueChart,
      paymentChart,
      machinesChart,
      loadAnalytics,
      applyQuickFilter,
      formatCurrency
    }
  }
}
</script>
