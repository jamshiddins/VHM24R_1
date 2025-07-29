<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-md w-full space-y-8">
      <div>
        <div class="mx-auto h-24 w-24 flex items-center justify-center">
          <img src="/logo.svg" alt="VHM24R Hub" class="h-20 w-20" />
        </div>
        <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900">
          VHM24R Hub
        </h2>
        <p class="mt-2 text-center text-sm text-gray-600">
          Система управления заказами
        </p>
      </div>

      <div class="mt-8 space-y-6">
        <!-- Обычная авторизация -->
        <div class="bg-white rounded-lg shadow p-6">
          <div class="text-center mb-6">
            <div class="mx-auto h-16 w-16 flex items-center justify-center rounded-full bg-green-500 mb-4">
              <span class="text-white text-2xl">🔑</span>
            </div>
            <h3 class="text-lg font-medium text-gray-900 mb-2">
              Вход в систему
            </h3>
            <p class="text-sm text-gray-500">
              Введите логин и пароль для доступа
            </p>
          </div>
          
          <form @submit.prevent="handleLogin" class="space-y-4">
            <div>
              <label for="username" class="block text-sm font-medium text-gray-700">
                Логин
              </label>
              <input
                id="username"
                v-model="loginForm.username"
                type="text"
                required
                class="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm"
                placeholder="Введите логин"
              />
            </div>
            
            <div>
              <label for="password" class="block text-sm font-medium text-gray-700">
                Пароль
              </label>
              <input
                id="password"
                v-model="loginForm.password"
                type="password"
                required
                class="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm"
                placeholder="Введите пароль"
              />
            </div>
            
            <div>
              <button
                type="submit"
                :disabled="loginLoading"
                class="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span v-if="loginLoading" class="mr-2">
                  <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                </span>
                {{ loginLoading ? 'Вход...' : 'Войти' }}
              </button>
            </div>
            
            <div v-if="loginError" class="text-red-600 text-sm text-center">
              {{ loginError }}
            </div>
          </form>
          
          <div class="mt-4 text-center">
            <p class="text-xs text-gray-500">
              Тестовые данные: admin / admin123
            </p>
          </div>
        </div>

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
  props: {
    token: String,
    uid: String,
    sessionToken: String,
    adminToken: String
  },
  setup(props) {
    const router = useRouter()
    const route = useRoute()
    const authStatus = ref(null)
    const errorMessage = ref('')
    
    // Обычная авторизация
    const loginForm = ref({
      username: '',
      password: ''
    })
    const loginLoading = ref(false)
    const loginError = ref('')

    const handleLogin = async () => {
      loginLoading.value = true
      loginError.value = ''
      
      try {
        const response = await api.post('/api/v1/auth/login', {
          username: loginForm.value.username,
          password: loginForm.value.password
        })

        // Сохраняем токен и данные пользователя
        localStorage.setItem('token', response.data.access_token)
        localStorage.setItem('user', JSON.stringify(response.data.user))

        // Перенаправляем в систему
        router.push('/')

      } catch (error) {
        loginError.value = error.response?.data?.detail || 'Неверный логин или пароль'
      } finally {
        loginLoading.value = false
      }
    }

    const checkTelegramAuth = async () => {
      // Проверяем, есть ли токен в URL (из Telegram бота)
      const token = props.token || route.query.token
      const uid = props.uid || route.query.uid

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

    const checkSessionAuth = async () => {
      if (props.sessionToken) {
        authStatus.value = 'checking'
        
        try {
          const response = await api.post('/auth/session', {
            session_token: props.sessionToken
          })

          // Сохраняем токен и данные пользователя
          localStorage.setItem('token', response.data.access_token)
          localStorage.setItem('user', JSON.stringify(response.data.user))

          authStatus.value = 'success'

          // Перенаправляем в систему через 1 секунду
          setTimeout(() => {
            router.push('/')
          }, 1000)

        } catch (error) {
          authStatus.value = 'error'
          errorMessage.value = error.response?.data?.detail || 'Ссылка недействительна или истекла'
        }
      }
    }

    const checkAdminAuth = async () => {
      if (props.adminToken) {
        authStatus.value = 'checking'
        
        try {
          const response = await api.post('/auth/admin', {
            admin_token: props.adminToken
          })

          // Сохраняем токен и данные пользователя
          localStorage.setItem('token', response.data.access_token)
          localStorage.setItem('user', JSON.stringify(response.data.user))

          authStatus.value = 'success'

          // Перенаправляем в систему через 1 секунду
          setTimeout(() => {
            router.push('/')
          }, 1000)

        } catch (error) {
          authStatus.value = 'error'
          errorMessage.value = error.response?.data?.detail || 'Административная ссылка недействительна или истекла'
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

      // Проверяем различные типы авторизации
      if (props.sessionToken) {
        checkSessionAuth()
      } else if (props.adminToken) {
        checkAdminAuth()
      } else {
        checkTelegramAuth()
      }
    })

    return {
      authStatus,
      errorMessage,
      loginForm,
      loginLoading,
      loginError,
      handleLogin
    }
  }
}
</script>
