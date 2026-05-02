<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const API = '/api/auth'

const ROLES = ['user', 'observer', 'consignee']

const ROLE_STYLE = {
  user:      'bg-gray-100 text-gray-600',
  observer:  'bg-blue-100 text-blue-700',
  consignee: 'bg-amber-100 text-amber-700',
}

const pending  = ref([])
const approved = ref([])
const loading  = ref(true)
const tab      = ref('pending')
const toast    = ref({ show: false, msg: '', type: 'success' })

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/)
  return m ? m[1] : ''
}
const headers = () => ({ 'X-CSRFToken': getCsrf() })

async function loadData() {
  loading.value = true
  try {
    const [p, a] = await Promise.all([
      axios.get(`${API}/pending/`),
      axios.get(`${API}/all/`),
    ])
    pending.value  = p.data
    approved.value = a.data
  } finally {
    loading.value = false
  }
}

async function approve(id) {
  await axios.post(`${API}/approve/${id}/`, {}, { headers: headers() })
  showToast('User approved.')
  await loadData()
}

async function reject(id) {
  if (!confirm('Reject and permanently delete this registration?')) return
  await axios.delete(`${API}/reject/${id}/`, { headers: headers() })
  showToast('Registration rejected.', 'error')
  await loadData()
}

async function revoke(id) {
  if (!confirm('Revoke access? User will not be able to login until re-approved.')) return
  await axios.post(`${API}/revoke/${id}/`, {}, { headers: headers() })
  showToast('Access revoked.', 'error')
  await loadData()
}

async function updateRole(id, role) {
  await axios.patch(`${API}/role/${id}/`, { role }, { headers: headers() })
  showToast(`Role updated to ${role}.`)
}

function showToast(msg, type = 'success') {
  toast.value = { show: true, msg, type }
  setTimeout(() => { toast.value.show = false }, 3000)
}

onMounted(loadData)
</script>

<template>
  <div class="p-6 max-w-5xl">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-gray-800 tracking-tight">User Management</h1>
      <p class="text-sm text-gray-500 mt-1">Approve registrations and manage user roles</p>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 p-1 bg-light-bg rounded-xl mb-6 w-fit">
      <button
        v-for="t in ['pending', 'approved']"
        :key="t"
        @click="tab = t"
        class="px-5 py-2 rounded-lg text-sm font-semibold capitalize transition-all"
        :class="tab === t ? 'bg-light-surface soft-shadow text-gray-800' : 'text-gray-500 hover:text-gray-700'"
      >
        {{ t }}
        <span v-if="t === 'pending' && pending.length" class="ml-1.5 px-1.5 py-0.5 text-xs rounded-full bg-red-100 text-red-600">
          {{ pending.length }}
        </span>
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center gap-2 text-sm text-gray-400 py-8">
      <div class="i-carbon-loading animate-spin text-lg"></div>
      Loading…
    </div>

    <!-- Pending tab -->
    <div v-else-if="tab === 'pending'">
      <div v-if="!pending.length" class="py-16 text-center">
        <div class="i-carbon-checkmark-outline text-4xl text-gray-300 mx-auto mb-3"></div>
        <p class="text-sm text-gray-400">No pending registrations</p>
      </div>

      <div v-else class="flex flex-col gap-3">
        <div
          v-for="u in pending"
          :key="u.id"
          class="bg-light-surface rounded-2xl soft-shadow p-5 flex items-center gap-4"
        >
          <div class="w-10 h-10 rounded-full bg-light-bg soft-shadow-inset flex items-center justify-center shrink-0">
            <div class="i-carbon-user text-xl text-gray-500"></div>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-semibold text-gray-800">{{ u.name }}</p>
            <p class="text-xs text-gray-500 mt-0.5">{{ u.designation }}</p>
            <div class="flex gap-4 mt-1.5 text-xs text-gray-400">
              <span><span class="font-medium text-gray-600">HRMS:</span> {{ u.hrms_id }}</span>
              <span><span class="font-medium text-gray-600">PF:</span> {{ u.pf_number }}</span>
              <span>{{ u.created_at }}</span>
            </div>
          </div>
          <div class="flex gap-2 shrink-0">
            <button
              @click="approve(u.id)"
              class="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-green-600 text-white text-xs font-semibold hover:bg-green-700 transition-colors"
            >
              <div class="i-carbon-checkmark text-sm"></div>
              Approve
            </button>
            <button
              @click="reject(u.id)"
              class="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-red-50 text-red-600 border border-red-200 text-xs font-semibold hover:bg-red-100 transition-colors"
            >
              <div class="i-carbon-close text-sm"></div>
              Reject
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Approved tab -->
    <div v-else-if="tab === 'approved'">
      <div v-if="!approved.length" class="py-16 text-center">
        <p class="text-sm text-gray-400">No approved users yet</p>
      </div>

      <div v-else class="bg-light-surface rounded-2xl soft-shadow overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-100">
              <th class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-5 py-3">Name</th>
              <th class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-5 py-3">HRMS ID</th>
              <th class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-5 py-3">Designation</th>
              <th class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-5 py-3">PF No.</th>
              <th class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-5 py-3">Role</th>
              <th class="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-5 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in approved" :key="u.id" class="border-b border-gray-50 hover:bg-light-bg transition-colors">
              <td class="px-5 py-3 font-medium text-gray-800">{{ u.name }}</td>
              <td class="px-5 py-3 text-gray-600 font-mono text-xs">{{ u.hrms_id }}</td>
              <td class="px-5 py-3 text-gray-600">{{ u.designation }}</td>
              <td class="px-5 py-3 text-gray-600 font-mono text-xs">{{ u.pf_number }}</td>
              <td class="px-5 py-3">
                <select
                  :value="u.role"
                  @change="updateRole(u.id, $event.target.value)"
                  class="px-2 py-1 rounded-lg text-xs font-semibold border border-gray-200 bg-white cursor-pointer focus:outline-none focus:border-gray-400 capitalize"
                  :class="ROLE_STYLE[u.role]"
                >
                  <option v-for="r in ROLES" :key="r" :value="r" class="capitalize bg-white text-gray-800">{{ r }}</option>
                </select>
              </td>
              <td class="px-5 py-3">
                <button
                  @click="revoke(u.id)"
                  class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-50 text-red-600 border border-red-200 text-xs font-semibold hover:bg-red-100 transition-colors"
                >
                  <div class="i-carbon-locked text-sm"></div>
                  Revoke
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Toast -->
    <transition name="toast">
      <div
        v-if="toast.show"
        class="fixed bottom-6 right-6 flex items-center gap-2 px-4 py-3 rounded-xl soft-shadow text-sm font-medium"
        :class="toast.type === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'"
      >
        <div :class="toast.type === 'success' ? 'i-carbon-checkmark' : 'i-carbon-locked'" class="text-base"></div>
        {{ toast.msg }}
      </div>
    </transition>
  </div>
</template>

<style scoped>
.toast-enter-active, .toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(8px); }
</style>
