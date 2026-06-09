<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

// ── State ─────────────────────────────────────────────────────────────────────
const works        = ref([])
const selectedWork = ref(null)
const bills        = ref([])
const summary      = ref([])
const loading      = ref(false)
const summaryLoading = ref(false)
const error        = ref('')
const worksLoading = ref(false)

// Upload
const fileInput    = ref(null)
const uploading    = ref(false)
const preview      = ref(null)
const previewError = ref('')
const saveError    = ref('')
const saveSuccess  = ref('')

// LOA search
const workSearch = ref('')

// ── Fetch works list ──────────────────────────────────────────────────────────
async function loadWorks() {
  worksLoading.value = true
  try {
    const { data } = await axios.get('/api/financial-progress/works/')
    works.value = data
  } catch {
    works.value = []
  } finally {
    worksLoading.value = false
  }
}

// ── Fetch bills and summary for selected work ─────────────────────────────────
async function loadBills() {
  if (!selectedWork.value) return
  loading.value = true
  error.value   = ''
  try {
    const { data } = await axios.get('/api/financial-progress/bills/', {
      params: { work_id: selectedWork.value.id },
    })
    bills.value = data
  } catch (e) {
    error.value = e.response?.data?.error || 'Failed to load bills.'
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  if (!selectedWork.value) return
  summaryLoading.value = true
  try {
    const { data } = await axios.get('/api/financial-progress/summary/', {
      params: { work_id: selectedWork.value.id },
    })
    summary.value = data
  } catch {
    summary.value = []
  } finally {
    summaryLoading.value = false
  }
}

function selectWork(w) {
  if (selectedWork.value?.id === w.id) return
  selectedWork.value = w
  bills.value        = []
  summary.value      = []
  preview.value      = null
  previewError.value = ''
  saveError.value    = ''
  saveSuccess.value  = ''
  loadBills()
  loadSummary()
}

// ── Filtered LOA list ─────────────────────────────────────────────────────────
const filteredWorks = computed(() => {
  const q = workSearch.value.trim().toLowerCase()
  if (!q) return works.value
  return works.value.filter(w =>
    (w.loa_number      || '').toLowerCase().includes(q) ||
    (w.name_of_work    || '').toLowerCase().includes(q) ||
    (w.contractor_name || '').toLowerCase().includes(q)
  )
})

// ── Upload & parse ────────────────────────────────────────────────────────────
function triggerUpload() {
  preview.value      = null
  previewError.value = ''
  saveError.value    = ''
  saveSuccess.value  = ''
  fileInput.value.click()
}

async function onFileChange(e) {
  const file = e.target.files[0]
  if (!file) return
  e.target.value = ''

  uploading.value    = true
  previewError.value = ''

  const form = new FormData()
  form.append('file', file)
  if (selectedWork.value) form.append('work_id', selectedWork.value.id)

  try {
    const { data } = await axios.post('/api/financial-progress/parse/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    preview.value = data
  } catch (e) {
    previewError.value = e.response?.data?.error || 'Failed to parse PDF.'
  } finally {
    uploading.value = false
  }
}

// ── Confirm save ──────────────────────────────────────────────────────────────
async function confirmSave() {
  if (!preview.value || !selectedWork.value) return
  saveError.value   = ''
  saveSuccess.value = ''
  uploading.value   = true

  try {
    await axios.post('/api/financial-progress/bills/', {
      work_id:          selectedWork.value.id,
      bill_number:      preview.value.bill_number,
      bill_date:        preview.value.bill_date || null,
      loa_number:       preview.value.loa_number,
      agreement_number: preview.value.agreement_number,
      items:            preview.value.items,
    })
    saveSuccess.value = `Bill "${preview.value.bill_number}" saved successfully.`
    preview.value     = null
    await loadBills()
    await loadSummary()
  } catch (e) {
    saveError.value = e.response?.data?.error || 'Failed to save bill.'
  } finally {
    uploading.value = false
  }
}

// ── Delete bill ───────────────────────────────────────────────────────────────
async function deleteBill(id, billNum) {
  if (!confirm(`Delete bill "${billNum}"? This will remove its financial data.`)) return
  try {
    await axios.delete(`/api/financial-progress/bills/${id}/`)
    await loadBills()
    await loadSummary()
  } catch (e) {
    error.value = e.response?.data?.error || 'Failed to delete.'
  }
}

// ── Formatting ────────────────────────────────────────────────────────────────
const fmt    = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 })
const fmtAmt = (v) => v != null ? '₹' + fmt.format(v) : '—'

function progressColor(pct) {
  if (pct >= 100) return '#22c55e'
  if (pct >= 75)  return '#3b82f6'
  if (pct >= 50)  return '#f59e0b'
  return '#ef4444'
}

function schedLabel(name) {
  const map    = { A: 'Supply', B: 'Execution/Installation' }
  const letter = name?.[0]?.toUpperCase() || ''
  const num    = name?.slice(1) || ''
  return `Schedule ${name} — ${map[letter] || ''} (Part ${num})`
}

onMounted(loadWorks)
</script>

<template>
  <div class="bg-white rounded-2xl soft-shadow h-full w-full flex overflow-hidden">

    <!-- ── Left panel: LOA list ──────────────────────────────────────────────── -->
    <div class="flex-shrink-0 w-72 border-r border-gray-100 flex flex-col h-full">

      <!-- Panel header -->
      <div class="px-5 pt-6 pb-4 border-b border-gray-100 flex-shrink-0">
        <h2 class="text-sm font-bold text-gray-700 uppercase tracking-wider mb-3">Select Work</h2>
        <!-- Search -->
        <div class="flex items-center bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 gap-2 focus-within:border-[#1D5F5E] focus-within:ring-2 focus-within:ring-[#1D5F5E]/10 transition-all">
          <div class="i-carbon-search text-gray-400 text-sm flex-shrink-0"></div>
          <input
            v-model="workSearch"
            type="text"
            placeholder="LOA, work name, contractor…"
            class="bg-transparent outline-none text-xs text-gray-700 placeholder-gray-400 w-full font-medium"
          />
          <button v-if="workSearch" @click="workSearch = ''" class="text-gray-300 hover:text-gray-500 transition-colors">
            <div class="i-carbon-close text-xs"></div>
          </button>
        </div>
      </div>

      <!-- LOA list -->
      <div class="flex-1 overflow-y-auto py-2 px-2" style="scrollbar-width: thin;">
        <div v-if="worksLoading" class="flex items-center gap-2 px-3 py-4 text-gray-400 text-xs">
          <div class="i-carbon-circle-dash animate-spin"></div> Loading…
        </div>
        <div v-else-if="filteredWorks.length === 0" class="text-center px-3 py-6 text-xs text-gray-400">
          No works found.
        </div>
        <div
          v-for="w in filteredWorks"
          :key="w.id"
          @click="selectWork(w)"
          class="relative px-3 py-2.5 rounded-xl cursor-pointer border transition-all mb-1.5 flex-shrink-0"
          :class="selectedWork?.id === w.id
            ? 'bg-[#1D5F5E]/5 border-[#1D5F5E]'
            : 'bg-white border-gray-200 hover:border-[#1D5F5E] hover:bg-[#1D5F5E]/5'"
        >
          <div class="flex items-start justify-between gap-1.5">
            <div class="min-w-0 flex-1">
              <p class="text-xs font-bold truncate"
                :class="selectedWork?.id === w.id ? 'text-[#1D5F5E]' : 'text-gray-900'">
                {{ w.loa_number || '—' }}
              </p>
              <p v-if="w.contractor_name" class="text-[11px] text-gray-400 truncate mt-0.5">{{ w.contractor_name }}</p>
            </div>
            <div
              class="w-4 h-4 rounded border-2 flex-shrink-0 flex items-center justify-center mt-0.5 transition-all"
              :class="selectedWork?.id === w.id ? 'bg-[#1D5F5E] border-[#1D5F5E]' : 'border-gray-300 bg-white'"
            >
              <div v-if="selectedWork?.id === w.id" class="i-carbon-checkmark text-white text-[10px]"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Right panel: content ──────────────────────────────────────────────── -->
    <div class="flex-1 flex flex-col overflow-hidden">

      <!-- Top bar -->
      <div class="flex-shrink-0 px-7 pt-6 pb-5 border-b border-gray-100 flex items-center justify-between gap-4">
        <div>
          <h1 class="text-2xl font-bold text-gray-900 tracking-tight">Financial Progress</h1>
          <p class="text-gray-400 text-sm font-medium mt-0.5">
            <template v-if="selectedWork">
              <span class="text-[#1D5F5E] font-semibold">{{ selectedWork.loa_number }}</span>
              <span v-if="selectedWork.name_of_work" class="ml-2 text-gray-400 truncate max-w-sm inline-block align-bottom">— {{ selectedWork.name_of_work }}</span>
            </template>
            <template v-else>Select a work to view financial progress.</template>
          </p>
        </div>
        <button
          v-if="selectedWork"
          @click="triggerUpload"
          :disabled="uploading"
          class="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all flex-shrink-0"
          style="background: #1D5F5E; color: white;"
        >
          <div v-if="uploading" class="i-carbon-circle-dash animate-spin text-base"></div>
          <div v-else class="i-carbon-upload text-base"></div>
          {{ uploading ? 'Processing…' : 'Upload Bill PDF' }}
        </button>
        <input ref="fileInput" type="file" accept=".pdf" class="hidden" @change="onFileChange" />
      </div>

      <!-- Body -->
      <div class="flex-1 overflow-y-auto px-7 py-6 space-y-6">

        <!-- No work selected -->
        <div v-if="!selectedWork" class="flex flex-col items-center justify-center h-48 text-gray-300 gap-3">
          <div class="i-carbon-money text-5xl"></div>
          <p class="text-sm font-medium text-gray-400">Select a work from the left panel.</p>
        </div>

        <template v-else>

          <!-- ── Uploaded bills strip ───────────────────────────────────── -->
          <div>
            <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Uploaded Bills</h2>
            <div v-if="loading" class="flex items-center gap-2 text-gray-400 text-sm">
              <div class="i-carbon-circle-dash animate-spin"></div> Loading…
            </div>
            <div v-else-if="bills.length === 0" class="text-sm text-gray-400">No bills uploaded yet.</div>
            <div v-else class="flex flex-wrap gap-2">
              <div
                v-for="b in bills"
                :key="b.id"
                class="group flex items-center gap-2 px-4 py-2 rounded-xl bg-gray-50 border border-gray-200 text-sm"
              >
                <div class="i-carbon-document text-gray-400 text-base"></div>
                <div>
                  <p class="font-semibold text-gray-800 text-xs">{{ b.bill_number }}</p>
                  <p class="text-xs text-gray-400">{{ b.bill_date || '—' }}</p>
                </div>
                <button
                  @click="deleteBill(b.id, b.bill_number)"
                  class="ml-1 opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600 transition-all"
                  title="Delete bill"
                >
                  <div class="i-carbon-trash-can text-sm"></div>
                </button>
              </div>
            </div>
          </div>

          <!-- ── Status messages ────────────────────────────────────────── -->
          <div v-if="previewError" class="flex items-center gap-2 text-red-500 text-sm p-4 bg-red-50 rounded-xl">
            <div class="i-carbon-warning text-base"></div>
            {{ previewError }}
          </div>
          <div v-if="saveSuccess" class="flex items-center gap-2 text-green-600 text-sm p-4 bg-green-50 rounded-xl">
            <div class="i-carbon-checkmark-filled text-base"></div>
            {{ saveSuccess }}
          </div>
          <div v-if="saveError" class="flex items-center gap-2 text-red-500 text-sm p-4 bg-red-50 rounded-xl">
            <div class="i-carbon-warning text-base"></div>
            {{ saveError }}
          </div>

          <!-- ── Upload preview ─────────────────────────────────────────── -->
          <div v-if="preview" class="border border-[#1D5F5E]/30 rounded-2xl overflow-hidden">
            <div class="bg-[#EEF4F3] px-6 py-4 flex items-center justify-between flex-wrap gap-3">
              <div>
                <p class="text-sm font-bold text-[#1D5F5E]">{{ preview.bill_number || 'Parsed Bill' }}</p>
                <p class="text-xs text-gray-500">{{ preview.bill_date }} · LOA: {{ preview.loa_number }}</p>
                <p v-if="preview.warnings?.length" class="text-xs text-amber-600 mt-1">
                  ⚠ {{ preview.warnings.join(' | ') }}
                </p>
              </div>
              <div class="flex gap-2">
                <button @click="preview = null" class="px-4 py-2 rounded-xl text-sm font-semibold text-gray-600 bg-white border border-gray-200 hover:bg-gray-50 transition-colors">
                  Cancel
                </button>
                <button
                  @click="confirmSave"
                  :disabled="uploading"
                  class="px-4 py-2 rounded-xl text-sm font-semibold text-white transition-colors"
                  style="background: #1D5F5E;"
                >
                  {{ uploading ? 'Saving…' : `Save Bill (${preview.items?.length || 0} items)` }}
                </button>
              </div>
            </div>
            <div class="overflow-x-auto max-h-72">
              <table class="w-full text-xs text-gray-700">
                <thead>
                  <tr class="bg-gray-50 text-xs font-semibold text-gray-500 uppercase tracking-wider border-b border-gray-100">
                    <th class="px-4 py-2 text-left">Schedule</th>
                    <th class="px-4 py-2 text-left">Item</th>
                    <th class="px-4 py-2 text-left">Unit</th>
                    <th class="px-4 py-2 text-right">Agmt Rate</th>
                    <th class="px-4 py-2 text-right">Curr Qty</th>
                    <th class="px-4 py-2 text-right">Contract Value</th>
                    <th class="px-4 py-2 text-right">Total Paid</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-50">
                  <tr v-for="(item, idx) in preview.items" :key="idx" class="hover:bg-gray-50">
                    <td class="px-4 py-2 font-mono font-semibold text-[#1D5F5E]">{{ item.schedule_name }}</td>
                    <td class="px-4 py-2">{{ item.item_number }}</td>
                    <td class="px-4 py-2 text-gray-500">{{ item.unit }}</td>
                    <td class="px-4 py-2 text-right">{{ fmt.format(item.agreement_rate) }}</td>
                    <td class="px-4 py-2 text-right">{{ item.current_agmt_qty }}</td>
                    <td class="px-4 py-2 text-right">{{ fmtAmt(item.current_agmt_qty * item.agreement_rate) }}</td>
                    <td class="px-4 py-2 text-right font-semibold">{{ fmtAmt(item.amt_total) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- ── Financial summary ──────────────────────────────────────── -->
          <div>
            <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">Item-wise Financial Progress</h2>

            <div v-if="summaryLoading" class="flex items-center gap-2 text-gray-400 text-sm">
              <div class="i-carbon-circle-dash animate-spin"></div> Loading…
            </div>

            <div v-else-if="summary.length === 0" class="text-sm text-gray-400">
              Upload a bill to see financial progress.
            </div>

            <div v-else class="space-y-6">
              <div v-for="sched in summary" :key="sched.schedule_name" class="rounded-2xl border border-gray-100 overflow-hidden">
                <div class="bg-gray-50 px-5 py-3 flex items-center justify-between flex-wrap gap-2">
                  <span class="font-bold text-gray-800 text-sm">{{ schedLabel(sched.schedule_name) }}</span>
                  <div class="flex items-center gap-4 text-xs text-gray-500">
                    <span>Contract: <strong class="text-gray-700">{{ fmtAmt(sched.contract_value) }}</strong></span>
                    <span>Paid: <strong class="text-gray-700">{{ fmtAmt(sched.amt_total) }}</strong></span>
                    <span
                      class="px-2.5 py-1 rounded-full text-xs font-bold"
                      :style="{ background: progressColor(sched.progress_pct) + '22', color: progressColor(sched.progress_pct) }"
                    >{{ sched.progress_pct }}%</span>
                  </div>
                </div>
                <table class="w-full text-sm">
                  <thead>
                    <tr class="text-xs font-semibold text-gray-400 uppercase tracking-wider border-b border-gray-100">
                      <th class="px-5 py-2 text-left w-8">#</th>
                      <th class="px-5 py-2 text-left">Description</th>
                      <th class="px-5 py-2 text-right whitespace-nowrap">Contract</th>
                      <th class="px-5 py-2 text-right whitespace-nowrap">Paid</th>
                      <th class="px-5 py-2 text-left min-w-[180px]">Progress</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-gray-50">
                    <tr v-for="item in sched.items" :key="item.id" class="hover:bg-gray-50 transition-colors">
                      <td class="px-5 py-3 text-xs font-mono text-gray-400">{{ item.item_number }}</td>
                      <td class="px-5 py-3 max-w-xs">
                        <p class="text-sm font-medium text-gray-800 truncate" :title="item.description">
                          {{ item.description || '—' }}
                        </p>
                        <p class="text-xs text-gray-400">{{ item.unit }}</p>
                      </td>
                      <td class="px-5 py-3 text-right text-sm text-gray-600 whitespace-nowrap">
                        {{ fmtAmt(item.contract_value) }}
                      </td>
                      <td class="px-5 py-3 text-right text-sm font-semibold text-gray-800 whitespace-nowrap">
                        {{ fmtAmt(item.amt_total) }}
                      </td>
                      <td class="px-5 py-3">
                        <div class="flex items-center gap-2">
                          <div class="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
                            <div
                              class="h-2 rounded-full transition-all duration-500"
                              :style="{ width: item.progress_pct + '%', background: progressColor(item.progress_pct) }"
                            ></div>
                          </div>
                          <span
                            class="text-xs font-bold min-w-[38px] text-right"
                            :style="{ color: progressColor(item.progress_pct) }"
                          >{{ item.progress_pct }}%</span>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

        </template>
      </div>
    </div>

  </div>
</template>
