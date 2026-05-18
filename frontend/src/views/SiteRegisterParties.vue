<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/)
  return m ? m[1] : ''
}
const h = () => ({ 'X-CSRFToken': getCsrf() })

const works        = ref([])
const linkedUsers  = ref([])
const loading      = ref(true)
const search       = ref('')
const toast        = ref({ show: false, msg: '', type: 'success' })

// Add-party modal state
const modal        = ref(null)   // { work } or null
const selLinkId    = ref('')
const selRole      = ref('sse')
const adding       = ref(false)

async function load() {
  loading.value = true
  try {
    const [pw, pu] = await Promise.all([
      axios.get('/api/site-register/parties/'),
      axios.get('/api/site-register/linked-users/'),
    ])
    works.value       = pw.data
    linkedUsers.value = pu.data
  } catch {
    showToast('Failed to load data.', 'error')
  } finally {
    loading.value = false
  }
}

const filteredWorks = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return works.value
  return works.value.filter(w =>
    (w.loa_number     || '').toLowerCase().includes(q) ||
    (w.contractor_name|| '').toLowerCase().includes(q) ||
    (w.name_of_work   || '').toLowerCase().includes(q)
  )
})

function openModal(work) {
  modal.value  = { work }
  selLinkId.value = ''
  selRole.value   = 'sse'
}

function closeModal() { modal.value = null }

// Users not already mapped to this work
const availableUsers = computed(() => {
  if (!modal.value) return []
  const taken = new Set(modal.value.work.parties.map(p => p.user_id))
  return linkedUsers.value.filter(u => !taken.has(u.user_id))
})

async function addParty() {
  if (!selLinkId.value) return
  adding.value = true
  try {
    const { data } = await axios.post(
      `/api/site-register/parties/${modal.value.work.id}/`,
      { link_id: selLinkId.value, role: selRole.value },
      { headers: h() }
    )
    modal.value.work.parties.push(data)
    showToast('Party added.')
    closeModal()
  } catch (e) {
    showToast(e.response?.data?.error || 'Failed to add.', 'error')
  } finally {
    adding.value = false
  }
}

async function removeParty(work, mapping) {
  if (!confirm(`Remove ${mapping.name || mapping.hrms_id} from this LOA?`)) return
  try {
    await axios.delete(
      `/api/site-register/parties/${work.id}/${mapping.mapping_id}/`,
      { headers: h() }
    )
    work.parties = work.parties.filter(p => p.mapping_id !== mapping.mapping_id)
    showToast('Party removed.')
  } catch {
    showToast('Failed to remove.', 'error')
  }
}

function showToast(msg, type = 'success') {
  toast.value = { show: true, msg, type }
  setTimeout(() => { toast.value.show = false }, 3000)
}

const ROLE_STYLE = {
  sse:        'bg-blue-100 text-blue-700',
  contractor: 'bg-green-100 text-green-700',
}

onMounted(load)
</script>

<template>
  <div class="h-full overflow-y-auto px-6 py-6">
    <div class="max-w-4xl">

      <!-- Header -->
      <div class="mb-6">
        <h1 class="text-xl font-bold text-gray-800 dark:text-white tracking-tight">LOA Party Management</h1>
        <p class="text-sm text-gray-500 mt-0.5">Assign Telegram-linked SSEs and contractors to each LOA.</p>
      </div>

      <!-- Search -->
      <div class="relative mb-5">
        <div class="i-carbon-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-base pointer-events-none"></div>
        <input
          v-model="search"
          type="text"
          placeholder="Search by LOA, contractor or work name…"
          class="w-full pl-9 pr-4 py-2.5 rounded-xl border border-gray-200 dark:border-[#3a3a3c] bg-white dark:bg-[#1c1c1e] text-sm text-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#1D5F5E]/30"
        />
      </div>

      <!-- Loading -->
      <div v-if="loading" class="flex items-center gap-2 text-sm text-gray-400 mt-8">
        <div class="i-carbon-circle-dash animate-spin text-lg"></div> Loading…
      </div>

      <!-- Empty -->
      <div v-else-if="!filteredWorks.length" class="text-sm text-gray-400 mt-8">
        No works found.
      </div>

      <!-- Work cards -->
      <div v-else class="flex flex-col gap-4">
        <div
          v-for="work in filteredWorks"
          :key="work.id"
          class="bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] shadow-sm overflow-hidden"
        >
          <!-- Work header -->
          <div class="px-5 py-4 flex items-start justify-between gap-4 border-b border-gray-100 dark:border-[#2c2c2e]">
            <div class="min-w-0">
              <p class="text-sm font-bold text-gray-800 dark:text-white truncate">
                LOA {{ work.loa_number || '—' }}
              </p>
              <p class="text-xs text-gray-500 truncate mt-0.5">{{ work.contractor_name || '—' }}</p>
              <p class="text-xs text-gray-400 truncate">{{ work.name_of_work || '—' }}</p>
            </div>
            <button
              @click="openModal(work)"
              class="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1D5F5E] hover:bg-[#174E4D] text-white text-xs font-semibold transition-colors"
            >
              <div class="i-carbon-add text-sm"></div>
              Add Party
            </button>
          </div>

          <!-- Parties list -->
          <div class="px-5 py-3">
            <div v-if="!work.parties.length" class="text-xs text-gray-400 py-1">
              No parties assigned. Add SSE and contractor to enable Telegram bot.
            </div>
            <div v-else class="flex flex-col gap-2">
              <div
                v-for="party in work.parties"
                :key="party.mapping_id"
                class="flex items-center gap-3"
              >
                <span
                  class="shrink-0 text-xs font-bold px-2 py-0.5 rounded-full"
                  :class="ROLE_STYLE[party.role] || 'bg-gray-100 text-gray-600'"
                >{{ party.role.toUpperCase() }}</span>
                <div class="flex-1 min-w-0">
                  <span class="text-sm font-semibold text-gray-800 dark:text-white">{{ party.name || party.hrms_id }}</span>
                  <span class="text-xs text-gray-400 ml-2">{{ party.hrms_id }}</span>
                  <span v-if="party.designation" class="text-xs text-gray-400 ml-1">· {{ party.designation }}</span>
                </div>
                <button
                  @click="removeParty(work, party)"
                  class="shrink-0 p-1 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                  title="Remove"
                >
                  <div class="i-carbon-close text-sm"></div>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Party Modal -->
    <Teleport to="body">
      <div
        v-if="modal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        style="background: rgba(0,0,0,0.4);"
        @click.self="closeModal"
      >
        <div class="bg-white dark:bg-[#1c1c1e] rounded-2xl shadow-xl w-full max-w-md p-6 flex flex-col gap-5">
          <div class="flex items-center justify-between">
            <h2 class="text-base font-bold text-gray-800 dark:text-white">Add Party</h2>
            <button @click="closeModal" class="text-gray-400 hover:text-gray-600 p-1">
              <div class="i-carbon-close text-lg"></div>
            </button>
          </div>

          <div class="text-sm text-gray-500">
            LOA <span class="font-semibold text-gray-700 dark:text-gray-200">{{ modal.work.loa_number }}</span>
            · {{ modal.work.contractor_name }}
          </div>

          <!-- Role select -->
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Role</label>
            <div class="flex gap-2">
              <button
                v-for="r in ['sse', 'contractor']"
                :key="r"
                @click="selRole = r"
                class="flex-1 py-2 rounded-xl border text-sm font-semibold transition-colors"
                :class="selRole === r
                  ? 'bg-[#1D5F5E] text-white border-[#1D5F5E]'
                  : 'border-gray-200 dark:border-[#3a3a3c] text-gray-600 dark:text-[#aeaeb2] hover:border-[#1D5F5E]'"
              >{{ r.toUpperCase() }}</button>
            </div>
          </div>

          <!-- User select -->
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">User</label>
            <div v-if="!availableUsers.length" class="text-sm text-gray-400">
              No Telegram-linked users available. Users must link their Telegram first.
            </div>
            <select
              v-else
              v-model="selLinkId"
              class="w-full px-3 py-2.5 rounded-xl border border-gray-200 dark:border-[#3a3a3c] bg-white dark:bg-[#2c2c2e] text-sm text-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#1D5F5E]/30"
            >
              <option value="" disabled>Select a user…</option>
              <option
                v-for="u in availableUsers"
                :key="u.link_id"
                :value="u.link_id"
              >{{ u.name || u.hrms_id }} ({{ u.hrms_id }}){{ u.designation ? ' · ' + u.designation : '' }}</option>
            </select>
          </div>

          <!-- Actions -->
          <div class="flex gap-3 pt-1">
            <button
              @click="closeModal"
              class="flex-1 py-2.5 rounded-xl border border-gray-200 dark:border-[#3a3a3c] text-sm font-semibold text-gray-600 dark:text-[#aeaeb2] hover:bg-gray-50 dark:hover:bg-[#2c2c2e] transition-colors"
            >Cancel</button>
            <button
              @click="addParty"
              :disabled="!selLinkId || adding"
              class="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-[#1D5F5E] hover:bg-[#174E4D] text-white text-sm font-semibold transition-colors disabled:opacity-50"
            >
              <div v-if="adding" class="i-carbon-circle-dash animate-spin text-sm"></div>
              {{ adding ? 'Adding…' : 'Add Party' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Toast -->
    <transition name="toast">
      <div
        v-if="toast.show"
        class="fixed bottom-6 right-6 flex items-center gap-2 px-4 py-3 rounded-xl shadow-lg text-sm font-medium z-50"
        :class="toast.type === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'"
      >
        <div :class="toast.type === 'success' ? 'i-carbon-checkmark' : 'i-carbon-warning'" class="text-base"></div>
        {{ toast.msg }}
      </div>
    </transition>
  </div>
</template>

<style scoped>
.toast-enter-active, .toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(8px); }
</style>
