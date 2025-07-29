<template>
  <div class="space-y-6">
    <!-- Статистические карточки -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <div v-for="(stat, index) in stats" :key="index" class="rounded-lg border border-gray-800 bg-gray-900/50 backdrop-blur-sm">
        <div class="p-6">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium text-gray-400">{{ stat.label }}</p>
              <p class="text-2xl font-bold text-white">{{ stat.value }}</p>
              <p :class="stat.changeColor">{{ stat.change }}</p>
            </div>
            <div class="w-12 h-12 bg-orange-500/20 rounded-lg flex items-center justify-center">
              <component :is="stat.icon" class="w-6 h-6 text-orange-500" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Графики -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- График заказов по дням -->
      <div class="rounded-lg border border-gray-800 bg-gray-900/50 backdrop-blur-sm">
        <div class="flex flex-col space-y-1.5 p-6">
          <h3 class="text-lg font-semibold leading-none tracking-tight text-gray-100 flex items-center gap-2">
            <BarChart3Icon class="w-5 h-5 text-orange-500" />
            Заказы по дням
          </h3>
        </div>
        <div class="p-6 pt-0">
          <div class="h-64 bg-gray-800/50 rounded-md flex items-center justify-center">
            <canvas ref="ordersChart" class="w-full h-full"></canvas>
          </div>
        </div>
      </div>

      <!-- Типы платежей -->
      <div class="rounded-lg border border-gray-800 bg-gray-900/50 backdrop-blur-sm">
        <div class="flex flex-col space-y-1.5 p-6">
          <h3 class="text-lg font-semibold leading-none tracking-tight text-gray-100 flex items-center gap-2">
            <CreditCardIcon class="w-5 h-5 text-blue-500" />
            Типы платежей
          </h3>
        </div>
        <div class="p-6 pt-0">
          <div class="h-64 bg-gray-800/50 rounded-md flex items-center justify-center">
            <canvas ref="paymentsChart" class="w-full h-full"></canvas>
          </div>
        </div>
      </div>
    </div>

    <!-- Топ локации -->
    <div class="rounded-lg border border-gray-800 bg-gray-900/50 backdrop-blur-sm">
      <div class="flex flex-col space-y-1.5 p-6">
        <h3 class="text-lg font-semibold leading-none tracking-tight text-gray-100 flex items-center gap-2">
          <MapPinIcon class="w-5 h-5 text-purple-500" />
          Топ локации по заказам
        </h3>
      </div>
      <div class="p-6 pt-0">
        <div class="space-y-4">
          <div v-for="(location, index) in topLocations" :key="index" 
               class="flex items-center justify-between p-4 bg-gray-800/50 rounded-lg hover:bg-gray-800/70 transition-colors">
            <div class="flex items-center space-x-4">
              <div class="w-10 h-10 bg-purple-500/20 rounded-lg flex items-center justify-center">
                <span class="text-purple-400 font-bold">{{ index + 1 }}</span>
              </div>
              <div>
                <p class="text-gray-100 font-medium">{{ location.name }}</p>
                <p class="text-gray-400 text-sm">{{ location.machine }}</p>
              </div>
            </div>
            <div class="text-right">
              <p class="text-white font-bold">{{ location.orders }} заказов</p>
              <p class="text-gray-400 text-sm">{{ formatCurrency(location.revenue) }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Последние заказы -->
    <div class="rounded-lg border border-gray-800 bg-gray-900/50 backdrop-blur-sm">
      <div class="flex flex-col space-y-1.5 p-6">
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold leading-none tracking-tight text-gray-100 flex items-center gap-2">
            <FileTextIcon class="w-5 h-5 text-green-500" />
            Последние заказы
          </h3>
          <button class="inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none border border-gray-700 bg-transparent text-gray-300 hover:bg-gray-800 hover:text-white h-9 px-3 text-sm">
            Все заказы
          </button>
        </div>
      </div>
      <div class="p-6 pt-0">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-700">
                <th class="text-left py-3 px-2 text-gray-300 font-medium">Номер заказа</th>
                <th class="text-left py-3 px-2 text-gray-300 font-medium">Время</th>
                <th class="text-left py-3 px-2 text-gray-300 font-medium">Автомат</th>
                <th class="text-left py-3 px-2 text-gray-300 font-medium">Товар</th>
                <th class="text-left py-3 px-2 text-gray-300 font-medium">Сумма</th>
                <th class="text-left py-3 px-2 text-gray-300 font-medium">Статус</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="order in recentOrders" :key="order.id" 
                  class="border-b border-gray-800 hover:bg-gray-800/30 transition-colors cursor-pointer">
                <td class="py-3 px-2">
                  <button class="text-orange-400 hover:text-orange-300 font-medium transition-colors">
                    {{ order.orderNumber }}
                  </button>
                </td>
                <td class="py-3 px-2 text-gray-300">{{ formatTime(order.dateTime) }}</td>
                <td class="py-3 px-2 text-gray-300">{{ order.machineNumber }}</td>
                <td class="py-3 px-2 text-gray-300">{{ order.goodsName }}</td>
                <td class="py-3 px-2 text-gray-300 font-medium">{{ formatCurrency(order.amount) }}</td>
                <td class="py-3 px-2">
                  <span :class="getStatusColor(order.status)" class="px-2 py-1 rounded-full text-xs border">
                    {{ getStatusLabel(order.status) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { 
  FileText as FileTextIcon, 
  Upload as UploadIcon, 
  BarChart3 as BarChart3Icon, 
  MapPin as MapPinIcon, 
  DollarSign as DollarSignIcon, 
  CreditCard as CreditCardIcon,
  TrendingUp as TrendingUpIcon
} from 'lucide-vue-next'
import Chart from 'chart.js/auto'

export default {
  name: 'Dashboard',
  components: {
    FileTextIcon,
    UploadIcon,
    BarChart3Icon,
    MapPinIcon,
    DollarSignIcon,
    CreditCardIcon,
    TrendingUpIcon
  },
  setup() {
    const ordersChart = ref(null)
    const paymentsChart = ref(null)

    const stats = ref([
      { 
        label: 'Всего заказов', 
        value: '2,847', 
        change: '+12%', 
        changeColor: 'text-sm text-green-400',
        icon: 'FileTextIcon' 
      },
      { 
        label: 'Сумма продаж', 
        value: '₽847,293', 
        change: '+8%', 
        changeColor: 'text-sm text-green-400',
        icon: 'DollarSignIcon' 
      },
      { 
        label: 'Активных автоматов', 
        value: '47', 
        change: '+2', 
        changeColor: 'text-sm text-blue-400',
        icon: 'MapPinIcon' 
      },
      { 
        label: 'Загружено файлов', 
        value: '156', 
        change: '+5', 
        changeColor: 'text-sm text-green-400',
        icon: 'UploadIcon' 
      }
    ])

    const topLocations = ref([
      { name: "4 корпус кардиология", machine: "8da1181f0000", orders: 467, revenue: 5318000 },
      { name: "American hospital", machine: "3be8c71e0000", orders: 132, revenue: 2010000 },
      { name: "кпп кардиология", machine: "5b7b181f0000", orders: 115, revenue: 1880000 },
      { name: "1 корпус кардиология", machine: "17b7181f0000", orders: 105, revenue: 1680000 },
      { name: "Istanbul city", machine: "24a8181f0000", orders: 104, revenue: 1695000 }
    ])

    const recentOrders = ref([
      {
        id: 1,
        orderNumber: "ORD-001",
        dateTime: "2025-01-28 14:30:00",
        machineNumber: "VM-001",
        goodsName: "Cappuccino",
        amount: 15000,
        status: "new"
      },
      {
        id: 2,
        orderNumber: "ORD-002", 
        dateTime: "2025-01-28 15:45:00",
        machineNumber: "VM-002",
        goodsName: "Hot Chocolate",
        amount: 20000,
        status: "filled"
      },
      {
        id: 3,
        orderNumber: "ORD-003",
        dateTime: "2025-01-28 16:15:00",
        machineNumber: "VM-001",
        goodsName: "Ice Coffee",
        amount: 12000,
        status: "updated"
      }
    ])

    const formatCurrency = (amount) => {
      return new Intl.NumberFormat('ru-RU').format(amount) + ' сум'
    }

    const formatTime = (dateTime) => {
      return new Date(dateTime).toLocaleTimeString('ru-RU', { 
        hour: '2-digit', 
        minute: '2-digit' 
      })
    }

    const getStatusColor = (status) => {
      switch (status) {
        case 'new': return 'bg-green-500/20 text-green-400 border-green-500/30'
        case 'updated': return 'bg-orange-500/20 text-orange-400 border-orange-500/30'
        case 'filled': return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
        default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
      }
    }

    const getStatusLabel = (status) => {
      switch (status) {
        case 'new': return 'Новый'
        case 'updated': return 'Обновлён'
        case 'filled': return 'Заполнен'
        default: return status
      }
    }

    const initCharts = () => {
      // График заказов
      if (ordersChart.value) {
        new Chart(ordersChart.value, {
          type: 'bar',
          data: {
            labels: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
            datasets: [{
              label: 'Заказы',
              data: [120, 190, 300, 500, 200, 300, 450],
              backgroundColor: '#f97316',
              borderRadius: 4
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: {
                display: false
              }
            },
            scales: {
              y: {
                beginAtZero: true,
                grid: {
                  color: '#374151'
                },
                ticks: {
                  color: '#9ca3af'
                }
              },
              x: {
                grid: {
                  color: '#374151'
                },
                ticks: {
                  color: '#9ca3af'
                }
              }
            }
          }
        })
      }

      // График платежей
      if (paymentsChart.value) {
        new Chart(paymentsChart.value, {
          type: 'doughnut',
          data: {
            labels: ['Наличные', 'Карта', 'QR', 'Другое'],
            datasets: [{
              data: [871, 167, 103, 54],
              backgroundColor: ['#f97316', '#3b82f6', '#10b981', '#8b5cf6'],
              borderWidth: 0
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: {
                position: 'bottom',
                labels: {
                  color: '#9ca3af',
                  padding: 20
                }
              }
            }
          }
        })
      }
    }

    onMounted(() => {
      setTimeout(initCharts, 100)
    })

    return {
      stats,
      topLocations,
      recentOrders,
      ordersChart,
      paymentsChart,
      formatCurrency,
      formatTime,
      getStatusColor,
      getStatusLabel
    }
  }
}
</script>
