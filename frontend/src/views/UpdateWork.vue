<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const fmtDate = (val) => {
  if (!val) return '—'
  return String(val).split(' ')[0].split('T')[0]
}

const fmtDateTime = (val) => {
  if (!val) return '—'
  const d = new Date(val)
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const progressPct = (item) => {
  const total = item.supplied_quantity || 0
  const req = item.qty || 0
  if (!req) return 0
  return Math.min(Math.round((total / req) * 100), 999)
}

// ── State ──────────────────────────────────────────────────────────────────
const searchQuery   = ref('')
const itemFilter    = ref('')
const allWorks      = ref([])
const selectedWork  = ref(null)
const isLoading     = ref(true)

// Lot entry popup
const lotPopupItem  = ref(null)
const entryForm     = ref({ quantity: '', challan_no: '', udm_entry: '', isSubmitting: false, status: '' })

// Edit-work modal
const editingWork      = ref(null)
const isSavingWork     = ref(false)
const workSaveStatus   = ref('')
const showDeleteConfirm = ref(false)
const isDeletingWork   = ref(false)

// ── Load works ─────────────────────────────────────────────────────────────
const loadWorks = async () => {
  isLoading.value = true
  try {
    const res = await axios.get('/api/work-details/search/')
    allWorks.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    isLoading.value = false
  }
}
onMounted(loadWorks)

// ── Work list filtering ────────────────────────────────────────────────────
const filteredWorks = computed(() => {
  if (!searchQuery.value.trim()) return allWorks.value
  const q = searchQuery.value.toLowerCase()
  return allWorks.value.filter(w =>
    (w.loa_number      && w.loa_number.toLowerCase().includes(q)) ||
    (w.contractor_name && w.contractor_name.toLowerCase().includes(q)) ||
    (w.tender_number   && w.tender_number.toLowerCase().includes(q)) ||
    (w.consignee       && w.consignee.toLowerCase().includes(q))
  )
})

// ── Select a work → open items view ───────────────────────────────────────
const selectWork = (work) => {
  itemFilter.value   = ''
  lotPopupItem.value = null
  selectedWork.value = {
    ...work,
    items: work.items.map(i => ({ ...i }))
  }
}

// ── Item filtering ─────────────────────────────────────────────────────────
const filteredItems = computed(() => {
  if (!selectedWork.value) return []
  if (!itemFilter.value.trim()) return selectedWork.value.items
  const q = itemFilter.value.toLowerCase()
  return selectedWork.value.items.filter(i =>
    (i.schedule  && i.schedule.toLowerCase().includes(q)) ||
    (i.item_desc && i.item_desc.toLowerCase().includes(q))
  )
})

// ── Lot entry popup ────────────────────────────────────────────────────────
const openLotPopup = (item) => {
  lotPopupItem.value = item
  entryForm.value = { quantity: '', challan_no: '', udm_entry: '', isSubmitting: false, status: '' }
}
const closeLotPopup = () => {
  lotPopupItem.value = null
}

// ── Submit a lot entry ─────────────────────────────────────────────────────
const submitEntry = async () => {
  const item = lotPopupItem.value
  const form = entryForm.value
  if (!form.quantity || parseFloat(form.quantity) <= 0) {
    form.status = 'invalid'
    setTimeout(() => { form.status = '' }, 2000)
    return
  }
  form.isSubmitting = true
  form.status = ''
  try {
    const res = await axios.post(`/api/update-work/items/${item.id}/entries/`, {
      quantity:   parseFloat(form.quantity),
      challan_no: form.challan_no,
      udm_entry:  form.udm_entry,
    })
    if (!item.entries) item.entries = []
    item.entries.unshift(res.data)
    item.supplied_quantity = (item.supplied_quantity || 0) + parseFloat(form.quantity)
    form.quantity   = ''
    form.challan_no = ''
    form.udm_entry  = ''
    form.status = 'ok'
    setTimeout(() => { form.status = '' }, 2500)
  } catch (e) {
    console.error(e)
    form.status = e.response?.status === 403 ? 'denied' : 'error'
    setTimeout(() => { form.status = '' }, 2500)
  } finally {
    form.isSubmitting = false
  }
}

// ── Edit-work modal ────────────────────────────────────────────────────────
const openEditWork = (work) => {
  editingWork.value = {
    id: work.id,
    loa_number:         work.loa_number         || '',
    tender_number:      work.tender_number      || '',
    date:               work.date               || '',
    contract_agreement: work.contract_agreement || '',
    contractor_name:    work.contractor_name    || '',
    contractor_address: work.contractor_address || '',
    date_of_completion: work.date_of_completion || '',
    consignee:          work.consignee          || '',
  }
  workSaveStatus.value   = ''
  showDeleteConfirm.value = false
}
const closeEditWork = () => {
  editingWork.value       = null
  showDeleteConfirm.value = false
  workSaveStatus.value    = ''
}
const saveWork = async () => {
  isSavingWork.value   = true
  workSaveStatus.value = ''
  try {
    const { id, ...payload } = editingWork.value
    await axios.patch(`/api/update-work/works/${id}/`, payload)
    const idx = allWorks.value.findIndex(w => w.id === id)
    if (idx !== -1) allWorks.value[idx] = { ...allWorks.value[idx], ...editingWork.value }
    if (selectedWork.value?.id === id) Object.assign(selectedWork.value, editingWork.value)
    workSaveStatus.value = 'saved'
    setTimeout(closeEditWork, 900)
  } catch (e) {
    console.error(e)
    workSaveStatus.value = 'error'
  } finally {
    isSavingWork.value = false
  }
}
const deleteWork = async () => {
  isDeletingWork.value = true
  try {
    await axios.delete(`/api/update-work/works/${editingWork.value.id}/`)
    allWorks.value = allWorks.value.filter(w => w.id !== editingWork.value.id)
    closeEditWork()
  } catch (e) {
    console.error(e)
    workSaveStatus.value = 'error'
  } finally {
    isDeletingWork.value = false
  }
}
</script>

<template>
  <div class="bg-white rounded-2xl soft-shadow min-h-full w-full flex flex-col overflow-hidden">

    <!-- ══ WORK LIST VIEW ═══════════════════════════════════════════ -->
    <template v-if="!selectedWork">

      <div class="px-8 pt-7 pb-5 border-b border-gray-100">
        <h1 class="text-2xl font-bold text-gray-900 tracking-tight mb-1">Update Work Database</h1>
        <p class="text-gray-400 text-sm font-medium mb-5">Search, then open a work to submit lot entries against its items.</p>

        <div class="flex items-center bg-gray-50 border border-gray-200 rounded-2xl px-5 py-3 focus-within:ring-2 focus-within:ring-[#0071e3]/20 focus-within:border-[#0071e3] focus-within:bg-white transition-all">
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
        <div class="i-carbon-circle-dash animate-spin text-3xl text-[#0071e3]"></div>
      </div>

      <div v-else-if="filteredWorks.length === 0" class="flex-1 flex flex-col items-center justify-center py-24 text-center">
        <div class="i-carbon-document-unknown text-5xl text-gray-200 mb-4"></div>
        <p class="text-sm font-semibold text-gray-400">
          {{ searchQuery ? 'No works match your search.' : 'No works uploaded yet.' }}
        </p>
      </div>

      <template v-else>
        <div class="flex-1 overflow-x-auto">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="bg-gray-50 text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
                <th class="px-6 py-3">Contractor / LOA</th>
                <th class="px-4 py-3">Tender Number</th>
                <th class="px-4 py-3">Consignee</th>
                <th class="px-4 py-3">Completion</th>
                <th class="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="work in filteredWorks" :key="work.id" class="hover:bg-gray-50/70 transition-colors">
                <td class="px-6 py-4">
                  <p class="text-sm font-semibold text-gray-900">{{ work.contractor_name || '—' }}</p>
                  <span class="mt-1 inline-block text-[11px] font-semibold text-[#0071e3] bg-[#0071e3]/10 px-2 py-0.5 rounded-full">
                    {{ work.loa_number || '—' }}
                  </span>
                </td>
                <td class="px-4 py-4 text-xs font-medium text-gray-600 max-w-[200px]">
                  <p class="truncate">{{ work.tender_number || '—' }}</p>
                </td>
                <td class="px-4 py-4 text-xs font-medium text-gray-600">{{ work.consignee || '—' }}</td>
                <td class="px-4 py-4 text-xs font-medium text-gray-600 whitespace-nowrap">{{ fmtDate(work.date_of_completion) }}</td>
                <td class="px-4 py-4 text-right">
                  <div class="flex items-center justify-end gap-2">
                    <button @click="openEditWork(work)"
                      class="px-3.5 py-2 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-600 text-xs font-semibold transition-all flex items-center gap-1.5">
                      <div class="i-carbon-edit text-xs"></div> Edit
                    </button>
                    <button @click="selectWork(work)"
                      class="px-3.5 py-2 rounded-full bg-dark-active text-white text-xs font-semibold shadow shadow-black/20 hover:shadow-md hover:-translate-y-0.5 transition-all flex items-center gap-1">
                      Submit Entries <div class="i-carbon-chevron-right text-xs"></div>
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="px-6 py-3 border-t border-gray-100 bg-gray-50 rounded-b-2xl">
          <p class="text-[11px] text-gray-400 font-medium">
            {{ filteredWorks.length }} {{ filteredWorks.length === 1 ? 'work' : 'works' }}
            <template v-if="searchQuery"> matching "{{ searchQuery }}"</template>
          </p>
        </div>
      </template>

    </template>

    <!-- ══ ITEMS VIEW ══════════════════════════════════════════════ -->
    <template v-else>
      <div class="flex flex-col h-full animate-fade-in">

        <!-- Header -->
        <div class="px-8 pt-6 pb-5 border-b border-gray-100">
          <div class="flex items-start justify-between gap-6">
            <div class="flex items-start gap-4 min-w-0">
              <button @click="selectedWork = null"
                class="mt-0.5 w-9 h-9 flex-shrink-0 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 transition-all">
                <div class="i-carbon-arrow-left text-base"></div>
              </button>
              <div class="min-w-0">
                <h2 class="text-xl font-bold text-gray-900 truncate">{{ selectedWork.contractor_name }}</h2>
                <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 mt-2">
                  <span class="flex items-center gap-1.5 text-xs text-gray-500">
                    <span class="font-medium text-gray-400">LOA</span>
                    <span class="font-semibold text-gray-800">{{ selectedWork.loa_number || '—' }}</span>
                  </span>
                  <span class="text-gray-200">·</span>
                  <span class="flex items-center gap-1.5 text-xs text-gray-500">
                    <span class="font-medium text-gray-400">Tender</span>
                    <span class="font-semibold text-gray-800">{{ selectedWork.tender_number || '—' }}</span>
                  </span>
                  <span class="text-gray-200">·</span>
                  <span class="flex items-center gap-1.5 text-xs text-gray-500">
                    <span class="font-medium text-gray-400">Consignee</span>
                    <span class="font-semibold text-gray-800">{{ selectedWork.consignee || '—' }}</span>
                  </span>
                  <span class="text-gray-200">·</span>
                  <span class="flex items-center gap-1.5 text-xs text-gray-500">
                    <span class="font-medium text-gray-400">Completion</span>
                    <span class="font-semibold text-gray-800">{{ selectedWork.date_of_completion || '—' }}</span>
                  </span>
                </div>
              </div>
            </div>
            <!-- Item filter -->
            <div class="flex-shrink-0 flex items-center bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 w-56 focus-within:ring-2 focus-within:ring-[#0071e3]/20 focus-within:border-[#0071e3] transition-all">
              <div class="i-carbon-filter text-gray-400 mr-2 text-sm"></div>
              <input v-model="itemFilter" type="text" placeholder="Filter items..."
                class="bg-transparent outline-none w-full text-xs text-gray-700 placeholder-gray-400 font-medium">
            </div>
          </div>
        </div>

        <!-- Items table -->
        <div class="overflow-y-auto flex-1">
          <table class="w-full border-collapse">
            <thead class="bg-gray-50 sticky top-0 z-10">
              <tr class="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
                <th class="px-4 py-3 text-center w-14">Sch</th>
                <th class="px-4 py-3 text-center w-14">S.No</th>
                <th class="px-4 py-3 text-left">Item Description</th>
                <th class="px-4 py-3 text-right w-28">Required</th>
                <th class="px-4 py-3 text-right w-28">Submitted</th>
                <th class="px-4 py-3 w-40">Progress</th>
                <th class="px-4 py-3 text-center w-32">Action</th>
              </tr>
            </thead>
            <tbody>
              <template v-if="filteredItems.length === 0">
                <tr><td colspan="7" class="p-8 text-center text-gray-400 text-xs font-medium">No items match your filter.</td></tr>
              </template>

              <tr v-for="item in filteredItems" :key="item.id"
                class="border-b border-gray-100 hover:bg-gray-50/60 transition-colors">

                <!-- Schedule badge -->
                <td class="px-4 py-3.5 text-center">
                  <span class="rounded-md px-2 py-1 text-[10px] font-bold bg-gray-100 text-gray-600">
                    {{ item.schedule }}
                  </span>
                </td>

                <!-- Serial number -->
                <td class="px-4 py-3.5 text-center text-[11px] font-semibold text-gray-500">
                  {{ item.serial_number }}
                </td>

                <!-- Description + lot count -->
                <td class="px-4 py-3.5">
                  <p class="text-xs font-medium line-clamp-2 leading-relaxed text-gray-800">{{ item.item_desc }}</p>
                  <p class="text-[10px] mt-0.5 text-gray-400">
                    {{ (item.entries || []).length }} lot{{ (item.entries || []).length === 1 ? '' : 's' }} submitted
                  </p>
                </td>

                <!-- Required qty -->
                <td class="px-4 py-3.5 text-right text-xs font-semibold text-gray-600">
                  {{ item.qty }} <span class="font-normal text-gray-400">{{ item.unit }}</span>
                </td>

                <!-- Submitted qty -->
                <td class="px-4 py-3.5 text-right text-xs font-semibold"
                  :class="(item.supplied_quantity || 0) > (item.qty || 0) ? 'text-orange-500' : 'text-gray-800'">
                  {{ item.supplied_quantity || 0 }}
                  <span class="font-normal text-gray-400">{{ item.unit }}</span>
                  <span v-if="(item.supplied_quantity || 0) > (item.qty || 0)"
                    class="ml-1 text-[9px] text-orange-400 font-bold">OVER</span>
                </td>

                <!-- Progress bar -->
                <td class="px-4 py-3.5">
                  <div class="flex items-center gap-2">
                    <div class="flex-1 h-1.5 rounded-full overflow-hidden bg-gray-100">
                      <div class="h-full rounded-full transition-all duration-500"
                        :class="progressPct(item) > 100 ? 'bg-orange-400' : 'bg-[#0071e3]'"
                        :style="{ width: Math.min(progressPct(item), 100) + '%' }">
                      </div>
                    </div>
                    <span class="text-[10px] font-bold w-8 text-right"
                      :class="progressPct(item) > 100 ? 'text-orange-500' : 'text-gray-500'">
                      {{ progressPct(item) }}%
                    </span>
                  </div>
                </td>

                <!-- Action button -->
                <td class="px-4 py-3.5 text-center">
                  <button @click="openLotPopup(item)"
                    class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full bg-[#0071e3]/10 hover:bg-[#0071e3]/20 text-[#0071e3] text-[11px] font-semibold transition-all">
                    <div class="i-carbon-add text-xs"></div>
                    Add Lot
                  </button>
                </td>
              </tr>

            </tbody>
          </table>
        </div>

      </div>
    </template>

    <!-- ══ EDIT WORK MODAL ═══════════════════════════════════════════ -->
    <Teleport to="body">
      <div v-if="editingWork" class="fixed inset-0 z-50 flex items-center justify-center p-6"
        style="background:rgba(0,0,0,0.4);backdrop-filter:blur(8px);" @click.self="closeEditWork">
        <div class="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[92vh] overflow-y-auto animate-modal">

          <div class="flex items-center justify-between px-8 pt-7 pb-5 border-b border-gray-100">
            <div>
              <h2 class="text-lg font-semibold text-gray-900">Edit Work Details</h2>
              <p class="text-xs text-gray-400 mt-0.5 font-medium">Update work-level information</p>
            </div>
            <button @click="closeEditWork"
              class="w-9 h-9 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-500 transition-all">
              <div class="i-carbon-close text-sm"></div>
            </button>
          </div>

          <div class="px-8 py-6 flex flex-col gap-4">
            <div class="grid grid-cols-2 gap-4">
              <div class="flex flex-col gap-1.5">
                <label class="text-xs font-semibold text-gray-500 tracking-wide">LOA Number</label>
                <input v-model="editingWork.loa_number" type="text" placeholder="00890160138264"
                  class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-gray-800 outline-none focus:border-[#0071e3] focus:ring-2 focus:ring-[#0071e3]/10 focus:bg-white transition-all">
              </div>
              <div class="flex flex-col gap-1.5">
                <label class="text-xs font-semibold text-gray-500 tracking-wide">Tender Number</label>
                <input v-model="editingWork.tender_number" type="text"
                  class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-gray-800 outline-none focus:border-[#0071e3] focus:ring-2 focus:ring-[#0071e3]/10 focus:bg-white transition-all">
              </div>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div class="flex flex-col gap-1.5">
                <label class="text-xs font-semibold text-gray-500 tracking-wide">Date</label>
                <input v-model="editingWork.date" type="text"
                  class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-gray-800 outline-none focus:border-[#0071e3] focus:ring-2 focus:ring-[#0071e3]/10 focus:bg-white transition-all">
              </div>
              <div class="flex flex-col gap-1.5">
                <label class="text-xs font-semibold text-gray-500 tracking-wide">Contract Agreement</label>
                <input v-model="editingWork.contract_agreement" type="text"
                  class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-gray-800 outline-none focus:border-[#0071e3] focus:ring-2 focus:ring-[#0071e3]/10 focus:bg-white transition-all">
              </div>
            </div>
            <div class="flex flex-col gap-1.5">
              <label class="text-xs font-semibold text-gray-500 tracking-wide">Contractor Name</label>
              <input v-model="editingWork.contractor_name" type="text"
                class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-gray-800 outline-none focus:border-[#0071e3] focus:ring-2 focus:ring-[#0071e3]/10 focus:bg-white transition-all">
            </div>
            <div class="flex flex-col gap-1.5">
              <label class="text-xs font-semibold text-gray-500 tracking-wide">Contractor Address</label>
              <textarea v-model="editingWork.contractor_address" rows="2"
                class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-gray-800 outline-none focus:border-[#0071e3] focus:ring-2 focus:ring-[#0071e3]/10 focus:bg-white transition-all resize-none"></textarea>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div class="flex flex-col gap-1.5">
                <label class="text-xs font-semibold text-gray-500 tracking-wide">Date of Completion</label>
                <input v-model="editingWork.date_of_completion" type="text"
                  class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-gray-800 outline-none focus:border-[#0071e3] focus:ring-2 focus:ring-[#0071e3]/10 focus:bg-white transition-all">
              </div>
              <div class="flex flex-col gap-1.5">
                <label class="text-xs font-semibold text-gray-500 tracking-wide">Consignee</label>
                <input v-model="editingWork.consignee" type="text"
                  class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-gray-800 outline-none focus:border-[#0071e3] focus:ring-2 focus:ring-[#0071e3]/10 focus:bg-white transition-all">
              </div>
            </div>
          </div>

          <div class="px-8 pb-7 pt-4 flex items-center justify-between gap-3 border-t border-gray-100">
            <div>
              <button v-if="!showDeleteConfirm" @click="showDeleteConfirm = true"
                class="px-5 py-2.5 rounded-full border border-[#ff3b30]/30 text-[#ff3b30] text-xs font-semibold hover:bg-[#ff3b30]/8 transition-all flex items-center gap-1.5">
                <div class="i-carbon-trash-can text-xs"></div> Delete Work
              </button>
              <div v-else class="flex items-center gap-2">
                <span class="text-xs font-semibold text-[#ff3b30]">Delete this work?</span>
                <button @click="deleteWork" :disabled="isDeletingWork"
                  class="px-4 py-2 rounded-full bg-[#ff3b30] text-white text-xs font-semibold shadow shadow-[#ff3b30]/30 hover:shadow-md hover:-translate-y-0.5 transition-all disabled:opacity-50 flex items-center gap-1">
                  <div v-if="isDeletingWork" class="i-carbon-circle-dash animate-spin"></div>
                  <span v-else>Yes, Delete</span>
                </button>
                <button @click="showDeleteConfirm = false"
                  class="px-4 py-2 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-semibold transition-all">Cancel</button>
              </div>
            </div>
            <div class="flex items-center gap-3">
              <p v-if="workSaveStatus === 'error'" class="text-xs font-medium text-[#ff3b30]">Failed to save.</p>
              <button @click="closeEditWork"
                class="px-6 py-2.5 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-800 text-sm font-semibold transition-all">Cancel</button>
              <button @click="saveWork" :disabled="isSavingWork"
                class="px-6 py-2.5 rounded-full text-white text-sm font-semibold shadow-lg hover:shadow-xl hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:translate-y-0 flex items-center gap-2"
                :class="workSaveStatus === 'saved' ? 'bg-[#34c759] shadow-[#34c759]/30' : 'bg-dark-active shadow-black/20'">
                <div v-if="isSavingWork" class="i-carbon-circle-dash animate-spin"></div>
                <span>{{ workSaveStatus === 'saved' ? 'Saved!' : 'Save Changes' }}</span>
              </button>
            </div>
          </div>

        </div>
      </div>
    </Teleport>

    <!-- ══ LOT ENTRY POPUP ════════════════════════════════════════════ -->
    <Teleport to="body">
      <div v-if="lotPopupItem" class="fixed inset-0 z-50 flex items-center justify-center p-6"
        style="background:rgba(0,0,0,0.45);backdrop-filter:blur(8px);" @click.self="closeLotPopup">
        <div class="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[92vh] flex flex-col animate-modal">

          <!-- Popup header: item info -->
          <div class="px-8 pt-7 pb-5 border-b border-gray-100 flex-shrink-0">
            <div class="flex items-start justify-between gap-4">
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2 mb-1.5">
                  <span class="text-[10px] font-bold bg-[#0071e3]/10 text-[#0071e3] px-2 py-1 rounded-md">
                    {{ lotPopupItem.schedule }}
                  </span>
                  <span class="text-[10px] font-semibold text-gray-400">S.No {{ lotPopupItem.serial_number }}</span>
                </div>
                <h2 class="text-sm font-semibold text-gray-900 leading-snug line-clamp-2">
                  {{ lotPopupItem.item_desc }}
                </h2>
                <!-- Progress summary -->
                <div class="flex items-center gap-4 mt-3">
                  <div class="flex flex-col">
                    <span class="text-[10px] font-medium text-gray-400 uppercase tracking-wide">Required</span>
                    <span class="text-sm font-bold text-gray-800">
                      {{ lotPopupItem.qty }} <span class="text-xs font-normal text-gray-400">{{ lotPopupItem.unit }}</span>
                    </span>
                  </div>
                  <div class="w-px h-8 bg-gray-100"></div>
                  <div class="flex flex-col">
                    <span class="text-[10px] font-medium text-gray-400 uppercase tracking-wide">Submitted</span>
                    <span class="text-sm font-bold"
                      :class="(lotPopupItem.supplied_quantity || 0) > (lotPopupItem.qty || 0) ? 'text-orange-500' : 'text-[#0071e3]'">
                      {{ lotPopupItem.supplied_quantity || 0 }}
                      <span class="text-xs font-normal text-gray-400">{{ lotPopupItem.unit }}</span>
                    </span>
                  </div>
                  <div class="w-px h-8 bg-gray-100"></div>
                  <div class="flex flex-col flex-1">
                    <span class="text-[10px] font-medium text-gray-400 uppercase tracking-wide mb-1.5">Progress</span>
                    <div class="flex items-center gap-2">
                      <div class="flex-1 h-2 rounded-full overflow-hidden bg-gray-100">
                        <div class="h-full rounded-full transition-all duration-500"
                          :class="progressPct(lotPopupItem) > 100 ? 'bg-orange-400' : 'bg-[#0071e3]'"
                          :style="{ width: Math.min(progressPct(lotPopupItem), 100) + '%' }">
                        </div>
                      </div>
                      <span class="text-xs font-bold w-10 text-right"
                        :class="progressPct(lotPopupItem) > 100 ? 'text-orange-500' : 'text-gray-600'">
                        {{ progressPct(lotPopupItem) }}%
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

          <!-- Popup body: scrollable -->
          <div class="flex-1 overflow-y-auto px-8 py-6 flex flex-col gap-6">

            <!-- Submit new lot form -->
            <div>
              <h3 class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-4 flex items-center gap-2">
                <div class="i-carbon-add-filled text-[#0071e3]"></div>
                Submit New Lot
              </h3>
              <div class="grid grid-cols-3 gap-3 mb-4">
                <div class="flex flex-col gap-1.5">
                  <label class="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">
                    Quantity <span class="text-red-400">*</span>
                  </label>
                  <input
                    v-model="entryForm.quantity"
                    type="number" step="0.01" min="0.01"
                    placeholder="e.g. 20"
                    class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-semibold text-gray-800 outline-none focus:border-[#0071e3] focus:ring-2 focus:ring-[#0071e3]/10 focus:bg-white transition-all">
                </div>
                <div class="flex flex-col gap-1.5">
                  <label class="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Challan No.</label>
                  <input
                    v-model="entryForm.challan_no"
                    type="text" placeholder="RN.56091..."
                    class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-gray-800 outline-none focus:border-[#0071e3] focus:ring-2 focus:ring-[#0071e3]/10 focus:bg-white transition-all">
                </div>
                <div class="flex flex-col gap-1.5">
                  <label class="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">UDM Entry</label>
                  <input
                    v-model="entryForm.udm_entry"
                    type="text" placeholder="dt. 05-01..."
                    class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-gray-800 outline-none focus:border-[#0071e3] focus:ring-2 focus:ring-[#0071e3]/10 focus:bg-white transition-all">
                </div>
              </div>
              <button
                @click="submitEntry"
                :disabled="entryForm.isSubmitting"
                class="w-full py-3 rounded-2xl text-white text-sm font-bold shadow shadow-black/15 hover:shadow-md hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:translate-y-0 flex items-center justify-center gap-2"
                :class="{
                  'bg-dark-active':  !entryForm.status,
                  'bg-[#34c759]':    entryForm.status === 'ok',
                  'bg-[#ff3b30]':    ['error','denied','invalid'].includes(entryForm.status),
                }"
              >
                <div v-if="entryForm.isSubmitting" class="i-carbon-circle-dash animate-spin"></div>
                <span v-else-if="entryForm.status === 'ok'">Lot Submitted Successfully!</span>
                <span v-else-if="entryForm.status === 'denied'">Access Denied</span>
                <span v-else-if="entryForm.status === 'invalid'">Please enter a quantity greater than 0</span>
                <span v-else-if="entryForm.status === 'error'">Submission Failed — Try Again</span>
                <span v-else>Submit Lot Entry</span>
              </button>
            </div>

            <!-- Lot history -->
            <div>
              <h3 class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3 flex items-center gap-2">
                <div class="i-carbon-list text-gray-400"></div>
                Lot History
                <span class="ml-1 text-[10px] font-bold bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
                  {{ (lotPopupItem.entries || []).length }}
                </span>
              </h3>

              <div v-if="(lotPopupItem.entries || []).length === 0"
                class="py-8 text-center text-xs text-gray-400 font-medium bg-gray-50 rounded-2xl border border-dashed border-gray-200">
                No lots submitted yet. Use the form above to submit the first one.
              </div>

              <div v-else class="rounded-2xl border border-gray-100 overflow-hidden">
                <table class="w-full text-xs">
                  <thead class="bg-gray-50 text-[10px] text-gray-400 font-bold uppercase tracking-widest border-b border-gray-100">
                    <tr>
                      <th class="px-4 py-2.5 text-left">#</th>
                      <th class="px-4 py-2.5 text-right">Quantity</th>
                      <th class="px-4 py-2.5 text-left">Challan No.</th>
                      <th class="px-4 py-2.5 text-left">UDM Entry</th>
                      <th class="px-4 py-2.5 text-left">Submitted By</th>
                      <th class="px-4 py-2.5 text-left">Date & Time</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-gray-50">
                    <tr v-for="(entry, idx) in lotPopupItem.entries" :key="entry.id"
                      class="hover:bg-gray-50/60 transition-colors">
                      <td class="px-4 py-2.5 text-gray-400 font-semibold">{{ idx + 1 }}</td>
                      <td class="px-4 py-2.5 text-right font-bold text-gray-800">
                        {{ entry.quantity }} <span class="text-gray-400 font-normal">{{ lotPopupItem.unit }}</span>
                      </td>
                      <td class="px-4 py-2.5 text-gray-600 font-medium">{{ entry.challan_no || '—' }}</td>
                      <td class="px-4 py-2.5 text-gray-600 font-medium">{{ entry.udm_entry || '—' }}</td>
                      <td class="px-4 py-2.5 text-gray-600 font-medium">
                        {{ entry.submitted_by_user?.username || '—' }}
                      </td>
                      <td class="px-4 py-2.5 text-gray-400">{{ fmtDateTime(entry.submitted_at) }}</td>
                    </tr>
                  </tbody>
                  <tfoot class="bg-gray-50 border-t border-gray-100">
                    <tr>
                      <td class="px-4 py-2.5 text-[10px] font-bold text-gray-400 uppercase tracking-wide">Total</td>
                      <td class="px-4 py-2.5 text-right font-bold text-gray-800">
                        {{ lotPopupItem.supplied_quantity || 0 }}
                        <span class="text-gray-400 font-normal">{{ lotPopupItem.unit }}</span>
                      </td>
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
@keyframes fade-in  { from { opacity:0; transform:translateY(6px);          } to { opacity:1; transform:translateY(0);        } }
@keyframes modal-in { from { opacity:0; transform:scale(0.96)translateY(8px);} to { opacity:1; transform:scale(1)translateY(0); } }
.animate-fade-in { animation: fade-in  0.3s cubic-bezier(.4,0,.2,1); }
.animate-modal   { animation: modal-in 0.25s cubic-bezier(.4,0,.2,1); }
</style>
