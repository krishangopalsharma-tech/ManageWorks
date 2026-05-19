<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import axios from 'axios'
import QRCode from 'qrcode'

const BOT_USERNAME = 'ADISiteregister_bot'
const BOT_URL      = `https://t.me/${BOT_USERNAME}`

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/)
  return m ? m[1] : ''
}
const h = () => ({ 'X-CSRFToken': getCsrf() })

// ── Personal OTP link (top section) ──────────────────────────────────────────
const linked      = ref(false)
const otp         = ref(null)
const loading     = ref(true)
const generating  = ref(false)
const unlinking   = ref(false)
const copied      = ref(false)
const toast       = ref({ show: false, msg: '', type: 'success' })
const qrDataUrl   = ref(null)
const secondsLeft = ref(0)
let countdownTimer = null

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
    if (diff === 0) { clearInterval(countdownTimer); generateOtp() }
  }
  tick()
  countdownTimer = setInterval(tick, 1000)
}

const countdownDisplay = computed(() => {
  const s = secondsLeft.value
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
})

async function load() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/site-register/telegram/otp/')
    linked.value = data.linked
    otp.value    = data.otp || null
    if (otp.value) startCountdown(otp.value.expires_at)
    await buildQr()
  } finally {
    loading.value = false
  }
}

async function generateOtp() {
  generating.value = true
  try {
    const { data } = await axios.post('/api/site-register/telegram/otp/', {}, { headers: h() })
    otp.value = data.otp
    startCountdown(otp.value.expires_at)
  } catch {
    showToast('Failed to generate code.', 'error')
  } finally {
    generating.value = false
  }
}

async function unlink() {
  if (!confirm('Unlink your personal Telegram account?')) return
  unlinking.value = true
  try {
    await axios.delete('/api/site-register/telegram/unlink/', { headers: h() })
    linked.value = false
    otp.value    = null
    clearInterval(countdownTimer)
    showToast('Telegram account unlinked.')
  } catch {
    showToast('Failed to unlink.', 'error')
  } finally {
    unlinking.value = false
  }
}

async function copyCode() {
  if (!otp.value) return
  await navigator.clipboard.writeText(otp.value.code)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

// ── Rly Official Delegate list ─────────────────────────────────────────────
const delegates         = ref([])
const delegatesLoading  = ref(false)
const delegateSearch    = ref('')
const editingId         = ref(null)
const editForm          = ref({ name: '', designation: '', mobile: '' })
const saving            = ref(false)
const unlinkingId       = ref(null)

// invite
const invite            = ref(null)   // { code, expires_at }
const inviteSecondsLeft = ref(0)
const generatingInvite  = ref(false)
const inviteCopied      = ref(false)
const inviteQrUrl       = ref(null)
let inviteCountdown = null
let invitePollTimer = null

const filteredDelegates = computed(() => {
  const q = delegateSearch.value.toLowerCase()
  if (!q) return delegates.value
  return delegates.value.filter(u =>
    (u.name || '').toLowerCase().includes(q) ||
    (u.hrms_id || '').toLowerCase().includes(q) ||
    (u.designation || '').toLowerCase().includes(q)
  )
})

const inviteCountdownDisplay = computed(() => {
  const s = inviteSecondsLeft.value
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
})

async function loadDelegates() {
  delegatesLoading.value = true
  try {
    const { data } = await axios.get('/api/site-register/rly-linked-users/')
    delegates.value = data
  } catch { /* ignore */ } finally {
    delegatesLoading.value = false
  }
}

function startEdit(u) {
  editingId.value = u.id
  editForm.value  = { name: u.name || '', designation: u.designation || '', mobile: u.mobile || '' }
}
function cancelEdit() { editingId.value = null }

async function saveEdit(u) {
  saving.value = true
  try {
    const { data } = await axios.patch(
      `/api/site-register/rly-linked-users/${u.id}/`,
      editForm.value, { headers: h() }
    )
    const idx = delegates.value.findIndex(x => x.id === u.id)
    if (idx !== -1) delegates.value[idx] = data
    editingId.value = null
    showToast('Saved.')
  } catch {
    showToast('Save failed.', 'error')
  } finally {
    saving.value = false
  }
}

async function unlinkDelegate(u) {
  if (!confirm(`Unlink ${u.name || u.hrms_id} from Telegram?`)) return
  unlinkingId.value = u.id
  try {
    await axios.delete(`/api/site-register/rly-linked-users/${u.id}/`, { headers: h() })
    delegates.value = delegates.value.filter(x => x.id !== u.id)
    editingId.value = null
    showToast('Unlinked.')
  } catch {
    showToast('Unlink failed.', 'error')
  } finally {
    unlinkingId.value = null
  }
}

// ── Invite code flow ──────────────────────────────────────────────────────────
function startInviteCountdown(expiresAt) {
  clearInterval(inviteCountdown)
  const tick = () => {
    const diff = Math.max(0, Math.round((new Date(expiresAt) - Date.now()) / 1000))
    inviteSecondsLeft.value = diff
    if (diff === 0) {
      clearInterval(inviteCountdown)
      clearInterval(invitePollTimer)
      invite.value     = null
      inviteQrUrl.value = null
    }
  }
  tick()
  inviteCountdown = setInterval(tick, 1000)
}

function startInvitePoll(code) {
  clearInterval(invitePollTimer)
  invitePollTimer = setInterval(async () => {
    try {
      const { data } = await axios.get(`/api/site-register/rly-invite/${code}/`)
      if (data.used) {
        clearInterval(invitePollTimer)
        clearInterval(inviteCountdown)
        invite.value      = null
        inviteQrUrl.value = null
        showToast(`✅ ${data.linked_user?.name || 'User'} linked!`)
        loadDelegates()
      }
    } catch { /* ignore */ }
  }, 3000)
}

async function generateInvite() {
  generatingInvite.value = true
  try {
    const { data } = await axios.post('/api/site-register/rly-invite/', {}, { headers: h() })
    invite.value = data
    inviteQrUrl.value = await QRCode.toDataURL(BOT_URL, {
      width: 160, margin: 2,
      color: { dark: '#1D5F5E', light: '#FFFFFF' },
    })
    startInviteCountdown(data.expires_at)
    startInvitePoll(data.code)
  } catch {
    showToast('Failed to generate invite.', 'error')
  } finally {
    generatingInvite.value = false
  }
}

async function copyInvite() {
  if (!invite.value) return
  await navigator.clipboard.writeText(invite.value.code)
  inviteCopied.value = true
  setTimeout(() => { inviteCopied.value = false }, 2000)
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, type = 'success') {
  toast.value = { show: true, msg, type }
  setTimeout(() => { toast.value.show = false }, 3500)
}

onMounted(() => { load(); loadDelegates() })
onUnmounted(() => {
  clearInterval(countdownTimer)
  clearInterval(inviteCountdown)
  clearInterval(invitePollTimer)
})
</script>

<template>
  <div class="h-full overflow-y-auto px-6 py-6">

    <div class="mb-6">
      <h1 class="text-xl font-bold text-gray-800 dark:text-white tracking-tight">Link Rly Official Telegram</h1>
      <p class="text-sm text-gray-500 mt-0.5">Link your own account and manage your jurisdiction's Railway Official delegates.</p>
    </div>

    <!-- ── PERSONAL LINK (top row) ────────────────────────────────────────── -->
    <div v-if="loading" class="flex items-center gap-2 text-sm text-gray-400 mb-6">
      <div class="i-carbon-circle-dash animate-spin text-lg"></div> Loading…
    </div>

    <template v-else>
      <div class="flex gap-4 mb-6 items-start">

        <!-- Steps guide -->
        <div class="flex-1 bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] shadow-sm divide-y divide-gray-100 dark:divide-[#3a3a3c]">
          <div class="px-4 py-3 flex gap-3 items-start">
            <span class="w-5 h-5 rounded-full bg-[#1D5F5E] text-white text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">1</span>
            <div>
              <p class="text-sm font-semibold text-gray-800 dark:text-white">Generate your 6-digit code</p>
              <p class="text-xs text-gray-400 mt-0.5">Click "Generate" — code expires in 1 minute.</p>
            </div>
          </div>
          <div class="px-4 py-3 flex gap-3 items-start">
            <span class="w-5 h-5 rounded-full bg-[#1D5F5E] text-white text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">2</span>
            <div>
              <p class="text-sm font-semibold text-gray-800 dark:text-white">Open the bot</p>
              <p class="text-xs text-gray-400 mt-0.5">Scan QR or search <span class="font-mono text-[#1D5F5E]">@ADISiteregister_bot</span>.</p>
            </div>
          </div>
          <div class="px-4 py-3 flex gap-3 items-start">
            <span class="w-5 h-5 rounded-full bg-[#1D5F5E] text-white text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">3</span>
            <div>
              <p class="text-sm font-semibold text-gray-800 dark:text-white">Type the 6-digit code</p>
              <p class="text-xs text-gray-400 mt-0.5">Send the 6 digits in chat — bot will ask your HRMS ID.</p>
            </div>
          </div>
        </div>

        <!-- QR + OTP panel -->
        <div class="w-64 shrink-0 bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] shadow-sm p-4">
          <p class="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">Your Personal Link</p>

          <div v-if="linked" class="flex flex-col items-center gap-3">
            <div class="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
              <div class="i-carbon-checkmark text-blue-600 text-lg"></div>
            </div>
            <p class="text-sm font-bold text-gray-800 dark:text-white">Telegram Linked</p>
            <button @click="unlink" :disabled="unlinking"
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-red-200 text-red-600 text-xs font-semibold hover:bg-red-50 transition-colors disabled:opacity-50">
              <div v-if="unlinking" class="i-carbon-circle-dash animate-spin text-xs"></div>
              <div v-else class="i-carbon-unlink text-xs"></div>
              {{ unlinking ? 'Unlinking…' : 'Unlink' }}
            </button>
          </div>

          <div v-else class="flex flex-col items-center gap-3">
            <div class="p-1.5 bg-white rounded-xl shadow-sm border border-gray-100">
              <img v-if="qrDataUrl" :src="qrDataUrl" alt="Scan to open bot" class="w-32 h-32" />
            </div>

            <div v-if="otp" class="w-full">
              <div class="flex items-center gap-2 px-3 py-2.5 bg-[#1D5F5E]/5 rounded-xl justify-center">
                <code class="text-2xl font-mono font-bold text-[#1D5F5E] tracking-widest select-all">{{ otp.code }}</code>
                <button @click="copyCode"
                  class="shrink-0 p-1 rounded-lg border border-gray-200 dark:border-[#3a3a3c] text-gray-500 hover:bg-gray-100 transition-colors">
                  <div :class="copied ? 'i-carbon-checkmark text-green-600' : 'i-carbon-copy'" class="text-xs"></div>
                </button>
              </div>
              <div class="flex items-center justify-center gap-1 mt-1">
                <div class="i-carbon-timer text-xs" :class="secondsLeft <= 15 ? 'text-red-500' : 'text-gray-400'"></div>
                <span class="text-xs font-mono font-semibold" :class="secondsLeft <= 15 ? 'text-red-500' : 'text-gray-500'">
                  {{ countdownDisplay }}
                </span>
              </div>
            </div>

            <button @click="generateOtp" :disabled="generating"
              class="flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-[#1D5F5E] hover:bg-[#174E4D] text-white text-xs font-semibold transition-colors disabled:opacity-50">
              <div v-if="generating" class="i-carbon-circle-dash animate-spin text-xs"></div>
              <div v-else class="i-carbon-renew text-xs"></div>
              {{ otp ? 'Refresh Code' : 'Generate Link Code' }}
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- ── DELEGATE MANAGEMENT ────────────────────────────────────────────── -->
    <div class="bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] shadow-sm overflow-hidden">

      <!-- Header row -->
      <div class="px-5 py-4 border-b border-gray-100 dark:border-[#3a3a3c] flex items-center gap-3">
        <div class="flex-1">
          <h2 class="text-sm font-bold text-gray-700 dark:text-gray-200">Linked Telegram Users</h2>
          <p class="text-xs text-gray-400 mt-0.5">Railway officials in your jurisdiction linked via invite code</p>
        </div>
        <input v-model="delegateSearch" type="text" placeholder="Search…"
          class="text-xs px-3 py-1.5 rounded-lg border border-gray-200 dark:border-[#3a3a3c] bg-gray-50 dark:bg-[#2c2c2e] text-gray-700 dark:text-gray-200 placeholder-gray-400 outline-none focus:border-[#1D5F5E] w-40" />
        <button @click="loadDelegates" :disabled="delegatesLoading"
          class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-[#2c2c2e] transition-colors" title="Refresh">
          <div :class="delegatesLoading ? 'animate-spin' : ''" class="i-carbon-renew text-sm text-gray-400"></div>
        </button>
        <!-- Add delegate button -->
        <button @click="generateInvite" :disabled="generatingInvite || !!invite"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1D5F5E] hover:bg-[#174E4D] text-white text-xs font-semibold transition-colors disabled:opacity-50">
          <div v-if="generatingInvite" class="i-carbon-circle-dash animate-spin text-xs"></div>
          <div v-else class="i-carbon-add text-xs"></div>
          Add Official
        </button>
      </div>

      <!-- Invite code panel -->
      <transition name="slide">
        <div v-if="invite"
          class="px-5 py-4 bg-[#1D5F5E]/5 border-b border-[#1D5F5E]/20 flex items-center gap-6">
          <div class="p-1.5 bg-white rounded-xl shadow-sm border border-gray-100 shrink-0">
            <img v-if="inviteQrUrl" :src="inviteQrUrl" alt="Scan to open bot" class="w-24 h-24" />
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-xs font-bold text-[#1D5F5E] uppercase tracking-wider mb-2">Invite Code — Share with the official</p>
            <div class="flex items-center gap-2 mb-2">
              <code class="text-3xl font-mono font-bold text-[#1D5F5E] tracking-widest select-all">{{ invite.code }}</code>
              <button @click="copyInvite"
                class="p-1.5 rounded-lg border border-[#1D5F5E]/30 text-[#1D5F5E] hover:bg-[#1D5F5E]/10 transition-colors">
                <div :class="inviteCopied ? 'i-carbon-checkmark' : 'i-carbon-copy'" class="text-xs"></div>
              </button>
            </div>
            <div class="flex items-center gap-1.5">
              <div class="i-carbon-timer text-xs" :class="inviteSecondsLeft <= 30 ? 'text-red-500' : 'text-[#1D5F5E]'"></div>
              <span class="text-xs font-mono font-semibold" :class="inviteSecondsLeft <= 30 ? 'text-red-500' : 'text-gray-600 dark:text-gray-300'">
                {{ inviteCountdownDisplay }} remaining
              </span>
              <span class="text-xs text-gray-400 ml-1">· Single-use · Bot asks HRMS ID</span>
            </div>
          </div>
          <div class="flex flex-col items-center gap-1 shrink-0">
            <div class="i-carbon-circle-dash animate-spin text-[#1D5F5E] text-lg"></div>
            <span class="text-xs text-gray-400">Waiting…</span>
          </div>
        </div>
      </transition>

      <!-- Table -->
      <div v-if="delegatesLoading && !delegates.length" class="p-6 text-xs text-gray-400 flex items-center gap-2">
        <div class="i-carbon-circle-dash animate-spin"></div> Loading…
      </div>
      <div v-else-if="!filteredDelegates.length" class="p-6 text-xs text-gray-400 text-center">
        No Railway Officials linked. Click "Add Official" to generate an invite.
      </div>

      <table v-else class="w-full text-xs">
        <thead>
          <tr class="border-b border-gray-100 dark:border-[#2c2c2e]">
            <th class="px-5 py-2.5 text-left font-semibold text-gray-400 uppercase tracking-wider">Name</th>
            <th class="px-5 py-2.5 text-left font-semibold text-gray-400 uppercase tracking-wider">HRMS ID</th>
            <th class="px-5 py-2.5 text-left font-semibold text-gray-400 uppercase tracking-wider">Designation</th>
            <th class="px-5 py-2.5 text-left font-semibold text-gray-400 uppercase tracking-wider">Mobile</th>
            <th class="px-5 py-2.5 text-left font-semibold text-gray-400 uppercase tracking-wider">Telegram ID</th>
            <th class="px-5 py-2.5 text-right font-semibold text-gray-400 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="u in filteredDelegates" :key="u.id">
            <!-- View row -->
            <tr v-if="editingId !== u.id"
              class="border-b border-gray-50 dark:border-[#2c2c2e] hover:bg-gray-50 dark:hover:bg-[#2c2c2e] transition-colors">
              <td class="px-5 py-3">
                <div class="flex items-center gap-2">
                  <span class="font-semibold text-gray-800 dark:text-white">{{ u.name }}</span>
                  <span v-if="u.in_system"
                    class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                    In System
                  </span>
                </div>
              </td>
              <td class="px-5 py-3 font-mono text-gray-600 dark:text-gray-300">{{ u.hrms_id || '—' }}</td>
              <td class="px-5 py-3 text-gray-500">{{ u.designation || '—' }}</td>
              <td class="px-5 py-3 text-gray-500">{{ u.mobile || '—' }}</td>
              <td class="px-5 py-3 font-mono text-gray-400">{{ u.telegram_user_id }}</td>
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
                <input v-model="editForm.name"
                  class="w-full text-xs px-2 py-1 rounded-lg border border-[#1D5F5E]/30 bg-white dark:bg-[#2c2c2e] outline-none focus:border-[#1D5F5E]"
                  placeholder="Name" />
              </td>
              <td class="px-5 py-3 font-mono text-gray-400">{{ u.hrms_id || '—' }}</td>
              <td class="px-5 py-3">
                <input v-model="editForm.designation"
                  class="w-full text-xs px-2 py-1 rounded-lg border border-[#1D5F5E]/30 bg-white dark:bg-[#2c2c2e] outline-none focus:border-[#1D5F5E]"
                  placeholder="Designation" />
              </td>
              <td class="px-5 py-3">
                <input v-model="editForm.mobile"
                  class="w-full text-xs px-2 py-1 rounded-lg border border-[#1D5F5E]/30 bg-white dark:bg-[#2c2c2e] outline-none focus:border-[#1D5F5E]"
                  placeholder="Mobile" />
              </td>
              <td class="px-5 py-3 font-mono text-gray-400">{{ u.telegram_user_id }}</td>
              <td class="px-5 py-3 text-right">
                <div class="flex items-center justify-end gap-1.5">
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
                  <button @click="unlinkDelegate(u)" :disabled="unlinkingId === u.id"
                    class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-red-200 text-red-600 text-xs hover:bg-red-50 transition-colors disabled:opacity-50">
                    <div v-if="unlinkingId === u.id" class="i-carbon-circle-dash animate-spin text-xs"></div>
                    <div v-else class="i-carbon-unlink text-xs"></div>
                    Unlink
                  </button>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>

      <div class="px-5 py-3 border-t border-gray-100 dark:border-[#3a3a3c]">
        <p class="text-xs text-gray-400">
          {{ delegates.length }} user{{ delegates.length !== 1 ? 's' : '' }} linked in your jurisdiction ·
          Telegram ID is not editable
        </p>
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
.slide-enter-active, .slide-leave-active { transition: all 0.25s ease; }
.slide-enter-from, .slide-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
