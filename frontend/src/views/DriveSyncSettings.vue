<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/)
  return m ? m[1] : ''
}
const h = () => ({ 'X-CSRFToken': getCsrf() })

const loading   = ref(true)
const saving    = ref(false)
const showKey   = ref(false)
const apiKey    = ref('')
const hasApiKey = ref(false)
const isActive  = ref(true)
const links     = ref([])
const log       = ref([])
const toast     = ref({ show: false, msg: '', type: 'success' })

function showToast(msg, type = 'success') {
  toast.value = { show: true, msg, type }
  setTimeout(() => { toast.value.show = false }, 3000)
}

async function load() {
  loading.value = true
  try {
    const [cfgRes, overviewRes] = await Promise.all([
      axios.get('/api/drive-sync/admin/config/'),
      axios.get('/api/drive-sync/admin/overview/'),
    ])
    hasApiKey.value = cfgRes.data.has_api_key
    isActive.value  = cfgRes.data.is_active
    links.value     = overviewRes.data.links
    log.value       = overviewRes.data.log
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    const payload = { is_active: isActive.value }
    if (apiKey.value.trim()) payload.api_key = apiKey.value.trim()
    const { data } = await axios.patch('/api/drive-sync/admin/config/', payload, { headers: h() })
    hasApiKey.value = data.has_api_key
    isActive.value  = data.is_active
    apiKey.value    = ''
    showToast('Drive Sync settings saved.')
  } catch (e) {
    showToast(e.response?.data?.error || 'Save failed.', 'error')
  } finally {
    saving.value = false
  }
}

const statusStyle = {
  needs_review: 'bg-amber-50 text-amber-700 border-amber-200',
  error:        'bg-red-50 text-red-700 border-red-200',
}

onMounted(load)
</script>

<template>
  <div class="h-full overflow-y-auto px-6 py-6">
    <div class="max-w-4xl">

      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-xl font-bold text-gray-800 dark:text-white tracking-tight">Drive Sync</h1>
        <p class="text-sm text-gray-500 mt-0.5">Auto-import bills &amp; receipt notes from consignees' own Google Drive folders.</p>
      </div>

      <div v-if="loading" class="flex items-center gap-2 text-sm text-gray-400">
        <div class="i-carbon-circle-dash animate-spin text-lg"></div> Loading…
      </div>

      <template v-else>

        <!-- API key config -->
        <form @submit.prevent="saveConfig" class="bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] shadow-sm p-5 flex flex-col gap-4 mb-8">
          <div>
            <label class="text-xs font-bold text-gray-500 uppercase tracking-wide">Google Drive API Key</label>
            <div class="relative mt-1.5">
              <input v-model="apiKey" :type="showKey ? 'text' : 'password'"
                :placeholder="hasApiKey ? 'Key already set — leave blank to keep it' : 'Paste your Drive API key'"
                class="w-full px-4 py-2.5 pr-11 rounded-xl bg-white dark:bg-[#2c2c2e] border border-gray-200 dark:border-[#3a3a3c] text-sm text-gray-800 dark:text-white outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 transition-all" />
              <button type="button" @click="showKey = !showKey"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                <div :class="showKey ? 'i-carbon-view-off' : 'i-carbon-view'" class="text-base"></div>
              </button>
            </div>
            <p class="text-xs text-gray-400 mt-1.5">
              <span v-if="hasApiKey" class="text-green-600 font-semibold">✓ Key configured.</span>
              <span v-else class="text-amber-600 font-semibold">No key set — sync will not run.</span>
              From Google Cloud Console → APIs &amp; Services → Credentials, restricted to Drive API only.
            </p>
          </div>

          <div class="flex items-center gap-3">
            <button type="button" @click="isActive = !isActive"
              class="w-10 h-6 rounded-full transition-colors relative"
              :class="isActive ? 'bg-[#1D5F5E]' : 'bg-gray-200'">
              <span class="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all"
                :class="isActive ? 'left-4' : 'left-0.5'"></span>
            </button>
            <label class="text-sm font-semibold text-gray-700 dark:text-[#aeaeb2]">Sync enabled</label>
          </div>

          <button type="submit" :disabled="saving"
            class="self-start flex items-center gap-2 px-6 py-2.5 rounded-xl bg-[#1D5F5E] hover:bg-[#174E4D] text-white text-sm font-semibold transition-colors disabled:opacity-50">
            <div v-if="saving" class="i-carbon-circle-dash animate-spin text-sm"></div>
            {{ saving ? 'Saving…' : 'Save' }}
          </button>
        </form>

        <!-- Connected consignees -->
        <div class="mb-8">
          <h2 class="text-sm font-bold text-gray-700 dark:text-[#aeaeb2] mb-3">Connected Consignees ({{ links.length }})</h2>
          <div v-if="!links.length" class="bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] py-10 text-center text-sm text-gray-400">
            No one has connected their Drive folders yet.
          </div>
          <div v-else class="bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] shadow-sm overflow-x-auto">
            <table class="w-full text-sm min-w-[700px]">
              <thead>
                <tr class="border-b border-gray-100 dark:border-[#2c2c2e]">
                  <th class="text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest px-4 py-3">User</th>
                  <th class="text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest px-4 py-3">Workbills</th>
                  <th class="text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest px-4 py-3">CRN</th>
                  <th class="text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest px-4 py-3">Last Synced</th>
                  <th class="text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest px-4 py-3">Needs Review</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="l in links" :key="l.user_id" class="border-b border-gray-50 dark:border-[#2c2c2e]">
                  <td class="px-4 py-3">
                    <p class="font-semibold text-gray-800 dark:text-white">{{ l.name || l.username }}</p>
                    <p class="text-xs text-gray-400 font-mono">{{ l.username }}</p>
                  </td>
                  <td class="px-4 py-3">
                    <div :class="l.workbills_connected ? 'i-carbon-checkmark text-green-600' : 'i-carbon-close text-gray-300'" class="text-base"></div>
                  </td>
                  <td class="px-4 py-3">
                    <div :class="l.crn_connected ? 'i-carbon-checkmark text-green-600' : 'i-carbon-close text-gray-300'" class="text-base"></div>
                  </td>
                  <td class="px-4 py-3 text-xs text-gray-500">
                    {{ l.last_synced_at ? new Date(l.last_synced_at).toLocaleString() : 'never' }}
                  </td>
                  <td class="px-4 py-3">
                    <span v-if="l.needs_review_count || l.error_count" class="text-xs font-semibold text-amber-600">
                      {{ l.needs_review_count }} review{{ l.error_count ? `, ${l.error_count} error` : '' }}
                    </span>
                    <span v-else class="text-xs text-gray-300">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Combined log -->
        <div>
          <h2 class="text-sm font-bold text-gray-700 dark:text-[#aeaeb2] mb-3">Needs Review / Errors ({{ log.length }})</h2>
          <div v-if="!log.length" class="bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] py-10 text-center text-sm text-gray-400">
            Nothing flagged — everything synced cleanly.
          </div>
          <div v-else class="flex flex-col gap-2">
            <div v-for="entry in log" :key="entry.id"
              class="bg-white dark:bg-[#1c1c1e] rounded-xl border px-4 py-3"
              :class="statusStyle[entry.status] || 'border-gray-100 dark:border-[#3a3a3c]'">
              <div class="flex items-center gap-2 flex-wrap mb-1">
                <span class="text-xs font-bold uppercase px-2 py-0.5 rounded-full"
                  :class="entry.status === 'error' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'">
                  {{ entry.status === 'error' ? 'Error' : 'Needs Review' }}
                </span>
                <span class="text-xs text-gray-400 uppercase font-semibold">{{ entry.kind }}</span>
                <span class="text-sm font-semibold text-gray-800 dark:text-white">{{ entry.filename }}</span>
                <span class="text-xs text-gray-400 ml-auto">{{ entry.folder_link__user__username }}</span>
              </div>
              <p class="text-xs text-gray-500">{{ entry.reason }}</p>
              <p v-if="entry.matched_work__loa_number" class="text-xs text-gray-400 mt-1 font-mono">LOA {{ entry.matched_work__loa_number }}</p>
            </div>
          </div>
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
