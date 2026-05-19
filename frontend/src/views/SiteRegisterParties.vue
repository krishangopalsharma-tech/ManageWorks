<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/)
  return m ? m[1] : ''
}
const h = () => ({ 'X-CSRFToken': getCsrf() })


const contractors  = ref([])
const loading      = ref(true)
const search       = ref('')
const toast        = ref({ show: false, msg: '', type: 'success' })

async function load() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/site-register/parties/')
    contractors.value = data
  } catch {
    showToast('Failed to load data.', 'error')
  } finally {
    loading.value = false
  }
}

const filteredContractors = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return contractors.value
  return contractors.value
    .map(c => ({
      ...c,
      loas: c.loas.filter(l =>
        (c.contractor_name || '').toLowerCase().includes(q) ||
        (l.loa_number      || '').toLowerCase().includes(q) ||
        (l.name_of_work    || '').toLowerCase().includes(q)
      ),
    }))
    .filter(c => c.loas.length)
})

function openModal(contractor) {
  router.push({
    path: '/settings/add-supervisor',
    state: {
      contractor: contractor.contractor_name,
      loas: contractor.loas.map(l => ({ id: l.id, loa_number: l.loa_number, name_of_work: l.name_of_work })),
    },
  })
}

async function removeSupervisor(loa, sup) {
  if (!confirm(`Remove ${sup.name || sup.hrms_id} from LOA ${loa.loa_number}?`)) return
  try {
    await axios.delete(
      `/api/site-register/parties/${loa.id}/${sup.mapping_id}/`,
      { headers: h() }
    )
    loa.supervisors = loa.supervisors.filter(s => s.mapping_id !== sup.mapping_id)
    showToast('Removed.')
  } catch {
    showToast('Failed to remove.', 'error')
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
    <div class="max-w-4xl">

      <!-- Header -->
      <div class="mb-6">
        <h1 class="text-xl font-bold text-gray-800 dark:text-white tracking-tight">Site Supervisor Management</h1>
        <p class="text-sm text-gray-500 mt-0.5">Assign Telegram-linked site supervisors to contractor LOAs.</p>
      </div>

      <!-- Search -->
      <div class="relative mb-5">
        <div class="i-carbon-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-base pointer-events-none"></div>
        <input
          v-model="search" type="text"
          placeholder="Search contractor, LOA or work name…"
          class="w-full pl-9 pr-4 py-2.5 rounded-xl border border-gray-200 dark:border-[#3a3a3c] bg-white dark:bg-[#1c1c1e] text-sm text-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#1D5F5E]/30"
        />
      </div>

      <div v-if="loading" class="flex items-center gap-2 text-sm text-gray-400 mt-8">
        <div class="i-carbon-circle-dash animate-spin text-lg"></div> Loading…
      </div>

      <div v-else-if="!filteredContractors.length" class="text-sm text-gray-400 mt-8">
        No contractors found.
      </div>

      <!-- Contractor cards -->
      <div v-else class="flex flex-col gap-5">
        <div
          v-for="contractor in filteredContractors"
          :key="contractor.contractor_name"
          class="bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] shadow-sm overflow-hidden"
        >
          <!-- Contractor header -->
          <div class="px-5 py-4 flex items-center justify-between gap-4 border-b border-gray-100 dark:border-[#2c2c2e]">
            <div class="flex items-center gap-3 min-w-0">
              <div class="i-carbon-building text-[#1D5F5E] text-lg shrink-0"></div>
              <p class="text-sm font-bold text-gray-800 dark:text-white truncate">{{ contractor.contractor_name || '—' }}</p>
              <span class="shrink-0 text-xs text-gray-400">{{ contractor.loas.length }} LOA{{ contractor.loas.length !== 1 ? 's' : '' }}</span>
            </div>
            <button
              @click="openModal(contractor)"
              class="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1D5F5E] hover:bg-[#174E4D] text-white text-xs font-semibold transition-colors"
            >
              <div class="i-carbon-add text-sm"></div>
              Add Supervisor
            </button>
          </div>

          <!-- LOA rows -->
          <div class="divide-y divide-gray-50 dark:divide-[#2c2c2e]">
            <div v-for="loa in contractor.loas" :key="loa.id" class="px-5 py-3">
              <div class="flex items-start gap-3">
                <div class="shrink-0 pt-0.5">
                  <span class="text-xs font-bold text-[#1D5F5E] bg-[#1D5F5E]/10 px-2 py-0.5 rounded-full">
                    {{ loa.loa_number }}
                  </span>
                </div>
                <div class="flex-1 min-w-0">
                  <p class="text-xs text-gray-500 truncate mb-1.5">{{ loa.name_of_work || '—' }}</p>
                  <!-- Supervisors -->
                  <div v-if="!loa.supervisors.length" class="text-xs text-gray-400 italic">
                    No supervisor assigned
                  </div>
                  <div v-else class="flex flex-wrap gap-2">
                    <div
                      v-for="sup in loa.supervisors"
                      :key="sup.mapping_id"
                      class="flex items-center gap-1.5 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 text-xs font-medium px-2.5 py-1 rounded-full"
                    >
                      <div class="i-carbon-user text-xs"></div>
                      <span>{{ sup.name || sup.hrms_id }}</span>
                      <button
                        @click="removeSupervisor(loa, sup)"
                        class="ml-0.5 text-green-500 hover:text-red-500 transition-colors"
                        title="Remove"
                      >
                        <div class="i-carbon-close text-xs"></div>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

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
