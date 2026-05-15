<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const API = '/api/settings/smtp/'

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/)
  return m ? m[1] : ''
}
const h = () => ({ 'X-CSRFToken': getCsrf() })

const form = ref({
  host:          'smtp.gmail.com',
  port:          587,
  use_tls:       true,
  host_user:     '',
  host_password: '',
  from_email:    '',
})
const loading    = ref(true)
const saving     = ref(false)
const showPass   = ref(false)
const updated_at = ref(null)
const toast      = ref({ show: false, msg: '', type: 'success' })
const testEmail  = ref('')
const testing    = ref(false)

async function load() {
  loading.value = true
  try {
    const { data } = await axios.get(API)
    Object.assign(form.value, data)
    updated_at.value = data.updated_at
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await axios.patch(API, form.value, { headers: h() })
    showToast('SMTP settings saved.')
    await load()
  } catch {
    showToast('Save failed.', 'error')
  } finally {
    saving.value = false
  }
}

async function sendTest() {
  if (!testEmail.value) return
  testing.value = true
  try {
    const { data } = await axios.post('/api/settings/smtp/test/', { to_email: testEmail.value }, { headers: h() })
    showToast(data.message || 'Test email sent!')
  } catch (e) {
    showToast(e.response?.data?.error || 'Failed to send test email.', 'error')
  } finally {
    testing.value = false
  }
}

function showToast(msg, type = 'success') {
  toast.value = { show: true, msg, type }
  setTimeout(() => { toast.value.show = false }, 3000)
}

onMounted(load)
</script>

<template>
  <div class="h-full overflow-y-auto px-6 py-6">
    <div class="max-w-xl">

      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-xl font-bold text-gray-800 dark:text-white tracking-tight">SMTP Configuration</h1>
        <p class="text-sm text-gray-500 mt-0.5">Email settings used for sending passwords to users.</p>
      </div>

      <div v-if="loading" class="flex items-center gap-2 text-sm text-gray-400">
        <div class="i-carbon-circle-dash animate-spin text-lg"></div> Loading…
      </div>

      <form v-else @submit.prevent="save" class="flex flex-col gap-5">

        <!-- Host + Port -->
        <div class="grid grid-cols-2 gap-4">
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-bold text-gray-500 uppercase tracking-wide">SMTP Host</label>
            <input v-model="form.host" type="text" required placeholder="smtp.gmail.com"
              class="w-full px-4 py-2.5 rounded-xl bg-white dark:bg-[#1c1c1e] border border-gray-200 dark:border-[#3a3a3c] text-sm text-gray-800 dark:text-white outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 transition-all" />
          </div>
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-bold text-gray-500 uppercase tracking-wide">Port</label>
            <input v-model.number="form.port" type="number" required
              class="w-full px-4 py-2.5 rounded-xl bg-white dark:bg-[#1c1c1e] border border-gray-200 dark:border-[#3a3a3c] text-sm text-gray-800 dark:text-white outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 transition-all" />
          </div>
        </div>

        <!-- Use TLS -->
        <div class="flex items-center gap-3">
          <button type="button" @click="form.use_tls = !form.use_tls"
            class="w-10 h-6 rounded-full transition-colors relative"
            :class="form.use_tls ? 'bg-[#1D5F5E]' : 'bg-gray-200'">
            <span class="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all"
              :class="form.use_tls ? 'left-4' : 'left-0.5'"></span>
          </button>
          <label class="text-sm font-semibold text-gray-700 dark:text-[#aeaeb2]">Use TLS</label>
        </div>

        <!-- From / Host User -->
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-bold text-gray-500 uppercase tracking-wide">Sender Email (host_user)</label>
          <input v-model="form.host_user" type="email" required placeholder="adimanageworks@gmail.com"
            class="w-full px-4 py-2.5 rounded-xl bg-white dark:bg-[#1c1c1e] border border-gray-200 dark:border-[#3a3a3c] text-sm text-gray-800 dark:text-white outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 transition-all" />
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-bold text-gray-500 uppercase tracking-wide">From Email</label>
          <input v-model="form.from_email" type="email" required placeholder="adimanageworks@gmail.com"
            class="w-full px-4 py-2.5 rounded-xl bg-white dark:bg-[#1c1c1e] border border-gray-200 dark:border-[#3a3a3c] text-sm text-gray-800 dark:text-white outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 transition-all" />
        </div>

        <!-- App Password -->
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-bold text-gray-500 uppercase tracking-wide">App Password</label>
          <div class="relative">
            <input v-model="form.host_password" :type="showPass ? 'text' : 'password'"
              placeholder="Gmail App Password (16 chars)"
              class="w-full px-4 py-2.5 pr-11 rounded-xl bg-white dark:bg-[#1c1c1e] border border-gray-200 dark:border-[#3a3a3c] text-sm text-gray-800 dark:text-white outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 transition-all" />
            <button type="button" @click="showPass = !showPass"
              class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
              <div :class="showPass ? 'i-carbon-view-off' : 'i-carbon-view'" class="text-base"></div>
            </button>
          </div>
          <p class="text-xs text-gray-400">
            Generate at
            <a href="https://myaccount.google.com/apppasswords" target="_blank" class="underline hover:text-gray-600">myaccount.google.com/apppasswords</a>
            (requires 2-Step Verification).
          </p>
        </div>

        <!-- Last updated -->
        <p v-if="updated_at" class="text-xs text-gray-400">Last saved: {{ updated_at }}</p>

        <button type="submit" :disabled="saving"
          class="self-start flex items-center gap-2 px-6 py-2.5 rounded-xl bg-[#1D5F5E] hover:bg-[#174E4D] text-white text-sm font-semibold transition-colors disabled:opacity-50">
          <div v-if="saving" class="i-carbon-circle-dash animate-spin text-sm"></div>
          {{ saving ? 'Saving…' : 'Save Settings' }}
        </button>
      </form>

      <!-- Test Connection -->
      <div class="mt-8 pt-6" style="border-top: 1px solid var(--color-separator);">
        <h2 class="text-sm font-bold text-gray-700 dark:text-[#aeaeb2] mb-1">Test Connection</h2>
        <p class="text-xs text-gray-400 mb-4">Send a test email to verify SMTP settings are working.</p>
        <div class="flex gap-3 items-center">
          <input
            v-model="testEmail"
            type="email"
            placeholder="recipient@example.com"
            class="flex-1 px-4 py-2.5 rounded-xl bg-white dark:bg-[#1c1c1e] border border-gray-200 dark:border-[#3a3a3c] text-sm text-gray-800 dark:text-white outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 transition-all"
          />
          <button
            type="button"
            @click="sendTest"
            :disabled="testing || !testEmail"
            class="flex items-center gap-2 px-5 py-2.5 rounded-xl border border-[#1D5F5E] text-[#1D5F5E] text-sm font-semibold hover:bg-[#1D5F5E] hover:text-white transition-colors disabled:opacity-40 shrink-0"
          >
            <div v-if="testing" class="i-carbon-circle-dash animate-spin text-sm"></div>
            <div v-else class="i-carbon-send text-sm"></div>
            {{ testing ? 'Sending…' : 'Send Test Email' }}
          </button>
        </div>
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
