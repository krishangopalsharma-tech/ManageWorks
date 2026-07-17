<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const getCsrfToken = () => { const m = document.cookie.match(/csrftoken=([^;]+)/); return m ? m[1] : '' }

const fmtDate = (val) => {
  if (!val) return '—'
  const s = String(val).split('T')[0].split(' ')[0]
  if (/^\d{2}[\/\-]\d{2}[\/\-]\d{4}$/.test(s)) return s.replace(/-/g, '/')
  const m = s.match(/^(\d{4})[\/\-](\d{2})[\/\-](\d{2})$/)
  if (m) return `${m[3]}/${m[2]}/${m[1]}`
  return s
}
const romanOrdinal = (n) => {
  const nums = ['I','II','III','IV','V','VI','VII','VIII','IX','X']
  const suf  = ['st','nd','rd','th','th','th','th','th','th','th']
  if (n >= 1 && n <= 10) return nums[n - 1] + suf[n - 1]
  return `${n}th`
}

// ── State ──────────────────────────────────────────────────────────────────
const searchQuery  = ref('')
const allWorks     = ref([])
const isLoading    = ref(true)
const currentUser  = ref(null)

const isAdmin       = computed(() => currentUser.value?.role === 'admin' || currentUser.value?.is_staff)
// Metadata edit is admin (any LOA) or the LOA's own assigned consignee — backend
// enforces this per-work via _check_can_modify_work; this flag is just for showing
// the Edit button in the list (server still authorizes the actual PATCH).
const canModifyWork = computed(() => isAdmin.value || currentUser.value?.role === 'consignee')

// Edit-work modal
const editingWork       = ref(null)
const isSavingWork      = ref(false)
const workSaveStatus    = ref('')
const showDeleteConfirm = ref(false)
const isDeletingWork    = ref(false)
const deleteReason      = ref('')
const deleteReasonError = ref('')

// ── Load ───────────────────────────────────────────────────────────────────
const loadWorks = async () => {
  isLoading.value = true
  try {
    const [worksRes, meRes] = await Promise.allSettled([
      axios.get('/api/update-work/works/search/'),
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

// ── Work list filtering ────────────────────────────────────────────────────
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

// ── Edit-work modal ────────────────────────────────────────────────────────
const openEditWork = (work) => {
  editingWork.value = {
    id: work.id, loa_number: work.loa_number || '', tender_number: work.tender_number || '',
    date: work.date || '', contract_agreement: work.contract_agreement || '',
    name_of_work: work.name_of_work || '',
    contractor_name: work.contractor_name || '', contractor_address: work.contractor_address || '',
    date_of_completion: work.date_of_completion || '', consignee: work.consignee || '',
    extensions: (work.extensions || []).map(e => ({ ld_type: 'without_ld', ld_amount: '', ...e })),
  }
  workSaveStatus.value    = ''
  showDeleteConfirm.value = false
}
const closeEditWork = () => { editingWork.value = null; showDeleteConfirm.value = false; workSaveStatus.value = ''; deleteReason.value = ''; deleteReasonError.value = '' }

const addExtension = () => { editingWork.value.extensions.push({ extension_date: '', ld_type: 'without_ld', ld_amount: '' }) }
const removeExtension = (idx) => { editingWork.value.extensions.splice(idx, 1) }

const saveWork = async () => {
  isSavingWork.value   = true
  workSaveStatus.value = ''
  try {
    const { id, extensions, ...fields } = editingWork.value
    const payload = {
      ...fields,
      extensions: extensions.filter(e => (e.extension_date || '').trim()).map(e => ({
        extension_date: e.extension_date.trim(),
        ld_type: e.ld_type || 'without_ld',
        ld_amount: (e.ld_type === 'with_ld') ? (e.ld_amount || '').trim() : '',
      })),
    }
    await axios.patch(`/api/update-work/works/${id}/`, payload, { headers: { 'X-CSRFToken': getCsrfToken() } })
    const idx = allWorks.value.findIndex(w => w.id === id)
    if (idx !== -1) allWorks.value[idx] = { ...allWorks.value[idx], ...fields, extensions: payload.extensions }
    workSaveStatus.value = 'saved'
    setTimeout(closeEditWork, 900)
  } catch (e) {
    console.error(e)
    workSaveStatus.value = e.response?.status === 403 ? 'denied' : 'error'
  } finally {
    isSavingWork.value = false
  }
}

const deleteWork = async () => {
  deleteReasonError.value = ''
  if (!deleteReason.value.trim()) {
    deleteReasonError.value = 'Please enter a reason for deletion.'
    return
  }
  isDeletingWork.value = true
  try {
    await axios.delete(`/api/delete-log/works/${editingWork.value.id}/`, {
      headers: { 'X-CSRFToken': getCsrfToken() },
      data: { reason: deleteReason.value.trim() },
    })
    allWorks.value = allWorks.value.filter(w => w.id !== editingWork.value.id)
    deleteReason.value = ''
    closeEditWork()
  } catch (e) {
    console.error(e); workSaveStatus.value = 'error'
  } finally {
    isDeletingWork.value = false
  }
}
</script>

<template>
  <div class="bg-white rounded-2xl soft-shadow h-full w-full flex flex-col overflow-hidden">

    <div class="flex-shrink-0 px-8 pt-7 pb-5 border-b border-gray-100">
      <h1 class="text-2xl font-bold text-gray-900 tracking-tight mb-1">Update Work</h1>
      <p class="text-gray-400 text-sm font-medium mb-5">Edit LOA details — number, contractor, contract agreement, consignee, extensions.</p>
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
          <div v-for="work in filteredWorks" :key="work.id"
            class="w-full bg-white border border-gray-200 px-5 py-3 rounded-xl transition-all">
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
                  <span class="text-gray-200">·</span>
                  <span class="text-[11px] text-gray-500">Completion: <span class="font-semibold text-gray-700">{{ fmtDate(work.date_of_completion) }}</span></span>
                </div>
              </div>
              <div class="flex items-center gap-3 flex-shrink-0">
                <p class="text-xs text-gray-500 whitespace-nowrap">
                  <span class="font-bold text-gray-800">{{ work.items.length }}</span> items
                </p>
                <button v-if="canModifyWork" @click="openEditWork(work)"
                  class="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#1D5F5E] hover:bg-[#174E4D] text-white text-xs font-semibold transition-colors">
                  <div class="i-carbon-edit text-xs"></div> Edit
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ══ EDIT WORK MODAL ════════════════════════════════════════════ -->
    <Teleport to="body">
      <div v-if="editingWork" class="fixed inset-0 z-50 flex items-center justify-center p-6"
        style="background:rgba(0,0,0,0.4);backdrop-filter:blur(8px);" @click.self="closeEditWork">
        <div class="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[92vh] overflow-y-auto animate-modal">

          <div class="flex items-center justify-between px-7 pt-5 pb-4 border-b border-gray-100">
            <h2 class="text-base font-bold text-gray-900">Edit Work Details</h2>
            <button @click="closeEditWork" class="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-500 transition-all">
              <div class="i-carbon-close text-sm"></div>
            </button>
          </div>

          <div class="px-7 py-5 flex flex-col gap-4">
            <div class="grid grid-cols-2 gap-3">
              <div class="flex flex-col gap-1">
                <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wide">LOA Number</label>
                <input v-model="editingWork.loa_number" type="text" class="bg-gray-50 border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm font-medium text-gray-800 outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 focus:bg-white transition-all">
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wide">Tender Number</label>
                <input v-model="editingWork.tender_number" type="text" class="bg-gray-50 border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm font-medium text-gray-800 outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 focus:bg-white transition-all">
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wide">Date</label>
                <input v-model="editingWork.date" type="text" class="bg-gray-50 border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm font-medium text-gray-800 outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 focus:bg-white transition-all">
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wide">Contract Agreement</label>
                <input v-model="editingWork.contract_agreement" type="text" class="bg-gray-50 border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm font-medium text-gray-800 outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 focus:bg-white transition-all">
              </div>
            </div>
            <div class="flex flex-col gap-1">
              <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wide">Name of Work</label>
              <textarea v-model="editingWork.name_of_work" rows="2" class="bg-gray-50 border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm font-medium text-gray-800 outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 focus:bg-white transition-all resize-none"></textarea>
            </div>
            <div class="flex flex-col gap-1">
              <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wide">Contractor Name</label>
              <input v-model="editingWork.contractor_name" type="text" class="bg-gray-50 border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm font-medium text-gray-800 outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 focus:bg-white transition-all">
            </div>
            <div class="flex flex-col gap-1">
              <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wide">Contractor Address</label>
              <textarea v-model="editingWork.contractor_address" rows="2" class="bg-gray-50 border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm font-medium text-gray-800 outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 focus:bg-white transition-all resize-none"></textarea>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div class="flex flex-col gap-1">
                <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wide">Date of Completion</label>
                <input v-model="editingWork.date_of_completion" type="text" class="bg-gray-50 border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm font-medium text-gray-800 outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 focus:bg-white transition-all">
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wide">Consignee</label>
                <input v-model="editingWork.consignee" type="text" class="bg-gray-50 border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm font-medium text-gray-800 outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 focus:bg-white transition-all">
              </div>
            </div>

            <div class="rounded-2xl border border-gray-100 bg-gray-50/60 p-4">
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-2">
                  <div class="i-carbon-calendar text-gray-400 text-sm"></div>
                  <span class="text-xs font-bold text-gray-600 uppercase tracking-wide">Extension Dates</span>
                </div>
                <button @click="addExtension"
                  class="flex items-center gap-1 px-3 py-1.5 rounded-full bg-white border border-gray-200 hover:border-[#1D5F5E] hover:text-[#1D5F5E] text-gray-500 text-[11px] font-semibold transition-all shadow-sm">
                  <div class="i-carbon-add text-xs"></div> Add
                </button>
              </div>
              <div v-if="editingWork.extensions.length === 0" class="text-center py-3 text-[11px] text-gray-400 font-medium">No extensions yet.</div>
              <div v-else class="flex flex-col gap-2">
                <div v-for="(ext, idx) in editingWork.extensions" :key="idx" class="flex flex-col gap-1.5">
                  <div class="flex items-center gap-2">
                    <span class="text-[11px] font-bold text-gray-500 w-16 flex-shrink-0">{{ romanOrdinal(idx + 1) }} Ext.</span>
                    <input v-model="ext.extension_date" type="text" placeholder="e.g. 2027-09-04"
                      class="flex-1 bg-white border border-gray-200 rounded-xl px-3.5 py-2 text-sm font-medium text-gray-800 outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 transition-all">
                    <select v-model="ext.ld_type"
                      class="bg-white border border-gray-200 rounded-xl px-3 py-2 text-sm font-medium text-gray-800 outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 transition-all cursor-pointer">
                      <option value="without_ld">Without LD</option>
                      <option value="with_ld">With LD</option>
                    </select>
                    <button @click="removeExtension(idx)"
                      class="flex-shrink-0 w-7 h-7 rounded-full bg-white border border-gray-200 hover:border-[#ff3b30]/50 hover:text-[#ff3b30] text-gray-400 flex items-center justify-center transition-all">
                      <div class="i-carbon-close text-xs"></div>
                    </button>
                  </div>
                  <div v-if="ext.ld_type === 'with_ld'" class="flex items-center gap-2 pl-[4.5rem]">
                    <input v-model="ext.ld_amount" type="text" placeholder="LD amount (e.g. ₹5000/week or ₹10000/month)"
                      class="flex-1 bg-amber-50 border border-amber-200 rounded-xl px-3.5 py-2 text-sm font-medium text-gray-800 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-400/10 transition-all">
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="px-7 pb-6 pt-3 flex items-center justify-between gap-3 border-t border-gray-100">
            <div>
              <template v-if="isAdmin">
                <button v-if="!showDeleteConfirm" @click="showDeleteConfirm = true"
                  class="px-4 py-2 rounded-xl bg-red-50 text-red-600 border border-red-200 text-xs font-semibold hover:bg-red-100 transition-colors flex items-center gap-1.5">
                  <div class="i-carbon-trash-can text-xs"></div> Delete Work
                </button>
                <div v-else class="flex flex-col gap-2 max-w-sm">
                  <span class="text-xs font-semibold text-red-600">Delete this work? This cannot be undone.</span>
                  <textarea
                    v-model="deleteReason"
                    placeholder="Enter reason for deletion…"
                    rows="2"
                    class="w-full text-xs border rounded-xl px-3 py-2 outline-none resize-none focus:ring-2 focus:ring-red-300 focus:border-red-400"
                    :class="deleteReasonError ? 'border-red-400 bg-red-50' : 'border-gray-200 bg-gray-50'"
                  ></textarea>
                  <p v-if="deleteReasonError" class="text-xs text-red-500 -mt-1">{{ deleteReasonError }}</p>
                  <div class="flex items-center gap-2">
                    <button @click="deleteWork" :disabled="isDeletingWork"
                      class="px-4 py-2 rounded-xl bg-red-500 hover:bg-red-600 text-white text-xs font-semibold transition-colors disabled:opacity-50 flex items-center gap-1">
                      <div v-if="isDeletingWork" class="i-carbon-circle-dash animate-spin"></div>
                      <span v-else>Yes, Delete</span>
                    </button>
                    <button @click="showDeleteConfirm = false; deleteReason = ''; deleteReasonError = ''"
                      class="px-4 py-2 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 text-xs font-semibold transition-colors">
                      Cancel
                    </button>
                  </div>
                </div>
              </template>
            </div>
            <div class="flex items-center gap-3">
              <p v-if="workSaveStatus === 'error'" class="text-xs font-medium text-[#ff3b30]">Failed to save.</p>
              <p v-if="workSaveStatus === 'denied'" class="text-xs font-medium text-[#ff3b30]">Not authorised to edit this LOA.</p>
              <button @click="closeEditWork" class="px-5 py-2.5 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 text-sm font-semibold transition-colors">Cancel</button>
              <button @click="saveWork" :disabled="isSavingWork"
                class="px-5 py-2.5 rounded-xl text-white text-sm font-semibold transition-colors disabled:opacity-50 flex items-center gap-2"
                :class="workSaveStatus === 'saved' ? 'bg-[#5E8858]' : 'bg-[#1D5F5E] hover:bg-[#174E4D]'">
                <div v-if="isSavingWork" class="i-carbon-circle-dash animate-spin"></div>
                <span>{{ workSaveStatus === 'saved' ? 'Saved!' : 'Save Changes' }}</span>
              </button>
            </div>
          </div>

        </div>
      </div>
    </Teleport>

  </div>
</template>

<style scoped>
@keyframes modal-in { from { opacity:0; transform:scale(0.96) translateY(8px); } to { opacity:1; transform:scale(1) translateY(0); } }
.animate-modal { animation: modal-in 0.25s cubic-bezier(.4,0,.2,1); }
</style>
