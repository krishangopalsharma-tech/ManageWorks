<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import axios from 'axios'
import QRCode from 'qrcode'

const BOT_USERNAME = 'ADISiteregister_bot'
const BOT_URL      = `https://t.me/${BOT_USERNAME}`

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/)
  return m ? m[1] : ''
}
const h = () => ({ 'X-CSRFToken': getCsrf() })

const router = useRouter()
const route  = useRoute()

const contractor  = ref(history.state?.contractor || route.query.contractor || '')
const allLoas     = ref(history.state?.loas || [])

const selLoas     = ref(new Set(allLoas.value.map(l => l.id)))
const invite      = ref(null)
const qrDataUrl   = ref(null)
const secondsLeft = ref(0)
const generating  = ref(false)
const linked      = ref(null)
const toast       = ref({ show: false, msg: '', type: 'success' })
let countdownTimer = null
let pollTimer      = null

// ── Telegram users list ───────────────────────────────────────────────────────
const tgUsers         = ref([])
const tgUsersLoading  = ref(false)
const tgSearch        = ref('')
const editingId       = ref(null)
const editForm        = ref({ onboard_name: '', onboard_designation: '', onboard_mobile: '' })
const saving          = ref(false)

const filteredTgUsers = computed(() => {
  const q = tgSearch.value.toLowerCase()
  if (!q) return tgUsers.value
  return tgUsers.value.filter(u =>
    (u.name || '').toLowerCase().includes(q) ||
    (u.telegram_user_id || '').toString().includes(q) ||
    (u.designation || '').toLowerCase().includes(q)
  )
})

async function loadTgUsers() {
  tgUsersLoading.value = true
  try {
    const { data } = await axios.get('/api/site-register/linked-users/')
    tgUsers.value = data
  } catch { /* ignore */ } finally {
    tgUsersLoading.value = false
  }
}

function startEdit(u) {
  editingId.value = u.link_id
  editForm.value  = {
    onboard_name:        u.name || '',
    onboard_designation: u.designation || '',
    onboard_mobile:      u.mobile || '',
  }
}

function cancelEdit() { editingId.value = null }

async function saveEdit(u) {
  saving.value = true
  try {
    const { data } = await axios.patch(
      `/api/site-register/linked-users/${u.link_id}/`,
      editForm.value,
      { headers: h() }
    )
    const idx = tgUsers.value.findIndex(x => x.link_id === u.link_id)
    if (idx !== -1) tgUsers.value[idx] = data
    editingId.value = null
    showToast('Saved.')
  } catch {
    showToast('Save failed.', 'error')
  } finally {
    saving.value = false
  }
}

// ── Invite ────────────────────────────────────────────────────────────────────
const selectedCount = computed(() => selLoas.value.size)

function toggleLoa(id) {
  if (selLoas.value.has(id)) selLoas.value.delete(id)
  else selLoas.value.add(id)
}

async function buildQr() {
  qrDataUrl.value = await QRCode.toDataURL(BOT_URL, {
    width: 180, margin: 2,
    color: { dark: '#1D5F5E', light: '#FFFFFF' },
  })
}

function startCountdown(expiresAt) {
  clearInterval(countdownTimer)
  const tick = () => {
    const diff = Math.max(0, Math.round((new Date(expiresAt) - Date.now()) / 1000))
    secondsLeft.value = diff
    if (diff === 0) {
      clearInterval(countdownTimer)
      clearInterval(pollTimer)
      invite.value = null
    }
  }
  tick()
  countdownTimer = setInterval(tick, 1000)
}

function startPolling(code) {
  clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    try {
      const { data } = await axios.get(`/api/site-register/supervisor-invite/${code}/`)
      if (data.used) {
        clearInterval(pollTimer)
        clearInterval(countdownTimer)
        linked.value = data.linked_user
        showToast(`${data.linked_user.name || data.linked_user.hrms_id} linked as supervisor!`)
        loadTgUsers()
      }
    } catch { /* ignore */ }
  }, 3000)
}

async function generateInvite() {
  if (!selectedCount.value) { showToast('Select at least one LOA.', 'error'); return }
  generating.value = true
  clearInterval(pollTimer); clearInterval(countdownTimer)
  linked.value = null
  try {
    const { data } = await axios.post(
      '/api/site-register/supervisor-invite/',
      { loa_ids: [...selLoas.value] },
      { headers: h() }
    )
    invite.value = data
    startCountdown(data.expires_at)
    startPolling(data.code)
  } catch (e) {
    showToast(e.response?.data?.error || 'Failed to generate invite.', 'error')
  } finally {
    generating.value = false
  }
}

async function copyCode() {
  if (!invite.value) return
  await navigator.clipboard.writeText(invite.value.code)
  showToast('Code copied!')
}

function showToast(msg, type = 'success') {
  toast.value = { show: true, msg, type }
  setTimeout(() => { toast.value.show = false }, 3000)
}

onMounted(async () => {
  await buildQr()
  loadTgUsers()
  if (allLoas.value.length) await generateInvite()
})

onUnmounted(() => {
  clearInterval(countdownTimer)
  clearInterval(pollTimer)
})
</script>

<template>
  <div class="px-6 py-6 min-h-full">

    <!-- Header -->
    <div class="mb-5 flex items-center gap-3">
      <button @click="router.back()"
        class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-[#2c2c2e] transition-colors"
        style="color: var(--color-text-tertiary);">
        <div class="i-carbon-arrow-left text-lg"></div>
      </button>
      <div>
        <h1 class="text-xl font-bold text-gray-800 dark:text-white tracking-tight">Add Site Supervisor</h1>
        <p class="text-sm text-gray-500 mt-0.5">{{ contractor || 'Contractor' }}</p>
      </div>
    </div>

    <!-- Top row: LOA checklist + QR/OTP side by side -->
    <div class="flex gap-4 mb-6 items-start">

      <!-- LOA checklist -->
      <div class="flex-1 min-w-0 bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] shadow-sm p-5">
        <h2 class="text-sm font-bold text-gray-700 dark:text-gray-200 mb-1">Apply to LOAs</h2>
        <p class="text-xs text-gray-400 mb-3">Uncheck LOAs to exclude from this invite.</p>
        <div class="flex flex-col gap-1.5">
          <label v-for="loa in allLoas" :key="loa.id"
            class="flex items-start gap-3 px-3 py-2 rounded-xl cursor-pointer hover:bg-gray-50 dark:hover:bg-[#2c2c2e] transition-colors">
            <input type="checkbox" :checked="selLoas.has(loa.id)" @change="toggleLoa(loa.id)"
              class="w-4 h-4 accent-[#1D5F5E] mt-0.5 shrink-0" />
            <div class="flex-1 min-w-0">
              <p class="text-sm font-semibold text-gray-800 dark:text-white">{{ loa.loa_number }}</p>
              <p class="text-xs text-gray-400 truncate">{{ loa.name_of_work }}</p>
            </div>
          </label>
        </div>
      </div>

      <!-- QR + OTP panel -->
      <div class="w-72 shrink-0 bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] shadow-sm p-5">

        <!-- Success -->
        <div v-if="linked" class="flex flex-col items-center gap-3 py-4 text-center">
          <div class="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
            <div class="i-carbon-checkmark-filled text-green-600 text-2xl"></div>
          </div>
          <p class="text-sm font-bold text-green-700 dark:text-green-400">Supervisor Linked!</p>
          <p class="text-xs text-gray-500">
            {{ linked.name || linked.hrms_id }}
            <span v-if="linked.designation"> · {{ linked.designation }}</span>
          </p>
          <div class="flex gap-2 w-full mt-2">
            <button @click="linked = null; invite = null; generateInvite()"
              class="flex-1 py-2 rounded-xl bg-[#1D5F5E] text-white text-xs font-semibold hover:bg-[#174E4D] transition-colors">
              Add Another
            </button>
            <button @click="router.back()"
              class="flex-1 py-2 rounded-xl border border-gray-200 dark:border-[#3a3a3c] text-xs font-semibold text-gray-600 dark:text-[#aeaeb2] hover:bg-gray-50 dark:hover:bg-[#2c2c2e] transition-colors">
              Done
            </button>
          </div>
        </div>

        <!-- No invite yet -->
        <div v-else-if="!invite" class="flex flex-col items-center gap-4 py-6">
          <div class="p-3 bg-gray-50 dark:bg-[#2c2c2e] rounded-2xl">
            <img v-if="qrDataUrl" :src="qrDataUrl" alt="Bot QR" class="w-36 h-36 opacity-40" />
          </div>
          <p class="text-xs text-gray-400 text-center">Generate an invite code to share with the supervisor.</p>
          <button @click="generateInvite" :disabled="generating || !selectedCount"
            class="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#1D5F5E] hover:bg-[#174E4D] text-white text-xs font-semibold transition-colors disabled:opacity-50">
            <div v-if="generating" class="i-carbon-circle-dash animate-spin text-xs"></div>
            {{ generating ? 'Generating…' : 'Generate Invite Code' }}
          </button>
        </div>

        <!-- Active invite -->
        <div v-else class="flex flex-col items-center gap-4">
          <p class="text-xs font-bold text-gray-500 uppercase tracking-widest">Share with Supervisor</p>

          <!-- QR -->
          <div class="p-2 bg-white rounded-xl shadow-sm border border-gray-100">
            <img :src="qrDataUrl" alt="Bot QR" class="w-36 h-36" />
          </div>

          <!-- Steps note -->
          <p class="text-xs text-gray-400 text-center">Scan QR or open <span class="font-mono text-[#1D5F5E]">@ADISiteregister_bot</span>, then type the code below.</p>

          <!-- Code -->
          <div class="w-full">
            <div class="flex items-center gap-2 px-4 py-3 bg-gray-50 dark:bg-[#2c2c2e] rounded-xl justify-center">
              <span class="text-2xl font-mono font-bold tracking-[0.25em] text-[#1D5F5E]">{{ invite.code }}</span>
              <button @click="copyCode"
                class="p-1.5 rounded-lg hover:bg-gray-200 dark:hover:bg-[#3a3a3c] transition-colors"
                style="color: var(--color-text-tertiary);">
                <div class="i-carbon-copy text-sm"></div>
              </button>
            </div>
            <div class="flex items-center justify-center gap-1.5 mt-1.5 text-xs"
              :class="secondsLeft < 30 ? 'text-red-500' : 'text-gray-400'">
              <div class="i-carbon-time text-xs"></div>
              <span>Expires in {{ secondsLeft }}s</span>
            </div>
          </div>

          <!-- Waiting -->
          <div class="flex items-center gap-2 text-xs text-gray-400">
            <div class="i-carbon-circle-dash animate-spin text-xs"></div>
            Waiting for supervisor…
          </div>

          <button @click="generateInvite" :disabled="generating"
            class="text-xs text-[#1D5F5E] hover:underline disabled:opacity-50">
            Generate new code
          </button>
        </div>
      </div>
    </div>

    <!-- Bottom: Linked Telegram Users list -->
    <div class="bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] shadow-sm overflow-hidden">
      <div class="px-5 py-4 border-b border-gray-100 dark:border-[#3a3a3c] flex items-center gap-3">
        <h2 class="text-sm font-bold text-gray-700 dark:text-gray-200 flex-1">Linked Telegram Users</h2>
        <input v-model="tgSearch" type="text" placeholder="Search…"
          class="text-xs px-3 py-1.5 rounded-lg border border-gray-200 dark:border-[#3a3a3c] bg-gray-50 dark:bg-[#2c2c2e] text-gray-700 dark:text-gray-200 placeholder-gray-400 outline-none focus:border-[#1D5F5E] w-48" />
        <button @click="loadTgUsers" :disabled="tgUsersLoading"
          class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-[#2c2c2e] transition-colors" title="Refresh">
          <div :class="tgUsersLoading ? 'animate-spin' : ''" class="i-carbon-renew text-sm text-gray-400"></div>
        </button>
      </div>

      <div v-if="tgUsersLoading && !tgUsers.length" class="p-6 text-xs text-gray-400 flex items-center gap-2">
        <div class="i-carbon-circle-dash animate-spin"></div> Loading…
      </div>
      <div v-else-if="!filteredTgUsers.length" class="p-6 text-xs text-gray-400 text-center">No linked users found.</div>

      <table v-else class="w-full text-xs">
        <thead>
          <tr class="border-b border-gray-100 dark:border-[#2c2c2e]">
            <th class="px-5 py-2.5 text-left font-semibold text-gray-400 uppercase tracking-wider">Type</th>
            <th class="px-5 py-2.5 text-left font-semibold text-gray-400 uppercase tracking-wider">Name</th>
            <th class="px-5 py-2.5 text-left font-semibold text-gray-400 uppercase tracking-wider">Designation</th>
            <th class="px-5 py-2.5 text-left font-semibold text-gray-400 uppercase tracking-wider">Mobile</th>
            <th class="px-5 py-2.5 text-left font-semibold text-gray-400 uppercase tracking-wider">Telegram ID</th>
            <th class="px-5 py-2.5 text-left font-semibold text-gray-400 uppercase tracking-wider">Chat ID</th>
            <th class="px-5 py-2.5 text-right font-semibold text-gray-400 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="u in filteredTgUsers" :key="u.link_id">
            <!-- View row -->
            <tr v-if="editingId !== u.link_id"
              class="border-b border-gray-50 dark:border-[#2c2c2e] hover:bg-gray-50 dark:hover:bg-[#2c2c2e] transition-colors">
              <td class="px-5 py-3">
                <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium"
                  :class="u.is_contractor
                    ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400'
                    : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'">
                  <div :class="u.is_contractor ? 'i-carbon-construction' : 'i-carbon-user-avatar'" class="text-xs"></div>
                  {{ u.is_contractor ? 'Contractor' : 'Official' }}
                </span>
              </td>
              <td class="px-5 py-3 font-semibold text-gray-800 dark:text-white">{{ u.name }}</td>
              <td class="px-5 py-3 text-gray-500">{{ u.designation || '—' }}</td>
              <td class="px-5 py-3 text-gray-500">{{ u.mobile || '—' }}</td>
              <td class="px-5 py-3 font-mono text-gray-500">{{ u.telegram_user_id }}</td>
              <td class="px-5 py-3 font-mono text-gray-400">{{ u.telegram_chat_id }}</td>
              <td class="px-5 py-3 text-right">
                <button @click="startEdit(u)"
                  class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-gray-200 dark:border-[#3a3a3c] text-gray-500 hover:text-[#1D5F5E] hover:border-[#1D5F5E] transition-colors">
                  <div class="i-carbon-edit text-xs"></div> Edit
                </button>
              </td>
            </tr>
            <!-- Edit row -->
            <tr v-else class="border-b border-[#1D5F5E]/20 bg-[#1D5F5E]/5">
              <td class="px-5 py-3">
                <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium"
                  :class="u.is_contractor
                    ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400'
                    : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'">
                  {{ u.is_contractor ? 'Contractor' : 'Official' }}
                </span>
              </td>
              <td class="px-5 py-3">
                <input v-model="editForm.onboard_name" class="w-full text-xs px-2 py-1 rounded-lg border border-[#1D5F5E]/30 bg-white dark:bg-[#2c2c2e] outline-none focus:border-[#1D5F5E]" placeholder="Name" />
              </td>
              <td class="px-5 py-3">
                <input v-model="editForm.onboard_designation" class="w-full text-xs px-2 py-1 rounded-lg border border-[#1D5F5E]/30 bg-white dark:bg-[#2c2c2e] outline-none focus:border-[#1D5F5E]" placeholder="Designation" />
              </td>
              <td class="px-5 py-3">
                <input v-if="u.is_contractor" v-model="editForm.onboard_mobile" class="w-full text-xs px-2 py-1 rounded-lg border border-[#1D5F5E]/30 bg-white dark:bg-[#2c2c2e] outline-none focus:border-[#1D5F5E]" placeholder="Mobile" />
                <span v-else class="text-gray-400">—</span>
              </td>
              <td class="px-5 py-3 font-mono text-gray-400">{{ u.telegram_user_id }}</td>
              <td class="px-5 py-3 font-mono text-gray-400 text-xs">{{ u.telegram_chat_id }}<span class="text-gray-300 ml-1">(locked)</span></td>
              <td class="px-5 py-3 text-right">
                <div class="flex items-center justify-end gap-2">
                  <button @click="saveEdit(u)" :disabled="saving"
                    class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#1D5F5E] text-white text-xs font-semibold hover:bg-[#174E4D] disabled:opacity-50 transition-colors">
                    <div v-if="saving" class="i-carbon-circle-dash animate-spin text-xs"></div>
                    <div v-else class="i-carbon-checkmark text-xs"></div>
                    Save
                  </button>
                  <button @click="cancelEdit"
                    class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-gray-200 dark:border-[#3a3a3c] text-gray-500 text-xs hover:bg-gray-100 dark:hover:bg-[#3a3a3c] transition-colors">
                    Cancel
                  </button>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>

      <div class="px-5 py-3 border-t border-gray-100 dark:border-[#3a3a3c]">
        <p class="text-xs text-gray-400">{{ tgUsers.length }} user{{ tgUsers.length !== 1 ? 's' : '' }} linked · Chat ID is not editable</p>
      </div>
    </div>

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
</style>
