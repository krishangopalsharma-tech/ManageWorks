<script setup>
import { ref } from 'vue'
import axios from 'axios'

const fileInput = ref(null)
const selectedFile = ref(null)
const sheetLink = ref('')
const isUploading = ref(false)
const uploadStatus = ref('')

const handleFileSelect = (e) => {
  const file = e.target.files[0]
  if (file && (file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))) {
    selectedFile.value = file
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
  uploadStatus.value = 'Uploading...'

  const formData = new FormData()
  if (selectedFile.value) {
    formData.append('file', selectedFile.value)
  }
  if (sheetLink.value) {
    formData.append('link', sheetLink.value)
  }

  try {
    const apiUrl = '/api/add-work/upload/'
    const response = await axios.post(apiUrl, formData)
    uploadStatus.value = `Success: Uploaded document`
    selectedFile.value = null
    sheetLink.value = ''
  } catch (error) {
    console.error(error)
    if (error.response && error.response.data && error.response.data.error) {
      uploadStatus.value = error.response.data.error
    } else {
      uploadStatus.value = 'Failed to upload document.'
    }
  } finally {
    isUploading.value = false
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
          {{ isUploading ? 'Processing...' : 'Upload Work Data' }}
        </button>
        
        <p v-if="uploadStatus" class="text-sm font-medium" :class="uploadStatus.startsWith('Success') ? 'text-green-600' : 'text-red-500'">
          {{ uploadStatus }}
        </p>
      </div>

    </div>
  </div>
</template>
