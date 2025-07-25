<template>
  <div class="space-y-6">
    <!-- Фильтры -->
    <div class="bg-white rounded-lg shadow p-6">
      <h2 class="text-xl font-bold mb-4">Фильтры заказов</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Номер заказа</label>
          <input
            v-model="filters.order_number"
            type="text"
            placeholder="Введите номер заказа"
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
        </div>
        
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Код автомата</label>
          <input
            v-model="filters.machine_code"
            type="text"
            placeholder="Код автомата"
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
        </div>
        
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Тип оплаты</label>
          <select
            v-model="filters.payment_type"
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Все типы</option>
            <option value="Cash">Наличные</option>
            <option value="Card">Карта</option>
            <option value="Digital">Цифровые</option>
          </select>
        </div>
        
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Статус</label>
          <select
            v-model="filters.match_status"
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Все статусы</option>
            <option value="matched">Сопоставлен</option>
            <option value="unmatched">Не сопоставлен</option>
            <option value="partial">Частично</option>
          </select>
        </div>
      </div>
      
      <!-- Быстрые фильтры по дате -->
      <div class="flex flex-wrap gap-2 mb-4">
        <button
          v-for="preset in datePresets"
          :key="preset.label"
          @click="applyDatePreset(preset)"
          class="px-4 py-2 text-sm border rounded-md hover:bg-gray-50"
        >
          {{ preset.label }}
        </button>
      </div>
      
      <!-- Произвольный период -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
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
          <label class="block text-sm font-medium text-gray-700 mb-1">Тип изменений</label>
          <select
            v-model="filters.change_type"
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Все изменения</option>
            <option value="new">🟩 Новые</option>
            <option value="updated">🟧 Обновлённые</option>
            <option value="filled">🟦 Заполненные</option>
            <option value="changed">🔸 Изменённые</option>
          </select>
        </div>
      </div>
      
      <div class="flex gap-2">
        <button @click="loadOrders" class="btn-primary">
          Применить фильтры
        </button>
        <button @click="resetFilters" class="btn-secondary">
          Сбросить
        </button>
        <button @click="exportData" class="btn-secondary">
          📊 Экспорт
        </button>
      </div>
    </div>

    <!-- Таблица заказов -->
    <div class="bg-white rounded-lg shadow overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-200">
        <h2 class="text-xl font-bold">
          Заказы ({{ pagination.total }})
        </h2>
      </div>
      
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Номер заказа
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Автомат
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Товар
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Сумма
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Дата
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Оплата
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Статус
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr 
              v-for="order in orders" 
              :key="order.id"
              class="hover:bg-gray-50 cursor-pointer"
              :class="getRowClass(order)"
              @click="viewOrderDetails(order)"
            >
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm font-medium text-gray-900">
                  {{ order.order_number }}
                </div>
                <div class="text-xs text-gray-500">
                  v{{ order.version }}
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {{ order.machine_code || '-' }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm text-gray-900">{{ order.goods_name || '-' }}</div>
                <div class="text-xs text-gray-500">{{ order.taste_name || '' }}</div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                {{ formatCurrency(order.order_price) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ formatDateTime(order.creation_time) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 py-1 text-xs font-medium rounded-full"
                      :class="getPaymentTypeClass(order.payment_type)">
                  {{ order.payment_type || 'Не указано' }}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 py-1 text-xs font-medium rounded-full"
                      :class="getStatusClass(order.match_status)">
                  {{ getStatusText(order.match_status) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      
      <!-- Пагинация -->
      <div class="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200">
        <div class="flex-1 flex justify-between sm:hidden">
          <button 
            @click="previousPage" 
            :disabled="pagination.page === 1"
            class="btn-secondary"
          >
            Назад
          </button>
          <button 
            @click="nextPage" 
            :disabled="pagination.page === pagination.pages"
            class="btn-secondary"
          >
            Вперёд
          </button>
        </div>
        
        <div class="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
          <div>
            <p class="text-sm text-gray-700">
              Показано {{ getStartIndex() }} - {{ getEndIndex() }} из {{ pagination.total }} результатов
            </p>
          </div>
          <div>
            <nav class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px">
              <button 
                @click="previousPage"
                :disabled="pagination.page === 1"
                class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50"
              >
                ←
              </button>
              
              <button
                v-for="page in getVisiblePages()"
                :key="page"
                @click="goToPage(page)"
                :class="{
                  'bg-blue-50 border-blue-500 text-blue-600': page === pagination.page,
                  'bg-white border-gray-300 text-gray-500 hover:bg-gray-50': page !== pagination.page
                }"
                class="relative inline-flex items-center px-4 py-2 border text-sm font-medium"
              >
                {{ page }}
              </button>
              
              <button 
                @click="nextPage"
                :disabled="pagination.page === pagination.pages"
                class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50"
              >
                →
              </button>
            </nav>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, onMounted } from 'vue'
import api from '../services/api'

export default {
  name: 'OrderList',
  setup() {
    const orders = ref([])
    const loading = ref(false)
    
    const filters = reactive({
      order_number: '',
      machine_code: '',
      payment_type: '',
      match_status: '',
      date_from: '',
      date_to: '',
      change_type: ''
    })
    
    const pagination = reactive({
      page: 1,
      page_size: 50,
      total: 0,
      pages: 0
    })
    
    const datePresets = [
      { label: 'Сегодня', days: 0 },
      { label: 'Вчера', days: 1 },
      { label: '7 дней', days: 7 },
      { label: '30 дней', days: 30 }
    ]
    
    const loadOrders = async () => {
      if (loading.value) return
      
      loading.value = true
      try {
        const params = {
          page: pagination.page,
          page_size: pagination.page_size,
          ...filters
        }
        
        // Удаляем пустые параметры
        Object.keys(params).forEach(key => {
          if (!params[key]) delete params[key]
        })
        
        const response = await api.get('/orders', { params })
        
        orders.value = response.data.orders
        Object.assign(pagination, response.data.pagination)
        
      } catch (error) {
        window.notify('Ошибка при загрузке заказов: ' + error.message, 'error')
      } finally {
        loading.value = false
      }
    }
    
    const resetFilters = () => {
      Object.keys(filters).forEach(key => {
        filters[key] = ''
      })
      pagination.page = 1
      loadOrders()
    }
    
    const applyDatePreset = (preset) => {
      const today = new Date()
      const date = new Date(today)
      date.setDate(date.getDate() - preset.days)
      filters.date_from = date.toISOString().split('T')[0]
      filters.date_to = today.toISOString().split('T')[0]
      
      pagination.page = 1
      loadOrders()
    }
    
    const viewOrderDetails = (order) => {
      // Показать детали заказа
      console.log('Order details:', order)
    }
    
    const exportData = async () => {
      try {
        const params = { ...filters }
        const response = await api.get('/orders/export', { 
          params,
          responseType: 'blob'
        })
        
        // Создаём ссылку для скачивания
        const url = window.URL.createObjectURL(new Blob([response.data]))
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', `orders_${new Date().toISOString().split('T')[0]}.csv`)
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        
        window.notify('Экспорт завершён', 'success')
      } catch (error) {
        window.notify('Ошибка при экспорте: ' + error.message, 'error')
      }
    }
    
    // Пагинация
    const previousPage = () => {
      if (pagination.page > 1) {
        pagination.page--
        loadOrders()
      }
    }
    
    const nextPage = () => {
      if (pagination.page < pagination.pages) {
        pagination.page++
        loadOrders()
      }
    }
    
    const goToPage = (page) => {
      pagination.page = page
      loadOrders()
    }
    
    const getVisiblePages = () => {
      const current = pagination.page
      const total = pagination.pages
      const visible = []
      
      const start = Math.max(1, current - 2)
      const end = Math.min(total, current + 2)
      
      for (let i = start; i <= end; i++) {
        visible.push(i)
      }
      
      return visible
    }
    
    const getStartIndex = () => {
      return (pagination.page - 1) * pagination.page_size + 1
    }
    
    const getEndIndex = () => {
      return Math.min(pagination.page * pagination.page_size, pagination.total)
    }
    
    // Стилизация
    const getRowClass = (order) => {
      const classes = []
      
      if (order.version === 1) {
        classes.push('border-l-4 border-green-400') // новый
      } else {
        classes.push('border-l-4 border-orange-400') // обновлённый
      }
      
      return classes.join(' ')
    }
    
    const getStatusClass = (status) => {
      const classes = {
        'matched': 'bg-green-100 text-green-800',
        'unmatched': 'bg-gray-100 text-gray-800',
        'partial': 'bg-yellow-100 text-yellow-800'
      }
      return classes[status] || 'bg-gray-100 text-gray-800'
    }
    
    const getStatusText = (status) => {
      const texts = {
        'matched': 'Сопоставлен',
        'unmatched': 'Не сопоставлен',
        'partial': 'Частично'
      }
      return texts[status] || status
    }
    
    const getPaymentTypeClass = (type) => {
      const classes = {
        'Cash': 'bg-green-100 text-green-800',
        'Card': 'bg-blue-100 text-blue-800',
        'Digital': 'bg-purple-100 text-purple-800'
      }
      return classes[type] || 'bg-gray-100 text-gray-800'
    }
    
    const formatCurrency = (amount) => {
      if (!amount) return '-'
      return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'UZS'
      }).format(amount)
    }
    
    const formatDateTime = (datetime) => {
      if (!datetime) return '-'
      return new Date(datetime).toLocaleString('ru-RU')
    }
    
    onMounted(() => {
      loadOrders()
    })
    
    return {
      orders,
      loading,
      filters,
      pagination,
      datePresets,
      loadOrders,
      resetFilters,
      applyDatePreset,
      viewOrderDetails,
      exportData,
      previousPage,
      nextPage,
      goToPage,
      getVisiblePages,
      getStartIndex,
      getEndIndex,
      getRowClass,
      getStatusClass,
      getStatusText,
      getPaymentTypeClass,
      formatCurrency,
      formatDateTime
    }
  }
}
</script>
