<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const sheets  = ref([])
const loading = ref(false)
const saving  = ref(false)
const error   = ref('')

const form = ref({ name: '', sheet_url: '', is_active: true })
const editingId = ref(null)
const showForm  = ref(false)

const loadSheets = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/settings/site-gsheet/sheets/')
    sheets.value = res.data
  } catch {
    error.value = 'Failed to load sheets.'
  } finally {
    loading.value = false
  }
}

const openAdd = () => {
  form.value  = { name: '', sheet_url: '', is_active: true }
  editingId.value = null
  showForm.value  = true
}

const openEdit = (sheet) => {
  form.value  = { name: sheet.name, sheet_url: sheet.sheet_url, is_active: sheet.is_active }
  editingId.value = sheet.id
  showForm.value  = true
}

const save = async () => {
  saving.value = true
  error.value  = ''
  try {
    if (editingId.value) {
      const res = await axios.put(`/api/settings/site-gsheet/sheets/${editingId.value}/`, form.value)
      const idx = sheets.value.findIndex(s => s.id === editingId.value)
      if (idx !== -1) sheets.value[idx] = res.data
    } else {
      const res = await axios.post('/api/settings/site-gsheet/sheets/', form.value)
      sheets.value.push(res.data)
    }
    showForm.value = false
  } catch (e) {
    error.value = e.response?.data ? JSON.stringify(e.response.data) : 'Save failed.'
  } finally {
    saving.value = false
  }
}

const remove = async (id) => {
  if (!confirm('Delete this sheet link?')) return
  try {
    await axios.delete(`/api/settings/site-gsheet/sheets/${id}/`)
    sheets.value = sheets.value.filter(s => s.id !== id)
  } catch {
    error.value = 'Delete failed.'
  }
}

onMounted(loadSheets)
</script>

<template>
  <div class="bg-white rounded-2xl soft-shadow h-full w-full flex flex-col overflow-hidden">

    <!-- Header -->
    <div class="flex-shrink-0 px-8 pt-7 pb-5 border-b border-gray-100">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-gray-900 tracking-tight mb-1">Site GSheet</h1>
          <p class="text-gray-400 text-sm font-medium">Link Google Sheets for Site Register monitoring.</p>
        </div>
        <button
          @click="openAdd"
          class="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#1D5F5E] hover:bg-[#174E4D] text-white text-sm font-semibold transition-colors"
        >
          <div class="i-carbon-add text-sm"></div>
          Add Sheet
        </button>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto px-8 py-6 flex flex-col gap-5">

      <!-- Error -->
      <div v-if="error" class="flex items-center gap-2 px-4 py-3 rounded-xl text-sm text-red-700 bg-red-50 border border-red-200">
        <div class="i-carbon-warning-alt shrink-0"></div>{{ error }}
      </div>

      <!-- Add / Edit form -->
      <div
        v-if="showForm"
        class="bg-white border border-gray-200 rounded-2xl p-6 flex flex-col gap-4 soft-shadow"
      >
        <h2 class="text-sm font-bold text-gray-900">{{ editingId ? 'Edit Sheet' : 'Add Sheet' }}</h2>
        <div class="flex flex-col gap-3">
          <div class="flex flex-col gap-1">
            <label class="text-[9px] font-bold text-gray-400 uppercase tracking-widest">Name</label>
            <input
              v-model="form.name"
              placeholder="e.g. Site A Register"
              class="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm text-gray-700 font-medium bg-gray-50 focus:bg-white focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 outline-none transition-all"
            />
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-[9px] font-bold text-gray-400 uppercase tracking-widest">Google Sheet URL</label>
            <input
              v-model="form.sheet_url"
              placeholder="https://docs.google.com/spreadsheets/d/..."
              class="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm text-gray-700 font-medium bg-gray-50 focus:bg-white focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 outline-none transition-all"
            />
          </div>
          <label class="flex items-center gap-2 text-sm text-gray-700 font-medium cursor-pointer select-none">
            <input type="checkbox" v-model="form.is_active" class="rounded accent-[#1D5F5E]" />
            Active
          </label>
        </div>
        <div class="flex gap-3 pt-1">
          <button
            @click="save"
            :disabled="saving"
            class="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#1D5F5E] hover:bg-[#174E4D] text-white text-sm font-semibold transition-colors disabled:opacity-50"
          >
            <div v-if="saving" class="i-carbon-circle-dash animate-spin text-xs"></div>
            {{ saving ? 'Saving…' : 'Save' }}
          </button>
          <button
            @click="showForm = false"
            class="px-4 py-2 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="flex items-center gap-2 text-sm text-gray-400 py-8">
        <div class="i-carbon-circle-dash animate-spin text-lg"></div> Loading…
      </div>

      <!-- Empty state -->
      <div
        v-else-if="!loading && sheets.length === 0"
        class="flex flex-col items-center justify-center py-24 text-center"
      >
        <div class="i-carbon-link text-5xl text-gray-200 mb-4"></div>
        <p class="text-sm font-semibold text-gray-400">No sheets linked yet.</p>
        <p class="text-xs text-gray-400 mt-1">Click <strong>Add Sheet</strong> to link a Google Sheet.</p>
      </div>

      <!-- Sheets table -->
      <div v-else class="bg-white border border-gray-200 rounded-2xl soft-shadow overflow-hidden">
        <table class="w-full">
          <thead>
            <tr class="bg-gray-50 border-b border-gray-100">
              <th class="text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest px-5 py-3">Name</th>
              <th class="text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest px-5 py-3">Sheet ID</th>
              <th class="text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest px-5 py-3">Status</th>
              <th class="text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest px-5 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="sheet in sheets"
              :key="sheet.id"
              class="border-b border-gray-50 hover:bg-accent-soft/40 transition-colors"
            >
              <td class="px-5 py-3.5 text-sm font-semibold text-gray-800">{{ sheet.name }}</td>
              <td class="px-5 py-3.5 font-mono text-xs text-gray-500">{{ sheet.sheet_id }}</td>
              <td class="px-5 py-3.5">
                <span
                  class="text-[11px] font-bold px-2 py-0.5 rounded-full"
                  :class="sheet.is_active
                    ? 'bg-[#1D5F5E]/10 text-[#1D5F5E]'
                    : 'bg-gray-100 text-gray-400'"
                >
                  {{ sheet.is_active ? 'Active' : 'Inactive' }}
                </span>
              </td>
              <td class="px-5 py-3.5">
                <div class="flex items-center gap-3">
                  <button
                    @click="openEdit(sheet)"
                    class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-xs font-semibold text-gray-600 hover:bg-gray-50 hover:border-[#1D5F5E] hover:text-[#1D5F5E] transition-colors"
                  >
                    <div class="i-carbon-edit text-xs"></div> Edit
                  </button>
                  <button
                    @click="remove(sheet.id)"
                    class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-200 text-xs font-semibold text-red-500 bg-red-50 hover:bg-red-100 transition-colors"
                  >
                    <div class="i-carbon-trash-can text-xs"></div> Delete
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

    </div>
  </div>
</template>
