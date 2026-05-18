<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const API = '/api/settings/telegram/'

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/)
  return m ? m[1] : ''
}
const h = () => ({ 'X-CSRFToken': getCsrf() })

const form = ref({
  bot_token:            '',
  upload_group_chat_id: '',
  is_active:            false,
})
const loading    = ref(true)
const saving     = ref(false)
const showToken  = ref(false)
const updated_at = ref(null)
const testing    = ref(false)
const toast      = ref({ show: false, msg: '', type: 'success' })

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
    showToast('Telegram settings saved.')
    await load()
  } catch {
    showToast('Save failed.', 'error')
  } finally {
    saving.value = false
  }
}

async function sendTest() {
  testing.value = true
  try {
    const { data } = await axios.post(API + 'test/', {}, { headers: h() })
    showToast(data.message || 'Test message sent.')
  } catch (e) {
    showToast(e.response?.data?.error || 'Test failed.', 'error')
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
        <h1 class="text-xl font-bold text-gray-800 dark:text-white tracking-tight">Telegram Bot Configuration</h1>
        <p class="text-sm text-gray-500 mt-0.5">Settings for the Site Register Telegram bot (long polling).</p>
      </div>

      <div v-if="loading" class="flex items-center gap-2 text-sm text-gray-400">
        <div class="i-carbon-circle-dash animate-spin text-lg"></div> Loading…
      </div>

      <form v-else @submit.prevent="save" class="flex flex-col gap-5">

        <!-- Bot Token -->
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-bold text-gray-500 uppercase tracking-wide">Bot Token</label>
          <div class="relative">
            <input v-model="form.bot_token" :type="showToken ? 'text' : 'password'"
              placeholder="1234567890:ABCdef..."
              class="w-full px-4 py-2.5 pr-11 rounded-xl bg-white dark:bg-[#1c1c1e] border border-gray-200 dark:border-[#3a3a3c] text-sm text-gray-800 dark:text-white outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 transition-all" />
            <button type="button" @click="showToken = !showToken"
              class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
              <div :class="showToken ? 'i-carbon-view-off' : 'i-carbon-view'" class="text-base"></div>
            </button>
          </div>
          <p class="text-xs text-gray-400">Get from <span class="font-mono">@BotFather</span> on Telegram.</p>
        </div>

        <!-- Upload Group Chat ID -->
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-bold text-gray-500 uppercase tracking-wide">Upload Archive Group Chat ID</label>
          <input v-model="form.upload_group_chat_id" type="text" placeholder="-1001234567890"
            class="w-full px-4 py-2.5 rounded-xl bg-white dark:bg-[#1c1c1e] border border-gray-200 dark:border-[#3a3a3c] text-sm text-gray-800 dark:text-white outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 transition-all" />
          <p class="text-xs text-gray-400">Negative number for groups/channels. Bot must be admin in this group.</p>
        </div>

        <!-- Active toggle -->
        <div class="flex items-center gap-3">
          <button type="button" @click="form.is_active = !form.is_active"
            class="w-10 h-6 rounded-full transition-colors relative"
            :class="form.is_active ? 'bg-[#1D5F5E]' : 'bg-gray-200'">
            <span class="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all"
              :class="form.is_active ? 'left-4' : 'left-0.5'"></span>
          </button>
          <label class="text-sm font-semibold text-gray-700 dark:text-[#aeaeb2]">Bot Active</label>
        </div>

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
        <p class="text-xs text-gray-400 mb-4">Sends a test message to the upload archive group.</p>
        <button type="button" @click="sendTest" :disabled="testing"
          class="flex items-center gap-2 px-5 py-2.5 rounded-xl border border-[#1D5F5E] text-[#1D5F5E] text-sm font-semibold hover:bg-[#1D5F5E] hover:text-white transition-colors disabled:opacity-40">
          <div v-if="testing" class="i-carbon-circle-dash animate-spin text-sm"></div>
          <div v-else class="i-carbon-send text-sm"></div>
          {{ testing ? 'Sending…' : 'Send Test Message' }}
        </button>
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
