<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const API = '/api/site-register/telegram/'

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/)
  return m ? m[1] : ''
}
const h = () => ({ 'X-CSRFToken': getCsrf() })

const linked      = ref(false)
const otp         = ref(null)
const loading     = ref(true)
const generating  = ref(false)
const unlinking   = ref(false)
const copied      = ref(false)
const toast       = ref({ show: false, msg: '', type: 'success' })

async function load() {
  loading.value = true
  try {
    const { data } = await axios.get(`${API}otp/`)
    linked.value = data.linked
    otp.value    = data.otp || null
  } finally {
    loading.value = false
  }
}

async function generateOtp() {
  generating.value = true
  try {
    const { data } = await axios.post(`${API}otp/`, {}, { headers: h() })
    otp.value = data.otp
    showToast('New code generated.')
  } catch {
    showToast('Failed to generate code.', 'error')
  } finally {
    generating.value = false
  }
}

async function unlink() {
  if (!confirm('Unlink your Telegram account?')) return
  unlinking.value = true
  try {
    await axios.delete(`${API}unlink/`, { headers: h() })
    linked.value = false
    otp.value    = null
    showToast('Telegram account unlinked.')
  } catch {
    showToast('Failed to unlink.', 'error')
  } finally {
    unlinking.value = false
  }
}

async function copyOtp() {
  if (!otp.value) return
  await navigator.clipboard.writeText(`/start ${otp.value}`)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

function showToast(msg, type = 'success') {
  toast.value = { show: true, msg, type }
  setTimeout(() => { toast.value.show = false }, 3000)
}

onMounted(load)
</script>

<template>
  <div class="h-full overflow-y-auto px-6 py-6">
    <div class="max-w-lg">

      <div class="mb-8">
        <h1 class="text-xl font-bold text-gray-800 dark:text-white tracking-tight">Link Telegram Account</h1>
        <p class="text-sm text-gray-500 mt-0.5">Connect your Telegram to use the Site Register bot.</p>
      </div>

      <div v-if="loading" class="flex items-center gap-2 text-sm text-gray-400">
        <div class="i-carbon-circle-dash animate-spin text-lg"></div> Loading…
      </div>

      <template v-else>

        <!-- Already linked -->
        <div v-if="linked"
          class="bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] soft-shadow p-6 flex flex-col gap-4">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
              <div class="i-carbon-checkmark text-blue-600 text-lg"></div>
            </div>
            <div>
              <p class="text-sm font-bold text-gray-800 dark:text-white">Telegram linked</p>
              <p class="text-xs text-gray-400">Your account is connected to the Site Register bot.</p>
            </div>
          </div>
          <button @click="unlink" :disabled="unlinking"
            class="self-start flex items-center gap-2 px-4 py-2 rounded-xl border border-red-200 text-red-600 text-sm font-semibold hover:bg-red-50 transition-colors disabled:opacity-50">
            <div v-if="unlinking" class="i-carbon-circle-dash animate-spin text-sm"></div>
            <div v-else class="i-carbon-unlink text-sm"></div>
            {{ unlinking ? 'Unlinking…' : 'Unlink Telegram' }}
          </button>
        </div>

        <!-- Not linked -->
        <div v-else class="flex flex-col gap-5">

          <!-- Steps -->
          <div class="bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] soft-shadow divide-y divide-gray-100 dark:divide-[#3a3a3c]">
            <div class="px-5 py-4 flex gap-4 items-start">
              <span class="w-6 h-6 rounded-full bg-[#1D5F5E] text-white text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">1</span>
              <div>
                <p class="text-sm font-semibold text-gray-800 dark:text-white">Generate your link code</p>
                <p class="text-xs text-gray-400 mt-0.5">Click below to get a one-time code.</p>
              </div>
            </div>
            <div class="px-5 py-4 flex gap-4 items-start">
              <span class="w-6 h-6 rounded-full bg-[#1D5F5E] text-white text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">2</span>
              <div>
                <p class="text-sm font-semibold text-gray-800 dark:text-white">Open the bot on Telegram</p>
                <p class="text-xs text-gray-400 mt-0.5">Search for the ManageWorks bot and start a chat.</p>
              </div>
            </div>
            <div class="px-5 py-4 flex gap-4 items-start">
              <span class="w-6 h-6 rounded-full bg-[#1D5F5E] text-white text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">3</span>
              <div>
                <p class="text-sm font-semibold text-gray-800 dark:text-white">Send the command to the bot</p>
                <p class="text-xs text-gray-400 mt-0.5">Copy the command below and send it in the bot chat.</p>
              </div>
            </div>
          </div>

          <!-- OTP display -->
          <div v-if="otp" class="bg-white dark:bg-[#1c1c1e] rounded-2xl border border-[#1D5F5E]/30 soft-shadow p-5 flex flex-col gap-3">
            <p class="text-xs font-bold text-gray-400 uppercase tracking-widest">Your link command</p>
            <div class="flex items-center gap-3">
              <code class="flex-1 text-base font-mono font-bold text-[#1D5F5E] bg-[#1D5F5E]/5 px-4 py-3 rounded-xl select-all">
                /start {{ otp }}
              </code>
              <button @click="copyOtp"
                class="shrink-0 flex items-center gap-1.5 px-4 py-3 rounded-xl border border-gray-200 dark:border-[#3a3a3c] text-sm font-semibold text-gray-600 dark:text-[#aeaeb2] hover:bg-gray-50 dark:hover:bg-[#2c2c2e] transition-colors">
                <div :class="copied ? 'i-carbon-checkmark text-green-600' : 'i-carbon-copy'" class="text-sm"></div>
                {{ copied ? 'Copied!' : 'Copy' }}
              </button>
            </div>
            <p class="text-xs text-gray-400">This code is single-use. Generate a new one if it expires.</p>
          </div>

          <!-- Generate button -->
          <button @click="generateOtp" :disabled="generating"
            class="self-start flex items-center gap-2 px-6 py-2.5 rounded-xl bg-[#1D5F5E] hover:bg-[#174E4D] text-white text-sm font-semibold transition-colors disabled:opacity-50">
            <div v-if="generating" class="i-carbon-circle-dash animate-spin text-sm"></div>
            <div v-else class="i-carbon-link text-sm"></div>
            {{ otp ? 'Regenerate Code' : 'Generate Link Code' }}
          </button>

        </div>
      </template>
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
