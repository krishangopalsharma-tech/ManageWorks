<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'

const fmtAmt = (val) => {
  if (!val && val !== 0) return '—'
  return '₹' + Number(val).toLocaleString('en-IN', { maximumFractionDigits: 2 })
}
const fmtDateTime = (val) => {
  if (!val) return '—'
  const d = new Date(val)
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}
const uid = () => Math.random().toString(36).slice(2, 10)

// ── Step state ────────────────────────────────────────────────────────────
// 1: pick work  2: MB header (number + notes)  3: items  4: review
const step = ref(1)

const workQuery    = ref('')
const workResults  = ref([])
const selectedWork = ref(null)
const isSearchingWorks = ref(false)

const mbNumber = ref('')
const notes    = ref('')

const mbNumberDisplay = computed(() => {
  const v = String(mbNumber.value || '').trim()
  if (!v) return ''
  return /^\d+$/.test(v) ? `MB${v.padStart(2, '0')}` : v
})

const scheduleFilter = ref('')  // '', 'A', 'B'
const itemQuery      = ref('')
const itemResults    = ref([])
const isSearchingItems = ref(false)

// pickedItems: array of { key, work_item, serial_number, item_desc, schedule, qty_default, unit, rate, quantity, prior_percentage, current_percentage, selected }
const pickedItems = ref([])
const bulkPct     = ref('')

const savedRecords = ref([])
const summary      = ref(null)
const saveStatus   = ref('')
const isSaving     = ref(false)

// ── Work search ───────────────────────────────────────────────────────────
let workSearchTimer = null
watch(workQuery, (q) => {
  clearTimeout(workSearchTimer)
  workSearchTimer = setTimeout(() => searchWorks(q), 250)
})

const searchWorks = async (q) => {
  isSearchingWorks.value = true
  try {
    const { data } = await axios.get('/api/mb-details/works/', { params: { q } })
    workResults.value = data
  } catch (e) { console.error(e) }
  finally { isSearchingWorks.value = false }
}

const pickWork = (w) => {
  selectedWork.value = w
  step.value = 2
}

// ── MB header → items ─────────────────────────────────────────────────────
const canProceedToItems = computed(() => String(mbNumber.value || '').trim().length > 0)

const goToItems = () => {
  if (!canProceedToItems.value) return
  step.value = 3
}

// ── Item search ───────────────────────────────────────────────────────────
let itemSearchTimer = null
watch([itemQuery, scheduleFilter], () => {
  clearTimeout(itemSearchTimer)
  itemSearchTimer = setTimeout(searchItems, 250)
})

const searchItems = async () => {
  if (!selectedWork.value) return
  isSearchingItems.value = true
  try {
    const { data } = await axios.get(
      `/api/mb-details/works/${selectedWork.value.id}/items/`,
      { params: { schedule: scheduleFilter.value, q: itemQuery.value } }
    )
    itemResults.value = data
  } catch (e) { console.error(e) }
  finally { isSearchingItems.value = false }
}

const addItem = async (item) => {
  let priorPct = 0
  try {
    const { data } = await axios.get(`/api/mb-details/items/${item.id}/prior/`)
    priorPct = data.suggested_prior_pct || 0
  } catch (e) { console.error(e) }

  pickedItems.value.push({
    key:                uid(),
    work_item:          item.id,
    serial_number:      item.serial_number,
    item_desc:          item.item_desc,
    schedule:           item.schedule,
    qty_default:        item.qty,
    unit:               item.unit,
    rate:               item.unit_rate_below || 0,
    quantity:           item.qty || 0,
    prior_percentage:   priorPct,
    current_percentage: 0,
    selected:           true,  // newly added rows are selected by default for bulk %
  })
}

const removeRow = (key) => {
  pickedItems.value = pickedItems.value.filter(r => r.key !== key)
}

// Duplicate a row — split-qty scenario (same item, different prior/current or qty)
const duplicateRow = (row) => {
  pickedItems.value.push({
    ...row,
    key: uid(),
    quantity: 0,
    prior_percentage: 0,
    current_percentage: 0,
    selected: true,
  })
}

const rowAmount = (row) => {
  const qty  = parseFloat(row.quantity) || 0
  const rate = parseFloat(row.rate)     || 0
  const cur  = parseFloat(row.current_percentage) || 0
  const pri  = parseFloat(row.prior_percentage)   || 0
  return Math.round(qty * rate * (cur - pri) / 100 * 100) / 100
}

const mbTotalAmount = computed(() =>
  pickedItems.value.reduce((s, r) => s + rowAmount(r), 0)
)

// ── Bulk percentage apply ─────────────────────────────────────────────────
const selectedCount = computed(() => pickedItems.value.filter(r => r.selected).length)

const selectAll   = () => pickedItems.value.forEach(r => r.selected = true)
const selectNone  = () => pickedItems.value.forEach(r => r.selected = false)

const applyBulkPct = () => {
  const pct = parseFloat(bulkPct.value)
  if (isNaN(pct) || pct <= 0 || pct > 100) return
  pickedItems.value.forEach(r => {
    if (r.selected) r.current_percentage = pct
  })
  // After applying, deselect so next batch is fresh
  pickedItems.value.forEach(r => r.selected = false)
  bulkPct.value = ''
}

// ── Save ──────────────────────────────────────────────────────────────────
const rowIsValid = (r) => {
  const qty = parseFloat(r.quantity) || 0
  const cur = parseFloat(r.current_percentage) || 0
  const pri = parseFloat(r.prior_percentage)   || 0
  return qty > 0 && cur > pri && cur <= 100 && pri >= 0
}

const canReview = computed(() =>
  pickedItems.value.length > 0 && pickedItems.value.every(rowIsValid)
)

const invalidCount = computed(() => pickedItems.value.filter(r => !rowIsValid(r)).length)

const saveMB = async () => {
  if (!canReview.value || !selectedWork.value) return
  isSaving.value = true
  saveStatus.value = ''
  try {
    const payload = {
      work:      selectedWork.value.id,
      mb_number: String(mbNumber.value || '').trim(),
      notes:     notes.value,
      items:     pickedItems.value.map(r => ({
        work_item:          r.work_item,
        quantity:           parseFloat(r.quantity),
        prior_percentage:   parseFloat(r.prior_percentage) || 0,
        current_percentage: parseFloat(r.current_percentage),
      })),
    }
    await axios.post('/api/mb-details/records/', payload)
    saveStatus.value = 'saved'
    await Promise.all([loadRecords(), loadSummary()])
    setTimeout(() => {
      saveStatus.value = ''
      resetFlow()
    }, 1200)
  } catch (e) {
    console.error(e)
    saveStatus.value = e.response?.data?.error || (e.response?.status === 403 ? 'denied' : 'error')
    setTimeout(() => { saveStatus.value = '' }, 3500)
  } finally {
    isSaving.value = false
  }
}

const resetFlow = () => {
  step.value = 1
  workQuery.value = ''
  workResults.value = []
  selectedWork.value = null
  mbNumber.value = ''
  notes.value = ''
  scheduleFilter.value = ''
  itemQuery.value = ''
  itemResults.value = []
  pickedItems.value = []
  bulkPct.value = ''
  searchWorks('')
}

// ── Records / summary ─────────────────────────────────────────────────────
const loadRecords = async () => {
  try {
    const { data } = await axios.get('/api/mb-details/records/')
    savedRecords.value = data
  } catch (e) { console.error(e) }
}

const loadSummary = async () => {
  try {
    const { data } = await axios.get('/api/mb-details/summary/')
    summary.value = data
  } catch (e) { console.error(e) }
}

const deleteRecord = async (id) => {
  if (!confirm('Delete this MB record? This is irreversible.')) return
  try {
    await axios.delete(`/api/mb-details/records/${id}/`)
    await Promise.all([loadRecords(), loadSummary()])
  } catch (e) {
    console.error(e)
    alert(e.response?.status === 403 ? 'Permission denied.' : 'Failed to delete.')
  }
}

onMounted(() => {
  searchWorks('')
  loadRecords()
  loadSummary()
})
</script>

<template>
  <div class="bg-white rounded-2xl soft-shadow h-full w-full flex flex-col overflow-hidden">

    <!-- Header — single row: title + stepper + summary + reset -->
    <div class="flex-shrink-0 px-8 pt-5 pb-4 border-b border-gray-100 flex items-center gap-4 flex-wrap">
      <h1 class="text-xl font-bold text-gray-900 tracking-tight flex-shrink-0">MB Details</h1>

      <!-- Stepper inline -->
      <div class="flex items-center gap-2 flex-1 min-w-0 justify-center">
        <div v-for="(label, i) in ['Select Work', 'MB Header', 'Add Items', 'Review']" :key="i"
          class="flex items-center gap-1.5">
          <div :class="step > i+1 ? 'bg-[#34c759] text-white'
                       : step === i+1 ? 'bg-[#0071e3] text-white shadow shadow-[#0071e3]/30'
                       : 'bg-gray-100 text-gray-400'"
            class="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold transition-all flex-shrink-0">
            <span v-if="step > i+1" class="i-carbon-checkmark text-xs"></span>
            <span v-else>{{ i + 1 }}</span>
          </div>
          <span :class="step === i+1 ? 'text-gray-800' : 'text-gray-400'" class="text-[11px] font-semibold whitespace-nowrap">{{ label }}</span>
          <span v-if="i < 3" class="w-4 h-px bg-gray-200"></span>
        </div>
      </div>

      <div v-if="summary" class="flex items-center gap-2 flex-shrink-0">
        <div class="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5">
          <span class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Billed</span>
          <span class="text-xs font-bold text-gray-800">{{ fmtAmt(summary.mb_total) }}</span>
        </div>
        <div class="flex items-center gap-2 bg-blue-50 border border-blue-100 rounded-lg px-3 py-1.5">
          <span class="text-[10px] font-bold text-blue-600 uppercase tracking-widest">Fin. Progress</span>
          <span class="text-xs font-bold text-blue-700">{{ summary.financial_progress }}%</span>
        </div>
      </div>

      <button v-if="step > 1" @click="resetFlow"
        class="text-xs font-semibold text-gray-500 hover:text-gray-800 px-3 py-1.5 rounded-full bg-gray-100 hover:bg-gray-200 transition-all flex-shrink-0">
        Reset
      </button>
    </div>

    <!-- Body -->
    <div class="flex-1 overflow-y-auto px-8 py-6">

      <!-- ─ Step 1: Select Work ─ -->
      <div v-if="step === 1">
        <div class="flex items-center bg-gray-50 border border-gray-200 rounded-2xl px-5 py-3 focus-within:ring-2 focus-within:ring-[#0071e3]/20 focus-within:border-[#0071e3] focus-within:bg-white transition-all">
          <div class="i-carbon-search text-gray-400 text-base mr-3"></div>
          <input v-model="workQuery" type="text"
            placeholder="Search by LOA, Contractor, Tender, Consignee..."
            class="bg-transparent outline-none w-full text-gray-700 font-medium placeholder-gray-400 text-sm">
          <div v-if="isSearchingWorks" class="i-carbon-circle-dash animate-spin text-gray-400"></div>
        </div>

        <div class="mt-5">
          <p class="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-3">
            {{ workResults.length }} work{{ workResults.length === 1 ? '' : 's' }}
          </p>
          <div v-if="workResults.length === 0" class="py-12 text-center text-xs text-gray-400 font-medium">
            {{ workQuery ? 'No works match.' : 'No works available.' }}
          </div>
          <div v-else class="grid grid-cols-1 gap-2">
            <button v-for="w in workResults" :key="w.id" @click="pickWork(w)"
              class="text-left bg-white border border-gray-200 hover:border-[#0071e3] hover:bg-[#0071e3]/5 rounded-xl px-4 py-3 transition-all group">
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0">
                  <p class="text-sm font-semibold text-gray-900 truncate">{{ w.contractor_name || '—' }}</p>
                  <div class="flex items-center gap-3 flex-wrap mt-1">
                    <span class="text-[11px] font-semibold text-[#0071e3] bg-[#0071e3]/10 px-2 py-0.5 rounded-full">{{ w.loa_number || '—' }}</span>
                    <span class="text-[11px] text-gray-500">Tender: <span class="font-semibold text-gray-700">{{ w.tender_number || '—' }}</span></span>
                    <span class="text-[11px] text-gray-500">Consignee: <span class="font-semibold text-gray-700">{{ w.consignee || '—' }}</span></span>
                  </div>
                </div>
                <div class="i-carbon-chevron-right text-gray-300 group-hover:text-[#0071e3] transition-colors"></div>
              </div>
            </button>
          </div>
        </div>

        <!-- Recent records -->
        <div v-if="savedRecords.length > 0" class="mt-10">
          <p class="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-3">Recent MB Records</p>
          <div class="bg-white border border-gray-200 rounded-2xl overflow-hidden">
            <table class="w-full text-xs">
              <thead class="bg-gray-50 text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
                <tr>
                  <th class="px-4 py-3 text-left">MB</th>
                  <th class="px-4 py-3 text-left">Work</th>
                  <th class="px-4 py-3 text-right w-16">Items</th>
                  <th class="px-4 py-3 text-right w-32">Released</th>
                  <th class="px-4 py-3 text-left w-40">By / When</th>
                  <th class="px-4 py-3 text-center w-16"></th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                <tr v-for="rec in savedRecords" :key="rec.id" class="hover:bg-gray-50/60 transition-colors">
                  <td class="px-4 py-3 font-bold text-gray-800 max-w-[200px] truncate" :title="rec.mb_number">{{ /^\d+$/.test(String(rec.mb_number)) ? 'MB' + String(rec.mb_number).padStart(2, '0') : rec.mb_number }}</td>
                  <td class="px-4 py-3">
                    <p class="font-semibold text-gray-800 truncate">{{ rec.contractor }}</p>
                    <p class="text-[10px] text-gray-400 mt-0.5">{{ rec.work_loa }}</p>
                  </td>
                  <td class="px-4 py-3 text-right font-semibold text-gray-700">{{ rec.items.length }}</td>
                  <td class="px-4 py-3 text-right font-bold text-gray-900">{{ fmtAmt(rec.total_amount) }}</td>
                  <td class="px-4 py-3 text-[11px] text-gray-500">
                    <p class="font-semibold text-gray-700">{{ rec.created_by_username || '—' }}</p>
                    <p class="text-[10px] text-gray-400">{{ fmtDateTime(rec.created_at) }}</p>
                  </td>
                  <td class="px-4 py-3 text-center">
                    <button @click="deleteRecord(rec.id)"
                      class="w-7 h-7 rounded-full bg-gray-100 hover:bg-[#ff3b30]/10 hover:text-[#ff3b30] text-gray-400 flex items-center justify-center transition-all mx-auto">
                      <div class="i-carbon-trash-can text-xs"></div>
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ─ Step 2: MB header ─ -->
      <div v-else-if="step === 2">
        <div class="flex items-center gap-3 mb-6">
          <button @click="step = 1" class="w-9 h-9 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 transition-all">
            <div class="i-carbon-arrow-left"></div>
          </button>
          <div>
            <p class="text-xs font-semibold text-gray-400 uppercase tracking-widest">Selected Work</p>
            <p class="text-sm font-bold text-gray-900">{{ selectedWork?.contractor_name }} · <span class="text-[#0071e3]">{{ selectedWork?.loa_number }}</span></p>
          </div>
        </div>

        <div class="max-w-2xl bg-gray-50/60 border border-gray-200 rounded-2xl p-6">
          <div class="flex flex-col gap-1.5 mb-4">
            <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wide">MB Number / Reference <span class="text-red-400">*</span></label>
            <input v-model="mbNumber" type="text"
              placeholder="e.g. Measurement No. 10384230062214/SSE/TELE/II/ADI/FM/L1/03"
              class="bg-white border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm font-semibold text-gray-800 outline-none focus:border-[#0071e3] focus:ring-2 focus:ring-[#0071e3]/10 transition-all">
            <p class="text-[10px] text-gray-400 mt-0.5">Free text. Must be unique per work.</p>
          </div>

          <div class="flex flex-col gap-1.5 mb-5">
            <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wide">Notes</label>
            <textarea v-model="notes" rows="2" placeholder="Any remarks for this MB..."
              class="bg-white border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm font-medium text-gray-800 outline-none focus:border-[#0071e3] focus:ring-2 focus:ring-[#0071e3]/10 transition-all resize-none"></textarea>
          </div>

          <button @click="goToItems" :disabled="!canProceedToItems"
            class="px-5 py-2.5 rounded-full bg-dark-active text-white text-sm font-semibold shadow shadow-black/20 hover:shadow-md hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:translate-y-0 flex items-center gap-2">
            Continue to Items <div class="i-carbon-chevron-right text-xs"></div>
          </button>
        </div>
      </div>

      <!-- ─ Step 3: Items ─ -->
      <div v-else-if="step === 3">
        <div class="flex items-center gap-3 mb-4">
          <button @click="step = 2" class="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 transition-all flex-shrink-0">
            <div class="i-carbon-arrow-left"></div>
          </button>
          <p class="text-sm font-bold text-gray-900 truncate flex-1">
            {{ selectedWork?.loa_number }} · <span class="text-[#0071e3]" :title="mbNumber">{{ mbNumberDisplay }}</span>
          </p>
          <button v-if="pickedItems.length > 0" @click="step = 4" :disabled="!canReview"
            class="px-5 py-2.5 rounded-full bg-dark-active text-white text-sm font-semibold shadow shadow-black/20 hover:shadow-md hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:translate-y-0 flex items-center gap-2 flex-shrink-0">
            Review <div class="i-carbon-chevron-right text-xs"></div>
          </button>
        </div>

        <div class="grid grid-cols-12 gap-6">

          <!-- Item search column -->
          <div class="col-span-12 xl:col-span-5">
            <div class="flex items-center gap-2 mb-3">
              <button @click="scheduleFilter = ''"
                :class="scheduleFilter === '' ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
                class="px-3 py-1.5 rounded-full text-[11px] font-semibold transition-all">All</button>
              <button @click="scheduleFilter = 'A'"
                :class="scheduleFilter === 'A' ? 'bg-[#0071e3] text-white' : 'bg-blue-50 text-[#0071e3] hover:bg-blue-100'"
                class="px-3 py-1.5 rounded-full text-[11px] font-semibold transition-all">Sch A</button>
              <button @click="scheduleFilter = 'B'"
                :class="scheduleFilter === 'B' ? 'bg-[#34c759] text-white' : 'bg-green-50 text-[#34c759] hover:bg-green-100'"
                class="px-3 py-1.5 rounded-full text-[11px] font-semibold transition-all">Sch B</button>
            </div>

            <div class="flex items-center bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 focus-within:ring-2 focus-within:ring-[#0071e3]/20 focus-within:border-[#0071e3] transition-all">
              <div class="i-carbon-search text-gray-400 mr-2"></div>
              <input v-model="itemQuery" type="text" placeholder="Search item by description or serial no..."
                class="bg-transparent outline-none w-full text-sm text-gray-700 placeholder-gray-400 font-medium">
              <div v-if="isSearchingItems" class="i-carbon-circle-dash animate-spin text-gray-400"></div>
            </div>

            <p class="text-[11px] font-bold text-gray-400 uppercase tracking-widest mt-4 mb-2">
              {{ itemResults.length }} items
            </p>
            <div v-if="itemResults.length === 0" class="py-8 text-center text-xs text-gray-400 font-medium bg-gray-50 rounded-xl border border-dashed border-gray-200">
              Search to see items.
            </div>
            <div v-else class="flex flex-col gap-2 max-h-[540px] overflow-y-auto pr-1">
              <div v-for="item in itemResults" :key="item.id"
                class="bg-white border border-gray-200 rounded-xl px-4 py-3 flex items-center justify-between gap-3">
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2 mb-1">
                    <span :class="String(item.schedule||'').toUpperCase().startsWith('A') ? 'bg-blue-50 text-blue-600' : 'bg-green-50 text-green-700'"
                      class="text-[10px] font-bold px-1.5 py-0.5 rounded">{{ item.schedule }}</span>
                    <span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">S.No {{ item.serial_number }}</span>
                    <span class="text-[10px] font-semibold text-gray-400">{{ item.qty }} {{ item.unit }}</span>
                    <span class="text-[10px] font-semibold text-gray-700">{{ fmtAmt(item.total_amount) }}</span>
                  </div>
                  <p class="text-xs text-gray-800 line-clamp-2 leading-relaxed">{{ item.item_desc }}</p>
                </div>
                <button @click="addItem(item)"
                  class="flex-shrink-0 px-3 py-1.5 rounded-full bg-[#0071e3]/10 hover:bg-[#0071e3]/20 text-[#0071e3] text-[11px] font-semibold transition-all flex items-center gap-1">
                  <div class="i-carbon-add text-xs"></div> Add
                </button>
              </div>
            </div>
          </div>

          <!-- Picked items column -->
          <div class="col-span-12 xl:col-span-7">
            <div class="bg-gray-50/60 border border-gray-200 rounded-2xl p-4">

              <div class="flex items-center justify-between mb-3 gap-3 flex-wrap">
                <div class="flex items-center gap-2">
                  <span class="text-xs font-bold text-gray-600 uppercase tracking-wide">MB Items</span>
                  <span class="text-[10px] font-bold text-gray-400">{{ pickedItems.length }}</span>
                </div>

                <!-- Bulk % apply -->
                <div v-if="pickedItems.length > 0" class="flex items-center gap-2 bg-white border border-gray-200 rounded-xl p-1.5">
                  <span class="text-[10px] font-bold text-gray-500 uppercase tracking-wide px-2">Set % for selected ({{ selectedCount }})</span>
                  <button @click="selectAll"  class="text-[10px] font-semibold text-gray-600 hover:text-gray-900 px-2">All</button>
                  <button @click="selectNone" class="text-[10px] font-semibold text-gray-600 hover:text-gray-900 px-2">None</button>
                  <input v-model="bulkPct" type="number" min="0.01" max="100" step="0.01" placeholder="80"
                    class="w-16 bg-gray-50 border border-gray-200 rounded-lg px-2 py-1 text-xs font-bold text-gray-800 outline-none focus:border-[#0071e3] text-right">
                  <button @click="applyBulkPct" :disabled="!bulkPct || selectedCount === 0"
                    class="px-3 py-1 rounded-lg bg-[#0071e3] text-white text-[11px] font-bold hover:bg-[#0055b3] transition-all disabled:opacity-40 disabled:cursor-not-allowed">
                    Apply
                  </button>
                </div>
              </div>

              <div v-if="pickedItems.length === 0" class="py-4 text-center text-xs text-gray-400 font-medium">
                No items yet. Pick from list on left.
              </div>

              <div v-else class="flex flex-col gap-2 max-h-[560px] overflow-y-auto pr-1">
                <div v-for="row in pickedItems" :key="row.key"
                  class="bg-white border rounded-xl p-3 transition-all"
                  :class="row.selected ? 'border-[#0071e3] ring-2 ring-[#0071e3]/10' : 'border-gray-200'">

                  <!-- Top row: checkbox + desc -->
                  <div class="flex items-start gap-3 mb-2">
                    <label class="flex-shrink-0 flex items-center mt-0.5 cursor-pointer">
                      <input v-model="row.selected" type="checkbox"
                        class="w-4 h-4 rounded border-gray-300 text-[#0071e3] focus:ring-[#0071e3]/30">
                    </label>
                    <div class="min-w-0 flex-1">
                      <div class="flex items-center gap-2 mb-0.5 flex-wrap">
                        <span :class="String(row.schedule||'').toUpperCase().startsWith('A') ? 'bg-blue-50 text-blue-600' : 'bg-green-50 text-green-700'"
                          class="text-[10px] font-bold px-1.5 py-0.5 rounded">{{ row.schedule }}</span>
                        <span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">S.No {{ row.serial_number }}</span>
                        <span class="text-[10px] font-semibold text-gray-400">Contract qty: {{ row.qty_default }} {{ row.unit }}</span>
                        <span class="text-[10px] font-semibold text-gray-400">Rate: {{ fmtAmt(row.rate) }}</span>
                      </div>
                      <p class="text-xs text-gray-800 line-clamp-2">{{ row.item_desc }}</p>
                    </div>
                    <div class="flex flex-shrink-0 items-center gap-1">
                      <button @click="duplicateRow(row)" title="Split quantity"
                        class="w-7 h-7 rounded-full bg-gray-100 hover:bg-[#0071e3]/10 hover:text-[#0071e3] text-gray-400 flex items-center justify-center transition-all">
                        <div class="i-carbon-copy text-xs"></div>
                      </button>
                      <button @click="removeRow(row.key)"
                        class="w-7 h-7 rounded-full bg-gray-100 hover:bg-[#ff3b30]/10 hover:text-[#ff3b30] text-gray-400 flex items-center justify-center transition-all">
                        <div class="i-carbon-close text-xs"></div>
                      </button>
                    </div>
                  </div>

                  <!-- Qty / prior / current / amount -->
                  <div class="grid grid-cols-4 gap-2 pl-7">
                    <div class="flex flex-col gap-1">
                      <label class="text-[9px] font-bold text-gray-400 uppercase tracking-wide">Quantity</label>
                      <input v-model="row.quantity" type="number" min="0" step="0.01"
                        class="bg-gray-50 border border-gray-200 rounded-lg px-2 py-1.5 text-xs font-semibold text-gray-800 outline-none focus:border-[#0071e3] focus:bg-white text-right">
                    </div>
                    <div class="flex flex-col gap-1">
                      <label class="text-[9px] font-bold text-gray-400 uppercase tracking-wide">Prior %</label>
                      <div class="relative">
                        <input v-model="row.prior_percentage" type="number" min="0" max="100" step="0.01"
                          class="w-full bg-gray-50 border border-gray-200 rounded-lg pr-5 pl-2 py-1.5 text-xs font-semibold text-gray-800 outline-none focus:border-[#0071e3] focus:bg-white text-right">
                        <span class="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-bold text-gray-400">%</span>
                      </div>
                    </div>
                    <div class="flex flex-col gap-1">
                      <label class="text-[9px] font-bold text-gray-400 uppercase tracking-wide">Current %</label>
                      <div class="relative">
                        <input v-model="row.current_percentage" type="number" min="0" max="100" step="0.01"
                          class="w-full bg-gray-50 border rounded-lg pr-5 pl-2 py-1.5 text-xs font-semibold text-gray-800 outline-none focus:bg-white text-right"
                          :class="rowIsValid(row) ? 'border-gray-200 focus:border-[#0071e3]' : 'border-[#ff3b30]/40 focus:border-[#ff3b30]'">
                        <span class="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-bold text-gray-400">%</span>
                      </div>
                    </div>
                    <div class="flex flex-col gap-1">
                      <label class="text-[9px] font-bold text-gray-400 uppercase tracking-wide">Released</label>
                      <div class="bg-[#0071e3]/5 border border-[#0071e3]/20 rounded-lg px-2 py-1.5 text-xs font-bold text-[#0071e3] text-right">
                        {{ fmtAmt(rowAmount(row)) }}
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Totals -->
                <div class="mt-2 pt-3 border-t border-gray-200 flex items-center justify-between">
                  <div class="text-[11px] font-semibold text-gray-500">
                    <span v-if="invalidCount > 0" class="text-[#ff3b30]">{{ invalidCount }} row(s) need fixing (current % must exceed prior %)</span>
                    <span v-else class="text-[#34c759]">All rows valid</span>
                  </div>
                  <div class="flex items-center gap-3">
                    <span class="text-[10px] font-bold text-gray-400 uppercase tracking-wide">MB Total</span>
                    <span class="text-base font-bold text-gray-900">{{ fmtAmt(mbTotalAmount) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>

      <!-- ─ Step 4: Review ─ -->
      <div v-else-if="step === 4">
        <div class="flex items-center gap-3 mb-4">
          <button @click="step = 3" class="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 transition-all flex-shrink-0">
            <div class="i-carbon-arrow-left"></div>
          </button>
          <p class="text-sm font-bold text-gray-900 truncate flex-1" :title="mbNumber">
            {{ selectedWork?.loa_number }} · <span class="text-[#0071e3]">{{ mbNumberDisplay }}</span> · {{ pickedItems.length }} lines
          </p>
        </div>

        <div class="bg-white border border-gray-200 rounded-2xl overflow-hidden mb-5">
          <table class="w-full text-xs">
            <thead class="bg-gray-50 text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
              <tr>
                <th class="px-3 py-3 text-left w-12">Sch</th>
                <th class="px-3 py-3 text-left w-16">S.No</th>
                <th class="px-3 py-3 text-left">Description</th>
                <th class="px-3 py-3 text-right w-20">Qty</th>
                <th class="px-3 py-3 text-right w-24">Rate</th>
                <th class="px-3 py-3 text-right w-16">Prior %</th>
                <th class="px-3 py-3 text-right w-16">Curr %</th>
                <th class="px-3 py-3 text-right w-28">Released</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="row in pickedItems" :key="row.key">
                <td class="px-3 py-3">
                  <span :class="String(row.schedule||'').toUpperCase().startsWith('A') ? 'bg-blue-50 text-blue-600' : 'bg-green-50 text-green-700'"
                    class="text-[10px] font-bold px-1.5 py-0.5 rounded">{{ row.schedule }}</span>
                </td>
                <td class="px-3 py-3 text-gray-500 font-semibold">{{ row.serial_number }}</td>
                <td class="px-3 py-3 text-gray-800">
                  <p class="line-clamp-2">{{ row.item_desc }}</p>
                </td>
                <td class="px-3 py-3 text-right text-gray-700 font-semibold">{{ row.quantity }} <span class="text-gray-400 font-normal">{{ row.unit }}</span></td>
                <td class="px-3 py-3 text-right text-gray-600">{{ fmtAmt(row.rate) }}</td>
                <td class="px-3 py-3 text-right text-gray-600 font-semibold">{{ row.prior_percentage }}%</td>
                <td class="px-3 py-3 text-right text-gray-800 font-bold">{{ row.current_percentage }}%</td>
                <td class="px-3 py-3 text-right font-bold text-[#0071e3]">{{ fmtAmt(rowAmount(row)) }}</td>
              </tr>
            </tbody>
            <tfoot class="bg-gray-50 border-t border-gray-100">
              <tr>
                <td colspan="7" class="px-3 py-3 text-right text-[10px] font-bold text-gray-400 uppercase tracking-wide">MB Total</td>
                <td class="px-3 py-3 text-right text-base font-bold text-gray-900">{{ fmtAmt(mbTotalAmount) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>

        <div class="flex items-center justify-end gap-3">
          <p v-if="saveStatus && saveStatus !== 'saved'" class="text-xs font-medium text-[#ff3b30]">{{ saveStatus }}</p>
          <button @click="step = 3"
            class="px-5 py-2.5 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-800 text-sm font-semibold transition-all">
            Back to Items
          </button>
          <button @click="saveMB" :disabled="!canReview || isSaving"
            :class="saveStatus === 'saved' ? 'bg-[#34c759] shadow-[#34c759]/30' : 'bg-dark-active shadow-black/20'"
            class="px-5 py-2.5 rounded-full text-white text-sm font-semibold shadow-lg hover:shadow-xl hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:translate-y-0 flex items-center gap-2">
            <div v-if="isSaving" class="i-carbon-circle-dash animate-spin"></div>
            <span>{{ saveStatus === 'saved' ? 'Saved!' : 'Save MB Record' }}</span>
          </button>
        </div>
      </div>

    </div>
  </div>
</template>
