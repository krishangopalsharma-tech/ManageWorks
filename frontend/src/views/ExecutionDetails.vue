<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

// Location normalisation: force uppercase; two-token input → sort codes + join with hyphen
const normalizeLocation = (val) => {
  if (!val) return ''
  const parts = val.trim().toUpperCase().split(/[\s-]+/).filter(Boolean)
  if (parts.length === 2) return [...parts].sort().join('-')
  return parts.join(' ')
}

const execPct = (item) => { const r = item.qty || 0; if (!r) return 0; return Math.min(Math.round((item.executed_quantity || 0) / r * 100), 999) }

const recalcExecuted = (item) => {
  const entries = (item.entries || []).filter(e => e.entry_type === 'execution')
  item.executed_quantity = entries.reduce((s, e) => s + (e.quantity || 0), 0)
}

// ── State ──────────────────────────────────────────────────────────────────
const searchQuery  = ref('')
const itemFilter   = ref('')
const allWorks     = ref([])
const selectedWork = ref(null)
const isLoading    = ref(true)
const currentUser  = ref(null)

const isAdmin = computed(() => currentUser.value?.role === 'admin' || currentUser.value?.is_staff)
// Execution Details is view-only for Admin/Super Admin. Any consignee (assigned
// here, assigned elsewhere, or fully unassigned) may submit — no ownership check.
const canSubmitExecution = computed(() => currentUser.value?.role === 'consignee')

const canEditEntry = (entry) => {
  if (!currentUser.value) return false
  return entry.submitted_by_user?.id === currentUser.value.id
}

// Delete is narrower than submit/edit: only Super Admin (any LOA) or the
// LOA's own assigned consignee — not just any consignee, and not plain Admin.
const isWorkConsignee = computed(() => {
  if (!currentUser.value || !selectedWork.value) return false
  return currentUser.value.hrms_id === selectedWork.value.hrms_id
})
const canDeleteEntry = computed(() => currentUser.value?.is_super_admin || isWorkConsignee.value)

// Lot entry popup
const lotPopupItem = ref(null)
const entryForm    = ref({ quantity: '', location: '', remarks: '', isSubmitting: false, status: '' })

// Inline entry editing
const editingEntry    = ref(null)
const isSavingEntry   = ref(false)
const entrySaveStatus = ref('')

// ── Load ───────────────────────────────────────────────────────────────────
const loadWorks = async () => {
  isLoading.value = true
  try {
    const [worksRes, meRes] = await Promise.allSettled([
      axios.get('/api/execution-details/works/search/'),
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

// Execution Details only shows EE + SI items (not pure-supply items)
const executionItems = computed(() => {
  if (!selectedWork.value) return []
  return (selectedWork.value.items || []).filter(i => i.category !== 'supply')
})

const filteredItems = computed(() => {
  if (!itemFilter.value.trim()) return executionItems.value
  const q = itemFilter.value.toLowerCase()
  return executionItems.value.filter(i =>
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
    else if (sortKey.value === 'submitted') { av = a.executed_quantity || 0;    bv = b.executed_quantity || 0 }
    else if (sortKey.value === 'progress')  { av = execPct(a);                  bv = execPct(b) }
    return sortDir.value === 'asc' ? av - bv : bv - av
  })
})

const selectWork = async (work) => {
  itemFilter.value   = ''
  sortKey.value      = ''
  lotPopupItem.value = null
  selectedWork.value = { ...work, items: work.items.map(i => ({ ...i, entries: (i.entries || []).map(e => ({ ...e })) })) }
  try {
    const res = await axios.get(`/api/execution-details/works/${work.id}/detail/`)
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
  entryForm.value = { quantity: '', location: '', remarks: '', isSubmitting: false, status: '' }
}
const closeLotPopup = () => { lotPopupItem.value = null; editingEntry.value = null }

const submitEntry = async () => {
  const item = lotPopupItem.value
  const form = entryForm.value

  if (!form.quantity || parseFloat(form.quantity) <= 0) {
    form.status = 'invalid'; setTimeout(() => { form.status = '' }, 2000); return
  }
  if (!form.location.trim()) {
    form.status = 'noloc'; setTimeout(() => { form.status = '' }, 2000); return
  }

  form.isSubmitting = true
  form.status = ''
  try {
    const payload = {
      quantity: parseFloat(form.quantity),
      location: form.location,
      remarks:  form.remarks,
    }
    const res = await axios.post(`/api/execution-details/items/${item.id}/entries/`, payload)
    if (!item.entries) item.entries = []
    item.entries.push(res.data)
    recalcExecuted(item)

    form.quantity = ''; form.location = ''; form.remarks = ''
    form.status = 'ok'
    setTimeout(() => { form.status = '' }, 2500)
  } catch (e) {
    console.error(e)
    const st = e.response?.status
    form.status = st === 403 ? 'denied' : 'error'
    setTimeout(() => { form.status = '' }, 3500)
  } finally {
    form.isSubmitting = false
  }
}

const openEditEntry = (entry) => {
  entrySaveStatus.value = ''
  editingEntry.value = {
    id: entry.id, quantity: entry.quantity,
    location: entry.location || '', remarks: entry.remarks || '',
  }
}
const closeEditEntry = () => { editingEntry.value = null; entrySaveStatus.value = '' }

const deletingEntryId = ref(null)
const deleteEntry = async (entry) => {
  const item = lotPopupItem.value
  if (!confirm(`Delete this lot entry (${entry.quantity} ${item.unit})? This can't be undone.`)) return

  deletingEntryId.value = entry.id
  try {
    await axios.delete(`/api/execution-details/entries/${entry.id}/`)
    item.entries = (item.entries || []).filter(e => e.id !== entry.id)
    recalcExecuted(item)
  } catch (err) {
    console.error(err)
    alert(err.response?.status === 403 ? 'You do not have permission to delete this entry.' : 'Failed to delete entry.')
  } finally {
    deletingEntryId.value = null
  }
}

const saveEditEntry = async () => {
  const e    = editingEntry.value
  const item = lotPopupItem.value
  if (!e.quantity || parseFloat(e.quantity) <= 0) return

  isSavingEntry.value   = true
  entrySaveStatus.value = ''
  try {
    const payload = { quantity: parseFloat(e.quantity), location: e.location, remarks: e.remarks }
    const res = await axios.patch(`/api/execution-details/entries/${e.id}/`, payload)
    const idx = (item.entries || []).findIndex(x => x.id === e.id)
    if (idx !== -1) item.entries[idx] = res.data
    recalcExecuted(item)
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
        <h1 class="text-2xl font-bold text-gray-900 tracking-tight mb-1">Execution Details</h1>
        <p class="text-gray-400 text-sm font-medium mb-5">Search, then open a work to submit execution lot entries against its items.</p>
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
                    <span class="font-bold text-gray-800">{{ (work.items || []).filter(i => i.category !== 'supply').length }}</span> execution items
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
                <p v-if="isAdmin" class="mt-2 text-[11px] font-semibold text-amber-600 bg-amber-50 inline-block px-2 py-0.5 rounded-full">
                  View only — Admins cannot submit execution entries
                </p>
              </div>
            </div>
            <div class="flex-shrink-0 flex items-center gap-2">
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
                  <div class="flex items-center justify-end gap-1">Executed <div :class="sortIcon('submitted')" class="text-[9px]" :style="{ opacity: sortKey === 'submitted' ? 1 : 0.35 }"></div></div>
                </th>
                <th @click="toggleSort('progress')" class="px-4 py-3 w-40 cursor-pointer select-none hover:text-gray-600 transition-colors">
                  <div class="flex items-center gap-1">Progress <div :class="sortIcon('progress')" class="text-[9px]" :style="{ opacity: sortKey === 'progress' ? 1 : 0.35 }"></div></div>
                </th>
                <th class="px-4 py-3 text-center w-28">Action</th>
              </tr>
            </thead>
            <tbody>
              <template v-if="filteredItems.length === 0">
                <tr><td colspan="7" class="p-8 text-center text-gray-400 text-xs font-medium">No execution items match your filter.</td></tr>
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
                        'bg-data-si/10 text-data-si':     item.category === 'supply_installation',
                        'bg-data-exec/10 text-data-exec': item.category === 'execution',
                      }">
                      {{ item.category === 'supply_installation' ? 'S+I' : 'Execution' }}
                    </span>
                    <p class="text-[10px] text-gray-400">
                      {{ (item.entries || []).filter(e => e.entry_type === 'execution').length }} entr{{ (item.entries || []).filter(e => e.entry_type === 'execution').length === 1 ? 'y' : 'ies' }} submitted
                    </p>
                  </div>
                </td>
                <td class="px-4 py-3.5 text-right text-xs font-semibold text-gray-600">
                  {{ item.qty }} <span class="font-normal text-gray-400">{{ item.unit }}</span>
                </td>
                <td class="px-4 py-3.5 text-right text-xs font-semibold"
                  :class="(item.executed_quantity || 0) > (item.qty || 0) ? 'text-status-critical' : 'text-gray-800'">
                  {{ item.executed_quantity || 0 }} <span class="font-normal text-gray-400">{{ item.unit }}</span>
                </td>
                <td class="px-4 py-3.5">
                  <div class="flex items-center gap-2">
                    <div class="flex-1 h-1.5 rounded-full overflow-hidden bg-gray-100">
                      <div class="h-full rounded-full transition-all duration-500"
                        :class="execPct(item) > 100 ? 'bg-status-critical' : 'bg-data-exec'"
                        :style="{ width: Math.min(execPct(item), 100) + '%' }"></div>
                    </div>
                    <span class="text-[10px] font-bold w-8 text-right"
                      :class="execPct(item) > 100 ? 'text-status-critical' : 'text-gray-500'">
                      {{ execPct(item) }}%
                    </span>
                  </div>
                </td>
                <td class="px-4 py-3.5 text-center">
                  <button @click="openLotPopup(item)"
                    class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#1D5F5E]/10 hover:bg-[#1D5F5E]/20 text-[#1D5F5E] text-[11px] font-semibold transition-all">
                    <div :class="canSubmitExecution ? 'i-carbon-add' : 'i-carbon-view'" class="text-xs"></div> {{ canSubmitExecution ? 'Add' : 'View' }}
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
                  <span class="text-[10px] font-bold px-2 py-1 rounded-md bg-data-exec/10 text-data-exec">{{ lotPopupItem.schedule }}</span>
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
                    <span class="text-[10px] font-medium text-gray-400 uppercase tracking-wide">Executed</span>
                    <span class="text-sm font-bold text-accent-b">{{ lotPopupItem.executed_quantity || 0 }} <span class="text-xs font-normal text-gray-400">{{ lotPopupItem.unit }}</span></span>
                  </div>
                  <div class="w-px h-8 bg-gray-100"></div>
                  <div class="flex flex-col flex-1">
                    <span class="text-[10px] font-medium text-gray-400 uppercase tracking-wide mb-1.5">Progress</span>
                    <div class="flex items-center gap-2">
                      <div class="flex-1 h-2 rounded-full overflow-hidden bg-gray-100">
                        <div class="h-full rounded-full transition-all duration-500"
                          :class="execPct(lotPopupItem) > 100 ? 'bg-status-critical' : 'bg-data-exec'"
                          :style="{ width: Math.min(execPct(lotPopupItem), 100) + '%' }"></div>
                      </div>
                      <span class="text-xs font-bold w-10 text-right" :class="execPct(lotPopupItem) > 100 ? 'text-status-critical' : 'text-gray-600'">
                        {{ execPct(lotPopupItem) }}%
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

            <!-- ── Submit New Entry (any consignee, admin excluded) ── -->
            <div v-if="canSubmitExecution">
              <h3 class="text-xs font-bold text-gray-500 uppercase tracking-widest flex items-center gap-2 mb-4">
                <div class="i-carbon-add-filled text-[#1D5F5E]"></div> Submit New Entry
              </h3>

              <div class="flex flex-col gap-3 mb-4">
                <div class="grid grid-cols-2 gap-3">
                  <div class="flex flex-col gap-1.5">
                    <label class="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Quantity <span class="text-red-400">*</span></label>
                    <input v-model="entryForm.quantity" type="number" step="0.01" min="0.01" placeholder="Units executed"
                      class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-semibold text-gray-800 outline-none focus:border-[#34c759] focus:ring-2 focus:ring-[#34c759]/10 focus:bg-white transition-all">
                  </div>
                  <div class="flex flex-col gap-1.5">
                    <label class="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Location <span class="text-red-400">*</span></label>
                    <input v-model="entryForm.location" type="text" placeholder="Station / Section"
                      style="text-transform:uppercase"
                      @blur="entryForm.location = normalizeLocation(entryForm.location)"
                      class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-gray-800 outline-none focus:border-[#34c759] focus:ring-2 focus:ring-[#34c759]/10 focus:bg-white transition-all">
                  </div>
                </div>
                <div class="flex flex-col gap-1.5">
                  <label class="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Remarks</label>
                  <textarea v-model="entryForm.remarks" rows="2" placeholder="Any notes or observations..."
                    class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-gray-800 outline-none focus:border-[#34c759] focus:ring-2 focus:ring-[#34c759]/10 focus:bg-white transition-all resize-none"></textarea>
                </div>
              </div>

              <button @click="submitEntry" :disabled="entryForm.isSubmitting"
                class="w-full py-3 rounded-2xl text-white text-sm font-bold shadow shadow-black/15 hover:shadow-md hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:translate-y-0 flex items-center justify-center gap-2"
                :class="{
                  'bg-[#C17841] hover:bg-[#A9653A]': !entryForm.status,
                  'bg-[#5E8858]': entryForm.status === 'ok',
                  'bg-red-500':   ['error','denied','invalid','noloc'].includes(entryForm.status),
                }">
                <div v-if="entryForm.isSubmitting" class="i-carbon-circle-dash animate-spin"></div>
                <span v-else-if="entryForm.status === 'ok'">Entry Submitted!</span>
                <span v-else-if="entryForm.status === 'denied'">Access Denied</span>
                <span v-else-if="entryForm.status === 'invalid'">Enter a quantity greater than 0</span>
                <span v-else-if="entryForm.status === 'noloc'">Location is required for execution entries</span>
                <span v-else-if="entryForm.status === 'error'">Submission Failed — Try Again</span>
                <span v-else>Submit Execution Entry</span>
              </button>
            </div>
            <div v-else class="rounded-xl bg-amber-50 border border-amber-200 px-4 py-2.5 flex items-start gap-2">
              <div class="i-carbon-information text-amber-500 mt-0.5 shrink-0"></div>
              <p class="text-[11px] text-amber-700">Admins have view-only access here — execution entries can only be submitted by consignees.</p>
            </div>

            <!-- ── Entry History ── -->
            <div>
              <h3 class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3 flex items-center gap-2">
                <div class="i-carbon-list text-gray-400"></div> Entry History
                <span class="ml-1 text-[10px] font-bold bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
                  {{ (lotPopupItem.entries || []).filter(e => e.entry_type === 'execution').length }}
                </span>
              </h3>

              <div v-if="entrySaveStatus === 'error'" class="mb-2 text-xs font-medium text-[#ff3b30]">Failed to save edit.</div>
              <div v-if="entrySaveStatus === 'denied'" class="mb-2 text-xs font-medium text-[#ff3b30]">Permission denied.</div>

              <div v-if="(lotPopupItem.entries || []).filter(e => e.entry_type === 'execution').length === 0"
                class="py-8 text-center text-xs text-gray-400 font-medium bg-gray-50 rounded-2xl border border-dashed border-gray-200">
                No execution entries submitted yet.
              </div>
              <div v-else class="rounded-2xl border border-gray-100 overflow-hidden">
                <table class="w-full text-xs">
                  <thead class="bg-gray-50 text-[10px] text-gray-400 font-bold uppercase tracking-widest border-b border-gray-100">
                    <tr>
                      <th class="px-3 py-2.5 text-left w-7">#</th>
                      <th class="px-3 py-2.5 text-right w-16">Qty</th>
                      <th class="px-3 py-2.5 text-left">Location</th>
                      <th class="px-3 py-2.5 text-left">Remarks</th>
                      <th class="px-3 py-2.5 text-left w-20">By</th>
                      <th class="px-3 py-2.5 text-center w-14">Edit</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-gray-50">
                    <template v-for="(entry, idx) in (lotPopupItem.entries || []).filter(e => e.entry_type === 'execution')" :key="entry.id">

                      <tr v-if="editingEntry?.id === entry.id" class="bg-accent-b-soft/40">
                        <td class="px-3 py-2 text-gray-400 font-semibold">{{ idx + 1 }}</td>
                        <td class="px-3 py-2">
                          <input v-model="editingEntry.quantity" type="number" step="0.01" min="0.01"
                            class="w-14 bg-white border border-accent-b/30 rounded-lg px-2 py-1 text-xs font-semibold text-gray-800 outline-none focus:border-accent-b text-right">
                        </td>
                        <td class="px-3 py-2">
                          <input v-model="editingEntry.location" type="text"
                            style="text-transform:uppercase"
                            @blur="editingEntry.location = normalizeLocation(editingEntry.location)"
                            class="w-full bg-white border border-gray-200 rounded-lg px-2 py-1 text-xs text-gray-700 outline-none focus:border-accent-b">
                        </td>
                        <td class="px-3 py-2">
                          <input v-model="editingEntry.remarks" type="text"
                            class="w-full bg-white border border-gray-200 rounded-lg px-2 py-1 text-xs text-gray-700 outline-none focus:border-accent-b">
                        </td>
                        <td class="px-3 py-2 text-gray-500">{{ entry.submitted_by_user?.username || '—' }}</td>
                        <td class="px-3 py-2">
                          <div class="flex items-center gap-1">
                            <button @click="saveEditEntry" :disabled="isSavingEntry"
                              class="px-2 py-1 rounded-lg bg-accent-b text-white text-[10px] font-bold hover:opacity-90 transition-all disabled:opacity-50 flex items-center gap-1">
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
                        <td class="px-3 py-2.5 text-gray-600 font-medium max-w-[120px] truncate">{{ entry.location || '—' }}</td>
                        <td class="px-3 py-2.5 text-gray-500 max-w-[120px] truncate text-[11px]">{{ entry.remarks || '—' }}</td>
                        <td class="px-3 py-2.5 text-gray-500 text-[11px]">{{ entry.submitted_by_user?.username || '—' }}</td>
                        <td class="px-3 py-2.5 text-center">
                          <div class="flex items-center justify-center gap-1">
                            <button v-if="canEditEntry(entry)"
                              @click="openEditEntry(entry)"
                              class="px-2 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 text-[10px] font-bold transition-all flex items-center gap-1">
                              <div class="i-carbon-edit text-[10px]"></div>
                            </button>
                            <button v-if="canDeleteEntry"
                              @click="deleteEntry(entry)"
                              :disabled="deletingEntryId === entry.id"
                              class="px-2 py-1 rounded-lg bg-red-50 hover:bg-red-100 text-red-500 text-[10px] font-bold transition-all disabled:opacity-50 flex items-center gap-1">
                              <div v-if="deletingEntryId === entry.id" class="i-carbon-circle-dash animate-spin text-[10px]"></div>
                              <div v-else class="i-carbon-trash-can text-[10px]"></div>
                            </button>
                            <span v-if="!canEditEntry(entry) && !canDeleteEntry" class="text-gray-200">—</span>
                          </div>
                        </td>
                      </tr>

                    </template>
                  </tbody>
                  <tfoot class="bg-gray-50 border-t border-gray-100">
                    <tr>
                      <td class="px-3 py-2.5 text-[10px] font-bold text-gray-400 uppercase tracking-wide">Total</td>
                      <td class="px-3 py-2.5 text-right font-bold text-gray-800">{{ lotPopupItem.executed_quantity || 0 }}</td>
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

  </div>
</template>

<style scoped>
@keyframes fade-in  { from { opacity:0; transform:translateY(6px);            } to { opacity:1; transform:translateY(0);        } }
@keyframes modal-in { from { opacity:0; transform:scale(0.96) translateY(8px); } to { opacity:1; transform:scale(1) translateY(0); } }
.animate-fade-in { animation: fade-in  0.3s cubic-bezier(.4,0,.2,1); }
.animate-modal   { animation: modal-in 0.25s cubic-bezier(.4,0,.2,1); }
</style>
