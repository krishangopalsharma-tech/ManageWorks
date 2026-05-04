<script setup>
import { ref } from 'vue'
import axios from 'axios'

const fileInput = ref(null)
const selectedFile = ref(null)
const sheetLink = ref('')
const isUploading = ref(false)
const uploadStatus = ref('')
const uploadStatusType = ref('')  // 'created' | 'updated' | 'no_changes' | 'error'
const uploadProgress = ref(0)
const uploadPhase = ref('')  // 'uploading' | 'processing' | ''

const handleFileSelect = (e) => {
  const file = e.target.files[0]
  if (file && (file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))) {
    selectedFile.value = file
    uploadStatus.value = ''
  } else {
    alert('Please upload a valid Excel file (.xlsx or .xls)')
  }
}

const triggerFileInput = () => fileInput.value.click()

const submitData = async () => {
  if (!selectedFile.value && !sheetLink.value) {
    alert('Please provide an Excel file or Google Sheet link.')
    return
  }

  isUploading.value = true
  uploadStatus.value = ''
  uploadStatusType.value = ''
  uploadProgress.value = 0
  uploadPhase.value = selectedFile.value ? 'uploading' : 'processing'

  const formData = new FormData()
  if (selectedFile.value) {
    formData.append('file', selectedFile.value)
  }
  if (sheetLink.value) {
    formData.append('link', sheetLink.value)
  }

  const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? ''

  try {
    const apiUrl = '/api/add-work/upload/'
    const res = await axios.post(apiUrl, formData, {
      headers: { 'X-CSRFToken': csrfToken },
      onUploadProgress: (evt) => {
        if (evt.total) {
          const pct = Math.round((evt.loaded / evt.total) * 100)
          uploadProgress.value = pct
          if (pct === 100) uploadPhase.value = 'processing'
        }
      },
    })
    uploadProgress.value = 100
    uploadStatusType.value = res.data.status   // 'created' | 'updated' | 'no_changes'
    uploadStatus.value = res.data.message
    if (res.data.status === 'created') {
      selectedFile.value = null
      sheetLink.value = ''
    }
  } catch (error) {
    console.error(error)
    uploadStatusType.value = 'error'
    uploadStatus.value = error.response?.data?.error || 'Failed to upload document.'
  } finally {
    isUploading.value = false
    uploadPhase.value = ''
  }
}
</script>

<template>
  <div class="bg-light-surface min-h-full w-full rounded-2xl soft-shadow p-10 flex flex-col items-center">
    
    <div class="w-full max-w-2xl text-center mb-10">
      <h1 class="text-3xl font-bold text-gray-800 tracking-tight mb-2">Upload New Work</h1>
      <p class="text-gray-500 font-medium text-sm">Upload standard Excel schema or provide a public Google Sheet link.</p>
    </div>

    <div class="w-full max-w-2xl space-y-8">
      
      <!-- File Upload Zone -->
      <div 
        @click="triggerFileInput"
        class="border-2 border-dashed border-gray-300 rounded-2xl p-12 flex flex-col items-center justify-center cursor-pointer hover:bg-white hover:border-[#0071e3] transition-colors"
      >
        <input type="file" ref="fileInput" class="hidden" accept=".xlsx,.xls" @change="handleFileSelect" />
        <div class="w-16 h-16 rounded-full bg-light-bg flex-center text-[#0071e3] mb-4">
          <div class="i-carbon-upload text-3xl"></div>
        </div>
        <h3 class="text-lg font-semibold text-gray-700 mb-1">
          {{ selectedFile ? selectedFile.name : 'Select Excel Document' }}
        </h3>
        <p class="text-sm text-gray-400">Click to browse or drag and drop (.xlsx)</p>
      </div>

      <div class="flex items-center gap-4">
        <div class="h-px bg-gray-200 flex-1"></div>
        <span class="text-sm font-semibold text-gray-400 uppercase tracking-widest">or</span>
        <div class="h-px bg-gray-200 flex-1"></div>
      </div>

      <!-- Link Input -->
      <div class="w-full">
        <label class="block text-sm font-semibold text-gray-600 mb-2 pl-2">Google Sheet Link</label>
        <div class="flex items-center bg-white border border-gray-300 rounded-xl px-5 py-4 w-full group focus-within:ring-2 focus-within:ring-[#0071e3]/20 focus-within:border-[#0071e3] transition-all">
          <div class="i-carbon-link text-gray-400 text-xl mr-3"></div>
          <input 
            v-model="sheetLink"
            type="text" 
            placeholder="Paste public sharing link here..." 
            class="bg-transparent outline-none w-full text-gray-700 placeholder-gray-400 font-medium"
          >
        </div>
      </div>

      <!-- Submit -->
      <div class="pt-6 flex flex-col items-center gap-4">
        <button
          @click="submitData"
          :disabled="isUploading"
          class="w-full max-w-xs px-8 py-4 rounded-full bg-dark-active text-white shadow-lg shadow-black/20 hover:shadow-xl transition-all hover:-translate-y-0.5 font-semibold tracking-wide disabled:opacity-50 disabled:cursor-not-allowed flex-center gap-2"
        >
          <div v-if="isUploading" class="i-carbon-circle-dash animate-spin"></div>
          {{ isUploading ? (uploadPhase === 'processing' ? 'Processing...' : 'Uploading...') : 'Upload Work Data' }}
        </button>

        <!-- Progress bar -->
        <div v-if="isUploading" class="w-full max-w-xs flex flex-col gap-1.5">
          <div class="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
            <!-- Determinate bar for file upload -->
            <div v-if="selectedFile && uploadPhase === 'uploading'"
              class="h-full bg-[#0071e3] rounded-full transition-all duration-300"
              :style="{ width: uploadProgress + '%' }">
            </div>
            <!-- Indeterminate animated bar for sheet fetch / server processing -->
            <div v-else
              class="h-full bg-[#0071e3] rounded-full animate-indeterminate">
            </div>
          </div>
          <p class="text-xs text-center text-gray-400 font-medium">
            <template v-if="uploadPhase === 'uploading'">Uploading file… {{ uploadProgress }}%</template>
            <template v-else>Fetching &amp; parsing sheet — this may take a few seconds</template>
          </p>
        </div>

        <div v-if="uploadStatus" class="w-full max-w-sm rounded-xl px-4 py-3 flex items-start gap-3"
          :class="{
            'bg-green-50 border border-green-200': uploadStatusType === 'created',
            'bg-blue-50 border border-blue-200':   uploadStatusType === 'updated',
            'bg-gray-50 border border-gray-200':   uploadStatusType === 'no_changes',
            'bg-red-50 border border-red-200':     uploadStatusType === 'error',
          }">
          <div class="mt-0.5 flex-shrink-0 text-base"
            :class="{
              'i-carbon-checkmark-filled text-green-500': uploadStatusType === 'created',
              'i-carbon-update-now text-blue-500':        uploadStatusType === 'updated',
              'i-carbon-information text-gray-400':       uploadStatusType === 'no_changes',
              'i-carbon-warning-filled text-red-500':     uploadStatusType === 'error',
            }">
          </div>
          <p class="text-sm font-medium"
            :class="{
              'text-green-700': uploadStatusType === 'created',
              'text-blue-700':  uploadStatusType === 'updated',
              'text-gray-600':  uploadStatusType === 'no_changes',
              'text-red-600':   uploadStatusType === 'error',
            }">
            {{ uploadStatus }}
          </p>
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
@keyframes indeterminate {
  0%   { transform: translateX(-100%) scaleX(0.4); }
  50%  { transform: translateX(50%)   scaleX(0.6); }
  100% { transform: translateX(200%)  scaleX(0.4); }
}
.animate-indeterminate {
  width: 60%;
  animation: indeterminate 1.4s ease-in-out infinite;
  transform-origin: left center;
}
</style>
