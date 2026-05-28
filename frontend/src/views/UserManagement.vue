<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'

const API = '/api/auth'

const ROLES = ['consignee', 'admin']
const ROLE_STYLE = {
  consignee: 'bg-amber-100 text-amber-700',
  admin:     'bg-purple-100 text-purple-700',
}

// ── State ──────────────────────────────────────────────────────────────────
const pending       = ref([])
const approved      = ref([])
const allWorks      = ref([])
const loading       = ref(true)
const tab           = ref('approved')
const toast         = ref({ show: false, msg: '', type: 'success' })

// detail view
const detailUser    = ref(null)   // selected consignee
const isEditing     = ref(false)
const editDesig     = ref('')
const editRole      = ref('')
const editEmail     = ref('')
const isSaving      = ref(false)
const workSearch    = ref('')

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/)
  return m ? m[1] : ''
}
const h = () => ({ 'X-CSRFToken': getCsrf() })

// ── Tab auto-logic ────────────────────────────────────────────────────────
watch(pending, (val) => {
  if (val.length > 0) tab.value = 'pending'
  else                tab.value = 'approved'
}, { immediate: false })

// ── Load ──────────────────────────────────────────────────────────────────
async function loadData() {
  loading.value = true
  try {
    const [p, a, w] = await Promise.all([
      axios.get(`${API}/pending/`),
      axios.get(`${API}/all/`),
      axios.get(`${API}/works/`),
    ])
    pending.value  = p.data
    approved.value = a.data
    allWorks.value = w.data
    // set initial tab based on pending count
    tab.value = p.data.length > 0 ? 'pending' : 'approved'
  } finally {
    loading.value = false
  }
}

// ── Pending actions ───────────────────────────────────────────────────────
async function approve(id) {
  await axios.post(`${API}/approve/${id}/`, {}, { headers: h() })
  showToast('User approved.')
  await loadData()
}
async function reject(id) {
  if (!confirm('Reject and permanently delete this registration?')) return
  await axios.delete(`${API}/reject/${id}/`, { headers: h() })
  showToast('Registration rejected.', 'error')
  await loadData()
}

// ── Approved list ─────────────────────────────────────────────────────────
function openDetail(u) {
  detailUser.value = u
  isEditing.value  = false
  editDesig.value  = u.designation
  editRole.value   = u.role
  editEmail.value  = u.email || ''
  workSearch.value = ''
}
function closeDetail() {
  detailUser.value = null
  isEditing.value  = false
}
function startEdit() {
  isEditing.value = true
}
function cancelEdit() {
  editDesig.value = detailUser.value.designation
  editRole.value  = detailUser.value.role
  editEmail.value = detailUser.value.email || ''
  isEditing.value = false
}

async function saveUser() {
  if (!detailUser.value) return
  isSaving.value = true
  try {
    await axios.patch(`${API}/update/${detailUser.value.id}/`, {
      designation: editDesig.value,
      role:        editRole.value,
      email:       editEmail.value,
    }, { headers: h() })
    const u = approved.value.find(x => x.id === detailUser.value.id)
    if (u) { u.designation = editDesig.value; u.role = editRole.value; u.email = editEmail.value }
    detailUser.value = { ...detailUser.value, designation: editDesig.value, role: editRole.value, email: editEmail.value }
    isEditing.value  = false
    showToast('User updated.')
  } catch {
    showToast('Save failed.', 'error')
  } finally {
    isSaving.value = false
  }
}

async function revoke(id) {
  if (!confirm('Revoke access? User cannot login until re-approved.')) return
  await axios.post(`${API}/revoke/${id}/`, {}, { headers: h() })
  showToast('Access revoked.', 'error')
  if (detailUser.value?.id === id) detailUser.value = null
  await loadData()
}

// ── Work assignment ───────────────────────────────────────────────────────
const assignedWorks = computed(() => {
  if (!detailUser.value) return []
  return allWorks.value.filter(w => w.hrms_id === detailUser.value.hrms_id)
})

const addableWorks = computed(() => {
  const q    = workSearch.value.trim().toLowerCase()
  const pool = allWorks.value.filter(w => !w.hrms_id || !w.hrms_id.trim())
  if (!q) return pool.slice(0, 30)
  return pool.filter(w =>
    (w.loa_number      || '').toLowerCase().includes(q) ||
    (w.contractor_name || '').toLowerCase().includes(q) ||
    (w.tender_number   || '').toLowerCase().includes(q)
  ).slice(0, 30)
})

const unassignedCount = computed(() =>
  allWorks.value.filter(w => !w.hrms_id || !w.hrms_id.trim()).length
)

async function assignWork(work) {
  if (!detailUser.value) return
  try {
    await axios.post(`${API}/assign-work/`, {
      work_id: work.id,
      hrms_id: detailUser.value.hrms_id,
    }, { headers: h() })
    work.hrms_id = detailUser.value.hrms_id
    showToast('Work assigned.')
    workSearch.value = ''
  } catch {
    showToast('Assign failed.', 'error')
  }
}

async function unassignWork(work) {
  try {
    await axios.post(`${API}/assign-work/`, { work_id: work.id, hrms_id: '' }, { headers: h() })
    work.hrms_id = ''
    showToast('Work removed.')
  } catch {
    showToast('Failed.', 'error')
  }
}

// ── Telegram link (admin view of a user's link status) ────────────────────
const tgOtp       = ref(null)   // OTP code string or null
const tgLinked    = ref(false)  // whether user has linked Telegram
const tgLoading   = ref(false)

async function loadTelegramStatus(userId) {
  // Admin cannot fetch another user's OTP via the current endpoint (self-only).
  // We only show the "linked" badge here; OTP generation is user's own action.
  tgOtp.value    = null
  tgLinked.value = false
}

// ── Toast ─────────────────────────────────────────────────────────────────
function showToast(msg, type = 'success') {
  toast.value = { show: true, msg, type }
  setTimeout(() => { toast.value.show = false }, 3000)
}

onMounted(loadData)
</script>

<template>
  <div class="h-full flex flex-col overflow-hidden">

    <!-- ═══ DETAIL VIEW ════════════════════════════════════════════════════ -->
    <template v-if="detailUser">

      <!-- Top bar -->
      <div class="flex-shrink-0 px-6 pt-5 pb-4 border-b border-gray-100 dark:border-[#3a3a3c] flex items-center gap-3">
        <button @click="closeDetail"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-[#3a3a3c] text-sm text-gray-600 dark:text-[#aeaeb2] hover:bg-gray-50 dark:hover:bg-[#2c2c2e] transition-colors">
          <div class="i-carbon-arrow-left text-sm"></div>
          <span class="font-medium">Users</span>
        </button>
        <span class="text-sm font-semibold text-gray-800 dark:text-white truncate">{{ detailUser.name }}</span>
        <div class="flex-1"></div>

        <!-- Actions -->
        <template v-if="!isEditing">
          <button @click="startEdit"
            class="flex items-center gap-1.5 px-4 py-2 rounded-xl border border-gray-200 dark:border-[#3a3a3c] bg-white dark:bg-[#1c1c1e] text-gray-700 dark:text-[#aeaeb2] text-sm font-semibold hover:bg-gray-50 dark:hover:bg-[#2c2c2e] transition-colors">
            <div class="i-carbon-edit text-sm"></div> Edit
          </button>
        </template>
        <template v-else>
          <button @click="cancelEdit"
            class="px-4 py-2 rounded-xl border border-gray-200 dark:border-[#3a3a3c] bg-white dark:bg-[#1c1c1e] text-gray-700 dark:text-[#aeaeb2] text-sm font-semibold hover:bg-gray-50 dark:hover:bg-[#2c2c2e] transition-colors">
            Cancel
          </button>
          <button @click="saveUser" :disabled="isSaving"
            class="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#1D5F5E] hover:bg-[#174E4D] text-white text-sm font-semibold transition-colors disabled:opacity-50">
            <div v-if="isSaving" class="i-carbon-circle-dash animate-spin text-xs"></div>
            {{ isSaving ? 'Saving…' : 'Save' }}
          </button>
        </template>
        <button @click="revoke(detailUser.id)"
          class="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-red-500 hover:bg-red-600 text-white text-sm font-semibold transition-colors">
          <div class="i-carbon-locked text-sm"></div> Revoke
        </button>
      </div>

      <!-- Detail body — two column -->
      <div class="flex-1 overflow-hidden flex">

        <!-- Left: profile + assigned works -->
        <div class="w-1/2 overflow-y-auto px-6 py-6 border-r border-gray-100 dark:border-[#3a3a3c]">
          <div class="max-w-xl flex flex-col gap-6">

            <!-- Profile card -->
            <div class="bg-white dark:bg-[#1c1c1e] rounded-2xl soft-shadow border border-gray-100 dark:border-[#3a3a3c] overflow-hidden">
              <!-- Avatar + name row -->
              <div class="px-6 py-2.5 flex items-center gap-4">
                <div class="w-14 h-14 rounded-full flex items-center justify-center text-xl font-bold shrink-0"
                  :class="detailUser.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-amber-100 text-amber-700'">
                  {{ (detailUser.name || '?')[0].toUpperCase() }}
                </div>
                <div>
                  <p class="text-base font-bold text-gray-800 dark:text-white">{{ detailUser.name }}</p>
                  <span class="inline-block mt-1 text-[11px] font-bold px-2.5 py-0.5 rounded-full capitalize"
                    :class="ROLE_STYLE[isEditing ? editRole : detailUser.role] || 'bg-gray-100 text-gray-600'">
                    {{ isEditing ? editRole : detailUser.role }}
                  </span>
                </div>
              </div>

              <!-- Info grid -->
              <div class="grid grid-cols-2 border-t border-gray-100 dark:border-[#3a3a3c]">
                <div class="px-6 py-2 border-b border-r border-gray-100 dark:border-[#3a3a3c] flex items-baseline gap-2">
                  <p class="text-[9px] font-bold text-gray-400 uppercase tracking-widest shrink-0">HRMS ID</p>
                  <p class="text-sm font-semibold text-gray-800 dark:text-white font-mono">{{ detailUser.hrms_id }}</p>
                </div>
                <div class="px-6 py-2 border-b border-gray-100 dark:border-[#3a3a3c] flex items-baseline gap-2">
                  <p class="text-[9px] font-bold text-gray-400 uppercase tracking-widest shrink-0">PF No</p>
                  <p class="text-sm font-semibold text-gray-800 dark:text-white font-mono">{{ detailUser.pf_number }}</p>
                </div>
                <div class="px-6 py-2 border-r border-gray-100 dark:border-[#3a3a3c] flex items-baseline gap-2">
                  <p class="text-[9px] font-bold text-gray-400 uppercase tracking-widest shrink-0">Designation</p>
                  <input v-if="isEditing" v-model="editDesig" type="text"
                    class="w-full bg-gray-50 dark:bg-[#2c2c2e] border border-gray-200 dark:border-[#3a3a3c] rounded-lg px-3 py-1 text-sm font-medium text-gray-800 dark:text-white outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 transition-all">
                  <p v-else class="text-sm font-semibold text-gray-800 dark:text-white">{{ detailUser.designation }}</p>
                </div>
                <div class="px-6 py-2 flex items-baseline gap-2">
                  <p class="text-[9px] font-bold text-gray-400 uppercase tracking-widest shrink-0">Role</p>
                  <select v-if="isEditing" v-model="editRole"
                    class="w-full bg-gray-50 dark:bg-[#2c2c2e] border border-gray-200 dark:border-[#3a3a3c] rounded-lg px-3 py-1 text-sm font-semibold text-gray-800 dark:text-white outline-none focus:border-[#1D5F5E] transition-all cursor-pointer">
                    <option v-for="r in ROLES" :key="r" :value="r" class="bg-white text-gray-800 capitalize">{{ r }}</option>
                  </select>
                  <p v-else class="text-sm font-semibold text-gray-800 dark:text-white capitalize">{{ detailUser.role }}</p>
                </div>
                <div class="col-span-2 px-6 py-2 border-t border-gray-100 dark:border-[#3a3a3c] flex items-baseline gap-2">
                  <p class="text-[9px] font-bold text-gray-400 uppercase tracking-widest shrink-0">Email</p>
                  <input v-if="isEditing" v-model="editEmail" type="email"
                    class="w-full bg-gray-50 dark:bg-[#2c2c2e] border border-gray-200 dark:border-[#3a3a3c] rounded-lg px-3 py-1 text-sm font-medium text-gray-800 dark:text-white outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 transition-all"
                    placeholder="user@example.com">
                  <p v-else class="text-sm font-semibold text-gray-800 dark:text-white">{{ detailUser.email || '—' }}</p>
                </div>
                <div class="col-span-2 px-6 py-2 border-t border-gray-100 dark:border-[#3a3a3c] flex items-center gap-2">
                  <p class="text-[9px] font-bold text-gray-400 uppercase tracking-widest shrink-0">Telegram</p>
                  <span v-if="detailUser.telegram_linked"
                    class="inline-flex items-center gap-1 text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-blue-100 text-blue-700">
                    <div class="i-carbon-checkmark text-xs"></div> Linked
                  </span>
                  <span v-else class="text-[11px] text-gray-400">Not linked — user must connect from their profile</span>
                </div>
              </div>
            </div>

            <!-- Assigned works -->
            <div>
              <div class="flex items-center justify-between mb-3">
                <p class="text-sm font-bold text-gray-700 dark:text-[#f5f5f7]">
                  Assigned Works
                  <span class="ml-1.5 text-[11px] font-bold text-gray-400">({{ assignedWorks.length }})</span>
                </p>
              </div>

              <div v-if="assignedWorks.length === 0"
                class="bg-white dark:bg-[#1c1c1e] rounded-2xl soft-shadow border border-gray-100 dark:border-[#3a3a3c] py-10 text-center">
                <div class="i-carbon-document-unknown text-3xl text-gray-300 mx-auto mb-2"></div>
                <p class="text-sm text-gray-400">No works assigned to this consignee</p>
              </div>
              <div v-else class="flex flex-col gap-2.5">
                <div v-for="w in assignedWorks" :key="w.id"
                  class="bg-white dark:bg-[#1c1c1e] rounded-2xl soft-shadow border border-gray-100 dark:border-[#3a3a3c] px-5 py-4 flex items-start gap-4">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 flex-wrap mb-1.5">
                      <span class="text-[11px] font-bold text-[#1D5F5E] bg-[#1D5F5E]/10 px-2.5 py-0.5 rounded-full">
                        {{ w.loa_number || '—' }}
                      </span>
                      <span v-if="w.tender_number" class="text-[11px] text-gray-500 dark:text-[#aeaeb2]">{{ w.tender_number }}</span>
                    </div>
                    <p class="text-sm font-bold text-gray-800 dark:text-white">{{ w.contractor_name || '—' }}</p>
                    <p v-if="w.name_of_work" class="text-[11px] text-gray-400 dark:text-[#8e8e93] mt-1 line-clamp-2">{{ w.name_of_work }}</p>
                  </div>
                  <button @click="unassignWork(w)"
                    class="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-200 dark:border-red-900/50 text-red-500 bg-white dark:bg-[#1c1c1e] hover:bg-red-50 dark:hover:bg-red-900/20 text-[11px] font-semibold transition-colors mt-0.5">
                    <div class="i-carbon-subtract-alt text-xs"></div> Remove
                  </button>
                </div>
              </div>
            </div>

          </div>
        </div>

        <!-- Right: unassigned works to assign -->
        <div class="w-1/2 flex-shrink-0 flex flex-col overflow-hidden">
          <div class="px-6 pt-6 pb-4">
            <p class="text-base font-bold text-gray-800 dark:text-white">List Of Unassigned work</p>
            <span v-if="unassignedCount > 0"
              class="inline-flex items-center gap-1 mt-1 text-[11px] font-bold text-red-500 bg-red-50 dark:bg-red-900/20 px-2 py-0.5 rounded-full">
              <div class="i-carbon-warning-filled text-xs"></div>
              {{ unassignedCount }} unassigned system-wide
            </span>
          </div>

          <!-- Search -->
          <div class="px-6 pb-4">
            <div class="flex items-center bg-white dark:bg-[#2c2c2e] border border-gray-200 dark:border-[#3a3a3c] rounded-xl px-4 py-2.5 focus-within:border-[#1D5F5E] focus-within:ring-2 focus-within:ring-[#1D5F5E]/10 transition-all">
              <div class="i-carbon-search text-gray-400 mr-3 text-sm"></div>
              <input v-model="workSearch" type="text" placeholder="Search by LOA number, contractor, tender..."
                class="bg-transparent outline-none flex-1 text-sm text-gray-700 dark:text-[#f5f5f7] placeholder-gray-400">
            </div>
          </div>

          <!-- Work list -->
          <div class="flex-1 overflow-y-auto px-6 pb-6">
            <div v-if="addableWorks.length === 0"
              class="py-12 text-center text-sm text-gray-400">
              {{ workSearch ? 'No works match.' : 'All works already assigned.' }}
            </div>
            <div v-else class="flex flex-col gap-2">
              <button v-for="w in addableWorks" :key="w.id"
                @click="assignWork(w)"
                class="w-full text-left bg-white dark:bg-[#1c1c1e] rounded-xl soft-shadow border border-gray-100 dark:border-[#3a3a3c] px-4 py-3.5 flex items-start gap-3 hover:border-[#1D5F5E] hover:shadow-md transition-all group">
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2 flex-wrap mb-1">
                    <span class="text-[11px] font-bold px-2 py-0.5 rounded-full bg-[#1D5F5E]/10 text-[#1D5F5E]">
                      {{ w.loa_number || '—' }}
                    </span>
                    <span v-if="w.tender_number" class="text-[11px] text-gray-500 dark:text-[#aeaeb2]">{{ w.tender_number }}</span>
                  </div>
                  <p class="text-sm font-semibold text-gray-800 dark:text-white">{{ w.contractor_name || '—' }}</p>
                  <p class="text-[11px] text-red-500 font-medium mt-0.5">Unassigned</p>
                </div>
                <div class="shrink-0 flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-[#1D5F5E]/10 text-[#1D5F5E] text-[11px] font-semibold group-hover:bg-[#1D5F5E] group-hover:text-white transition-all mt-0.5">
                  <div class="i-carbon-add text-xs"></div> Assign
                </div>
              </button>
            </div>
          </div>
        </div>

      </div>

    </template>

    <!-- ═══ LIST VIEW ══════════════════════════════════════════════════════ -->
    <template v-else>

      <!-- Header -->
      <div class="flex-shrink-0 px-6 pt-5 pb-4 border-b border-gray-100">
        <h1 class="text-xl font-bold text-gray-800 tracking-tight">User Management</h1>
        <p class="text-sm text-gray-500 mt-0.5">Approve registrations and manage user roles</p>
      </div>

      <!-- Tabs -->
      <div class="flex-shrink-0 flex gap-1 px-6 pt-4 pb-0">
        <button v-for="t in ['pending', 'approved']" :key="t"
          @click="tab = t"
          class="px-5 py-2 rounded-lg text-sm font-semibold capitalize transition-all"
          :class="tab === t ? 'bg-[#1D5F5E] text-white' : 'text-gray-500 hover:text-gray-700'">
          {{ t }}
          <span v-if="t === 'pending' && pending.length"
            class="ml-1.5 px-1.5 py-0.5 text-[10px] rounded-full bg-red-100 text-red-600 font-bold">
            {{ pending.length }}
          </span>
        </button>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="flex items-center gap-2 text-sm text-gray-400 p-8">
        <div class="i-carbon-circle-dash animate-spin text-lg"></div> Loading…
      </div>

      <div v-else class="flex-1 overflow-y-auto px-6 py-4">

        <!-- ── Pending list ── -->
        <div v-if="tab === 'pending'">
          <div v-if="!pending.length" class="py-20 text-center">
            <div class="i-carbon-checkmark-outline text-5xl text-gray-300 mx-auto mb-3"></div>
            <p class="text-sm text-gray-400">No pending registrations</p>
          </div>
          <div v-else class="flex flex-col gap-3 max-w-2xl">
            <div v-for="u in pending" :key="u.id"
              class="bg-light-surface rounded-2xl soft-shadow p-5 flex items-center gap-4">
              <div class="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center shrink-0">
                <div class="i-carbon-user text-xl text-gray-500"></div>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-semibold text-gray-800">{{ u.name }}</p>
                <p class="text-xs text-gray-500 mt-0.5">{{ u.designation }}</p>
                <div class="flex gap-4 mt-1.5 text-xs text-gray-400">
                  <span>HRMS: <span class="font-medium text-gray-600">{{ u.hrms_id }}</span></span>
                  <span>PF: <span class="font-medium text-gray-600">{{ u.pf_number }}</span></span>
                  <span>{{ u.created_at }}</span>
                </div>
              </div>
              <div class="flex gap-2 shrink-0">
                <button @click="approve(u.id)"
                  class="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-green-600 text-white text-xs font-semibold hover:bg-green-700 transition-colors">
                  <div class="i-carbon-checkmark text-sm"></div> Approve
                </button>
                <button @click="reject(u.id)"
                  class="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-red-50 text-red-600 border border-red-200 text-xs font-semibold hover:bg-red-100 transition-colors">
                  <div class="i-carbon-close text-sm"></div> Reject
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- ── Approved list ── -->
        <div v-else-if="tab === 'approved'">
          <div v-if="!approved.length" class="py-20 text-center">
            <p class="text-sm text-gray-400">No approved users yet</p>
          </div>
          <div v-else class="bg-light-surface rounded-2xl soft-shadow overflow-hidden max-w-4xl">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-gray-100">
                  <th class="text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest px-5 py-3">Name</th>
                  <th class="text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest px-5 py-3">HRMS ID</th>
                  <th class="text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest px-5 py-3">Email</th>
                  <th class="text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest px-5 py-3">Designation</th>
                  <th class="text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest px-5 py-3">Role</th>
                  <th class="text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest px-5 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="u in approved" :key="u.id"
                  class="border-b border-gray-50 hover:bg-accent-soft/40 transition-colors cursor-pointer"
                  @click="openDetail(u)">
                  <td class="px-5 py-3.5">
                    <div class="flex items-center gap-2.5">
                      <div class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
                        :class="u.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-amber-100 text-amber-700'">
                        {{ (u.name || '?')[0].toUpperCase() }}
                      </div>
                      <span class="font-semibold text-gray-800">{{ u.name }}</span>
                    </div>
                  </td>
                  <td class="px-5 py-3.5 text-gray-600 font-mono text-xs">{{ u.hrms_id }}</td>
                  <td class="px-5 py-3.5 text-gray-600 text-xs">{{ u.email || '—' }}</td>
                  <td class="px-5 py-3.5 text-gray-600">{{ u.designation }}</td>
                  <td class="px-5 py-3.5">
                    <span class="text-[11px] font-bold px-2 py-0.5 rounded-full capitalize"
                      :class="ROLE_STYLE[u.role] || 'bg-gray-100 text-gray-600'">
                      {{ u.role }}
                    </span>
                  </td>
                  <td class="px-5 py-3.5" @click.stop>
                    <button @click="revoke(u.id)"
                      class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-50 text-red-600 border border-red-200 text-xs font-semibold hover:bg-red-100 transition-colors">
                      <div class="i-carbon-locked text-sm"></div> Revoke
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </template>

    <!-- Toast -->
    <transition name="toast">
      <div v-if="toast.show"
        class="fixed bottom-6 right-6 flex items-center gap-2 px-4 py-3 rounded-xl shadow-lg text-sm font-medium z-50"
        :class="toast.type === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'">
        <div :class="toast.type === 'success' ? 'i-carbon-checkmark' : 'i-carbon-warning'" class="text-base"></div>
        {{ toast.msg }}
      </div>
    </transition>
  </div>
</template>

<style scoped>
.toast-enter-active, .toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(8px); }
.line-clamp-1 { overflow: hidden; display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; }
</style>
