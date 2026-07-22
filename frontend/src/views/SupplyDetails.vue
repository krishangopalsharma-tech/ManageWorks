<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const fmtDate = (val) => {
  if (!val) return '—'
  const s = String(val).split('T')[0].split(' ')[0]
  if (/^\d{2}[\/\-]\d{2}[\/\-]\d{4}$/.test(s)) return s.replace(/-/g, '/')
  const m = s.match(/^(\d{4})[\/\-](\d{2})[\/\-](\d{2})$/)
  if (m) return `${m[3]}/${m[2]}/${m[1]}`
  return s
}

const supplyPct = (item) => { const r = item.qty || 0; if (!r) return 0; return Math.min(Math.round((item.supplied_quantity || 0) / r * 100), 999) }

const recalcSupplied = (item) => {
  const entries = (item.entries || []).filter(e => e.entry_type === 'supply')
  item.supplied_quantity = entries.reduce((s, e) => s + (e.quantity || 0), 0)
}

// ── State ──────────────────────────────────────────────────────────────────
const searchQuery  = ref('')
const itemFilter   = ref('')
const allWorks     = ref([])
const selectedWork = ref(null)
const isLoading    = ref(true)
const currentUser  = ref(null)

const isAdmin     = computed(() => currentUser.value?.role === 'admin' || currentUser.value?.is_staff)

// True when logged-in user is the primary consignee assigned to the selected work
const isWorkConsignee = computed(() => {
  if (!currentUser.value || !selectedWork.value) return false
  return currentUser.value.hrms_id === selectedWork.value.hrms_id
})
// Supply Details is view-only for Admin/Super Admin — only the assigned consignee submits.
const canSubmitSupply = computed(() => isWorkConsignee.value)

const canEditEntry = (entry) => {
  if (!currentUser.value) return false
  return entry.submitted_by_user?.id === currentUser.value.id
}

// Lot entry popup
const lotPopupItem = ref(null)
const entryForm    = ref({
  quantity: '', receive_note_no: '', date_of_receipt: '', challan_no: '', udm_entry: '',
  isSubmitting: false, status: '',
})

// Single PDF fill state
const pdfFilling = ref(false)
const pdfFillWarnings = ref([])

// Inline entry editing
const editingEntry    = ref(null)
const isSavingEntry   = ref(false)
const entrySaveStatus = ref('')

// ── Batch PDF Modal ────────────────────────────────────────────────────────
const batchModal      = ref(false)
const batchParsing    = ref(false)
const batchResults    = ref([])
const batchSubmitting = ref(false)
const batchDone       = ref(false)
const batchParseError = ref('')

const normalizeItemNum = (s) => {
  const n = parseInt(s, 10)
  return isNaN(n) ? s : String(n)
}
const parsePdfSerial = (raw) => {
  const s = (raw || '').trim().replace(/[\s\-/]+$/, '').toUpperCase()
  const m = s.match(/^([A-Z]\d*)-(\d+)$/)
  if (m) return { schedule: m[1], itemNum: normalizeItemNum(m[2]) }
  return { schedule: null, itemNum: normalizeItemNum(s) }
}
const descScore = (a, b) => {
  if (!a || !b) return 0
  const wa = new Set((a.toLowerCase().match(/\w+/g) || []).filter(w => w.length > 2))
  const wb = new Set((b.toLowerCase().match(/\w+/g) || []).filter(w => w.length > 2))
  let overlap = 0
  for (const w of wa) if (wb.has(w)) overlap++
  return overlap / Math.max(wa.size, wb.size, 1)
}
const normalizeNum = (s) => {
  const f = parseFloat(s)
  return (!isNaN(f) && f === Math.floor(f)) ? String(Math.floor(f)) : s
}
const parseItemSerial = (raw) => {
  const s = (raw || '').trim().replace(/[\s\-/]+$/, '').toUpperCase()
  const m = s.match(/^([A-Z]+)-(\d+)$/)
  if (m) return { schedule: m[1], itemNum: normalizeItemNum(m[2]) }
  return { schedule: null, itemNum: normalizeItemNum(normalizeNum(s)) }
}
const findBestMatch = (pdfSerial, pdfDesc) => {
  const items = supplyItems.value
  if (!items.length) return null
  const { schedule, itemNum } = parsePdfSerial(pdfSerial)

  let candidates = items.filter(item => {
    const { schedule: iSch, itemNum: iNum } = parseItemSerial(item.serial_number)
    const dbSch = iSch || (item.schedule || '').trim().toUpperCase()
    return schedule && itemNum && (dbSch === schedule || dbSch.startsWith(schedule)) && iNum === itemNum
  })
  if (!candidates.length && itemNum) {
    candidates = items.filter(item => parseItemSerial(item.serial_number).itemNum === itemNum)
  }
  if (!candidates.length) return null
  if (candidates.length === 1) return candidates[0]

  let best = null, bestScore = -1
  for (const item of candidates) {
    const s = descScore(pdfDesc, item.item_desc)
    if (s > bestScore) { bestScore = s; best = item }
  }
  return best
}

const openBatchModal = () => {
  batchResults.value = []
  batchParsing.value = false
  batchDone.value    = false
  batchParseError.value = ''
  batchModal.value   = true
}
const closeBatchModal = () => { batchModal.value = false }

const onBatchFilesSelected = async (evt) => {
  const files = Array.from(evt.target.files || [])
  if (!files.length) return
  batchParsing.value = true
  batchParseError.value = ''
  batchDone.value = false

  const MAX_CHUNK_BYTES = 800 * 1024
  const chunks = []
  let chunk = [], chunkSize = 0
  for (const f of files) {
    if (chunk.length && chunkSize + f.size > MAX_CHUNK_BYTES) {
      chunks.push(chunk)
      chunk = []
      chunkSize = 0
    }
    chunk.push(f)
    chunkSize += f.size
  }
  if (chunk.length) chunks.push(chunk)

  try {
    for (const chunkFiles of chunks) {
      const fd = new FormData()
      for (const f of chunkFiles) fd.append('files', f)
      if (selectedWork.value?.id) fd.append('work_id', selectedWork.value.id)
      const res = await axios.post('/api/supply-details/parse-pdfs/', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      const newResults = res.data.map(r => {
        const matchedItem = findBestMatch(r.serial_number, r.item_desc)
        return {
          ...r,
          matchedItemId: matchedItem ? matchedItem.id : '',
          include: !r.error,
          submitting: false, done: false, submitError: '',
        }
      })
      batchResults.value = [...batchResults.value, ...newResults]
    }
  } catch (e) {
    const st = e.response?.status
    if (st === 413) {
      batchParseError.value = 'One or more PDFs are too large to upload individually.'
    } else {
      batchParseError.value = 'Upload failed. Please try again.'
    }
    console.error(e)
  } finally {
    batchParsing.value = false
    evt.target.value = ''
  }
}

const submitBatchEntries = async () => {
  batchSubmitting.value = true
  const toSubmit = batchResults.value.filter(r => r.include && r.matchedItemId && !r.done)

  for (const r of toSubmit) {
    r.submitting = true
    r.submitError = ''
    const payload = {
      quantity:        r.quantity,
      receive_note_no: r.receive_note_no || '',
      date_of_receipt: r.date_of_receipt || null,
      challan_no:      r.challan_no || '',
      udm_entry:       '',
    }
    try {
      const res = await axios.post(`/api/supply-details/items/${r.matchedItemId}/entries/`, payload)
      const item = supplyItems.value.find(i => i.id === r.matchedItemId)
      if (item) {
        if (!item.entries) item.entries = []
        item.entries.push(res.data)
        recalcSupplied(item)
      }
      r.done = true
    } catch (e) {
      const status = e.response?.status
      if (status === 403) r.submitError = 'Access denied'
      else if (status === 409) r.submitError = 'Duplicate receipt no.'
      else r.submitError = 'Failed'
    } finally {
      r.submitting = false
    }
  }
  batchSubmitting.value = false
  batchDone.value = toSubmit.every(r => r.done)
  if (batchDone.value) {
    setTimeout(closeBatchModal, 800)
  }
}

// ── Load ───────────────────────────────────────────────────────────────────
const loadWorks = async () => {
  isLoading.value = true
  try {
    const [worksRes, meRes] = await Promise.allSettled([
      axios.get('/api/supply-details/works/search/'),
      axios.get('/api/auth/me/'),
    ])
    if (worksRes.status === 'fulfilled') allWorks.value    = worksRes.value.data
    if (meRes.status    === 'fulfilled') currentUser.value = meRes.value.data
  } catch (e) {
    console.error(e)
  } finally {
    isLoading.value = false
  }
}
onMounted(loadWorks)

const filteredWorks = computed(() => {
  if (!searchQuery.value.trim()) return allWorks.value
  const q = searchQuery.value.toLowerCase()
  return allWorks.value.filter(w =>
    (w.loa_number          && w.loa_number.toLowerCase().includes(q)) ||
    (w.contractor_name     && w.contractor_name.toLowerCase().includes(q)) ||
    (w.contractor_nickname && w.contractor_nickname.toLowerCase().includes(q)) ||
    (w.tender_number       && w.tender_number.toLowerCase().includes(q)) ||
    (w.consignee           && w.consignee.toLowerCase().includes(q))
  )
})

// Supply Details only shows SS + SI items (not pure-execution items)
const supplyItems = computed(() => {
  if (!selectedWork.value) return []
  return (selectedWork.value.items || []).filter(i => i.category !== 'execution')
})

const filteredItems = computed(() => {
  if (!itemFilter.value.trim()) return supplyItems.value
  const q = itemFilter.value.toLowerCase()
  return supplyItems.value.filter(i =>
    (i.schedule  && i.schedule.toLowerCase().includes(q)) ||
    (i.item_desc && i.item_desc.toLowerCase().includes(q))
  )
})

const sortKey = ref('')
const sortDir = ref('desc')
const toggleSort = (key) => {
  if (sortKey.value === key) { sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc' }
  else { sortKey.value = key; sortDir.value = 'desc' }
}
const sortIcon = (key) => {
  if (sortKey.value !== key) return 'i-carbon-arrows-vertical'
  return sortDir.value === 'asc' ? 'i-carbon-arrow-up' : 'i-carbon-arrow-down'
}
const _cmpSerial = (a, b) => {
  const sa = (a.schedule || '').toUpperCase()
  const sb = (b.schedule || '').toUpperCase()
  if (sa !== sb) return sa.localeCompare(sb)
  const an = parseInt(a.serial_number, 10)
  const bn = parseInt(b.serial_number, 10)
  if (!isNaN(an) && !isNaN(bn)) return an - bn
  return (a.serial_number || '').localeCompare(b.serial_number || '')
}
const sortedItems = computed(() => {
  if (!sortKey.value) return [...filteredItems.value].sort(_cmpSerial)
  return [...filteredItems.value].sort((a, b) => {
    let av, bv
    if      (sortKey.value === 'qty')       { av = a.qty || 0;                  bv = b.qty || 0 }
    else if (sortKey.value === 'submitted') { av = a.supplied_quantity || 0;    bv = b.supplied_quantity || 0 }
    else if (sortKey.value === 'progress')  { av = supplyPct(a);                bv = supplyPct(b) }
    return sortDir.value === 'asc' ? av - bv : bv - av
  })
})

const selectWork = async (work) => {
  itemFilter.value   = ''
  sortKey.value      = ''
  lotPopupItem.value = null
  selectedWork.value = { ...work, items: work.items.map(i => ({ ...i, entries: (i.entries || []).map(e => ({ ...e })) })) }
  try {
    const res = await axios.get(`/api/supply-details/works/${work.id}/detail/`)
    const fresh = res.data
    selectedWork.value = { ...fresh, items: fresh.items.map(i => ({ ...i, entries: (i.entries || []).map(e => ({ ...e })) })) }
    const idx = allWorks.value.findIndex(w => w.id === fresh.id)
    if (idx !== -1) allWorks.value[idx] = fresh
  } catch (e) {
    console.error('Failed to refresh work data:', e)
  }
}

const openLotPopup = (item) => {
  lotPopupItem.value = item
  editingEntry.value    = null
  entrySaveStatus.value = ''
  pdfFillWarnings.value = []
  entryForm.value = {
    quantity: '', receive_note_no: '', date_of_receipt: '', challan_no: '', udm_entry: '',
    isSubmitting: false, status: '',
  }
}
const closeLotPopup = () => { lotPopupItem.value = null; editingEntry.value = null }

const fillFromPdf = async (evt) => {
  const file = evt.target.files?.[0]
  if (!file) return
  pdfFilling.value      = true
  pdfFillWarnings.value = []
  const fd = new FormData()
  fd.append('files', file)
  if (selectedWork.value?.id) fd.append('work_id', selectedWork.value.id)
  try {
    const res = await axios.post('/api/supply-details/parse-pdfs/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    const parsed = res.data[0]
    if (parsed.error) {
      pdfFillWarnings.value = parsed.parse_warnings || ['Failed to parse PDF.']
    } else {
      entryForm.value.receive_note_no = parsed.receive_note_no || ''
      entryForm.value.date_of_receipt = parsed.date_of_receipt || ''
      entryForm.value.challan_no      = parsed.challan_no      || ''
      entryForm.value.quantity        = parsed.quantity != null ? String(parsed.quantity) : ''
      pdfFillWarnings.value = parsed.parse_warnings || []
    }
  } catch (e) {
    pdfFillWarnings.value = ['Upload failed. Please try again.']
  } finally {
    pdfFilling.value = false
    evt.target.value = ''
  }
}

const submitEntry = async () => {
  const item = lotPopupItem.value
  const form = entryForm.value

  if (!form.quantity || parseFloat(form.quantity) <= 0) {
    form.status = 'invalid'; setTimeout(() => { form.status = '' }, 2000); return
  }

  form.isSubmitting = true
  form.status = ''
  try {
    const payload = {
      quantity:        parseFloat(form.quantity),
      receive_note_no: form.receive_note_no,
      date_of_receipt: form.date_of_receipt || null,
      challan_no:      form.challan_no,
      udm_entry:       form.udm_entry,
    }
    const res = await axios.post(`/api/supply-details/items/${item.id}/entries/`, payload)
    if (!item.entries) item.entries = []
    item.entries.push(res.data)
    recalcSupplied(item)

    form.quantity = ''; form.receive_note_no = ''; form.date_of_receipt = ''
    form.challan_no = ''; form.udm_entry = ''
    pdfFillWarnings.value = []
    form.status = 'ok'
    setTimeout(() => { form.status = '' }, 2500)
  } catch (e) {
    console.error(e)
    const st = e.response?.status
    form.status = st === 403 ? 'denied' : st === 409 ? 'duplicate' : 'error'
    setTimeout(() => { form.status = '' }, 3500)
  } finally {
    form.isSubmitting = false
  }
}

const openEditEntry = (entry) => {
  entrySaveStatus.value = ''
  editingEntry.value = {
    id: entry.id, quantity: entry.quantity,
    receive_note_no: entry.receive_note_no || '', date_of_receipt: entry.date_of_receipt || '',
    challan_no: entry.challan_no || '', udm_entry: entry.udm_entry || '',
  }
}
const closeEditEntry = () => { editingEntry.value = null; entrySaveStatus.value = '' }

const saveEditEntry = async () => {
  const e    = editingEntry.value
  const item = lotPopupItem.value
  if (!e.quantity || parseFloat(e.quantity) <= 0) return

  isSavingEntry.value   = true
  entrySaveStatus.value = ''
  try {
    const payload = {
      quantity: parseFloat(e.quantity),
      receive_note_no: e.receive_note_no, date_of_receipt: e.date_of_receipt || null,
      challan_no: e.challan_no, udm_entry: e.udm_entry,
    }
    const res = await axios.patch(`/api/supply-details/entries/${e.id}/`, payload)
    const idx = (item.entries || []).findIndex(x => x.id === e.id)
    if (idx !== -1) item.entries[idx] = res.data
    recalcSupplied(item)
    entrySaveStatus.value = 'saved'
    setTimeout(closeEditEntry, 900)
  } catch (err) {
    console.error(err)
    entrySaveStatus.value = err.response?.status === 403 ? 'denied' : 'error'
  } finally {
    isSavingEntry.value = false
  }
}
</script>

<template>
  <div class="bg-white rounded-2xl soft-shadow h-full w-full flex flex-col overflow-hidden">

    <!-- ══ WORK LIST VIEW ════════════════════════════════════════════ -->
    <template v-if="!selectedWork">
      <div class="flex-shrink-0 px-8 pt-7 pb-5 border-b border-gray-100">
        <h1 class="text-2xl font-bold text-gray-900 tracking-tight mb-1">Supply Details</h1>
        <p class="text-gray-400 text-sm font-medium mb-5">Search, then open a work to submit supply lot entries against its items.</p>
        <div class="flex items-center bg-gray-50 border border-gray-200 rounded-2xl px-5 py-3 focus-within:ring-2 focus-within:ring-[#1D5F5E]/20 focus-within:border-[#1D5F5E] focus-within:bg-white transition-all">
          <div class="i-carbon-search text-gray-400 text-base mr-3 flex-shrink-0"></div>
          <input v-model="searchQuery" type="text"
            placeholder="Search by LOA, Contractor, Tender, Consignee..."
            class="bg-transparent outline-none w-full text-gray-700 font-medium placeholder-gray-400 text-sm">
          <button v-if="searchQuery" @click="searchQuery = ''" class="ml-2 text-gray-300 hover:text-gray-500 transition-colors">
            <div class="i-carbon-close text-sm"></div>
          </button>
        </div>
      </div>

      <div v-if="isLoading" class="flex-1 flex items-center justify-center py-24">
        <div class="i-carbon-circle-dash animate-spin text-3xl text-[#1D5F5E]"></div>
      </div>

      <div v-else-if="filteredWorks.length === 0" class="flex-1 flex flex-col items-center justify-center py-24 text-center">
        <div class="i-carbon-document-unknown text-5xl text-gray-200 mb-4"></div>
        <p class="text-sm font-semibold text-gray-400">{{ searchQuery ? 'No works match your search.' : 'No works uploaded yet.' }}</p>
      </div>

      <template v-else>
        <div class="flex-1 overflow-auto px-8 py-5">
          <p class="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-4">
            {{ filteredWorks.length }} {{ filteredWorks.length === 1 ? 'work' : 'works' }}
            <template v-if="searchQuery"> matching "{{ searchQuery }}"</template>
          </p>
          <div class="grid grid-cols-1 gap-3">
            <button v-for="work in filteredWorks" :key="work.id" type="button"
              class="w-full text-left bg-white border border-gray-200 hover:border-[#1D5F5E] hover:bg-[#1D5F5E]/5 px-5 py-3 rounded-xl transition-all group cursor-pointer"
              @click="selectWork(work)">
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-center gap-2 min-w-0">
                    <span class="text-sm font-bold text-gray-900 shrink-0">{{ work.loa_number || '—' }}</span>
                    <span class="text-[11px] font-semibold bg-sky-100 text-sky-950 px-2.5 py-0.5 rounded-full truncate max-w-[180px]">{{ work.contractor_name || '—' }}</span>
                    <span v-if="work.contractor_nickname" class="text-[11px] font-semibold bg-[#fac9b8] text-[#7c3d2a] px-2.5 py-0.5 rounded-full truncate max-w-[140px]">{{ work.contractor_nickname }}</span>
                    <span v-if="work.tender_number" class="text-[11px] font-semibold bg-amber-100 text-emerald-900 px-2.5 py-0.5 rounded-full truncate max-w-[180px]">{{ work.tender_number }}</span>
                  </div>
                  <div class="flex items-center gap-3 flex-wrap mt-1.5">
                    <span class="text-[11px] text-gray-500">Consignee: <span class="font-semibold text-gray-700">{{ work.consignee_display || work.consignee || '—' }}</span></span>
                  </div>
                </div>
                <div class="flex items-center gap-3 flex-shrink-0">
                  <p class="text-xs text-gray-500 whitespace-nowrap">
                    <span class="font-bold text-gray-800">{{ (work.items || []).filter(i => i.category !== 'execution').length }}</span> supply items
                  </p>
                  <div class="i-carbon-chevron-right text-gray-300 group-hover:text-[#1D5F5E] transition-colors text-lg"></div>
                </div>
              </div>
            </button>
          </div>
        </div>
      </template>
    </template>

    <!-- ══ ITEMS VIEW ════════════════════════════════════════════════ -->
    <template v-else>
      <div class="flex flex-col h-full animate-fade-in">
        <div class="px-8 pt-6 pb-5 border-b border-gray-100">
          <div class="flex items-start justify-between gap-6">
            <div class="flex items-start gap-4 min-w-0">
              <button @click="selectedWork = null"
                class="mt-0.5 w-9 h-9 flex-shrink-0 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 transition-all">
                <div class="i-carbon-arrow-left text-base"></div>
              </button>
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2 min-w-0">
                  <span class="text-xl font-bold text-gray-900 shrink-0">{{ selectedWork.loa_number || '—' }}</span>
                  <span class="text-sm font-semibold bg-sky-100 text-sky-950 px-3 py-1 rounded-full truncate max-w-[260px]">{{ selectedWork.contractor_name }}</span>
                  <span v-if="selectedWork.contractor_nickname" class="text-sm font-semibold bg-[#fac9b8] text-[#7c3d2a] px-3 py-1 rounded-full truncate max-w-[200px]">{{ selectedWork.contractor_nickname }}</span>
                </div>
                <p v-if="selectedWork.name_of_work" class="text-xs text-gray-500 mt-1.5 leading-snug max-w-2xl">{{ selectedWork.name_of_work }}</p>
                <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 mt-2">
                  <span class="flex items-center gap-1.5 text-xs text-gray-500">
                    <span class="font-medium text-gray-400">Consignee</span>
                    <span class="font-semibold text-gray-800">{{ selectedWork.consignee_display || selectedWork.consignee || '—' }}</span>
                  </span>
                </div>
                <p v-if="!isWorkConsignee && !isAdmin" class="mt-2 text-[11px] font-semibold text-amber-600 bg-amber-50 inline-block px-2 py-0.5 rounded-full">
                  View only — you are not the assigned consignee for this LOA
                </p>
                <p v-else-if="isAdmin" class="mt-2 text-[11px] font-semibold text-amber-600 bg-amber-50 inline-block px-2 py-0.5 rounded-full">
                  View only — Admins cannot submit supply entries
                </p>
              </div>
            </div>
            <div class="flex-shrink-0 flex items-center gap-2">
              <button v-if="canSubmitSupply" @click="openBatchModal"
                class="flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-[#1D5F5E]/10 hover:bg-[#1D5F5E]/20 text-[#1D5F5E] text-xs font-semibold transition-all">
                <div class="i-carbon-document-pdf text-sm"></div>
                Upload PDF Receipts
              </button>
              <div class="flex items-center bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 w-48 focus-within:ring-2 focus-within:ring-[#1D5F5E]/20 focus-within:border-[#1D5F5E] transition-all">
                <div class="i-carbon-filter text-gray-400 mr-2 text-sm"></div>
                <input v-model="itemFilter" type="text" placeholder="Filter items..."
                  class="bg-transparent outline-none w-full text-xs text-gray-700 placeholder-gray-400 font-medium">
              </div>
            </div>
          </div>
        </div>

        <div class="overflow-y-auto flex-1">
          <table class="w-full border-collapse">
            <thead class="bg-gray-50 sticky top-0 z-10">
              <tr class="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
                <th class="px-4 py-3 text-center w-14">Sch</th>
                <th class="px-4 py-3 text-center w-14">S.No</th>
                <th class="px-4 py-3 text-left">Item Description</th>
                <th @click="toggleSort('qty')" class="px-4 py-3 text-right w-28 cursor-pointer select-none hover:text-gray-600 transition-colors">
                  <div class="flex items-center justify-end gap-1">Scope <div :class="sortIcon('qty')" class="text-[9px]" :style="{ opacity: sortKey === 'qty' ? 1 : 0.35 }"></div></div>
                </th>
                <th @click="toggleSort('submitted')" class="px-4 py-3 text-right w-28 cursor-pointer select-none hover:text-gray-600 transition-colors">
                  <div class="flex items-center justify-end gap-1">Supplied <div :class="sortIcon('submitted')" class="text-[9px]" :style="{ opacity: sortKey === 'submitted' ? 1 : 0.35 }"></div></div>
                </th>
                <th @click="toggleSort('progress')" class="px-4 py-3 w-40 cursor-pointer select-none hover:text-gray-600 transition-colors">
                  <div class="flex items-center gap-1">Progress <div :class="sortIcon('progress')" class="text-[9px]" :style="{ opacity: sortKey === 'progress' ? 1 : 0.35 }"></div></div>
                </th>
                <th class="px-4 py-3 text-center w-28">Action</th>
              </tr>
            </thead>
            <tbody>
              <template v-if="filteredItems.length === 0">
                <tr><td colspan="7" class="p-8 text-center text-gray-400 text-xs font-medium">No supply items match your filter.</td></tr>
              </template>
              <tr v-for="item in sortedItems" :key="item.id" class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                <td class="px-4 py-3.5 text-center">
                  <span class="rounded-md px-2 py-1 text-[10px] font-bold"
                    :class="String(item.schedule||'').toUpperCase().startsWith('A') ? 'bg-data-supply/10 text-data-supply' : 'bg-data-exec/10 text-data-exec'">
                    {{ item.schedule }}
                  </span>
                </td>
                <td class="px-4 py-3.5 text-center text-[11px] font-semibold text-gray-500">{{ item.serial_number }}</td>
                <td class="px-4 py-3.5">
                  <p class="text-xs font-medium line-clamp-2 leading-relaxed text-gray-800">{{ item.item_desc }}</p>
                  <div class="flex items-center gap-1.5 mt-0.5">
                    <span v-if="item.category" class="text-[9px] font-semibold px-1.5 py-0.5 rounded"
                      :class="{
                        'bg-data-supply/10 text-data-supply': item.category === 'supply',
                        'bg-data-si/10 text-data-si':         item.category === 'supply_installation',
                      }">
                      {{ item.category === 'supply' ? 'Supply' : 'S+I' }}
                    </span>
                    <p class="text-[10px] text-gray-400">
                      {{ (item.entries || []).filter(e => e.entry_type === 'supply').length }} entr{{ (item.entries || []).filter(e => e.entry_type === 'supply').length === 1 ? 'y' : 'ies' }} submitted
                    </p>
                  </div>
                </td>
                <td class="px-4 py-3.5 text-right text-xs font-semibold text-gray-600">
                  {{ item.qty }} <span class="font-normal text-gray-400">{{ item.unit }}</span>
                </td>
                <td class="px-4 py-3.5 text-right text-xs font-semibold"
                  :class="(item.supplied_quantity || 0) > (item.qty || 0) ? 'text-status-critical' : 'text-gray-800'">
                  {{ item.supplied_quantity || 0 }} <span class="font-normal text-gray-400">{{ item.unit }}</span>
                </td>
                <td class="px-4 py-3.5">
                  <div class="flex items-center gap-2">
                    <div class="flex-1 h-1.5 rounded-full overflow-hidden bg-gray-100">
                      <div class="h-full rounded-full transition-all duration-500"
                        :class="supplyPct(item) > 100 ? 'bg-status-critical' : 'bg-data-supply'"
                        :style="{ width: Math.min(supplyPct(item), 100) + '%' }"></div>
                    </div>
                    <span class="text-[10px] font-bold w-8 text-right"
                      :class="supplyPct(item) > 100 ? 'text-status-critical' : 'text-gray-500'">
                      {{ supplyPct(item) }}%
                    </span>
                  </div>
                </td>
                <td class="px-4 py-3.5 text-center">
                  <button @click="openLotPopup(item)"
                    class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#1D5F5E]/10 hover:bg-[#1D5F5E]/20 text-[#1D5F5E] text-[11px] font-semibold transition-all">
                    <div :class="canSubmitSupply ? 'i-carbon-add' : 'i-carbon-view'" class="text-xs"></div> {{ canSubmitSupply ? 'Add' : 'View' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ══ LOT ENTRY POPUP ════════════════════════════════════════════ -->
    <Teleport to="body">
      <div v-if="lotPopupItem" class="fixed inset-0 z-50 flex items-center justify-center p-6"
        style="background:rgba(0,0,0,0.45);backdrop-filter:blur(8px);" @click.self="closeLotPopup">
        <div class="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[92vh] flex flex-col animate-modal">

          <div class="px-8 pt-7 pb-5 border-b border-gray-100 flex-shrink-0">
            <div class="flex items-start justify-between gap-4">
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2 mb-1.5">
                  <span class="text-[10px] font-bold px-2 py-1 rounded-md bg-data-supply/10 text-data-supply">{{ lotPopupItem.schedule }}</span>
                  <span class="text-[10px] font-semibold text-gray-400">S.No {{ lotPopupItem.serial_number }}</span>
                </div>
                <h2 class="text-sm font-semibold text-gray-900 leading-snug line-clamp-2">{{ lotPopupItem.item_desc }}</h2>
                <div class="flex items-center gap-4 mt-3 flex-wrap">
                  <div class="flex flex-col">
                    <span class="text-[10px] font-medium text-gray-400 uppercase tracking-wide">Scope</span>
                    <span class="text-sm font-bold text-gray-800">{{ lotPopupItem.qty }} <span class="text-xs font-normal text-gray-400">{{ lotPopupItem.unit }}</span></span>
                  </div>
                  <div class="w-px h-8 bg-gray-100"></div>
                  <div class="flex flex-col">
                    <span class="text-[10px] font-medium text-gray-400 uppercase tracking-wide">Supplied</span>
                    <span class="text-sm font-bold text-accent">{{ lotPopupItem.supplied_quantity || 0 }} <span class="text-xs font-normal text-gray-400">{{ lotPopupItem.unit }}</span></span>
                  </div>
                  <div class="w-px h-8 bg-gray-100"></div>
                  <div class="flex flex-col flex-1">
                    <span class="text-[10px] font-medium text-gray-400 uppercase tracking-wide mb-1.5">Progress</span>
                    <div class="flex items-center gap-2">
                      <div class="flex-1 h-2 rounded-full overflow-hidden bg-gray-100">
                        <div class="h-full rounded-full transition-all duration-500"
                          :class="supplyPct(lotPopupItem) > 100 ? 'bg-status-critical' : 'bg-data-supply'"
                          :style="{ width: Math.min(supplyPct(lotPopupItem), 100) + '%' }"></div>
                      </div>
                      <span class="text-xs font-bold w-10 text-right" :class="supplyPct(lotPopupItem) > 100 ? 'text-status-critical' : 'text-gray-600'">
                        {{ supplyPct(lotPopupItem) }}%
                      </span>
                    </div>
                  </div>
                </div>
              </div>
              <button @click="closeLotPopup"
                class="flex-shrink-0 w-9 h-9 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-500 transition-all">
                <div class="i-carbon-close text-sm"></div>
              </button>
            </div>
          </div>

          <div class="flex-1 overflow-y-auto px-8 py-6 flex flex-col gap-6">

            <!-- ── Submit New Entry (assigned consignee only) ── -->
            <div v-if="canSubmitSupply">
              <div class="flex items-center justify-between mb-4">
                <h3 class="text-xs font-bold text-gray-500 uppercase tracking-widest flex items-center gap-2">
                  <div class="i-carbon-add-filled text-[#1D5F5E]"></div> Submit New Entry
                </h3>
                <label class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-600 text-[11px] font-semibold cursor-pointer transition-all"
                  :class="{ 'opacity-60 pointer-events-none': pdfFilling }">
                  <div v-if="pdfFilling" class="i-carbon-circle-dash animate-spin text-xs"></div>
                  <div v-else class="i-carbon-document-pdf text-xs"></div>
                  {{ pdfFilling ? 'Reading PDF…' : 'Fill from PDF' }}
                  <input type="file" accept=".pdf" class="hidden" @change="fillFromPdf">
                </label>
              </div>

              <div v-if="pdfFillWarnings.length" class="mb-3 rounded-xl bg-amber-50 border border-amber-200 px-4 py-2.5">
                <p class="text-[11px] font-semibold text-amber-700 mb-1">PDF parse notes:</p>
                <ul class="list-disc list-inside space-y-0.5">
                  <li v-for="w in pdfFillWarnings" :key="w" class="text-[11px] text-amber-600">{{ w }}</li>
                </ul>
              </div>

              <div class="flex flex-col gap-3 mb-4">
                <div class="grid grid-cols-2 gap-3">
                  <div class="flex flex-col gap-1.5">
                    <label class="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Receive Note No. (DMTR)</label>
                    <input v-model="entryForm.receive_note_no" type="text" placeholder="56091-26-00049"
                      class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-gray-800 outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 focus:bg-white transition-all">
                  </div>
                  <div class="flex flex-col gap-1.5">
                    <label class="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Date of Receipt <span class="text-red-400">*</span></label>
                    <input v-model="entryForm.date_of_receipt" type="date"
                      class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-gray-800 outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 focus:bg-white transition-all">
                  </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                  <div class="flex flex-col gap-1.5">
                    <label class="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Quantity <span class="text-red-400">*</span></label>
                    <input v-model="entryForm.quantity" type="number" step="0.01" min="0.01" placeholder="e.g. 20"
                      class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-semibold text-gray-800 outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 focus:bg-white transition-all">
                  </div>
                  <div class="flex flex-col gap-1.5">
                    <label class="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Challan No. &amp; Date</label>
                    <input v-model="entryForm.challan_no" type="text" placeholder="MEEPL/26-27/... dt.20-04-2026"
                      class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-gray-800 outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 focus:bg-white transition-all">
                  </div>
                </div>
                <div class="flex flex-col gap-1.5">
                  <label class="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">UDM Entry</label>
                  <input v-model="entryForm.udm_entry" type="text" placeholder="UDM register entry…"
                    class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-gray-800 outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 focus:bg-white transition-all">
                </div>
              </div>

              <button @click="submitEntry" :disabled="entryForm.isSubmitting"
                class="w-full py-3 rounded-2xl text-white text-sm font-bold shadow shadow-black/15 hover:shadow-md hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:translate-y-0 flex items-center justify-center gap-2"
                :class="{
                  'bg-[#1D5F5E] hover:bg-[#174E4D]': !entryForm.status,
                  'bg-[#5E8858]': entryForm.status === 'ok',
                  'bg-red-500':   ['error','denied','invalid','duplicate'].includes(entryForm.status),
                }">
                <div v-if="entryForm.isSubmitting" class="i-carbon-circle-dash animate-spin"></div>
                <span v-else-if="entryForm.status === 'ok'">Entry Submitted!</span>
                <span v-else-if="entryForm.status === 'denied'">Access Denied</span>
                <span v-else-if="entryForm.status === 'duplicate'">Receive Note already exists — duplicate rejected</span>
                <span v-else-if="entryForm.status === 'invalid'">Enter a quantity greater than 0</span>
                <span v-else-if="entryForm.status === 'error'">Submission Failed — Try Again</span>
                <span v-else>Submit Supply Entry</span>
              </button>
            </div>
            <div v-else class="rounded-xl bg-amber-50 border border-amber-200 px-4 py-2.5 flex items-start gap-2">
              <div class="i-carbon-information text-amber-500 mt-0.5 shrink-0"></div>
              <p class="text-[11px] text-amber-700">
                {{ isAdmin ? 'Admins have view-only access here — supply entries can only be submitted by the assigned consignee.' : 'Only the assigned consignee for this LOA can submit supply entries.' }}
              </p>
            </div>

            <!-- ── Entry History ── -->
            <div>
              <h3 class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3 flex items-center gap-2">
                <div class="i-carbon-list text-gray-400"></div> Entry History
                <span class="ml-1 text-[10px] font-bold bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
                  {{ (lotPopupItem.entries || []).filter(e => e.entry_type === 'supply').length }}
                </span>
              </h3>

              <div v-if="entrySaveStatus === 'error'" class="mb-2 text-xs font-medium text-[#ff3b30]">Failed to save edit.</div>
              <div v-if="entrySaveStatus === 'denied'" class="mb-2 text-xs font-medium text-[#ff3b30]">Permission denied.</div>

              <div v-if="(lotPopupItem.entries || []).filter(e => e.entry_type === 'supply').length === 0"
                class="py-8 text-center text-xs text-gray-400 font-medium bg-gray-50 rounded-2xl border border-dashed border-gray-200">
                No supply entries submitted yet.
              </div>
              <div v-else class="rounded-2xl border border-gray-100 overflow-hidden">
                <table class="w-full text-xs">
                  <thead class="bg-gray-50 text-[10px] text-gray-400 font-bold uppercase tracking-widest border-b border-gray-100">
                    <tr>
                      <th class="px-3 py-2.5 text-left w-7">#</th>
                      <th class="px-3 py-2.5 text-right w-16">Qty</th>
                      <th class="px-3 py-2.5 text-left">Rcv Note / Date</th>
                      <th class="px-3 py-2.5 text-left">Challan</th>
                      <th class="px-3 py-2.5 text-left w-20">By</th>
                      <th class="px-3 py-2.5 text-center w-14">Edit</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-gray-50">
                    <template v-for="(entry, idx) in (lotPopupItem.entries || []).filter(e => e.entry_type === 'supply')" :key="entry.id">

                      <tr v-if="editingEntry?.id === entry.id" class="bg-accent-soft/40">
                        <td class="px-3 py-2 text-gray-400 font-semibold">{{ idx + 1 }}</td>
                        <td class="px-3 py-2">
                          <input v-model="editingEntry.quantity" type="number" step="0.01" min="0.01"
                            class="w-14 bg-white border border-accent/30 rounded-lg px-2 py-1 text-xs font-semibold text-gray-800 outline-none focus:border-accent text-right">
                        </td>
                        <td class="px-3 py-2">
                          <div class="flex flex-col gap-1">
                            <input v-model="editingEntry.receive_note_no" type="text" placeholder="DMTR No."
                              class="w-full bg-white border border-gray-200 rounded-lg px-2 py-1 text-xs text-gray-700 outline-none focus:border-accent">
                            <input v-model="editingEntry.date_of_receipt" type="date"
                              class="w-full bg-white border border-gray-200 rounded-lg px-2 py-1 text-xs text-gray-700 outline-none focus:border-accent">
                          </div>
                        </td>
                        <td class="px-3 py-2">
                          <input v-model="editingEntry.challan_no" type="text"
                            class="w-full bg-white border border-gray-200 rounded-lg px-2 py-1 text-xs text-gray-700 outline-none focus:border-accent">
                        </td>
                        <td class="px-3 py-2 text-gray-500">{{ entry.submitted_by_user?.username || '—' }}</td>
                        <td class="px-3 py-2">
                          <div class="flex items-center gap-1">
                            <button @click="saveEditEntry" :disabled="isSavingEntry"
                              class="px-2 py-1 rounded-lg bg-accent text-white text-[10px] font-bold hover:bg-accent-hover transition-all disabled:opacity-50 flex items-center gap-1">
                              <div v-if="isSavingEntry" class="i-carbon-circle-dash animate-spin text-[10px]"></div>
                              <span v-else>Save</span>
                            </button>
                            <button @click="closeEditEntry"
                              class="px-2 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 text-[10px] font-bold transition-all">✕</button>
                          </div>
                        </td>
                      </tr>

                      <tr v-else class="hover:bg-gray-50/60 transition-colors">
                        <td class="px-3 py-2.5 text-gray-400 font-semibold">{{ idx + 1 }}</td>
                        <td class="px-3 py-2.5 text-right font-bold text-gray-800">
                          {{ entry.quantity }} <span class="text-gray-400 font-normal text-[10px]">{{ lotPopupItem.unit }}</span>
                        </td>
                        <td class="px-3 py-2.5">
                          <p class="font-semibold text-gray-700 truncate max-w-[120px]">{{ entry.receive_note_no || '—' }}</p>
                          <p class="text-[10px] text-[#1D5F5E] font-medium mt-0.5">{{ fmtDate(entry.date_of_receipt) }}</p>
                        </td>
                        <td class="px-3 py-2.5 text-gray-500 max-w-[120px] truncate text-[11px]">{{ entry.challan_no || '—' }}</td>
                        <td class="px-3 py-2.5 text-gray-500 text-[11px]">{{ entry.submitted_by_user?.username || '—' }}</td>
                        <td class="px-3 py-2.5 text-center">
                          <button v-if="canEditEntry(entry)"
                            @click="openEditEntry(entry)"
                            class="px-2 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 text-[10px] font-bold transition-all flex items-center gap-1 mx-auto">
                            <div class="i-carbon-edit text-[10px]"></div>
                          </button>
                          <span v-else class="text-gray-200">—</span>
                        </td>
                      </tr>

                    </template>
                  </tbody>
                  <tfoot class="bg-gray-50 border-t border-gray-100">
                    <tr>
                      <td class="px-3 py-2.5 text-[10px] font-bold text-gray-400 uppercase tracking-wide">Total</td>
                      <td class="px-3 py-2.5 text-right font-bold text-gray-800">{{ lotPopupItem.supplied_quantity || 0 }}</td>
                      <td colspan="4"></td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>

          </div>
        </div>
      </div>
    </Teleport>

    <!-- ══ BATCH PDF UPLOAD MODAL ════════════════════════════════════ -->
    <Teleport to="body">
      <div v-if="batchModal" class="fixed inset-0 z-50 flex items-center justify-center p-6"
        style="background:rgba(0,0,0,0.45);backdrop-filter:blur(8px);" @click.self="closeBatchModal">
        <div class="bg-white rounded-3xl shadow-2xl w-full max-w-3xl max-h-[92vh] flex flex-col animate-modal">

          <div class="flex items-center justify-between px-7 pt-5 pb-4 border-b border-gray-100 flex-shrink-0">
            <div>
              <h2 class="text-base font-bold text-gray-900">Batch PDF Receipt Upload</h2>
              <p class="text-[11px] text-gray-400 mt-0.5">Select one or more receipt PDFs. Fields are extracted automatically.</p>
            </div>
            <button @click="closeBatchModal" class="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-500 transition-all">
              <div class="i-carbon-close text-sm"></div>
            </button>
          </div>

          <div class="flex-1 overflow-y-auto px-7 py-5 flex flex-col gap-5">

            <div v-if="batchParseError" class="rounded-xl bg-red-50 border border-red-200 px-4 py-3 flex items-center gap-2">
              <div class="i-carbon-warning-filled text-red-500 flex-shrink-0"></div>
              <p class="text-xs font-semibold text-red-600">{{ batchParseError }}</p>
            </div>

            <label v-if="!batchParsing && batchResults.length === 0"
              class="flex flex-col items-center justify-center border-2 border-dashed border-gray-200 hover:border-[#1D5F5E]/50 rounded-2xl py-12 cursor-pointer transition-all group">
              <div class="i-carbon-document-pdf text-4xl text-gray-300 group-hover:text-[#1D5F5E]/60 transition-colors mb-3"></div>
              <p class="text-sm font-semibold text-gray-500 group-hover:text-gray-700">Click to select PDF receipts</p>
              <p class="text-xs text-gray-400 mt-1">Multiple files supported</p>
              <input type="file" accept=".pdf" multiple class="hidden" @change="onBatchFilesSelected">
            </label>

            <div v-if="batchParsing" class="flex flex-col items-center py-12 gap-3">
              <div class="i-carbon-circle-dash animate-spin text-3xl text-[#1D5F5E]"></div>
              <p class="text-sm font-medium text-gray-500">Parsing PDFs…</p>
            </div>

            <template v-if="batchResults.length > 0">
              <div class="flex items-center justify-between">
                <p class="text-xs font-bold text-gray-500 uppercase tracking-wide">{{ batchResults.length }} PDF{{ batchResults.length > 1 ? 's' : '' }} parsed</p>
                <label class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-600 text-[11px] font-semibold cursor-pointer transition-all">
                  <div class="i-carbon-add text-xs"></div> Add more PDFs
                  <input type="file" accept=".pdf" multiple class="hidden" @change="onBatchFilesSelected">
                </label>
              </div>

              <div class="flex flex-col gap-3">
                <div v-for="(r, i) in batchResults" :key="i"
                  class="rounded-2xl border px-5 py-4 transition-all"
                  :class="r.done ? 'border-[#34c759]/30 bg-[#34c759]/5' : (r.error ? 'border-[#ff3b30]/30 bg-[#ff3b30]/5' : 'border-gray-100 bg-gray-50/40')">

                  <div class="flex items-center justify-between gap-3 mb-3">
                    <div class="flex items-center gap-2 min-w-0">
                      <div v-if="r.done" class="i-carbon-checkmark-filled text-[#34c759] text-base flex-shrink-0"></div>
                      <div v-else-if="r.error" class="i-carbon-warning-filled text-[#ff3b30] text-base flex-shrink-0"></div>
                      <div v-else class="i-carbon-document-pdf text-gray-400 text-base flex-shrink-0"></div>
                      <p class="text-xs font-semibold text-gray-700 truncate">{{ r.filename }}</p>
                    </div>
                    <label v-if="!r.done && !r.error" class="flex items-center gap-1.5 cursor-pointer flex-shrink-0">
                      <input type="checkbox" v-model="r.include" class="w-3.5 h-3.5 accent-[#1D5F5E]">
                      <span class="text-[11px] font-medium text-gray-500">Include</span>
                    </label>
                    <span v-if="r.done" class="text-[11px] font-semibold text-[#34c759]">Submitted</span>
                    <span v-if="r.submitError" class="text-[11px] font-semibold text-[#ff3b30]">{{ r.submitError }}</span>
                  </div>

                  <div v-if="(r.parse_warnings || []).length" class="mb-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2">
                    <ul class="space-y-0.5">
                      <li v-for="w in r.parse_warnings" :key="w" class="text-[10px] text-amber-700">⚠ {{ w }}</li>
                    </ul>
                  </div>

                  <div v-if="!r.error" class="grid grid-cols-2 gap-x-6 gap-y-2">
                    <div class="col-span-2 flex flex-col gap-1">
                      <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wide">Match to Item (Serial: {{ r.serial_number || '—' }})</label>
                      <select v-model="r.matchedItemId"
                        class="bg-white border rounded-xl px-3 py-2 text-xs font-medium text-gray-700 outline-none focus:border-[#1D5F5E]"
                        :class="r.matchedItemId ? 'border-gray-200' : 'border-amber-300'">
                        <option value="">— Select item —</option>
                        <option v-for="item in supplyItems" :key="item.id" :value="item.id">
                          [{{ item.serial_number }}] {{ item.item_desc?.slice(0, 60) }}…
                        </option>
                      </select>
                    </div>
                    <div>
                      <p class="text-[10px] text-gray-400 font-medium">Receive Note No.</p>
                      <p class="text-xs font-semibold text-gray-700 mt-0.5">{{ r.receive_note_no || '—' }}</p>
                    </div>
                    <div>
                      <p class="text-[10px] text-gray-400 font-medium">Date of Receipt</p>
                      <p class="text-xs font-semibold text-gray-700 mt-0.5">{{ fmtDate(r.date_of_receipt) }}</p>
                    </div>
                    <div>
                      <p class="text-[10px] text-gray-400 font-medium">Quantity</p>
                      <p class="text-xs font-semibold text-gray-700 mt-0.5">{{ r.quantity ?? '—' }} <span class="font-normal text-gray-400">{{ r.unit || '' }}</span></p>
                    </div>
                    <div>
                      <p class="text-[10px] text-gray-400 font-medium">Challan No. &amp; Date</p>
                      <p class="text-xs font-semibold text-gray-700 mt-0.5 truncate">{{ r.challan_no || '—' }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </template>

          </div>

          <div v-if="batchResults.length > 0 && !batchParsing"
            class="px-7 pb-6 pt-3 flex items-center justify-between gap-3 border-t border-gray-100 flex-shrink-0">
            <p class="text-xs text-gray-400 font-medium">
              {{ batchResults.filter(r => r.include && r.matchedItemId && !r.done).length }} entr{{ batchResults.filter(r => r.include && r.matchedItemId && !r.done).length === 1 ? 'y' : 'ies' }} ready to submit
            </p>
            <div class="flex items-center gap-3">
              <button @click="closeBatchModal" class="px-5 py-2.5 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 text-sm font-semibold transition-colors">Close</button>
              <button @click="submitBatchEntries"
                :disabled="batchSubmitting || !batchResults.some(r => r.include && r.matchedItemId && !r.done)"
                class="px-5 py-2.5 rounded-xl bg-[#1D5F5E] text-white text-sm font-semibold hover:bg-[#174E4D] transition-colors disabled:opacity-50 flex items-center gap-2">
                <div v-if="batchSubmitting" class="i-carbon-circle-dash animate-spin"></div>
                <span>Submit Selected</span>
              </button>
            </div>
          </div>

        </div>
      </div>
    </Teleport>

  </div>
</template>

<style scoped>
@keyframes fade-in  { from { opacity:0; transform:translateY(6px);            } to { opacity:1; transform:translateY(0);        } }
@keyframes modal-in { from { opacity:0; transform:scale(0.96) translateY(8px); } to { opacity:1; transform:scale(1) translateY(0); } }
.animate-fade-in { animation: fade-in  0.3s cubic-bezier(.4,0,.2,1); }
.animate-modal   { animation: modal-in 0.25s cubic-bezier(.4,0,.2,1); }
</style>
