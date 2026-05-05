<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'
import { useAuth } from '../composables/useAuth'

const { state: authState } = useAuth()
const isAdmin = computed(() => authState.user?.role === 'admin' || authState.user?.is_staff)

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

// Convert DD/MM/YYYY (or DD-MM-YYYY) from PDF to YYYY-MM-DD for <input type="date">
const parseDateToIso = (str) => {
  if (!str) return ''
  const m = str.trim().match(/^(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})$/)
  if (m) return `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`
  if (/^\d{4}-\d{2}-\d{2}$/.test(str.trim())) return str.trim()
  return ''
}

// Steps: 1=Select Work, 2=Upload PDF, 3=Review & Save
const step = ref(1)

const workQuery    = ref('')
const workResults  = ref([])
const selectedWork = ref(null)
const isSearchingWorks = ref(false)

const mbNumber       = ref('')
const measurementDate = ref('')
const notes          = ref('')

const mbNumberDisplay = computed(() => {
  const v = String(mbNumber.value || '').trim()
  if (!v) return ''
  return /^\d+$/.test(v) ? `MB${v.padStart(2, '0')}` : v
})

// Items imported from PDF
// shape: { key, work_item, serial_number, item_desc, schedule, qty_default, unit, rate,
//          quantity, prior_percentage, current_percentage, selected, not_received_warning }
const pickedItems = ref([])
const bulkPct     = ref('')

const savedRecords = ref([])
const summary      = ref(null)
const saveStatus   = ref('')
const isSaving     = ref(false)

// PDF import
const pdfFileInput   = ref(null)
const isImporting    = ref(false)
const importStatus   = ref('')
const importWarnings = ref([])
const unmatchedItems = ref([])

// Edit modal state
const editRecord          = ref(null)
const editMbNumber        = ref('')
const editMeasurementDate = ref('')
const editNotes           = ref('')
const editItems      = ref([])
const editSaving     = ref(false)
const editSaveStatus = ref('')

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
  loadSummary()
}

// ── PDF Import ────────────────────────────────────────────────────────────
const triggerPdfPicker = () => pdfFileInput.value?.click()

const onPdfSelected = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return
  await importPdf(file)
  event.target.value = ''
}

const importPdf = async (file) => {
  isImporting.value    = true
  importStatus.value   = ''
  importWarnings.value = []
  unmatchedItems.value = []
  try {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('work_id', selectedWork.value.id)
    const { data } = await axios.post('/api/mb-details/import-pdf/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })

    if (data.header?.mb_number)          mbNumber.value = data.header.mb_number
    if (data.header?.date_of_measurement) measurementDate.value = parseDateToIso(data.header.date_of_measurement)

    const matched   = []
    const unmatched = []
    for (const r of (data.items || [])) {
      if (r.matched) {
        matched.push({
          key:                  uid(),
          work_item:            r.work_item,
          serial_number:        r.item_no,
          item_desc:            r.description || r.work_item_label || '',
          schedule:             r.schedule,
          qty_default:          r.contract_qty || r.quantity,
          unit:                 r.unit,
          rate:                 r.unit_rate_below || 0,
          quantity:             r.quantity || 0,
          prior_percentage:     r.suggested_prior || 0,
          current_percentage:   r.current_percentage || 0,
          selected:             false,
          not_received_warning: r.not_received_warning || false,
        })
      } else {
        unmatched.push(r)
      }
    }
    pickedItems.value    = matched
    unmatchedItems.value = unmatched
    importWarnings.value = data.warnings || []

    if (matched.length > 0) {
      importStatus.value = 'ok'
      step.value = 3
    } else {
      importStatus.value = 'no-match'
    }
    setTimeout(() => { importStatus.value = '' }, 4000)
  } catch (e) {
    console.error(e)
    importStatus.value = e.response?.data?.error || 'Import failed.'
    setTimeout(() => { importStatus.value = '' }, 4500)
  } finally {
    isImporting.value = false
  }
}

// ── Row helpers ───────────────────────────────────────────────────────────
const rowAmount = (row) => {
  const qty  = parseFloat(row.quantity)           || 0
  const rate = parseFloat(row.rate)               || 0
  const cur  = parseFloat(row.current_percentage) || 0
  const pri  = parseFloat(row.prior_percentage)   || 0
  return Math.round(qty * rate * (cur - pri) / 100 * 100) / 100
}

const mbTotalAmount = computed(() =>
  pickedItems.value.reduce((s, r) => s + rowAmount(r), 0)
)

const rowIsValid = (r) => {
  const qty = parseFloat(r.quantity)           || 0
  const cur = parseFloat(r.current_percentage) || 0
  const pri = parseFloat(r.prior_percentage)   || 0
  return qty > 0 && cur > pri && cur <= 100 && pri >= 0
}

const canSave     = computed(() => pickedItems.value.length > 0 && pickedItems.value.every(rowIsValid))
const invalidCount = computed(() => pickedItems.value.filter(r => !rowIsValid(r)).length)

// ── Bulk % apply ──────────────────────────────────────────────────────────
const selectedCount = computed(() => pickedItems.value.filter(r => r.selected).length)
const selectAll     = () => pickedItems.value.forEach(r => r.selected = true)
const selectNone    = () => pickedItems.value.forEach(r => r.selected = false)

const applyBulkPct = () => {
  const pct = parseFloat(bulkPct.value)
  if (isNaN(pct) || pct <= 0 || pct > 100) return
  pickedItems.value.forEach(r => { if (r.selected) r.current_percentage = pct })
  pickedItems.value.forEach(r => r.selected = false)
  bulkPct.value = ''
}

// ── Save new MB record ────────────────────────────────────────────────────
const saveMB = async () => {
  if (!canSave.value || !selectedWork.value) return
  isSaving.value   = true
  saveStatus.value = ''
  try {
    await axios.post('/api/mb-details/records/', {
      work:             selectedWork.value.id,
      mb_number:        String(mbNumber.value || '').trim(),
      measurement_date: measurementDate.value || null,
      notes:            notes.value,
      items:     pickedItems.value.map(r => ({
        work_item:          r.work_item,
        quantity:           parseFloat(r.quantity),
        prior_percentage:   parseFloat(r.prior_percentage) || 0,
        current_percentage: parseFloat(r.current_percentage),
      })),
    })
    saveStatus.value = 'saved'
    await Promise.all([loadRecords(), loadSummary()])
    setTimeout(() => { saveStatus.value = ''; resetFlow() }, 1200)
  } catch (e) {
    console.error(e)
    saveStatus.value = e.response?.data?.error || (e.response?.status === 403 ? 'denied' : 'error')
    setTimeout(() => { saveStatus.value = '' }, 3500)
  } finally {
    isSaving.value = false
  }
}

const resetFlow = () => {
  step.value           = 1
  workQuery.value      = ''
  workResults.value    = []
  selectedWork.value   = null
  mbNumber.value        = ''
  measurementDate.value = ''
  notes.value           = ''
  pickedItems.value    = []
  bulkPct.value        = ''
  importWarnings.value = []
  unmatchedItems.value = []
  importStatus.value   = ''
  searchWorks('')
}

// ── Records & summary ─────────────────────────────────────────────────────
const loadRecords = async () => {
  try {
    const { data } = await axios.get('/api/mb-details/records/')
    savedRecords.value = data
  } catch (e) { console.error(e) }
}

const loadSummary = async () => {
  try {
    const params = selectedWork.value ? { work_id: selectedWork.value.id } : {}
    const { data } = await axios.get('/api/mb-details/summary/', { params })
    summary.value = data
  } catch (e) { console.error(e) }
}

const deleteRecord = async (id) => {
  if (!confirm('Delete this MB record? This is irreversible.')) return
  try {
    await axios.delete(`/api/mb-details/records/${id}/`)
    await Promise.all([loadRecords(), loadSummary()])
  } catch (e) {
    alert(e.response?.status === 403 ? 'Permission denied.' : 'Failed to delete.')
  }
}

// ── Edit modal ────────────────────────────────────────────────────────────
const openEdit = (record) => {
  editRecord.value          = record
  editMbNumber.value        = record.mb_number
  editMeasurementDate.value = record.measurement_date || ''
  editNotes.value           = record.notes || ''
  editItems.value    = record.items.map(i => ({
    work_item:          i.work_item,
    serial_number:      i.work_item_sno,
    item_desc:          i.work_item_desc,
    schedule:           i.work_item_sch,
    unit:               i.work_item_unit,
    rate:               i.work_item_rate || 0,
    qty_default:        i.work_item_qty,
    quantity:           i.quantity,
    prior_percentage:   i.prior_percentage,
    current_percentage: i.current_percentage,
  }))
  editSaveStatus.value = ''
}

const closeEdit = () => {
  editRecord.value = null
  editItems.value  = []
}

const editRowAmount = (row) => {
  const qty  = parseFloat(row.quantity)           || 0
  const rate = parseFloat(row.rate)               || 0
  const cur  = parseFloat(row.current_percentage) || 0
  const pri  = parseFloat(row.prior_percentage)   || 0
  return Math.round(qty * rate * (cur - pri) / 100 * 100) / 100
}

const editRowIsValid = (r) => {
  const qty = parseFloat(r.quantity)           || 0
  const cur = parseFloat(r.current_percentage) || 0
  const pri = parseFloat(r.prior_percentage)   || 0
  return qty > 0 && cur > pri && cur <= 100 && pri >= 0
}

const editTotal     = computed(() => editItems.value.reduce((s, r) => s + editRowAmount(r), 0))
const editCanSave   = computed(() => editItems.value.length > 0 && editItems.value.every(editRowIsValid))
const editInvalid   = computed(() => editItems.value.filter(r => !editRowIsValid(r)).length)

const sortBy  = ref('mb_number')
const sortDir = ref('asc')

const toggleSort = (field) => {
  if (sortBy.value === field) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else { sortBy.value = field; sortDir.value = 'asc' }
}

const workRecords = (workId) => {
  const recs = savedRecords.value.filter(r => r.work === workId)
  return [...recs].sort((a, b) => {
    let av, bv
    if (sortBy.value === 'mb_number') {
      av = String(a.mb_number || ''); bv = String(b.mb_number || '')
      const ai = parseInt(av), bi = parseInt(bv)
      if (!isNaN(ai) && !isNaN(bi)) { av = ai; bv = bi }
    } else if (sortBy.value === 'total_amount') {
      av = parseFloat(a.total_amount) || 0; bv = parseFloat(b.total_amount) || 0
    } else if (sortBy.value === 'created_at') {
      av = new Date(a.created_at).getTime(); bv = new Date(b.created_at).getTime()
    } else if (sortBy.value === 'items') {
      av = a.items.length; bv = b.items.length
    }
    if (av < bv) return sortDir.value === 'asc' ? -1 : 1
    if (av > bv) return sortDir.value === 'asc' ? 1 : -1
    return 0
  })
}

const fmtMbNum = (n) => /^\d+$/.test(String(n)) ? 'MB' + String(n).padStart(2, '0') : n

const saveEdit = async () => {
  if (!editCanSave.value || !editRecord.value) return
  editSaving.value     = true
  editSaveStatus.value = ''
  try {
    await axios.patch(`/api/mb-details/records/${editRecord.value.id}/`, {
      mb_number:        editMbNumber.value,
      measurement_date: editMeasurementDate.value || null,
      notes:            editNotes.value,
      items:     editItems.value.map(r => ({
        work_item:          r.work_item,
        quantity:           parseFloat(r.quantity),
        prior_percentage:   parseFloat(r.prior_percentage) || 0,
        current_percentage: parseFloat(r.current_percentage),
      })),
    })
    editSaveStatus.value = 'saved'
    await Promise.all([loadRecords(), loadSummary()])
    setTimeout(() => { editSaveStatus.value = ''; closeEdit() }, 1200)
  } catch (e) {
    console.error(e)
    editSaveStatus.value = e.response?.data?.error || (e.response?.status === 403 ? 'denied' : 'error')
    setTimeout(() => { editSaveStatus.value = '' }, 3500)
  } finally {
    editSaving.value = false
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

    <!-- Header -->
    <div class="flex-shrink-0 px-8 pt-5 pb-4 border-b border-gray-100 flex items-center gap-4 flex-wrap">
      <h1 class="text-xl font-bold text-gray-900 tracking-tight flex-shrink-0">MB Details</h1>

      <!-- Stepper -->
      <div class="flex items-center gap-2 flex-1 min-w-0 justify-center">
        <div v-for="(label, i) in ['Select Work', 'Upload PDF', 'Review & Save']" :key="i"
          class="flex items-center gap-1.5">
          <div :class="step > i+1 ? 'bg-[#34c759] text-white'
                       : step === i+1 ? 'bg-[#0071e3] text-white shadow shadow-[#0071e3]/30'
                       : 'bg-gray-100 text-gray-400'"
            class="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold transition-all flex-shrink-0">
            <span v-if="step > i+1" class="i-carbon-checkmark text-xs"></span>
            <span v-else>{{ i + 1 }}</span>
          </div>
          <span :class="step === i+1 ? 'text-gray-800' : 'text-gray-400'"
            class="text-[11px] font-semibold whitespace-nowrap">{{ label }}</span>
          <span v-if="i < 2" class="w-4 h-px bg-gray-200"></span>
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
          <div class="grid grid-cols-1 gap-3">
            <div v-for="w in workResults" :key="w.id">
              <!-- Work card -->
              <button @click="pickWork(w)"
                class="w-full text-left bg-white border border-gray-200 hover:border-[#0071e3] hover:bg-[#0071e3]/5 px-4 py-3 transition-all group rounded-xl">
                <div class="flex items-center justify-between gap-3">
                  <div class="min-w-0">
                    <p class="text-sm font-semibold text-gray-900 truncate">{{ w.contractor_name || '—' }}</p>
                    <div class="flex items-center gap-3 flex-wrap mt-1">
                      <span class="text-[11px] font-semibold text-[#0071e3] bg-[#0071e3]/10 px-2 py-0.5 rounded-full">{{ w.loa_number || '—' }}</span>
                      <span class="text-[11px] text-gray-500">Tender: <span class="font-semibold text-gray-700">{{ w.tender_number || '—' }}</span></span>
                      <span class="text-[11px] text-gray-500">Consignee: <span class="font-semibold text-gray-700">{{ w.consignee || '—' }}</span></span>
                    </div>
                  </div>
                  <div class="flex items-center gap-2 flex-shrink-0">
                    <span v-if="workRecords(w.id).length > 0"
                      class="text-[10px] font-bold text-[#0071e3] bg-[#0071e3]/10 px-2 py-0.5 rounded-full">
                      {{ workRecords(w.id).length }} MB{{ workRecords(w.id).length > 1 ? 's' : '' }}
                    </span>
                    <div class="i-carbon-add-alt text-gray-300 group-hover:text-[#0071e3] transition-colors"></div>
                  </div>
                </div>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- ─ Step 2: Upload PDF ─ -->
      <div v-else-if="step === 2">
        <div class="flex items-center gap-3 mb-4">
          <button @click="step = 1" class="w-9 h-9 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 transition-all">
            <div class="i-carbon-arrow-left"></div>
          </button>
          <div class="min-w-0">
            <p class="text-xs font-semibold text-gray-400 uppercase tracking-widest">Selected Work</p>
            <p class="text-sm font-bold text-gray-900">{{ selectedWork?.contractor_name }} · <span class="text-[#0071e3]">{{ selectedWork?.loa_number }}</span></p>
            <p v-if="selectedWork?.name_of_work" class="text-xs text-gray-500 mt-0.5 leading-snug max-w-2xl">{{ selectedWork.name_of_work }}</p>
          </div>
        </div>

        <div>
          <input ref="pdfFileInput" type="file" accept="application/pdf" @change="onPdfSelected" class="hidden">

          <div class="border border-gray-200 rounded-xl overflow-hidden">
            <!-- Upload card — consignee only -->
            <div v-if="!isAdmin" class="bg-gray-50 border-b border-dashed border-gray-300 hover:border-[#0071e3] px-4 py-3 flex items-center gap-3 transition-colors cursor-pointer"
              :class="selectedWork && workRecords(selectedWork.id).length > 0 ? 'border-b' : 'border-b-0'"
              @click="triggerPdfPicker">
              <div v-if="isImporting" class="i-carbon-circle-dash animate-spin text-[#0071e3] text-xl flex-shrink-0"></div>
              <div v-else class="i-carbon-document-pdf text-gray-300 text-2xl flex-shrink-0"></div>
              <div class="flex-1 min-w-0">
                <p class="text-xs font-bold text-gray-700">{{ isImporting ? 'Parsing PDF…' : 'Upload Record Measurement PDF' }}</p>
                <p class="text-[10px] text-gray-400">Click to choose · PDF auto-fills MB number, items, quantities, and payment %</p>
              </div>
              <button :disabled="isImporting"
                class="px-3 py-1.5 rounded-full bg-[#0071e3] text-white text-[11px] font-semibold shadow shadow-[#0071e3]/30 hover:shadow-md hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:translate-y-0 flex-shrink-0"
                @click.stop="triggerPdfPicker">
                Choose PDF
              </button>
            </div>

            <!-- MB records for selected work -->
            <div v-if="selectedWork && workRecords(selectedWork.id).length > 0">
              <table class="w-full text-xs">
                <thead class="bg-gray-50/80 border-b border-gray-100">
                  <tr>
                    <th class="px-4 py-2 text-left w-36">
                      <button @click="toggleSort('mb_number')"
                        class="flex items-center gap-1 text-[10px] font-bold text-gray-400 uppercase tracking-widest hover:text-gray-700 transition-colors">
                        MB No
                        <span :class="sortBy === 'mb_number' ? 'text-[#0071e3]' : 'text-gray-300'">
                          {{ sortBy === 'mb_number' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}
                        </span>
                      </button>
                    </th>
                    <th class="px-4 py-2 text-left">
                      <button @click="toggleSort('items')"
                        class="flex items-center gap-1 text-[10px] font-bold text-gray-400 uppercase tracking-widest hover:text-gray-700 transition-colors">
                        Items
                        <span :class="sortBy === 'items' ? 'text-[#0071e3]' : 'text-gray-300'">
                          {{ sortBy === 'items' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}
                        </span>
                      </button>
                    </th>
                    <th class="px-4 py-2 text-right">
                      <button @click="toggleSort('total_amount')"
                        class="flex items-center gap-1 text-[10px] font-bold text-gray-400 uppercase tracking-widest hover:text-gray-700 transition-colors ml-auto">
                        Amount
                        <span :class="sortBy === 'total_amount' ? 'text-[#0071e3]' : 'text-gray-300'">
                          {{ sortBy === 'total_amount' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}
                        </span>
                      </button>
                    </th>
                    <th class="px-4 py-2 text-right hidden sm:table-cell">
                      <button @click="toggleSort('created_at')"
                        class="flex items-center gap-1 text-[10px] font-bold text-gray-400 uppercase tracking-widest hover:text-gray-700 transition-colors ml-auto">
                        Date
                        <span :class="sortBy === 'created_at' ? 'text-[#0071e3]' : 'text-gray-300'">
                          {{ sortBy === 'created_at' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}
                        </span>
                      </button>
                    </th>
                    <th class="px-4 py-2 w-20"></th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                  <tr v-for="rec in workRecords(selectedWork.id)" :key="rec.id"
                    class="bg-white hover:bg-gray-50/60 transition-colors">
                    <td class="px-4 py-2.5 font-bold text-gray-800">{{ fmtMbNum(rec.mb_number) }}</td>
                    <td class="px-4 py-2.5 text-gray-500">
                      {{ rec.items.length }} item{{ rec.items.length === 1 ? '' : 's' }}
                      <span v-if="rec.notes" class="ml-2 text-[10px] text-gray-400 italic">{{ rec.notes }}</span>
                    </td>
                    <td class="px-4 py-2.5 text-right font-bold text-gray-900">{{ fmtAmt(rec.total_amount) }}</td>
                    <td class="px-4 py-2.5 text-right text-[10px] text-gray-400 hidden sm:table-cell">
                      {{ rec.measurement_date
                          ? new Date(rec.measurement_date + 'T00:00:00').toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
                          : fmtDateTime(rec.created_at) }}
                    </td>
                    <td class="px-4 py-2.5 text-right">
                      <div class="flex items-center justify-end gap-1.5">
                        <template v-if="!isAdmin">
                          <button @click="openEdit(rec)" title="Edit"
                            class="w-7 h-7 rounded-full bg-gray-100 hover:bg-[#0071e3]/10 hover:text-[#0071e3] text-gray-500 flex items-center justify-center transition-all">
                            <div class="i-carbon-edit text-xs"></div>
                          </button>
                          <button @click="deleteRecord(rec.id)" title="Delete"
                            class="w-7 h-7 rounded-full bg-gray-100 hover:bg-[#ff3b30]/10 hover:text-[#ff3b30] text-gray-500 flex items-center justify-center transition-all">
                            <div class="i-carbon-trash-can text-xs"></div>
                          </button>
                        </template>
                        <span v-else class="text-[10px] text-gray-400 italic">View only</span>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Import status -->
          <div v-if="importStatus && importStatus !== 'ok'" class="mt-2">
            <p v-if="importStatus === 'no-match'" class="text-xs font-semibold text-[#ff9500]">
              PDF parsed, but no items matched this work. Check if the correct work is selected.
            </p>
            <p v-else class="text-xs font-semibold text-[#ff3b30]">{{ importStatus }}</p>
          </div>
        </div>
      </div>

      <!-- ─ Step 3: Review & Save ─ -->
      <div v-else-if="step === 3">
        <!-- Header bar -->
        <div class="flex items-center gap-3 mb-4 flex-wrap">
          <button @click="step = 2" class="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 transition-all flex-shrink-0">
            <div class="i-carbon-arrow-left"></div>
          </button>

          <!-- Editable MB number / notes inline -->
          <div class="flex-1 min-w-0 flex flex-col gap-0.5">
            <input v-model="mbNumber" type="text" placeholder="MB Number / Reference"
              class="text-sm font-bold text-gray-900 bg-transparent outline-none border-b border-transparent focus:border-[#0071e3] w-full truncate transition-colors"
              :title="mbNumber">
            <div class="flex items-center gap-2">
              <span class="text-[10px] text-gray-400 whitespace-nowrap">Date of Measurement:</span>
              <input v-model="measurementDate" type="date"
                class="text-xs text-gray-600 bg-transparent outline-none border-b border-transparent focus:border-[#0071e3] transition-colors">
            </div>
            <input v-model="notes" type="text" placeholder="Notes (optional)"
              class="text-xs text-gray-400 bg-transparent outline-none border-b border-transparent focus:border-gray-300 w-full transition-colors">
          </div>

          <div v-if="!isAdmin" class="flex items-center gap-2 flex-shrink-0">
            <p v-if="saveStatus && saveStatus !== 'saved'" class="text-xs font-medium text-[#ff3b30]">{{ saveStatus }}</p>
            <button @click="saveMB" :disabled="!canSave || isSaving"
              :class="saveStatus === 'saved' ? 'bg-[#34c759] shadow-[#34c759]/30' : 'bg-[#1d1d1f] shadow-black/20'"
              class="px-5 py-2.5 rounded-full text-white text-sm font-semibold shadow-lg hover:shadow-xl hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:translate-y-0 flex items-center gap-2">
              <div v-if="isSaving" class="i-carbon-circle-dash animate-spin"></div>
              <span>{{ saveStatus === 'saved' ? 'Saved!' : 'Save MB Record' }}</span>
            </button>
          </div>
        </div>

        <!-- Warnings banner -->
        <div v-if="importWarnings.length > 0 || unmatchedItems.length > 0"
          class="mb-4 bg-amber-50 border border-amber-200 rounded-xl p-3">
          <p class="text-[11px] font-bold text-amber-700 uppercase tracking-wide mb-2">PDF Import Warnings</p>
          <ul class="text-[11px] text-amber-800 list-disc pl-4 space-y-0.5">
            <li v-for="(w, i) in importWarnings" :key="i">{{ w }}</li>
          </ul>
          <div v-if="unmatchedItems.length > 0" class="mt-2 pt-2 border-t border-amber-200">
            <p class="text-[10px] font-semibold text-amber-700 mb-1">Unmatched items (not in this work):</p>
            <ul class="text-[11px] text-amber-800 list-disc pl-4 space-y-0.5">
              <li v-for="u in unmatchedItems" :key="u.item_no + u.schedule">
                Sch {{ u.schedule }} · S.No {{ u.item_no }} · {{ (u.description || '').slice(0, 80) }} ({{ u.quantity }} {{ u.unit }} @ {{ u.current_percentage }}%)
              </li>
            </ul>
          </div>
        </div>

        <!-- Bulk % toolbar -->
        <div v-if="pickedItems.length > 0"
          class="mb-3 flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl p-2 flex-wrap">
          <span class="text-[10px] font-bold text-gray-500 uppercase tracking-wide px-2">Set % for selected ({{ selectedCount }})</span>
          <button @click="selectAll"  class="text-[10px] font-semibold text-gray-600 hover:text-gray-900 px-2">All</button>
          <button @click="selectNone" class="text-[10px] font-semibold text-gray-600 hover:text-gray-900 px-2">None</button>
          <input v-model="bulkPct" type="number" min="0.01" max="100" step="0.01" placeholder="80"
            class="w-16 bg-white border border-gray-200 rounded-lg px-2 py-1 text-xs font-bold text-gray-800 outline-none focus:border-[#0071e3] text-right">
          <button @click="applyBulkPct" :disabled="!bulkPct || selectedCount === 0"
            class="px-3 py-1 rounded-lg bg-[#0071e3] text-white text-[11px] font-bold hover:bg-[#0055b3] transition-all disabled:opacity-40 disabled:cursor-not-allowed">
            Apply
          </button>
        </div>

        <!-- Items table -->
        <div class="bg-white border border-gray-200 rounded-2xl overflow-hidden">
          <table class="w-full text-xs">
            <thead class="bg-gray-50 text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
              <tr>
                <th class="px-3 py-3 text-center w-8">
                  <input type="checkbox" @change="e => e.target.checked ? selectAll() : selectNone()"
                    class="w-3.5 h-3.5 rounded border-gray-300 text-[#0071e3]">
                </th>
                <th class="px-3 py-3 text-left w-12">Sch</th>
                <th class="px-3 py-3 text-left w-16">S.No</th>
                <th class="px-3 py-3 text-left">Description</th>
                <th class="px-3 py-3 text-right w-24">Qty</th>
                <th class="px-3 py-3 text-right w-20">Prior %</th>
                <th class="px-3 py-3 text-right w-20">Curr %</th>
                <th class="px-3 py-3 text-right w-28">Released</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="row in pickedItems" :key="row.key"
                :class="row.not_received_warning ? 'bg-orange-50/40' : 'hover:bg-gray-50/40'"
                class="transition-colors">
                <td class="px-3 py-2.5 text-center">
                  <input v-model="row.selected" type="checkbox"
                    class="w-3.5 h-3.5 rounded border-gray-300 text-[#0071e3] focus:ring-[#0071e3]/30">
                </td>
                <td class="px-3 py-2.5">
                  <span :class="String(row.schedule||'').toUpperCase().startsWith('A') ? 'bg-blue-50 text-blue-600' : 'bg-green-50 text-green-700'"
                    class="text-[10px] font-bold px-1.5 py-0.5 rounded">{{ row.schedule }}</span>
                </td>
                <td class="px-3 py-2.5 font-semibold text-gray-500">{{ row.serial_number }}</td>
                <td class="px-3 py-2.5">
                  <p class="text-gray-800 line-clamp-2 leading-relaxed">{{ row.item_desc }}</p>
                  <span v-if="row.not_received_warning"
                    class="inline-flex items-center gap-1 mt-1 text-[10px] font-bold text-orange-600 bg-orange-100 px-1.5 py-0.5 rounded">
                    <div class="i-carbon-warning-alt text-xs"></div>
                    Item not received — please receive before payment
                  </span>
                </td>
                <td class="px-3 py-2.5 text-right">
                  <input v-model="row.quantity" type="number" min="0" step="0.01"
                    class="w-20 bg-gray-50 border border-gray-200 rounded-lg px-2 py-1 text-xs font-semibold text-gray-800 outline-none focus:border-[#0071e3] focus:bg-white text-right">
                </td>
                <td class="px-3 py-2.5 text-right">
                  <div class="relative inline-flex items-center">
                    <input v-model="row.prior_percentage" type="number" min="0" max="100" step="0.01"
                      class="w-16 bg-gray-50 border border-gray-200 rounded-lg pr-4 pl-2 py-1 text-xs font-semibold text-gray-800 outline-none focus:border-[#0071e3] focus:bg-white text-right">
                    <span class="absolute right-1.5 text-[9px] font-bold text-gray-400">%</span>
                  </div>
                </td>
                <td class="px-3 py-2.5 text-right">
                  <div class="relative inline-flex items-center">
                    <input v-model="row.current_percentage" type="number" min="0" max="100" step="0.01"
                      class="w-16 border rounded-lg pr-4 pl-2 py-1 text-xs font-semibold text-gray-800 outline-none focus:bg-white text-right"
                      :class="rowIsValid(row) ? 'bg-gray-50 border-gray-200 focus:border-[#0071e3]' : 'bg-red-50 border-[#ff3b30]/40 focus:border-[#ff3b30]'">
                    <span class="absolute right-1.5 text-[9px] font-bold text-gray-400">%</span>
                  </div>
                </td>
                <td class="px-3 py-2.5 text-right font-bold text-[#0071e3]">{{ fmtAmt(rowAmount(row)) }}</td>
              </tr>
            </tbody>
            <tfoot class="bg-gray-50 border-t border-gray-200">
              <tr>
                <td colspan="7" class="px-3 py-3 text-right">
                  <span v-if="invalidCount > 0" class="text-[11px] font-semibold text-[#ff3b30]">
                    {{ invalidCount }} row(s) need fixing (current % must exceed prior %)
                  </span>
                  <span v-else class="text-[11px] font-semibold text-[#34c759]">All rows valid</span>
                  <span class="mx-4 text-gray-300">|</span>
                  <span class="text-[10px] font-bold text-gray-400 uppercase tracking-wide">MB Total</span>
                </td>
                <td class="px-3 py-3 text-right text-base font-bold text-gray-900">{{ fmtAmt(mbTotalAmount) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

    </div>

  <!-- ─ Edit Modal ─────────────────────────────────────────────────────────── -->
  <Teleport to="body">


    <div v-if="editRecord" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="closeEdit"></div>

      <!-- Panel -->
      <div class="relative bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden">

        <!-- Modal header -->
        <div class="flex-shrink-0 px-6 pt-5 pb-4 border-b border-gray-100 flex items-center gap-4">
          <div class="flex-1 min-w-0 flex flex-col gap-1">
            <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Edit MB Record</p>
            <div class="flex items-center gap-3 flex-wrap">
              <input v-model="editMbNumber" type="text" placeholder="MB Number"
                class="text-sm font-bold text-gray-900 bg-transparent outline-none border-b border-gray-200 focus:border-[#0071e3] transition-colors min-w-0 flex-1">
              <div class="flex items-center gap-1.5 flex-shrink-0">
                <span class="text-[10px] text-gray-400 whitespace-nowrap">Meas. Date:</span>
                <input v-model="editMeasurementDate" type="date"
                  class="text-xs text-gray-600 bg-transparent outline-none border-b border-gray-200 focus:border-[#0071e3] transition-colors">
              </div>
              <input v-model="editNotes" type="text" placeholder="Notes (optional)"
                class="text-xs text-gray-500 bg-transparent outline-none border-b border-gray-200 focus:border-gray-400 transition-colors min-w-0 flex-1">
            </div>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            <p v-if="editSaveStatus && editSaveStatus !== 'saved'" class="text-xs font-medium text-[#ff3b30]">{{ editSaveStatus }}</p>
            <button @click="saveEdit" :disabled="!editCanSave || editSaving"
              :class="editSaveStatus === 'saved' ? 'bg-[#34c759] shadow-[#34c759]/30' : 'bg-[#1d1d1f] shadow-black/20'"
              class="px-4 py-2 rounded-full text-white text-xs font-semibold shadow hover:shadow-md hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:translate-y-0 flex items-center gap-2">
              <div v-if="editSaving" class="i-carbon-circle-dash animate-spin"></div>
              <span>{{ editSaveStatus === 'saved' ? 'Saved!' : 'Save Changes' }}</span>
            </button>
            <button @click="closeEdit"
              class="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-500 transition-all">
              <div class="i-carbon-close text-sm"></div>
            </button>
          </div>
        </div>

        <!-- Modal body: items table -->
        <div class="flex-1 overflow-y-auto">
          <table class="w-full text-xs">
            <thead class="bg-gray-50 text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100 sticky top-0">
              <tr>
                <th class="px-4 py-3 text-left w-12">Sch</th>
                <th class="px-4 py-3 text-left w-14">S.No</th>
                <th class="px-4 py-3 text-left">Description</th>
                <th class="px-4 py-3 text-right w-24">Qty</th>
                <th class="px-4 py-3 text-right w-20">Prior %</th>
                <th class="px-4 py-3 text-right w-20">Curr %</th>
                <th class="px-4 py-3 text-right w-28">Released</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="(row, idx) in editItems" :key="idx" class="hover:bg-gray-50/40 transition-colors">
                <td class="px-4 py-2.5">
                  <span :class="String(row.schedule||'').toUpperCase().startsWith('A') ? 'bg-blue-50 text-blue-600' : 'bg-green-50 text-green-700'"
                    class="text-[10px] font-bold px-1.5 py-0.5 rounded">{{ row.schedule }}</span>
                </td>
                <td class="px-4 py-2.5 font-semibold text-gray-500">{{ row.serial_number }}</td>
                <td class="px-4 py-2.5">
                  <p class="text-gray-800 line-clamp-2 leading-relaxed">{{ row.item_desc }}</p>
                  <p class="text-[10px] text-gray-400 mt-0.5">{{ row.qty_default }} {{ row.unit }} · Rate: {{ fmtAmt(row.rate) }}</p>
                </td>
                <td class="px-4 py-2.5 text-right">
                  <input v-model="row.quantity" type="number" min="0" step="0.01"
                    class="w-20 bg-gray-50 border border-gray-200 rounded-lg px-2 py-1 text-xs font-semibold text-gray-800 outline-none focus:border-[#0071e3] focus:bg-white text-right">
                </td>
                <td class="px-4 py-2.5 text-right">
                  <div class="relative inline-flex items-center">
                    <input v-model="row.prior_percentage" type="number" min="0" max="100" step="0.01"
                      class="w-16 bg-gray-50 border border-gray-200 rounded-lg pr-4 pl-2 py-1 text-xs font-semibold text-gray-800 outline-none focus:border-[#0071e3] focus:bg-white text-right">
                    <span class="absolute right-1.5 text-[9px] font-bold text-gray-400">%</span>
                  </div>
                </td>
                <td class="px-4 py-2.5 text-right">
                  <div class="relative inline-flex items-center">
                    <input v-model="row.current_percentage" type="number" min="0" max="100" step="0.01"
                      class="w-16 border rounded-lg pr-4 pl-2 py-1 text-xs font-semibold text-gray-800 outline-none focus:bg-white text-right"
                      :class="editRowIsValid(row) ? 'bg-gray-50 border-gray-200 focus:border-[#0071e3]' : 'bg-red-50 border-[#ff3b30]/40 focus:border-[#ff3b30]'">
                    <span class="absolute right-1.5 text-[9px] font-bold text-gray-400">%</span>
                  </div>
                </td>
                <td class="px-4 py-2.5 text-right font-bold text-[#0071e3]">{{ fmtAmt(editRowAmount(row)) }}</td>
              </tr>
            </tbody>
            <tfoot class="bg-gray-50 border-t border-gray-200 sticky bottom-0">
              <tr>
                <td colspan="6" class="px-4 py-3 text-right">
                  <span v-if="editInvalid > 0" class="text-[11px] font-semibold text-[#ff3b30]">
                    {{ editInvalid }} row(s) need fixing
                  </span>
                  <span v-else class="text-[11px] font-semibold text-[#34c759]">All rows valid</span>
                  <span class="mx-4 text-gray-300">|</span>
                  <span class="text-[10px] font-bold text-gray-400 uppercase tracking-wide">MB Total</span>
                </td>
                <td class="px-4 py-3 text-right text-base font-bold text-gray-900">{{ fmtAmt(editTotal) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  </Teleport>
</div>
</template>
