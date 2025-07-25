<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-md w-full space-y-8">
      <div>
        <div class="mx-auto h-12 w-12 flex items-center justify-center rounded-full bg-blue-100">
          <span class="text-2xl">🔐</span>
        </div>
        <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900">
          VHM24R Order Management
        </h2>
        <p class="mt-2 text-center text-sm text-gray-600">
          Система управления заказами
        </p>
      </div>

      <div class="mt-8 space-y-6">
        <!-- Telegram авторизация -->
        <div class="bg-white rounded-lg shadow p-6">
          <div class="text-center">
            <div class="mx-auto h-16 w-16 flex items-center justify-center rounded-full bg-blue-500 mb-4">
              <span class="text-white text-2xl">📱</span>
            </div>
            <h3 class="text-lg font-medium text-gray-900 mb-2">
              Вход через Telegram
            </h3>
            <p class="text-sm text-gray-500 mb-6">
              Для доступа к системе используйте Telegram бот
            </p>
            
            <div class="space-y-4">
              <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div class="flex items-center justify-center space-x-2 mb-2">
                  <span class="text-blue-600 font-medium">@vhm24rbot</span>
                </div>
                <p class="text-xs text-blue-600">
                  Официальный бот системы VHM24R
                </p>
              </div>
              
              <div class="text-left space-y-2 text-sm text-gray-600">
                <div class="flex items-start space-x-2">
                  <span class="text-blue-500 font-bold">1.</span>
                  <span>Найдите бота <strong>@vhm24rbot</strong> в Telegram</span>
                </div>
                <div class="flex items-start space-x-2">
                  <span class="text-blue-500 font-bold">2.</span>
                  <span>Нажмите <strong>/start</strong> для начала</span>
                </div>
                <div class="flex items-start space-x-2">
                  <span class="text-blue-500 font-bold">3.</span>
                  <span>Подайте заявку на доступ</span>
                </div>
                <div class="flex items-start space-x-2">
                  <span class="text-blue-500 font-bold">4.</span>
                  <span>Дождитесь одобрения администратора</span>
                </div>
                <div class="flex items-start space-x-2">
                  <span class="text-blue-500 font-bold">5.</span>
                  <span>Получите персональную ссылку для входа</span>
                </div>
              </div>
              
              <a 
                href="https://t.me/vhm24rbot" 
                target="_blank"
                class="inline-flex items-center justify-center w-full px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                <span class="mr-2">📱</span>
                Открыть Telegram бот
              </a>
            </div>
          </div>
        </div>

        <!-- Информация о системе -->
        <div class="bg-white rounded-lg shadow p-6">
          <h3 class="text-lg font-medium text-gray-900 mb-4">
            О системе VHM24R
          </h3>
          <div class="space-y-3 text-sm text-gray-600">
            <div class="flex items-start space-x-3">
              <span class="text-green-500">✅</span>
              <span>Загрузка файлов в 12 форматах (CSV, Excel, PDF и др.)</span>
            </div>
            <div class="flex items-start space-x-3">
              <span class="text-green-500">✅</span>
              <span>Автоматическое сопоставление и обновление данных</span>
            </div>
            <div class="flex items-start space-x-3">
              <span class="text-green-500">✅</span>
              <span>Отслеживание изменений в реальном времени</span>
            </div>
            <div class="flex items-start space-x-3">
              <span class="text-green-500">✅</span>
              <span>Интерактивная аналитика и отчеты</span>
            </div>
            <div class="flex items-start space-x-3">
              <span class="text-green-500">✅</span>
              <span>Экспорт данных в различных форматах</span>
            </div>
          </div>
        </div>

        <!-- Статус авторизации -->
        <div v-if="authStatus" class="bg-white rounded-lg shadow p-6">
          <div class="text-center">
            <div v-if="authStatus === 'checking'" class="space-y-3">
              <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
              <p class="text-sm text-gray-600">Проверка авторизации...</p>
            </div>
            
            <div v-else-if="authStatus === 'success'" class="space-y-3">
              <div class="mx-auto h-8 w-8 flex items-center justify-center rounded-full bg-green-100">
                <span class="text-green-600">✅</span>
              </div>
              <p class="text-sm text-green-600 font-medium">Авторизация успешна!</p>
              <p class="text-xs text-gray-500">Перенаправление в систему...</p>
            </div>
            
            <div v-else-if="authStatus === 'error'" class="space-y-3">
              <div class="mx-auto h-8 w-8 flex items-center justify-center rounded-full bg-red-100">
                <span class="text-red-600">❌</span>
              </div>
              <p class="text-sm text-red-600 font-medium">Ошибка авторизации</p>
              <p class="text-xs text-gray-500">{{ errorMessage }}</p>
              <button 
                @click="authStatus = null"
                class="text-blue-600 hover:text-blue-800 text-sm"
              >
                Попробовать снова
              </button>
            </div>
          </div>
        </div>

        <!-- Контакты -->
        <div class="text-center">
          <p class="text-xs text-gray-500">
            Вопросы по доступу? Обратитесь к администратору: 
            <a href="https://t.me/Jamshiddin" class="text-blue-600 hover:text-blue-800">
              @Jamshiddin
            </a>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import api from '../services/api'

export default {
  name: 'Login',
  setup() {
    const router = useRouter()
    const route = useRoute()
    const authStatus = ref(null)
    const errorMessage = ref('')

    const checkTelegramAuth = async () => {
      // Проверяем, есть ли токен в URL (из Telegram бота)
      const token = route.query.token
      const uid = route.query.uid

      if (token && uid) {
        authStatus.value = 'checking'
        
        try {
          const response = await api.post('/auth/telegram/verify', {
            token,
            uid
          })

          // Сохраняем токен и данные пользователя
          localStorage.setItem('token', response.data.access_token)
          localStorage.setItem('user', JSON.stringify(response.data.user))

          authStatus.value = 'success'

          // Перенаправляем в систему через 2 секунды
          setTimeout(() => {
            router.push('/')
          }, 2000)

        } catch (error) {
          authStatus.value = 'error'
          errorMessage.value = error.response?.data?.detail || 'Неизвестная ошибка'
        }
      }
    }

    onMounted(() => {
      // Проверяем, авторизован ли уже пользователь
      const token = localStorage.getItem('token')
      if (token) {
        router.push('/')
        return
      }

      // Проверяем авторизацию через Telegram
      checkTelegramAuth()
    })

    return {
      authStatus,
      errorMessage
    }
  }
}
</script>
