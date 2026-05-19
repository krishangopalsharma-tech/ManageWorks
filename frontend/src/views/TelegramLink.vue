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

// ── Invite code (single flow for all users) ───────────────────────────────────
const invite            = ref(null)   // { code, expires_at }
const inviteSecondsLeft = ref(0)
const generatingInvite  = ref(false)
const inviteCopied      = ref(false)
const qrDataUrl         = ref(null)
const toast             = ref({ show: false, msg: '', type: 'success' })
let inviteCountdown = null
let invitePollTimer = null

const inviteCountdownDisplay = computed(() => {
  const s = inviteSecondsLeft.value
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
})

async function buildQr() {
  qrDataUrl.value = await QRCode.toDataURL(BOT_URL, {
    width: 180, margin: 2,
    color: { dark: '#1D5F5E', light: '#FFFFFF' },
  })
}

function startInviteCountdown(expiresAt) {
  clearInterval(inviteCountdown)
  const tick = () => {
    const diff = Math.max(0, Math.round((new Date(expiresAt) - Date.now()) / 1000))
    inviteSecondsLeft.value = diff
    if (diff === 0) {
      clearInterval(inviteCountdown)
      clearInterval(invitePollTimer)
      invite.value = null
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
        invite.value = null
        showToast(`✅ ${data.linked_user?.name || 'User'} linked!`)
        loadDelegates()
        generateInvite()   // auto-generate new code
      }
    } catch { /* ignore */ }
  }, 3000)
}

async function generateInvite() {
  generatingInvite.value = true
  try {
    const { data } = await axios.post('/api/site-register/rly-invite/', {}, { headers: h() })
    invite.value = data
    startInviteCountdown(data.expires_at)
    startInvitePoll(data.code)
  } catch {
    showToast('Failed to generate code.', 'error')
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

// ── Linked users list ─────────────────────────────────────────────────────────
const selfEntry        = ref(null)
const delegates        = ref([])
const delegatesLoading = ref(false)
const delegateSearch   = ref('')
const editingId        = ref(null)
const editForm         = ref({ name: '', designation: '', mobile: '' })
const saving           = ref(false)
const unlinkingId      = ref(null)

const allLinked = computed(() => {
  const list = selfEntry.value ? [selfEntry.value] : []
  return list.concat(delegates.value)
})

const filteredDelegates = computed(() => {
  const q = delegateSearch.value.toLowerCase()
  if (!q) return allLinked.value
  return allLinked.value.filter(u =>
    (u.name || '').toLowerCase().includes(q) ||
    (u.hrms_id || '').toLowerCase().includes(q) ||
    (u.designation || '').toLowerCase().includes(q)
  )
})

async function loadDelegates() {
  delegatesLoading.value = true
  try {
    const [otpRes, dlgRes] = await Promise.all([
      axios.get('/api/site-register/telegram/otp/'),
      axios.get('/api/site-register/rly-linked-users/'),
    ])
    selfEntry.value = otpRes.data.link_info || null
    delegates.value = dlgRes.data
  } catch { /* ignore */ } finally {
    delegatesLoading.value = false
  }
}

function startEdit(u) {
  editingId.value = u.is_self ? 'self' : u.id
  editForm.value  = { name: u.name || '', designation: u.designation || '', mobile: u.mobile || '' }
}
function cancelEdit() { editingId.value = null }

async function saveSelf() {
  saving.value = true
  try {
    await axios.patch('/api/site-register/telegram/otp/', { mobile: editForm.value.mobile }, { headers: h() })
    selfEntry.value = { ...selfEntry.value, mobile: editForm.value.mobile }
    editingId.value = null
    showToast('Saved.')
  } catch {
    showToast('Save failed.', 'error')
  } finally {
    saving.value = false
  }
}

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

async function unlinkUser(u) {
  const label = u.name || u.hrms_id || 'this user'
  if (!confirm(`Unlink ${label} from Telegram?`)) return

  if (u.is_self) {
    unlinkingId.value = 'self'
    try {
      await axios.delete('/api/site-register/telegram/unlink/', { headers: h() })
      selfEntry.value = null
      editingId.value = null
      showToast('Your Telegram account unlinked.')
    } catch {
      showToast('Unlink failed.', 'error')
    } finally {
      unlinkingId.value = null
    }
    return
  }

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

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, type = 'success') {
  toast.value = { show: true, msg, type }
  setTimeout(() => { toast.value.show = false }, 3500)
}

onMounted(async () => {
  await Promise.all([buildQr(), loadDelegates()])
  generateInvite()
})
onUnmounted(() => {
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

    <!-- ── TOP: Steps + single QR/code panel ─────────────────────────────── -->
    <div class="flex gap-4 mb-6 items-start">

      <!-- Steps guide -->
      <div class="flex-1 bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] shadow-sm divide-y divide-gray-100 dark:divide-[#3a3a3c]">
        <div class="px-4 py-3 flex gap-3 items-start">
          <span class="w-5 h-5 rounded-full bg-[#1D5F5E] text-white text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">1</span>
          <div>
            <p class="text-sm font-semibold text-gray-800 dark:text-white">Get the 6-digit code</p>
            <p class="text-xs text-gray-400 mt-0.5">A code is shown on the right — expires in 5 minutes, auto-refreshes.</p>
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
            <p class="text-xs text-gray-400 mt-0.5">Bot will ask your HRMS ID to confirm identity and link your account.</p>
          </div>
        </div>
        <div class="px-4 py-3 flex gap-3 items-start">
          <span class="w-5 h-5 rounded-full bg-gray-300 dark:bg-gray-600 text-white text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">4</span>
          <div>
            <p class="text-sm font-semibold text-gray-500">Appears in the list below</p>
            <p class="text-xs text-gray-400 mt-0.5">Share this same code with any JE / Technician in your jurisdiction.</p>
          </div>
        </div>
      </div>

      <!-- Single QR + code panel -->
      <div class="w-64 shrink-0 bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] shadow-sm p-4">
        <p class="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">Link Code</p>

        <div class="flex flex-col items-center gap-3">
          <!-- QR always shown -->
          <div class="p-1.5 bg-white rounded-xl shadow-sm border border-gray-100">
            <img v-if="qrDataUrl" :src="qrDataUrl" alt="Scan to open bot" class="w-32 h-32" />
          </div>

          <!-- Active invite code -->
          <div v-if="invite" class="w-full">
            <div class="flex items-center gap-2 px-3 py-2.5 bg-[#1D5F5E]/5 rounded-xl justify-center">
              <code class="text-2xl font-mono font-bold text-[#1D5F5E] tracking-widest select-all">{{ invite.code }}</code>
              <button @click="copyInvite"
                class="shrink-0 p-1 rounded-lg border border-gray-200 dark:border-[#3a3a3c] text-gray-500 hover:bg-gray-100 transition-colors">
                <div :class="inviteCopied ? 'i-carbon-checkmark text-green-600' : 'i-carbon-copy'" class="text-xs"></div>
              </button>
            </div>
            <div class="flex items-center justify-center gap-1 mt-1">
              <div class="i-carbon-timer text-xs" :class="inviteSecondsLeft <= 30 ? 'text-red-500' : 'text-gray-400'"></div>
              <span class="text-xs font-mono font-semibold" :class="inviteSecondsLeft <= 30 ? 'text-red-500' : 'text-gray-500'">
                {{ inviteCountdownDisplay }}
              </span>
            </div>
          </div>

          <!-- Generating state -->
          <div v-else-if="generatingInvite" class="flex items-center gap-2 text-xs text-gray-400">
            <div class="i-carbon-circle-dash animate-spin"></div> Generating…
          </div>

          <!-- Expired — manual regenerate -->
          <button v-else @click="generateInvite"
            class="flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-[#1D5F5E] hover:bg-[#174E4D] text-white text-xs font-semibold transition-colors">
            <div class="i-carbon-renew text-xs"></div>
            Generate Code
          </button>

          <p class="text-[10px] text-gray-400 text-center leading-relaxed">
            Single-use · 5 min · share with anyone in your jurisdiction
          </p>
        </div>
      </div>
    </div>

    <!-- ── LINKED USERS TABLE ─────────────────────────────────────────────── -->
    <div class="bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] shadow-sm overflow-hidden">

      <div class="px-5 py-4 border-b border-gray-100 dark:border-[#3a3a3c] flex items-center gap-3">
        <div class="flex-1">
          <h2 class="text-sm font-bold text-gray-700 dark:text-gray-200">Linked Telegram Users</h2>
          <p class="text-xs text-gray-400 mt-0.5">All Railway Officials linked in your jurisdiction</p>
        </div>
        <input v-model="delegateSearch" type="text" placeholder="Search…"
          class="text-xs px-3 py-1.5 rounded-lg border border-gray-200 dark:border-[#3a3a3c] bg-gray-50 dark:bg-[#2c2c2e] text-gray-700 dark:text-gray-200 placeholder-gray-400 outline-none focus:border-[#1D5F5E] w-40" />
        <button @click="loadDelegates" :disabled="delegatesLoading"
          class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-[#2c2c2e] transition-colors" title="Refresh">
          <div :class="delegatesLoading ? 'animate-spin' : ''" class="i-carbon-renew text-sm text-gray-400"></div>
        </button>
      </div>

      <!-- Waiting banner while invite is active -->
      <transition name="slide">
        <div v-if="invite"
          class="px-5 py-3 bg-[#1D5F5E]/5 border-b border-[#1D5F5E]/20 flex items-center gap-3">
          <div class="i-carbon-circle-dash animate-spin text-[#1D5F5E] text-sm shrink-0"></div>
          <p class="text-xs text-gray-600 dark:text-gray-300">
            Waiting for someone to type code <code class="font-mono font-bold text-[#1D5F5E]">{{ invite.code }}</code> in the bot…
          </p>
        </div>
      </transition>

      <div v-if="delegatesLoading && !allLinked.length" class="p-6 text-xs text-gray-400 flex items-center gap-2">
        <div class="i-carbon-circle-dash animate-spin"></div> Loading…
      </div>
      <div v-else-if="!filteredDelegates.length" class="p-6 text-xs text-gray-400 text-center">
        No Railway Officials linked. Share the code above to link your own or others' accounts.
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
          <template v-for="u in filteredDelegates" :key="u.is_self ? 'self' : u.id">

            <!-- View row -->
            <tr v-if="editingId !== (u.is_self ? 'self' : u.id)"
              class="border-b border-gray-50 dark:border-[#2c2c2e] hover:bg-gray-50 dark:hover:bg-[#2c2c2e] transition-colors">
              <td class="px-5 py-3">
                <div class="flex items-center gap-2">
                  <span class="font-semibold text-gray-800 dark:text-white">{{ u.name }}</span>
                  <span v-if="u.is_self"
                    class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-[#1D5F5E]/10 text-[#1D5F5E]">You</span>
                  <span v-else-if="u.in_system"
                    class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">In System</span>
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

            <!-- Edit row (self) -->
            <tr v-else-if="u.is_self" class="border-b border-[#1D5F5E]/20 bg-[#1D5F5E]/5">
              <td class="px-5 py-3">
                <div class="flex items-center gap-2">
                  <span class="font-semibold text-gray-700 dark:text-gray-200">{{ u.name }}</span>
                  <span class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-[#1D5F5E]/10 text-[#1D5F5E]">You</span>
                </div>
              </td>
              <td class="px-5 py-3 font-mono text-gray-400">{{ u.hrms_id || '—' }}</td>
              <td class="px-5 py-3 text-gray-400 text-xs">{{ u.designation || '—' }}</td>
              <td class="px-5 py-3">
                <input v-model="editForm.mobile"
                  class="w-full text-xs px-2 py-1 rounded-lg border border-[#1D5F5E]/30 bg-white dark:bg-[#2c2c2e] outline-none focus:border-[#1D5F5E]"
                  placeholder="Mobile" />
              </td>
              <td class="px-5 py-3 font-mono text-gray-400">{{ u.telegram_user_id }}</td>
              <td class="px-5 py-3 text-right">
                <div class="flex items-center justify-end gap-1.5">
                  <button @click="saveSelf" :disabled="saving"
                    class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#1D5F5E] text-white text-xs font-semibold hover:bg-[#174E4D] disabled:opacity-50 transition-colors">
                    <div v-if="saving" class="i-carbon-circle-dash animate-spin text-xs"></div>
                    <div v-else class="i-carbon-checkmark text-xs"></div>
                    Save
                  </button>
                  <button @click="cancelEdit"
                    class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-gray-200 dark:border-[#3a3a3c] text-gray-500 text-xs hover:bg-gray-100 dark:hover:bg-[#3a3a3c] transition-colors">
                    Cancel
                  </button>
                  <button @click="unlinkUser(u)" :disabled="unlinkingId === 'self'"
                    class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-red-200 text-red-600 text-xs hover:bg-red-50 transition-colors disabled:opacity-50">
                    <div v-if="unlinkingId === 'self'" class="i-carbon-circle-dash animate-spin text-xs"></div>
                    <div v-else class="i-carbon-unlink text-xs"></div>
                    Unlink
                  </button>
                </div>
              </td>
            </tr>

            <!-- Edit row (delegate) -->
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
                  <button @click="unlinkUser(u)" :disabled="unlinkingId === u.id"
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
          {{ allLinked.length }} user{{ allLinked.length !== 1 ? 's' : '' }} linked in your jurisdiction ·
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
