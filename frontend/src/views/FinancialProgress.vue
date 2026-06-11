<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'

// ── Formatters ────────────────────────────────────────────────────────────────
const fmtDate = (val) => {
  if (!val) return '—'
  const s = String(val).split('T')[0].split(' ')[0]
  if (/^\d{2}[\/\-]\d{2}[\/\-]\d{4}$/.test(s)) return s.replace(/-/g, '/')
  const m = s.match(/^(\d{4})[\/\-](\d{2})[\/\-](\d{2})$/)
  if (m) return `${m[3]}/${m[2]}/${m[1]}`
  return s
}
const fmt    = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })
const fmtAmt = (v) => (v != null && v !== 0) ? '₹' + fmt.format(v) : '—'

function progressColor(pct) {
  if (pct >= 100) return '#22c55e'
  if (pct >= 75)  return '#3b82f6'
  if (pct >= 50)  return '#f59e0b'
  return '#ef4444'
}

// Extract "Bill 1" from "WR/ADI/S&T/2025/0027/B1/R1"
function billLabel(billNumber) {
  const m = String(billNumber || '').match(/B(\d+)/i)
  return m ? `Bill ${m[1]}` : billNumber
}
// "WR/ADI/S&T/2025/0027/B1/R1 (Bill 1)"
function billLabelFull(billNumber) {
  const m = String(billNumber || '').match(/B(\d+)/i)
  return m ? `${billNumber} (Bill ${m[1]})` : billNumber
}

// ── State ─────────────────────────────────────────────────────────────────────
const works        = ref([])
const worksLoading = ref(false)
const workSearch   = ref('')
const selectedWork = ref(null)
const activeTab    = ref('progress')  // 'progress' | 'bills'

// LOA detail
const bills        = ref([])
const items        = ref([])
const totals       = ref(null)
const tableLoading = ref(false)
const tableError   = ref('')

// Upload
const fileInput         = ref(null)
const uploading         = ref(false)
const preview           = ref(null)
const previewError      = ref('')
const saveError         = ref('')
const saveSuccess       = ref('')
const manualOverride    = ref('')   // manual total amount override (string input)

// Bill items edit
const editingBillId = ref(null)  // id of bill being edited (null = new upload)
const isEditingBill = computed(() => !!editingBillId.value)

// Preview inline editing / adding
const editingKey = ref(null)
const editQty    = ref('')
const editPaid   = ref('')
const showAddRow = ref(false)
const newItem    = ref({
  schedule_name: '', item_number: '', description: '',
  unit: 'Numbers', current_agmt_qty: '', amt_total: '', agreement_rate: '0',
})
const loaFetching   = ref(false)
const loaFetchFound = ref(false)

// Auto-calc amt_total when qty changes (if agreement_rate known from LOA)
watch(() => newItem.value.current_agmt_qty, (qty) => {
  const rate = parseFloat(newItem.value.agreement_rate) || 0
  if (rate > 0 && qty !== '' && qty !== null) {
    newItem.value.amt_total = String(Math.round(parseFloat(qty) * rate * 100) / 100)
  }
})

let _loaFetchTimer = null
watch(
  [() => newItem.value.schedule_name, () => newItem.value.item_number],
  ([sch, item]) => {
    loaFetchFound.value = false
    clearTimeout(_loaFetchTimer)
    if (!sch || !item || !selectedWork.value) return
    _loaFetchTimer = setTimeout(async () => {
      loaFetching.value = true
      try {
        const { data } = await axios.get('/api/financial-progress/loa-item/', {
          params: { work_id: selectedWork.value.id, schedule: sch.toUpperCase().trim(), item: item.trim() },
        })
        if (data.found) {
          newItem.value.description      = data.description      || newItem.value.description
          newItem.value.unit             = data.unit             || newItem.value.unit
          newItem.value.agreement_rate   = String(data.agreement_rate   ?? newItem.value.agreement_rate)
          newItem.value.current_agmt_qty = String(data.current_agmt_qty ?? newItem.value.current_agmt_qty)
          loaFetchFound.value = true
        }
      } catch { /* silent */ } finally {
        loaFetching.value = false
      }
    }, 400)
  }
)

const paidPreviewItems = computed(() =>
  (preview.value?.items || []).filter(i => (i.amt_total || 0) > 0)
)

const loaMismatchError = computed(() =>
  (preview.value?.warnings || []).find(w => w.toLowerCase().startsWith('loa mismatch')) || null
)

// Extract "Grand total mismatch" warning and the PDF total from it
const mismatchWarning = computed(() =>
  (preview.value?.warnings || []).find(w => w.toLowerCase().startsWith('grand total mismatch')) || null
)
const mismatchPdfTotal = computed(() => {
  if (!mismatchWarning.value) return null
  const m = mismatchWarning.value.match(/PDF=([\d,]+\.?\d*)/)
  return m ? parseFloat(m[1].replace(/,/g, '')) : null
})

const previewTotalAmount = computed(() =>
  paidPreviewItems.value.reduce((sum, i) => sum + (i.amt_total || 0), 0)
)

const tooltip = ref(null)
onBeforeUnmount(() => { tooltip.value = null })

// ── Works list ────────────────────────────────────────────────────────────────
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

const filteredWorks = computed(() => {
  const q = workSearch.value.trim().toLowerCase()
  if (!q) return works.value
  return works.value.filter(w =>
    (w.loa_number          || '').toLowerCase().includes(q) ||
    (w.tender_number       || '').toLowerCase().includes(q) ||
    (w.contractor_name     || '').toLowerCase().includes(q) ||
    (w.contractor_nickname || '').toLowerCase().includes(q) ||
    (w.consignee_display   || '').toLowerCase().includes(q)
  )
})

// ── LOA detail ────────────────────────────────────────────────────────────────
async function selectWork(w) {
  selectedWork.value  = w
  activeTab.value     = 'progress'
  bills.value         = []
  items.value         = []
  totals.value        = null
  preview.value       = null
  previewError.value  = ''
  saveError.value     = ''
  saveSuccess.value   = ''
  tableError.value    = ''
  editingBillId.value = null
  manualOverride.value = ''
  tableLoading.value  = true
  try {
    const { data } = await axios.get('/api/financial-progress/loa-table/', {
      params: { work_id: w.id },
    })
    bills.value  = data.bills   || []
    items.value  = data.items   || []
    totals.value = data.totals  || null
  } catch (e) {
    tableError.value = e.response?.data?.error || 'Failed to load.'
  } finally {
    tableLoading.value = false
  }
}

const visibleItems = computed(() => items.value.filter(i => i.cumulative_amount > 0))

// Per-bill parsed totals (sum of items' amounts for each bill, from bill_data)
const billParsedTotals = computed(() => {
  const map = {}
  for (const item of items.value) {
    for (const [billId, bd] of Object.entries(item.bill_data || {})) {
      map[billId] = (map[billId] || 0) + (bd.amount || 0)
    }
  }
  return map
})

function goBack() {
  tooltip.value        = null
  selectedWork.value   = null
  activeTab.value      = 'progress'
  bills.value          = []
  items.value          = []
  totals.value         = null
  preview.value        = null
  previewError.value   = ''
  saveError.value      = ''
  saveSuccess.value    = ''
  tableError.value     = ''
  editingBillId.value  = null
  manualOverride.value = ''
}

// ── Upload ────────────────────────────────────────────────────────────────────
function triggerUpload() {
  preview.value        = null
  previewError.value   = ''
  saveError.value      = ''
  saveSuccess.value    = ''
  editingBillId.value  = null
  manualOverride.value = ''
  fileInput.value.click()
}

function startEdit(item) {
  editingKey.value = `${item.schedule_name}:${item.item_number}`
  editQty.value    = String(item.current_agmt_qty)
  editPaid.value   = String(item.amt_total)
}
function cancelEdit() { editingKey.value = null }
function saveEdit(item) {
  const target = preview.value.items.find(
    i => i.schedule_name === item.schedule_name && i.item_number === item.item_number
  )
  if (target) {
    target.current_agmt_qty = parseFloat(editQty.value) || 0
    target.amt_total        = parseFloat(String(editPaid.value).replace(/,/g, '')) || 0
  }
  editingKey.value = null
}
function cancelAddRow() {
  showAddRow.value    = false
  loaFetchFound.value = false
  newItem.value = { schedule_name: '', item_number: '', description: '', unit: 'Numbers', current_agmt_qty: '', amt_total: '', agreement_rate: '0' }
}
function addNewItem() {
  const ni = newItem.value
  if (!ni.schedule_name || !ni.item_number) return
  preview.value.items.push({
    schedule_name:    ni.schedule_name.toUpperCase().trim(),
    item_number:      ni.item_number.trim(),
    description:      ni.description || '',
    unit:             ni.unit || '',
    agreement_rate:   parseFloat(ni.agreement_rate) || 0,
    current_agmt_qty: parseFloat(ni.current_agmt_qty) || 0,
    amt_total:        parseFloat(String(ni.amt_total).replace(/,/g, '')) || 0,
    remarks:          '',
  })
  cancelAddRow()
}

async function onFileChange(e) {
  const file = e.target.files[0]
  if (!file) return
  e.target.value = ''
  uploading.value    = true
  previewError.value = ''
  editingKey.value   = null
  showAddRow.value   = false
  const form = new FormData()
  form.append('file', file)
  if (selectedWork.value) form.append('work_id', selectedWork.value.id)
  try {
    const { data } = await axios.post('/api/financial-progress/parse/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    preview.value = data
  } catch (err) {
    previewError.value = err.response?.data?.error || 'Failed to parse PDF.'
  } finally {
    uploading.value = false
  }
}

async function confirmSave() {
  if (!preview.value || !selectedWork.value) return
  saveError.value   = ''
  saveSuccess.value = ''
  uploading.value   = true
  const billNum   = preview.value.bill_number
  const editId    = editingBillId.value
  const isEditing = !!editId
  try {
    const overrideAmt = parseFloat(manualOverride.value) || null
    if (isEditing) {
      await axios.patch(`/api/financial-progress/bills/${editId}/`, {
        items:                preview.value.items,
        total_amount_override: overrideAmt,
      })
    } else {
      await axios.post('/api/financial-progress/bills/', {
        work_id:               selectedWork.value.id,
        bill_number:           billNum,
        bill_date:             preview.value.bill_date || null,
        loa_number:            preview.value.loa_number,
        agreement_number:      preview.value.agreement_number,
        items:                 preview.value.items,
        total_amount_override: overrideAmt,
      })
    }
    preview.value        = null
    editingBillId.value  = null
    manualOverride.value = ''
    await selectWork(selectedWork.value)
    saveSuccess.value = isEditing
      ? `${billLabelFull(billNum)} updated.`
      : `${billLabelFull(billNum)} saved.`
    activeTab.value = 'bills'
  } catch (err) {
    saveError.value = err.response?.data?.error || 'Failed to save bill.'
  } finally {
    uploading.value = false
  }
}

async function deleteBill(id, billNum) {
  if (!confirm(`Delete bill "${billNum}"?`)) return
  try {
    await axios.delete(`/api/financial-progress/bills/${id}/`)
    await selectWork(selectedWork.value)
    activeTab.value = 'bills'
  } catch (err) {
    tableError.value = err.response?.data?.error || 'Failed to delete.'
  }
}

// ── Edit bill items (re-opens preview editor for an existing bill) ────────────
async function editBillItems(b) {
  previewError.value   = ''
  saveError.value      = ''
  saveSuccess.value    = ''
  editingKey.value     = null
  showAddRow.value     = false
  uploading.value      = true
  manualOverride.value = ''
  try {
    const { data } = await axios.get(`/api/financial-progress/bills/${b.id}/`)
    editingBillId.value  = b.id
    manualOverride.value = data.total_amount_override ? String(data.total_amount_override) : ''
    preview.value = {
      bill_number:      data.bill_number,
      bill_date:        data.bill_date || '',
      loa_number:       data.loa_number,
      agreement_number: data.agreement_number,
      warnings:         [],
      items:            data.items.map(i => ({
        schedule_name:    i.schedule_name,
        item_number:      i.item_number,
        description:      i.description,
        unit:             i.unit,
        agreement_rate:   i.agreement_rate,
        current_agmt_qty: i.current_agmt_qty,
        amt_total:        i.amt_total,
        remarks:          '',
      })),
    }
  } catch (err) {
    previewError.value = err.response?.data?.error || 'Failed to load bill items.'
  } finally {
    uploading.value = false
  }
}

// ── Tooltip ───────────────────────────────────────────────────────────────────
const TOOLTIP_W = 230

function tooltipStyle(x, y) {
  const nearRight = x + 14 + TOOLTIP_W > window.innerWidth
  return {
    left:  nearRight ? 'auto'                               : (x + 14) + 'px',
    right: nearRight ? (window.innerWidth - x + 14) + 'px' : 'auto',
    top:   (y - 10) + 'px',
  }
}

function showTooltip(e, billId, item) {
  const data = item.bill_data?.[String(billId)]
  if (!data || !data.amount) return

  const execQty = data.qty_upto_date || 0
  const dispQty = execQty > 0 ? execQty : data.qty

  const billPctBase = execQty > 0
    ? execQty * (item.agreement_rate || 0)
    : (data.qty || 0) * (item.agreement_rate || 0)
  const billPct = billPctBase > 0
    ? Math.round(Math.min(data.amount / billPctBase * 100, 100) * 10) / 10
    : data.pct

  tooltip.value = {
    style: tooltipStyle(e.clientX, e.clientY),
    amt:  data.amount,
    qty:  dispQty,
    unit: item.unit,
    pct:  billPct,
    bill: bills.value.find(b => b.id === billId)?.bill_number || '',
  }
}

function moveTooltip(e) {
  if (tooltip.value) {
    tooltip.value = { ...tooltip.value, style: tooltipStyle(e.clientX, e.clientY) }
  }
}

function hideTooltip() { tooltip.value = null }

onMounted(loadWorks)
</script>

<template>
  <div class="bg-white rounded-2xl soft-shadow h-full w-full flex flex-col overflow-hidden">

    <!-- ══ WORK LIST ══════════════════════════════════════════════════════════ -->
    <template v-if="!selectedWork">

      <div class="flex-shrink-0 px-8 pt-7 pb-5 border-b border-gray-100">
        <h1 class="text-2xl font-bold text-gray-900 tracking-tight mb-1">Financial Progress</h1>
        <p class="text-gray-400 text-sm font-medium mb-5">Select a LOA to view and manage bill-wise financial progress.</p>
        <div class="flex items-center bg-gray-50 border border-gray-200 rounded-2xl px-5 py-3 focus-within:ring-2 focus-within:ring-[#1D5F5E]/20 focus-within:border-[#1D5F5E] focus-within:bg-white transition-all">
          <div class="i-carbon-search text-gray-400 text-base mr-3 flex-shrink-0"></div>
          <input v-model="workSearch" type="text"
            placeholder="Search by LOA, contractor, tender, consignee…"
            class="bg-transparent outline-none w-full text-gray-700 font-medium placeholder-gray-400 text-sm" />
          <button v-if="workSearch" @click="workSearch = ''" class="ml-2 text-gray-300 hover:text-gray-500 transition-colors">
            <div class="i-carbon-close text-sm"></div>
          </button>
        </div>
      </div>

      <div v-if="worksLoading" class="flex-1 flex items-center justify-center py-24">
        <div class="i-carbon-circle-dash animate-spin text-3xl text-[#1D5F5E]"></div>
      </div>

      <div v-else-if="filteredWorks.length === 0" class="flex-1 flex flex-col items-center justify-center py-24 text-center">
        <div class="i-carbon-money text-5xl text-gray-200 mb-4"></div>
        <p class="text-sm font-semibold text-gray-400">
          {{ workSearch ? 'No works match your search.' : 'No works found.' }}
        </p>
      </div>

      <template v-else>
        <div class="flex-1 overflow-auto px-8 py-5">
          <p class="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-4">
            {{ filteredWorks.length }} {{ filteredWorks.length === 1 ? 'work' : 'works' }}
            <template v-if="workSearch"> matching "{{ workSearch }}"</template>
          </p>
          <div class="grid grid-cols-1 gap-3">
            <button
              v-for="w in filteredWorks" :key="w.id"
              @click="selectWork(w)"
              class="w-full text-left bg-white border border-gray-200 hover:border-[#1D5F5E] hover:bg-[#1D5F5E]/5 px-5 py-3 transition-all group rounded-xl"
            >
              <div class="flex items-center gap-4">
                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-center gap-2 min-w-0">
                    <span class="text-sm font-bold text-gray-900 shrink-0">{{ w.loa_number || '—' }}</span>
                    <span class="text-[11px] font-semibold bg-sky-100 text-sky-950 px-2.5 py-0.5 rounded-full truncate max-w-[180px]">{{ w.contractor_name || '—' }}</span>
                    <span v-if="w.contractor_nickname" class="text-[11px] font-semibold bg-[#fac9b8] text-[#7c3d2a] px-2.5 py-0.5 rounded-full truncate max-w-[140px]">{{ w.contractor_nickname }}</span>
                    <span v-if="w.tender_number" class="text-[11px] font-semibold bg-amber-100 text-emerald-900 px-2.5 py-0.5 rounded-full truncate max-w-[180px]">{{ w.tender_number }}</span>
                  </div>
                  <div class="flex items-center gap-3 flex-wrap mt-1.5">
                    <span class="text-[11px] text-gray-500">Consignee: <span class="font-semibold text-gray-700">{{ w.consignee_display || w.consignee || '—' }}</span></span>
                    <span class="text-gray-200">·</span>
                    <span class="text-[11px] text-gray-500">Completion: <span class="font-semibold text-gray-700">{{ fmtDate(w.date_of_completion) }}</span></span>
                  </div>
                </div>
                <div class="flex items-center gap-3 flex-shrink-0">
                  <p class="text-xs text-gray-500 whitespace-nowrap">
                    <span class="font-bold text-gray-800">{{ w.bill_count }}</span> {{ w.bill_count === 1 ? 'bill' : 'bills' }}
                  </p>
                  <div class="i-carbon-chevron-right text-gray-300 group-hover:text-[#1D5F5E] transition-colors text-lg"></div>
                </div>
              </div>
            </button>
          </div>
        </div>
      </template>

    </template>

    <!-- ══ LOA DETAIL ════════════════════════════════════════════════════════ -->
    <template v-else>
      <div class="flex flex-col h-full overflow-hidden">

        <!-- Header (no upload button here anymore) -->
        <div class="flex-shrink-0 px-6 pt-5 pb-4 border-b border-gray-100">
          <div class="flex items-start gap-4 min-w-0 flex-wrap">
            <button @click="goBack"
              class="mt-0.5 w-9 h-9 flex-shrink-0 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 transition-all">
              <div class="i-carbon-arrow-left text-base"></div>
            </button>
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2 min-w-0">
                <span class="text-xl font-bold text-gray-900 shrink-0">{{ selectedWork.loa_number || '—' }}</span>
                <span class="text-sm font-semibold bg-sky-100 text-sky-950 px-3 py-1 rounded-full truncate max-w-[260px]">{{ selectedWork.contractor_name }}</span>
                <span v-if="selectedWork.contractor_nickname" class="text-sm font-semibold bg-[#fac9b8] text-[#7c3d2a] px-3 py-1 rounded-full">{{ selectedWork.contractor_nickname }}</span>
                <span v-if="selectedWork.tender_number" class="text-sm font-semibold bg-amber-100 text-emerald-900 px-3 py-1 rounded-full truncate max-w-[220px]">{{ selectedWork.tender_number }}</span>
              </div>
              <div class="flex items-center gap-3 flex-wrap mt-1.5 text-xs text-gray-500">
                <span>Consignee: <span class="font-semibold text-gray-700">{{ selectedWork.consignee_display || selectedWork.consignee || '—' }}</span></span>
                <span class="text-gray-200">·</span>
                <span>Completion: <span class="font-semibold text-gray-700">{{ fmtDate(selectedWork.date_of_completion) }}</span></span>
              </div>
            </div>
          </div>
        </div>

        <!-- Totals banner -->
        <div v-if="totals && bills.length > 0" class="flex-shrink-0 mx-6 mt-4 rounded-2xl bg-[#EEF4F3] border border-[#1D5F5E]/20 px-5 py-3.5 flex flex-wrap items-center gap-4">
          <div class="flex flex-col min-w-[140px]">
            <span class="text-[10px] font-bold text-[#1D5F5E]/60 uppercase tracking-widest">Total Processed</span>
            <span class="text-lg font-bold text-[#1D5F5E]">{{ fmtAmt(totals.total_paid) }}</span>
          </div>
          <div class="hidden sm:block w-px h-10 bg-[#1D5F5E]/20"></div>
          <div class="flex-1 min-w-[180px]">
            <div class="flex items-center justify-between mb-1.5">
              <span class="text-[10px] font-bold text-[#1D5F5E]/60 uppercase tracking-widest">LOA Financial Progress</span>
              <span class="text-sm font-bold" :style="{ color: progressColor(totals.overall_pct) }">{{ totals.overall_pct }}%</span>
            </div>
            <div class="h-2 rounded-full bg-[#1D5F5E]/10 overflow-hidden">
              <div class="h-2 rounded-full transition-all duration-700"
                :style="{ width: Math.min(totals.overall_pct, 100) + '%', background: progressColor(totals.overall_pct) }">
              </div>
            </div>
            <div class="flex justify-between mt-1">
              <span class="text-[10px] text-gray-400">{{ fmtAmt(totals.total_paid) }} of {{ fmtAmt(totals.total_contract) }}</span>
            </div>
          </div>
        </div>

        <!-- Tab bar -->
        <div class="flex-shrink-0 flex items-center gap-1.5 px-6 mt-4">
          <button
            @click="activeTab = 'progress'"
            :class="activeTab === 'progress' ? 'bg-[#1D5F5E] text-white' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'"
            class="h-8 px-4 rounded-md text-xs font-semibold transition-all flex items-center gap-1.5"
          >
            <div class="i-carbon-data-table text-[11px]"></div>
            Financial Progress
          </button>
          <button
            @click="activeTab = 'bills'; previewError = ''; saveError = ''"
            :class="activeTab === 'bills' ? 'bg-[#1D5F5E] text-white' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'"
            class="h-8 px-4 rounded-md text-xs font-semibold transition-all flex items-center gap-1.5"
          >
            <div class="i-carbon-document text-[11px]"></div>
            Bills
            <span v-if="bills.length"
              :class="activeTab === 'bills' ? 'bg-white/20 text-white' : 'bg-[#1D5F5E]/10 text-[#1D5F5E]'"
              class="text-[11px] font-bold px-1.5 py-0.5 rounded-full leading-none">{{ bills.length }}</span>
          </button>
        </div>

        <!-- ── FINANCIAL PROGRESS TAB ──────────────────────────────────────── -->
        <template v-if="activeTab === 'progress'">
          <div class="flex-1 overflow-hidden flex flex-col min-h-0 px-6 py-4">

            <div v-if="tableLoading" class="flex-1 flex items-center justify-center text-gray-400 gap-2 text-sm">
              <div class="i-carbon-circle-dash animate-spin text-xl"></div> Loading…
            </div>

            <div v-else-if="tableError" class="flex items-center gap-2 text-red-500 text-sm p-4 bg-red-50 rounded-xl">
              <div class="i-carbon-warning"></div>{{ tableError }}
            </div>

            <div v-else-if="bills.length === 0" class="flex-1 flex flex-col items-center justify-center text-center py-16">
              <div class="i-carbon-document-add text-5xl text-gray-200 mb-4"></div>
              <p class="text-sm font-semibold text-gray-400">No bills uploaded yet.</p>
              <p class="text-xs text-gray-300 mt-1">
                Go to the
                <button @click="activeTab = 'bills'" class="text-[#1D5F5E] underline font-medium">Bills tab</button>
                to upload a bill PDF.
              </p>
            </div>

            <template v-else-if="visibleItems.length > 0">
              <div class="mb-3">
                <p class="text-xs font-bold text-gray-400 uppercase tracking-widest">
                  {{ visibleItems.length }} items with progress · {{ bills.length }} {{ bills.length === 1 ? 'bill' : 'bills' }}
                </p>
              </div>

              <div class="flex-1 overflow-auto rounded-xl border border-gray-100" style="scrollbar-width: thin;">
                <table class="text-sm border-collapse" style="min-width: max-content; width: 100%;">
                  <thead class="sticky top-0 z-10">
                    <tr class="bg-gray-50 text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
                      <th class="px-3 py-2.5 text-left border-b border-r border-gray-200 sticky left-0 bg-gray-50 z-20 whitespace-nowrap w-12">SCH</th>
                      <th class="px-3 py-2.5 text-center border-b border-r border-gray-200 sticky left-12 bg-gray-50 z-20 whitespace-nowrap w-12">ITEM</th>
                      <th class="px-3 py-2.5 text-left border-b border-r border-gray-200 min-w-[220px] sticky left-24 bg-gray-50 z-20">DESCRIPTION</th>
                      <th class="px-3 py-2.5 text-left border-b border-r border-gray-200 min-w-[150px] whitespace-nowrap">PROGRESS</th>
                      <th class="px-3 py-2.5 text-right border-b border-r border-gray-200 whitespace-nowrap">CUMULATIVE</th>
                      <th v-for="b in bills" :key="b.id"
                        class="px-4 py-2 text-right border-b border-r border-gray-200 last:border-r-0 whitespace-nowrap min-w-[100px]">
                        <div class="font-semibold">{{ billLabel(b.bill_number) }}</div>
                        <div class="text-[10px] font-normal text-gray-400 normal-case tracking-normal">{{ fmtDate(b.bill_date) }}</div>
                      </th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-gray-50">
                    <tr v-for="item in visibleItems" :key="item.schedule_name + '-' + item.item_number"
                      class="hover:bg-[#1D5F5E]/[0.03] transition-colors group">
                      <td class="px-3 py-3 border-r border-gray-100 sticky left-0 bg-white group-hover:bg-[#1D5F5E]/[0.03] z-10 font-mono text-xs font-bold text-[#1D5F5E] w-12">
                        {{ item.schedule_name }}
                      </td>
                      <td class="px-3 py-3 border-r border-gray-100 sticky left-12 bg-white group-hover:bg-[#1D5F5E]/[0.03] z-10 text-xs font-mono text-gray-500 text-center w-12">
                        {{ item.item_number }}
                      </td>
                      <td class="px-3 py-3 border-r border-gray-100 sticky left-24 bg-white group-hover:bg-[#1D5F5E]/[0.03] z-10 min-w-[220px] max-w-[280px]">
                        <p class="text-xs font-medium text-gray-800 line-clamp-2 leading-snug" :title="item.description">
                          {{ item.description || '—' }}
                        </p>
                        <span class="inline-flex items-center mt-0.5 text-[10px] font-semibold bg-violet-50 text-violet-600 px-2 py-0.5 rounded-full">
                          Qty {{ fmt.format(item.current_agmt_qty) }} {{ item.unit }}
                        </span>
                      </td>
                      <td class="px-3 py-3 border-r border-gray-100 min-w-[150px]">
                        <div class="flex items-center gap-2">
                          <div class="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                            <div class="h-1.5 rounded-full transition-all duration-500"
                              :style="{ width: item.progress_pct + '%', background: progressColor(item.progress_pct) }">
                            </div>
                          </div>
                          <span class="text-[11px] font-bold min-w-[34px] text-right"
                            :style="{ color: progressColor(item.progress_pct) }">
                            {{ item.progress_pct }}%
                          </span>
                        </div>
                      </td>
                      <td class="px-3 py-3 border-r border-gray-100 text-right text-xs font-bold text-gray-800 whitespace-nowrap">
                        {{ fmtAmt(item.cumulative_amount) }}
                      </td>
                      <td v-for="b in bills" :key="b.id"
                        class="px-4 py-3 border-r border-gray-100 text-right last:border-r-0 whitespace-nowrap"
                        @mouseenter="showTooltip($event, b.id, item)"
                        @mousemove="moveTooltip"
                        @mouseleave="hideTooltip"
                      >
                        <span v-if="item.bill_data?.[String(b.id)]?.amount"
                          class="text-xs font-semibold text-gray-700 cursor-default">
                          {{ fmtAmt(item.bill_data[String(b.id)].amount) }}
                        </span>
                        <span v-else class="text-xs text-gray-300">—</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>

            <div v-else-if="bills.length > 0" class="flex-1 flex flex-col items-center justify-center text-center py-16">
              <div class="i-carbon-data-table text-5xl text-gray-200 mb-4"></div>
              <p class="text-sm font-semibold text-gray-400">No items with financial progress yet.</p>
            </div>

          </div>
        </template>

        <!-- ── BILLS TAB ───────────────────────────────────────────────────── -->
        <template v-else>
          <div class="flex-1 overflow-hidden flex flex-col min-h-0 px-6 py-4">

            <!-- Upload button — always at top -->
            <div class="flex-shrink-0 flex items-center justify-between mb-3">
              <p class="text-xs font-bold text-gray-400 uppercase tracking-widest">
                {{ bills.length }} {{ bills.length === 1 ? 'bill' : 'bills' }} uploaded
              </p>
              <button
                @click="triggerUpload"
                :disabled="uploading"
                class="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all"
                style="background: #1D5F5E; color: white;"
              >
                <div v-if="uploading" class="i-carbon-circle-dash animate-spin text-base"></div>
                <div v-else class="i-carbon-upload text-base"></div>
                {{ uploading ? 'Processing…' : 'Upload Bill PDF' }}
              </button>
              <input ref="fileInput" type="file" accept=".pdf" class="hidden" @change="onFileChange" />
            </div>

            <!-- Status messages -->
            <div v-if="previewError || saveError || saveSuccess || tableError" class="flex-shrink-0 mb-3 space-y-2">
              <div v-if="previewError" class="flex items-center gap-2 text-red-500 text-sm p-3 bg-red-50 rounded-xl">
                <div class="i-carbon-warning text-base"></div>{{ previewError }}
              </div>
              <div v-if="saveSuccess" class="flex items-center gap-2 text-green-600 text-sm p-3 bg-green-50 rounded-xl">
                <div class="i-carbon-checkmark-filled text-base"></div>{{ saveSuccess }}
              </div>
              <div v-if="saveError" class="flex items-center gap-2 text-red-500 text-sm p-3 bg-red-50 rounded-xl">
                <div class="i-carbon-warning text-base"></div>{{ saveError }}
              </div>
              <div v-if="tableError" class="flex items-center gap-2 text-red-500 text-sm p-3 bg-red-50 rounded-xl">
                <div class="i-carbon-warning text-base"></div>{{ tableError }}
              </div>
            </div>

            <!-- Empty state -->
            <div v-if="bills.length === 0" class="flex-1 flex flex-col items-center justify-center text-center py-16">
              <div class="i-carbon-document-add text-5xl text-gray-200 mb-4"></div>
              <p class="text-sm font-semibold text-gray-400">No bills uploaded yet.</p>
              <p class="text-xs text-gray-300 mt-1">Upload a Bill PDF to begin tracking financial progress.</p>
            </div>

            <!-- Bill list -->
            <div v-else-if="bills.length > 0" class="flex-1 overflow-auto space-y-2 pb-2">
              <div v-for="b in bills" :key="b.id"
                class="border border-gray-100 rounded-xl px-4 py-3 hover:border-gray-200 transition-colors bg-white">

                <div class="flex items-center gap-3">
                  <div class="w-9 h-9 flex-shrink-0 rounded-xl flex items-center justify-center"
                    :class="b.total_amount_override != null ? 'bg-amber-50 border border-amber-200' : 'bg-teal-50 border border-teal-100'">
                    <div class="text-base"
                      :class="b.total_amount_override != null ? 'i-carbon-warning-alt text-amber-500' : 'i-carbon-document text-teal-600'"></div>
                  </div>
                  <div class="flex-1 min-w-0">
                    <p class="text-sm font-bold text-gray-800">{{ billLabelFull(b.bill_number) }}</p>
                    <div class="flex items-center gap-2 mt-0.5">
                      <span class="text-[11px] text-gray-400">{{ fmtDate(b.bill_date) }}</span>
                      <template v-if="b.total_amount_override != null">
                        <span class="text-[10px] font-bold text-amber-600 bg-amber-100 px-1.5 py-0.5 rounded-full">Manual</span>
                        <span class="text-[11px] font-semibold text-amber-700">{{ fmtAmt(b.total_amount_override) }}</span>
                      </template>
                      <template v-else-if="billParsedTotals[String(b.id)]">
                        <span class="text-[11px] text-gray-500">{{ fmtAmt(billParsedTotals[String(b.id)]) }}</span>
                      </template>
                    </div>
                  </div>
                  <div class="flex items-center gap-1 flex-shrink-0">
                    <button @click="editBillItems(b)"
                      class="w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:text-[#1D5F5E] hover:bg-[#1D5F5E]/10 transition-all"
                      title="Edit items / set manual override">
                      <div class="i-carbon-edit text-sm"></div>
                    </button>
                    <button @click="deleteBill(b.id, b.bill_number)"
                      class="w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition-all"
                      title="Delete bill">
                      <div class="i-carbon-trash-can text-sm"></div>
                    </button>
                  </div>
                </div>

              </div>
            </div>

          </div>
        </template>

      </div>
    </template>

    <!-- ── Bill Preview Modal ─────────────────────────────────────────────── -->
    <div v-if="preview" class="fixed inset-0 z-[500] flex items-center justify-center p-4" style="background: rgba(0,0,0,0.45);">
      <div class="bg-white rounded-2xl w-full flex flex-col shadow-2xl" style="max-width: 860px; max-height: 90vh;">

        <!-- LOA mismatch error -->
        <div v-if="loaMismatchError" class="flex-shrink-0 flex items-start gap-2 px-6 py-3 bg-red-50 border-b border-red-200 rounded-t-2xl">
          <div class="i-carbon-warning-filled text-red-500 text-base flex-shrink-0 mt-0.5"></div>
          <p class="text-sm font-semibold text-red-600">{{ loaMismatchError }}</p>
        </div>

        <!-- Header -->
        <div class="flex-shrink-0 bg-[#EEF4F3] px-6 py-4 flex items-center justify-between flex-wrap gap-3" :class="loaMismatchError ? '' : 'rounded-t-2xl'">
          <div>
            <p class="text-sm font-bold text-[#1D5F5E]">{{ billLabelFull(preview.bill_number) || 'Parsed Bill' }}</p>
            <p class="text-xs text-gray-500">{{ preview.bill_date }} · LOA: {{ preview.loa_number }}</p>
            <p v-if="preview.warnings?.filter(w => !w.toLowerCase().startsWith('loa mismatch')).length"
              class="text-xs text-amber-600 mt-1">
              ⚠ {{ preview.warnings.filter(w => !w.toLowerCase().startsWith('loa mismatch')).join(' | ') }}
            </p>
          </div>
          <div class="flex flex-col items-end flex-shrink-0">
            <span class="text-[10px] font-bold text-[#1D5F5E]/60 uppercase tracking-widest mb-0.5">Total Bill Amount</span>
            <span class="text-xl font-bold text-[#1D5F5E]">{{ fmtAmt(previewTotalAmount) }}</span>
            <span class="text-[10px] text-gray-400 mt-0.5">{{ paidPreviewItems.length }} paid items · verify against PDF</span>
          </div>
          <div class="flex gap-2">
            <button @click="preview = null; editingKey = null; showAddRow = false; editingBillId = null; manualOverride = ''"
              class="px-4 py-2 rounded-xl text-sm font-semibold text-gray-600 bg-white border border-gray-200 hover:bg-gray-50 transition-colors">
              Cancel
            </button>
            <button @click="confirmSave" :disabled="uploading || !!loaMismatchError"
              class="px-4 py-2 rounded-xl text-sm font-semibold text-white transition-colors"
              :style="loaMismatchError ? 'background: #9ca3af; cursor: not-allowed;' : 'background: #1D5F5E;'"
              :title="loaMismatchError ? 'Cannot save: LOA number does not match' : ''">
              {{ uploading ? 'Saving…' : isEditingBill ? `Update Bill (${paidPreviewItems.length} items)` : `Save Bill (${paidPreviewItems.length} items)` }}
            </button>
          </div>
        </div>

        <!-- Sub-header -->
        <div class="flex-shrink-0 bg-white px-4 py-2 border-b border-gray-100 flex items-center justify-between">
          <span class="text-xs text-gray-500">
            Showing <strong class="text-gray-800">{{ paidPreviewItems.length }}</strong> paid items
            <span class="text-gray-400">(of {{ preview.items?.length || 0 }} total parsed)</span>
          </span>
          <button @click="showAddRow = !showAddRow; cancelEdit()"
            class="flex items-center gap-1 text-xs font-semibold text-[#1D5F5E] hover:underline">
            <div class="i-carbon-add text-sm"></div> Add missing item
          </button>
        </div>

        <!-- Manual override strip -->
        <div class="flex-shrink-0 px-4 py-2.5 border-b flex items-center gap-3 flex-wrap"
          :class="manualOverride
            ? 'bg-amber-50 border-amber-200'
            : mismatchWarning
              ? 'bg-amber-50 border-amber-300'
              : 'bg-gray-50 border-gray-100'">
          <div class="i-carbon-warning-alt text-sm flex-shrink-0"
            :class="(manualOverride || mismatchWarning) ? 'text-amber-500' : 'text-gray-400'"></div>
          <span class="text-xs flex-1" :class="(manualOverride || mismatchWarning) ? 'text-amber-800' : 'text-gray-500'">
            <template v-if="mismatchWarning && !manualOverride">
              <strong>Total mismatch detected.</strong> Enter correct bill total to fix financial progress.
            </template>
            <template v-else>
              Parsed total incorrect? Enter correct bill total to override financial progress.
            </template>
          </span>
          <!-- Quick-fill button when mismatch has a known PDF total -->
          <button v-if="mismatchPdfTotal && !manualOverride"
            @click="manualOverride = String(mismatchPdfTotal)"
            class="flex-shrink-0 text-[11px] font-semibold px-2.5 py-1 rounded-lg border border-amber-400 text-amber-700 bg-amber-100 hover:bg-amber-200 transition-colors whitespace-nowrap">
            Use PDF total {{ fmtAmt(mismatchPdfTotal) }}
          </button>
          <div class="flex items-center gap-1.5 flex-shrink-0">
            <span class="text-xs font-medium" :class="(manualOverride || mismatchWarning) ? 'text-amber-600' : 'text-gray-400'">₹</span>
            <input
              v-model="manualOverride"
              type="number"
              min="0"
              placeholder="Manual total"
              class="w-36 text-right text-xs border rounded-lg px-2 py-1.5 outline-none transition-colors"
              :class="manualOverride
                ? 'border-amber-400 bg-white text-amber-800 font-semibold focus:border-amber-500'
                : mismatchWarning
                  ? 'border-amber-300 bg-amber-50 text-gray-700 focus:border-amber-500'
                  : 'border-gray-200 bg-white text-gray-700 focus:border-[#1D5F5E]'"
            />
            <button v-if="manualOverride" @click="manualOverride = ''"
              class="text-gray-400 hover:text-gray-600 ml-0.5" title="Clear override">
              <div class="i-carbon-close text-sm"></div>
            </button>
          </div>
          <span v-if="manualOverride" class="text-xs font-bold text-amber-700 flex-shrink-0">
            {{ fmtAmt(parseFloat(manualOverride)) }}
          </span>
        </div>

        <!-- Items table -->
        <div class="flex-1 overflow-auto">
          <table class="w-full text-xs text-gray-700">
            <thead class="sticky top-0 z-10">
              <tr class="bg-gray-50 text-[11px] font-semibold text-gray-500 uppercase tracking-wider border-b border-gray-100">
                <th class="px-3 py-2 text-left">SCH</th>
                <th class="px-3 py-2 text-left">ITEM</th>
                <th class="px-3 py-2 text-left" style="min-width:160px">DESCRIPTION</th>
                <th class="px-3 py-2 text-right">QTY</th>
                <th class="px-3 py-2 text-left">UNIT</th>
                <th class="px-3 py-2 text-right">PAID</th>
                <th class="px-2 py-2 w-8"></th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50">
              <template v-for="item in paidPreviewItems" :key="item.schedule_name + '-' + item.item_number">
                <tr v-if="editingKey === `${item.schedule_name}:${item.item_number}`" class="bg-amber-50">
                  <td class="px-3 py-2 font-mono font-semibold text-[#1D5F5E]">{{ item.schedule_name }}</td>
                  <td class="px-3 py-2 text-gray-500">{{ item.item_number }}</td>
                  <td class="px-3 py-2 text-gray-400 text-[10px]" style="max-width:200px">
                    <p class="line-clamp-2">{{ item.description || '—' }}</p>
                  </td>
                  <td class="px-3 py-2 text-right">
                    <input v-model="editQty" type="number"
                      class="w-20 text-right border border-amber-300 rounded px-1 py-0.5 text-xs bg-white outline-none focus:border-[#1D5F5E]" />
                  </td>
                  <td class="px-3 py-2 text-gray-500">{{ item.unit }}</td>
                  <td class="px-3 py-2 text-right">
                    <input v-model="editPaid" type="number"
                      class="w-24 text-right border border-amber-300 rounded px-1 py-0.5 text-xs bg-white outline-none focus:border-[#1D5F5E]" />
                  </td>
                  <td class="px-2 py-2">
                    <div class="flex items-center gap-1">
                      <button @click="saveEdit(item)" class="text-green-600 hover:text-green-700" title="Save">
                        <div class="i-carbon-checkmark text-sm"></div>
                      </button>
                      <button @click="cancelEdit" class="text-gray-400 hover:text-gray-600" title="Cancel">
                        <div class="i-carbon-close text-sm"></div>
                      </button>
                    </div>
                  </td>
                </tr>
                <tr v-else class="hover:bg-gray-50 group">
                  <td class="px-3 py-2 font-mono font-semibold text-[#1D5F5E]">{{ item.schedule_name }}</td>
                  <td class="px-3 py-2 text-gray-600">{{ item.item_number }}</td>
                  <td class="px-3 py-2" style="max-width:220px">
                    <p class="text-xs text-gray-700 line-clamp-2 leading-snug">{{ item.description || '—' }}</p>
                  </td>
                  <td class="px-3 py-2 text-right font-mono text-gray-700">{{ item.current_agmt_qty }}</td>
                  <td class="px-3 py-2 text-gray-500">{{ item.unit }}</td>
                  <td class="px-3 py-2 text-right font-semibold text-[#1D5F5E]">{{ fmtAmt(item.amt_total) }}</td>
                  <td class="px-2 py-2">
                    <button @click="startEdit(item); showAddRow = false"
                      class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-[#1D5F5E] transition-all" title="Edit">
                      <div class="i-carbon-edit text-sm"></div>
                    </button>
                  </td>
                </tr>
              </template>
              <tr v-if="showAddRow" class="bg-green-50/70">
                <td class="px-2 py-2">
                  <input v-model="newItem.schedule_name" placeholder="A1"
                    class="w-14 border border-green-300 rounded px-1 py-0.5 text-xs bg-white uppercase outline-none focus:border-[#1D5F5E]" />
                </td>
                <td class="px-2 py-2">
                  <div class="flex items-center gap-1">
                    <input v-model="newItem.item_number" placeholder="40"
                      class="w-12 border border-green-300 rounded px-1 py-0.5 text-xs bg-white outline-none focus:border-[#1D5F5E]" />
                    <div v-if="loaFetching" class="i-carbon-circle-dash animate-spin text-xs text-gray-400"></div>
                    <div v-else-if="loaFetchFound" class="i-carbon-checkmark-filled text-xs text-[#1D5F5E]" title="Auto-filled from LOA"></div>
                  </div>
                </td>
                <td class="px-2 py-2">
                  <input v-model="newItem.description" placeholder="Description (optional)"
                    class="w-full border border-green-300 rounded px-1 py-0.5 text-xs bg-white outline-none focus:border-[#1D5F5E]" />
                </td>
                <td class="px-2 py-2">
                  <input v-model="newItem.current_agmt_qty" type="number" placeholder="Qty"
                    class="w-20 text-right border border-green-300 rounded px-1 py-0.5 text-xs bg-white outline-none focus:border-[#1D5F5E]" />
                </td>
                <td class="px-2 py-2">
                  <input v-model="newItem.unit" placeholder="Unit"
                    class="w-16 border border-green-300 rounded px-1 py-0.5 text-xs bg-white outline-none focus:border-[#1D5F5E]" />
                </td>
                <td class="px-2 py-2">
                  <input v-model="newItem.amt_total" type="number" placeholder="Amount"
                    class="w-24 text-right border border-green-300 rounded px-1 py-0.5 text-xs bg-white outline-none focus:border-[#1D5F5E]"
                    :title="parseFloat(newItem.agreement_rate) > 0 ? 'Auto-calculated from LOA rate × qty. Override if needed.' : 'Enter amount manually'" />
                </td>
                <td class="px-2 py-2">
                  <div class="flex items-center gap-1">
                    <button @click="addNewItem" class="text-green-600 hover:text-green-700" title="Add item">
                      <div class="i-carbon-checkmark text-sm"></div>
                    </button>
                    <button @click="cancelAddRow" class="text-gray-400 hover:text-gray-600" title="Cancel">
                      <div class="i-carbon-close text-sm"></div>
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

      </div>
    </div>

    <!-- Tooltip -->
    <div
      v-if="tooltip"
      class="fixed z-[9999] pointer-events-none px-3 py-2.5 rounded-xl bg-gray-900 text-white text-xs shadow-xl"
      :style="tooltip.style"
    >
      <p class="font-semibold text-gray-200 mb-1.5 truncate max-w-[200px]">{{ tooltip.bill }}</p>
      <div class="space-y-0.5">
        <div class="flex justify-between gap-4">
          <span class="text-gray-400">Qty</span>
          <span class="font-semibold">{{ fmt.format(tooltip.qty) }}<span class="text-gray-500 font-normal text-[10px] ml-1">{{ tooltip.unit }}</span></span>
        </div>
        <div class="flex justify-between gap-4">
          <span class="text-gray-400">Bill %</span>
          <span class="font-semibold" :style="{ color: progressColor(tooltip.pct) }">{{ tooltip.pct }}%</span>
        </div>
        <div class="flex justify-between gap-4">
          <span class="text-gray-400">Amount</span>
          <span class="font-semibold text-emerald-400">{{ fmtAmt(tooltip.amt) }}</span>
        </div>
      </div>
    </div>

  </div>
</template>
