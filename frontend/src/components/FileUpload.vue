<template>
  <div class="space-y-6">
    <!-- Заголовок -->
    <div class="bg-white rounded-lg shadow p-6">
      <h2 class="text-2xl font-bold mb-4">Загрузка файлов</h2>
      
      <!-- Drag & Drop зона -->
      <div
        @drop="handleDrop"
        @dragover.prevent
        @dragenter.prevent
        class="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 transition-colors"
        :class="{ 'border-blue-400 bg-blue-50': isDragging }"
      >
        <input
          ref="fileInput"
          type="file"
          multiple
          accept=".csv,.xls,.xlsx,.txt,.doc,.docx,.pdf,.json,.xml,.zip,.rar"
          @change="handleFileSelect"
          class="hidden"
        >
        
        <div v-if="!selectedFiles.length">
          <svg class="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <h3 class="text-lg font-medium text-gray-900 mb-2">Загрузите файлы</h3>
          <p class="text-gray-500 mb-4">Перетащите файлы сюда или</p>
          <button @click="$refs.fileInput.click()" class="btn-primary">
            Выбрать файлы
          </button>
          <p class="text-xs text-gray-400 mt-2">
            Поддерживаемые форматы: CSV, XLS, XLSX, TXT, DOC, DOCX, PDF, JSON, XML, ZIP, RAR
          </p>
        </div>

        <!-- Список выбранных файлов -->
        <div v-else class="space-y-4">
          <h3 class="text-lg font-medium">Выбранные файлы ({{ selectedFiles.length }})</h3>
          <div class="grid gap-4">
            <div
              v-for="(file, index) in selectedFiles"
              :key="index"
              class="flex items-center justify-between p-3 bg-gray-50 rounded border"
            >
              <div class="flex items-center space-x-3">
                <div class="file-icon">📄</div>
                <div>
                  <p class="font-medium">{{ file.name }}</p>
                  <p class="text-sm text-gray-500">{{ formatFileSize(file.size) }}</p>
                </div>
              </div>
              <button @click="removeFile(index)" class="text-red-500 hover:text-red-700">
                ×
              </button>
            </div>
          </div>
          
          <div class="flex space-x-4">
            <button @click="selectedFiles = []" class="btn-secondary">
              Очистить
            </button>
            <button @click="$refs.fileInput.click()" class="btn-secondary">
              Добавить ещё
            </button>
            <button @click="uploadFiles" :disabled="uploading" class="btn-primary">
              {{ uploading ? 'Загружаем...' : 'Загрузить' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Прогресс загрузки -->
      <div v-if="uploadProgress.show" class="mt-6 p-4 bg-blue-50 rounded">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm font-medium">Прогресс обработки</span>
          <span class="text-sm">{{ uploadProgress.processed }}/{{ uploadProgress.total }}</span>
        </div>
        <div class="w-full bg-blue-200 rounded-full h-2">
          <div 
            class="bg-blue-600 h-2 rounded-full transition-all duration-300"
            :style="{ width: uploadProgress.percentage + '%' }"
          ></div>
        </div>
      </div>
    </div>

    <!-- Результаты загрузки -->
    <div v-if="uploadResults.length" class="bg-white rounded-lg shadow p-6">
      <h3 class="text-lg font-bold mb-4">Результаты загрузки</h3>
      <div class="space-y-3">
        <div
          v-for="result in uploadResults"
          :key="result.filename"
          class="flex items-center justify-between p-3 rounded border"
          :class="{
            'bg-green-50 border-green-200': !result.error,
            'bg-red-50 border-red-200': result.error
          }"
        >
          <div>
            <p class="font-medium">{{ result.filename }}</p>
            <p v-if="result.error" class="text-sm text-red-600">{{ result.error }}</p>
            <p v-else-if="result.similarity > 95" class="text-sm text-yellow-600">
              Схожесть {{ result.similarity }}% с существующим файлом
            </p>
            <p v-else class="text-sm text-green-600">Файл обработан успешно</p>
          </div>
          <div class="text-sm text-gray-500">
            {{ formatFileSize(result.size) }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import api from '../services/api'

export default {
  name: 'FileUpload',
  setup() {
    const selectedFiles = ref([])
    const isDragging = ref(false)
    const uploading = ref(false)
    const uploadResults = ref([])
    const uploadProgress = ref({
      show: false,
      processed: 0,
      total: 0,
      percentage: 0
    })

    const handleDrop = (e) => {
      e.preventDefault()
      isDragging.value = false
      const files = Array.from(e.dataTransfer.files)
      addFiles(files)
    }

    const handleFileSelect = (e) => {
      const files = Array.from(e.target.files)
      addFiles(files)
    }

    const addFiles = (files) => {
      const validFiles = files.filter(file => {
        const validTypes = [
          '.csv', '.xls', '.xlsx', '.txt', '.doc', '.docx', 
          '.pdf', '.json', '.xml', '.zip', '.rar'
        ]
        return validTypes.some(type => 
          file.name.toLowerCase().endsWith(type)
        )
      })
      selectedFiles.value.push(...validFiles)
    }

    const removeFile = (index) => {
      selectedFiles.value.splice(index, 1)
    }

    const formatFileSize = (bytes) => {
      const sizes = ['Bytes', 'KB', 'MB', 'GB']
      if (bytes === 0) return '0 Bytes'
      const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)))
      return Math.round(bytes / Math.pow(1024, i), 2) + ' ' + sizes[i]
    }

    const uploadFiles = async () => {
      if (!selectedFiles.value.length) return

      uploading.value = true
      uploadResults.value = []
      uploadProgress.value = { show: true, processed: 0, total: 0, percentage: 0 }

      try {
        const formData = new FormData()
        selectedFiles.value.forEach(file => {
          formData.append('files', file)
        })

        const response = await api.post('/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })

        uploadResults.value = response.data.files
        selectedFiles.value = []

        window.notify(`Загрузка завершена. Сессия: ${response.data.session_id}`, 'success')

      } catch (error) {
        window.notify('Ошибка при загрузке файлов: ' + error.message, 'error')
      } finally {
        uploading.value = false
      }
    }

    return {
      selectedFiles,
      isDragging,
      uploading,
      uploadResults,
      uploadProgress,
      handleDrop,
      handleFileSelect,
      removeFile,
      formatFileSize,
      uploadFiles
    }
  }
}
</script>
