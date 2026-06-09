<script setup>
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'

const logs    = ref([])
const loading = ref(true)
const error   = ref('')
const search  = ref('')

const fmtDateTime = (val) => {
  if (!val) return '—'
  const d = new Date(val)
  return d.toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

async function load() {
  loading.value = true
  error.value   = ''
  try {
    const { data } = await axios.get('/api/delete-log/')
    logs.value = data
  } catch (e) {
    error.value = e.response?.data?.error || 'Failed to load delete log.'
  } finally {
    loading.value = false
  }
}

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return logs.value
  return logs.value.filter(l =>
    (l.loa_number      || '').toLowerCase().includes(q) ||
    (l.name_of_work    || '').toLowerCase().includes(q) ||
    (l.contractor_name || '').toLowerCase().includes(q) ||
    (l.deleted_by      || '').toLowerCase().includes(q) ||
    (l.reason          || '').toLowerCase().includes(q)
  )
})

onMounted(load)
</script>

<template>
  <div class="bg-white rounded-2xl soft-shadow h-full w-full flex flex-col overflow-hidden">

    <!-- Header -->
    <div class="flex-shrink-0 px-8 pt-7 pb-5 border-b border-gray-100">
      <h1 class="text-2xl font-bold text-gray-900 tracking-tight mb-1">Delete Log</h1>
      <p class="text-gray-400 text-sm font-medium">Record of all LOAs deleted by admins, including reasons.</p>

      <!-- Search -->
      <div class="mt-4 flex items-center bg-gray-50 border border-gray-200 rounded-2xl px-5 py-3 focus-within:ring-2 focus-within:ring-[#1D5F5E]/20 focus-within:border-[#1D5F5E] focus-within:bg-white transition-all max-w-xl">
        <div class="i-carbon-search text-gray-400 text-lg mr-3 shrink-0"></div>
        <input
          v-model="search"
          type="text"
          placeholder="Search by LOA, work name, contractor, deleted by, reason…"
          class="flex-1 bg-transparent text-sm text-gray-800 placeholder-gray-400 outline-none"
        />
        <button v-if="search" @click="search = ''" class="ml-2 text-gray-400 hover:text-gray-600">
          <div class="i-carbon-close text-sm"></div>
        </button>
      </div>
    </div>

    <!-- Body -->
    <div class="flex-1 overflow-y-auto px-8 py-6">

      <!-- Loading -->
      <div v-if="loading" class="flex items-center justify-center h-40 text-gray-400 text-sm gap-2">
        <div class="i-carbon-circle-dash animate-spin text-xl"></div>
        Loading…
      </div>

      <!-- Error -->
      <div v-else-if="error" class="flex items-center gap-2 text-red-500 text-sm">
        <div class="i-carbon-warning text-base"></div>
        {{ error }}
      </div>

      <!-- Empty -->
      <div v-else-if="filtered.length === 0" class="flex flex-col items-center justify-center h-40 text-gray-400 text-sm gap-2">
        <div class="i-carbon-document text-3xl"></div>
        <span>{{ search ? 'No results match your search.' : 'No LOAs have been deleted yet.' }}</span>
      </div>

      <!-- Table -->
      <div v-else class="overflow-x-auto rounded-2xl border border-gray-100">
        <table class="w-full text-sm text-gray-700">
          <thead>
            <tr class="bg-gray-50 text-xs font-semibold text-gray-500 uppercase tracking-wider">
              <th class="px-5 py-3 text-left whitespace-nowrap">#</th>
              <th class="px-5 py-3 text-left whitespace-nowrap">LOA Number</th>
              <th class="px-5 py-3 text-left">Work Name</th>
              <th class="px-5 py-3 text-left whitespace-nowrap">Contractor</th>
              <th class="px-5 py-3 text-left whitespace-nowrap">Deleted By</th>
              <th class="px-5 py-3 text-left">Reason</th>
              <th class="px-5 py-3 text-left whitespace-nowrap">Deleted At</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr
              v-for="(log, idx) in filtered"
              :key="log.id"
              class="hover:bg-gray-50 transition-colors"
            >
              <td class="px-5 py-3 text-gray-400 font-mono text-xs">{{ idx + 1 }}</td>
              <td class="px-5 py-3 font-semibold text-gray-800 whitespace-nowrap">
                {{ log.loa_number || '—' }}
              </td>
              <td class="px-5 py-3 text-gray-600 max-w-xs">
                <span class="line-clamp-2">{{ log.name_of_work || '—' }}</span>
              </td>
              <td class="px-5 py-3 whitespace-nowrap text-gray-600">{{ log.contractor_name || '—' }}</td>
              <td class="px-5 py-3 whitespace-nowrap">
                <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#EEF4F3] text-[#1D5F5E] text-xs font-semibold">
                  <div class="i-carbon-user text-xs"></div>
                  {{ log.deleted_by || '—' }}
                </span>
              </td>
              <td class="px-5 py-3 text-gray-600 max-w-sm">
                <span class="line-clamp-3">{{ log.reason }}</span>
              </td>
              <td class="px-5 py-3 whitespace-nowrap text-gray-500 text-xs">{{ fmtDateTime(log.deleted_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Count -->
      <p v-if="!loading && !error && logs.length > 0" class="mt-3 text-xs text-gray-400">
        {{ filtered.length }} of {{ logs.length }} record{{ logs.length !== 1 ? 's' : '' }}
      </p>
    </div>

  </div>
</template>
