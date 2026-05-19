<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

// ── State ─────────────────────────────────────────────────────────────────
const allWorks      = ref([])
const isLoading     = ref(false)
const sheetErrors   = ref([])
const searchQuery   = ref('')

const selectedWork   = ref(null)   // Level 1: work detail
const selectedItem   = ref(null)   // Level 2: item drill-down
const selectedThread = ref(null)   // Level 3: thread detail

const viewMode = ref('date')       // 'date' | 'item'

// ── Load ──────────────────────────────────────────────────────────────────
const load = async () => {
  isLoading.value = true
  try {
    const res = await axios.get('/api/site-register/')
    allWorks.value    = res.data.works        || []
    sheetErrors.value = res.data.sheet_errors || []
  } catch {
    sheetErrors.value = [{ sheet: 'API', error: 'Failed to fetch data.' }]
  } finally {
    isLoading.value = false
  }
}
onMounted(load)

// ── Work list filter ───────────────────────────────────────────────────────
const filteredWorks = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return allWorks.value
  return allWorks.value.filter(w =>
    (w.loa_number      && w.loa_number.toLowerCase().includes(q)) ||
    (w.contractor_name && w.contractor_name.toLowerCase().includes(q)) ||
    (w.tender_number   && w.tender_number.toLowerCase().includes(q)) ||
    (w.consignee       && w.consignee.toLowerCase().includes(q))
  )
})

// ── Threads ────────────────────────────────────────────────────────────────
const workThreads = computed(() => {
  if (!selectedWork.value) return []
  return [...(selectedWork.value.threads || [])].sort((a, b) =>
    a.created_at > b.created_at ? -1 : 1
  )
})

// Item-wise: items enriched with thread count
const itemsWithThreads = computed(() => {
  if (!selectedWork.value) return []
  return selectedWork.value.items.map(item => {
    const threads = workThreads.value.filter(t => t.work_item_id === item.id)
    return { ...item, threads }
  })
})

// Threads for the selected item (level 2 drill-down)
const itemThreads = computed(() => {
  if (!selectedItem.value) return []
  return workThreads.value.filter(t => t.work_item_id === selectedItem.value.id)
})

// ── Item-wise grouping (GSheet, kept for legacy display) ───────────────────
const itemsWithEntries = computed(() => {
  if (!selectedWork.value) return []
  const entries = selectedWork.value.entries || []
  return selectedWork.value.items.map(item => {
    const matched = entries.filter(e =>
      e.schedule.toLowerCase() === (item.schedule || '').toLowerCase() &&
      e.serial_no.toLowerCase() === (item.serial_no || '').toLowerCase()
    )
    matched.sort((a, b) => (b.datetime > a.datetime ? 1 : -1))
    return { ...item, sheet_entries: matched }
  })
})

// ── Navigation ────────────────────────────────────────────────────────────
const selectWork = (work) => {
  selectedWork.value   = work
  selectedItem.value   = null
  selectedThread.value = null
  viewMode.value       = 'date'
}
const backToList = () => {
  selectedWork.value   = null
  selectedItem.value   = null
  selectedThread.value = null
}
const selectItem = (item) => {
  selectedItem.value   = item
  selectedThread.value = null
}
const backToWork = () => {
  selectedItem.value   = null
  selectedThread.value = null
}
const openThread = (thread) => { selectedThread.value = thread }
const closeThread = () => { selectedThread.value = null }

// ── Helpers ───────────────────────────────────────────────────────────────
const fmtDate = (val) => {
  if (!val) return '—'
  const s = String(val).split('T')[0].split(' ')[0]
  if (/^\d{2}[\/\-]\d{2}[\/\-]\d{4}$/.test(s)) return s.replace(/-/g, '/')
  const m = s.match(/^(\d{4})[\/\-](\d{2})[\/\-](\d{2})$/)
  if (m) return `${m[3]}/${m[2]}/${m[1]}`
  return s
}

const fmtDatetime = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso)
  const dd   = String(d.getDate()).padStart(2, '0')
  const mm   = String(d.getMonth() + 1).padStart(2, '0')
  const yyyy = d.getFullYear()
  const hh   = String(d.getHours()).padStart(2, '0')
  const min  = String(d.getMinutes()).padStart(2, '0')
  return `${dd}/${mm}/${yyyy} ${hh}:${min}`
}

const statusClass = (s) => ({
  open:     'bg-blue-50 text-blue-600',
  replied:  'bg-amber-50 text-amber-600',
  verified: 'bg-green-50 text-green-600',
  closed:   'bg-gray-100 text-gray-500',
}[s] || 'bg-gray-100 text-gray-500')

const roleClass = (r) => r === 'rly_official'
  ? 'bg-blue-100 text-blue-700'
  : 'bg-green-100 text-green-700'

const roleLabel = (r) => r === 'rly_official' ? 'Rly Official' : 'Site Supervisor'
</script>

<template>
  <div class="bg-white rounded-2xl soft-shadow h-full w-full flex flex-col overflow-hidden">

    <!-- ══ WORK LIST ══════════════════════════════════════════════════════ -->
    <template v-if="!selectedWork">

      <div class="flex-shrink-0 px-8 pt-7 pb-5 border-b border-gray-100">
        <h1 class="text-2xl font-bold text-gray-900 tracking-tight mb-1">Site Register</h1>
        <p class="text-gray-400 text-sm font-medium mb-5">
          All works — bot instructions, contractor replies, and sheet data.
        </p>
        <div class="flex items-center gap-3">
          <div class="flex-1 flex items-center bg-gray-50 border border-gray-200 rounded-2xl px-5 py-3
                      focus-within:ring-2 focus-within:ring-[#1D5F5E]/20 focus-within:border-[#1D5F5E]
                      focus-within:bg-white transition-all">
            <div class="i-carbon-search text-gray-400 text-base mr-3 flex-shrink-0"></div>
            <input v-model="searchQuery" type="text"
              placeholder="Search by LOA, Contractor, Tender, Consignee…"
              class="bg-transparent outline-none w-full text-gray-700 font-medium placeholder-gray-400 text-sm" />
            <button v-if="searchQuery" @click="searchQuery = ''" class="ml-2 text-gray-300 hover:text-gray-500 transition-colors">
              <div class="i-carbon-close text-sm"></div>
            </button>
          </div>
          <button @click="load" :disabled="isLoading"
            class="flex items-center justify-center w-11 h-11 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-500 transition-all flex-shrink-0"
            title="Refresh">
            <div class="i-carbon-renew text-base" :class="isLoading ? 'animate-spin' : ''"></div>
          </button>
        </div>
        <div v-if="sheetErrors.length > 0" class="mt-3 rounded-xl bg-red-50 border border-red-200 px-4 py-3">
          <p class="text-xs font-semibold text-red-600 mb-1">Sheet fetch errors:</p>
          <p v-for="e in sheetErrors" :key="e.sheet" class="text-xs text-red-500">{{ e.sheet }}: {{ e.error }}</p>
        </div>
      </div>

      <div v-if="isLoading" class="flex-1 flex items-center justify-center py-24">
        <div class="i-carbon-circle-dash animate-spin text-3xl text-[#1D5F5E]"></div>
      </div>
      <div v-else-if="filteredWorks.length === 0" class="flex-1 flex flex-col items-center justify-center py-24 text-center">
        <div class="i-carbon-document-unknown text-5xl text-gray-200 mb-4"></div>
        <p class="text-sm font-semibold text-gray-400">
          {{ searchQuery ? 'No works match your search.' : 'No works in system.' }}
        </p>
      </div>
      <template v-else>
        <div class="flex-1 overflow-auto px-8 py-5">
          <p class="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-4">
            {{ filteredWorks.length }} {{ filteredWorks.length === 1 ? 'work' : 'works' }}
            <template v-if="searchQuery"> matching "{{ searchQuery }}"</template>
          </p>
          <div class="grid grid-cols-1 gap-3">
            <div v-for="work in filteredWorks" :key="work.work_id"
              class="bg-white border border-gray-200 hover:border-[#1D5F5E] hover:bg-[#1D5F5E]/5 px-5 py-4 rounded-xl transition-all group cursor-pointer"
              @click="selectWork(work)">
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0 flex-1">
                  <p class="text-sm font-semibold text-gray-900 truncate">{{ work.contractor_name || '—' }}</p>
                  <div class="flex items-center gap-3 flex-wrap mt-1">
                    <span class="text-[11px] font-semibold text-[#1D5F5E] bg-[#1D5F5E]/10 px-2 py-0.5 rounded-full">
                      {{ work.loa_number || '—' }}
                    </span>
                    <span class="text-[11px] text-gray-500">
                      Tender: <span class="font-semibold text-gray-700">{{ work.tender_number || '—' }}</span>
                    </span>
                    <span class="text-[11px] text-gray-500">
                      Consignee: <span class="font-semibold text-gray-700">{{ work.consignee || '—' }}</span>
                    </span>
                    <span class="text-[11px] text-gray-500">
                      Completion: <span class="font-semibold text-gray-700">{{ fmtDate(work.date_of_completion) }}</span>
                    </span>
                    <span v-if="work.warning_count > 0"
                      class="text-[11px] font-semibold text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full flex items-center gap-1">
                      <span class="i-carbon-warning-filled text-[10px]"></span>
                      {{ work.warning_count }} warning{{ work.warning_count > 1 ? 's' : '' }}
                    </span>
                  </div>
                </div>
                <div class="flex items-center gap-4 flex-shrink-0">
                  <div class="text-right">
                    <p class="text-sm font-bold text-gray-800">{{ work.thread_count || 0 }}</p>
                    <p class="text-[10px] text-gray-400">SR entries</p>
                  </div>
                  <div class="text-right">
                    <p class="text-sm font-bold text-gray-800">{{ work.items.length }}</p>
                    <p class="text-[10px] text-gray-400">items</p>
                  </div>
                  <div class="i-carbon-chevron-right text-gray-300 group-hover:text-[#1D5F5E] transition-colors text-lg"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </template>

    <!-- ══ THREAD DETAIL (Level 3) ════════════════════════════════════════ -->
    <template v-else-if="selectedWork && selectedThread">
      <div class="flex flex-col h-full overflow-hidden animate-fade-in">

        <!-- Header -->
        <div class="flex-shrink-0 px-6 pt-5 pb-4 border-b border-gray-100">
          <div class="flex items-start gap-4 min-w-0">
            <button @click="closeThread"
              class="mt-0.5 w-9 h-9 flex-shrink-0 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 transition-all">
              <div class="i-carbon-arrow-left text-base"></div>
            </button>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-[11px] font-bold text-[#1D5F5E] bg-[#1D5F5E]/10 px-2 py-0.5 rounded-full">
                  {{ selectedThread.sr_number }}
                </span>
                <span v-if="selectedThread.work_item_ref"
                  class="text-[11px] font-semibold text-purple-700 bg-purple-50 px-2 py-0.5 rounded-full">
                  {{ selectedThread.work_item_ref }}
                </span>
                <span class="text-[11px] font-medium text-gray-500">{{ selectedThread.category_label }}</span>
                <span :class="['text-[11px] font-semibold px-2 py-0.5 rounded-full', statusClass(selectedThread.status)]">
                  {{ selectedThread.status.toUpperCase() }}
                </span>
              </div>
              <p class="text-xs text-gray-500 mt-1">
                {{ selectedWork.loa_number }} · {{ selectedWork.contractor_name }} ·
                {{ fmtDatetime(selectedThread.created_at) }} by {{ selectedThread.created_by_name }}
              </p>
            </div>
          </div>
        </div>

        <!-- Conversation thread -->
        <div class="flex-1 overflow-auto px-6 py-5 space-y-0">

          <!-- Original instruction -->
          <div class="flex gap-3 mb-0">
            <div class="flex flex-col items-center">
              <div class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                <span class="i-carbon-user-avatar text-blue-600 text-sm"></span>
              </div>
              <div class="w-0.5 bg-gray-200 flex-1 mt-1"></div>
            </div>
            <div class="flex-1 pb-5">
              <div class="flex items-center gap-2 mb-1.5">
                <span class="text-xs font-bold text-blue-700">{{ selectedThread.created_by_name }}</span>
                <span class="text-[11px] font-semibold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded-full">Rly Official</span>
                <span class="text-[11px] text-gray-400">{{ fmtDatetime(selectedThread.created_at) }}</span>
              </div>
              <div class="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3">
                <p class="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{{ selectedThread.initial_text || '—' }}</p>
              </div>
            </div>
          </div>

          <!-- Replies -->
          <div v-for="(msg, idx) in selectedThread.messages" :key="msg.id" class="flex gap-3 mb-0">
            <div class="flex flex-col items-center">
              <div :class="['w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
                msg.sender_role === 'rly_official' ? 'bg-blue-100' : 'bg-green-100']">
                <span :class="['i-carbon-user-avatar text-sm',
                  msg.sender_role === 'rly_official' ? 'text-blue-600' : 'text-green-600']"></span>
              </div>
              <div v-if="idx < selectedThread.messages.length - 1"
                class="w-0.5 bg-gray-200 flex-1 mt-1"></div>
            </div>
            <div class="flex-1 pb-5">
              <div class="flex items-center gap-2 mb-1.5">
                <span :class="['text-xs font-bold',
                  msg.sender_role === 'rly_official' ? 'text-blue-700' : 'text-green-700']">
                  {{ msg.sender_name }}
                </span>
                <span :class="['text-[11px] font-semibold px-1.5 py-0.5 rounded-full', roleClass(msg.sender_role)]">
                  {{ roleLabel(msg.sender_role) }}
                </span>
                <span class="text-[11px] text-gray-400">{{ fmtDatetime(msg.created_at) }}</span>
              </div>
              <div :class="['border rounded-xl px-4 py-3',
                msg.sender_role === 'rly_official'
                  ? 'bg-blue-50 border-blue-100'
                  : 'bg-green-50 border-green-100']">
                <p class="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{{ msg.text || '—' }}</p>
              </div>
            </div>
          </div>

          <!-- No replies yet -->
          <div v-if="!selectedThread.messages.length"
            class="text-center py-6 text-xs text-gray-400 font-medium">
            No replies yet from site supervisor.
          </div>
        </div>
      </div>
    </template>

    <!-- ══ ITEM DRILL-DOWN (Level 2) ══════════════════════════════════════ -->
    <template v-else-if="selectedWork && selectedItem">
      <div class="flex flex-col h-full overflow-hidden animate-fade-in">

        <!-- Header -->
        <div class="flex-shrink-0 px-6 pt-5 pb-4 border-b border-gray-100">
          <div class="flex items-start gap-4 min-w-0">
            <button @click="backToWork"
              class="mt-0.5 w-9 h-9 flex-shrink-0 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 transition-all">
              <div class="i-carbon-arrow-left text-base"></div>
            </button>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-[11px] font-semibold text-[#1D5F5E] bg-[#1D5F5E]/10 px-2 py-0.5 rounded-full">
                  Sch {{ selectedItem.schedule }} · Item {{ selectedItem.serial_no }}
                </span>
                <span class="text-[11px] text-gray-400">{{ selectedWork.contractor_name }}</span>
                <span class="text-gray-200 text-xs">·</span>
                <span class="text-[11px] text-gray-400">LOA {{ selectedWork.loa_number }}</span>
              </div>
              <p class="text-sm font-semibold text-gray-900 mt-1 max-w-3xl leading-snug">
                {{ selectedItem.item_desc || '—' }}
              </p>
              <div class="flex items-center gap-4 mt-1 text-xs text-gray-500">
                <span>Qty: <span class="font-semibold text-gray-700">{{ selectedItem.qty ?? '—' }} {{ selectedItem.unit }}</span></span>
                <span class="text-gray-200">·</span>
                <span>{{ itemThreads.length }} SR entr{{ itemThreads.length !== 1 ? 'ies' : 'y' }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Threads for this item -->
        <div class="flex-1 overflow-auto px-6 py-5">
          <div v-if="itemThreads.length === 0"
            class="flex flex-col items-center justify-center py-16 text-center">
            <div class="i-carbon-document-unknown text-5xl text-gray-200 mb-4"></div>
            <p class="text-sm font-semibold text-gray-400">No site register entries for this item yet.</p>
          </div>
          <div v-else class="space-y-3">
            <div v-for="t in itemThreads" :key="t.id"
              class="border border-gray-200 hover:border-[#1D5F5E] hover:bg-[#1D5F5E]/5 rounded-xl px-4 py-3.5 cursor-pointer transition-all group"
              @click="openThread(t)">
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2 flex-wrap mb-1">
                    <span class="text-[11px] font-bold text-[#1D5F5E]">{{ t.sr_number }}</span>
                    <span :class="['text-[11px] font-semibold px-1.5 py-0.5 rounded-full', statusClass(t.status)]">
                      {{ t.status.toUpperCase() }}
                    </span>
                    <span class="text-[11px] text-gray-400">{{ fmtDatetime(t.created_at) }}</span>
                    <span class="text-[11px] text-gray-500">by {{ t.created_by_name }}</span>
                  </div>
                  <p class="text-xs text-gray-700 line-clamp-2">{{ t.initial_text }}</p>
                </div>
                <div class="flex items-center gap-3 flex-shrink-0">
                  <div class="text-right">
                    <p class="text-xs font-bold text-gray-700">{{ t.messages.length }}</p>
                    <p class="text-[10px] text-gray-400">repl{{ t.messages.length !== 1 ? 'ies' : 'y' }}</p>
                  </div>
                  <div class="i-carbon-chevron-right text-gray-300 group-hover:text-[#1D5F5E] text-lg"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ══ WORK DETAIL — DATE / ITEM TABS (Level 1) ═══════════════════════ -->
    <template v-else-if="selectedWork">
      <div class="flex flex-col h-full overflow-hidden animate-fade-in">

        <!-- Header -->
        <div class="px-8 pt-6 pb-5 border-b border-gray-100 flex-shrink-0">
          <div class="flex items-start justify-between gap-6">
            <div class="flex items-start gap-4 min-w-0">
              <button @click="backToList"
                class="mt-0.5 w-9 h-9 flex-shrink-0 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 transition-all">
                <div class="i-carbon-arrow-left text-base"></div>
              </button>
              <div class="min-w-0">
                <h2 class="text-xl font-bold text-gray-900 truncate">{{ selectedWork.contractor_name }}</h2>
                <p v-if="selectedWork.name_of_work" class="text-xs text-gray-600 mt-0.5 leading-snug max-w-2xl">
                  {{ selectedWork.name_of_work }}
                </p>
                <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 mt-2">
                  <span class="flex items-center gap-1.5 text-xs text-gray-500">
                    <span class="font-medium text-gray-400">LOA</span>
                    <span class="font-semibold text-gray-800">{{ selectedWork.loa_number || '—' }}</span>
                  </span>
                  <span class="text-gray-200">·</span>
                  <span class="flex items-center gap-1.5 text-xs text-gray-500">
                    <span class="font-medium text-gray-400">Tender</span>
                    <span class="font-semibold text-gray-800">{{ selectedWork.tender_number || '—' }}</span>
                  </span>
                  <span class="text-gray-200">·</span>
                  <span class="flex items-center gap-1.5 text-xs text-gray-500">
                    <span class="font-medium text-gray-400">Consignee</span>
                    <span class="font-semibold text-gray-800">{{ selectedWork.consignee || '—' }}</span>
                  </span>
                  <span class="text-gray-200">·</span>
                  <span class="flex items-center gap-1.5 text-xs text-gray-500">
                    <span class="font-medium text-gray-400">Completion</span>
                    <span class="font-semibold text-gray-800">{{ fmtDate(selectedWork.date_of_completion) }}</span>
                  </span>
                </div>
              </div>
            </div>
          </div>
          <div class="flex gap-1.5 mt-4">
            <button @click="viewMode = 'date'"
              :class="viewMode === 'date' ? 'bg-[#1D5F5E] text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'"
              class="px-4 py-1.5 rounded-lg text-xs font-semibold transition-all">
              Date-wise
            </button>
            <button @click="viewMode = 'item'"
              :class="viewMode === 'item' ? 'bg-[#1D5F5E] text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'"
              class="px-4 py-1.5 rounded-lg text-xs font-semibold transition-all">
              Item-wise
            </button>
          </div>
        </div>

        <!-- ── DATE-WISE: all SR threads ──────────────────────────────── -->
        <div v-if="viewMode === 'date'" class="flex-1 overflow-auto px-6 py-5">
          <div v-if="workThreads.length === 0"
            class="flex flex-col items-center justify-center py-16 text-center">
            <div class="i-carbon-document-unknown text-5xl text-gray-200 mb-4"></div>
            <p class="text-sm font-semibold text-gray-400">No site register entries for this LOA yet.</p>
            <p class="text-xs text-gray-300 mt-1">Use the Telegram bot to create entries.</p>
          </div>
          <div v-else>
            <p class="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-4">
              {{ workThreads.length }} entr{{ workThreads.length === 1 ? 'y' : 'ies' }}
            </p>
            <div class="space-y-3">
              <div v-for="t in workThreads" :key="t.id"
                class="border border-gray-200 hover:border-[#1D5F5E] hover:bg-[#1D5F5E]/5 rounded-xl px-4 py-3.5 cursor-pointer transition-all group"
                @click="openThread(t)">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2 flex-wrap mb-1.5">
                      <span class="text-[11px] font-bold text-[#1D5F5E]">{{ t.sr_number }}</span>
                      <span v-if="t.work_item_ref"
                        class="text-[11px] font-semibold text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded-full">
                        {{ t.work_item_ref }}
                      </span>
                      <span v-else class="text-[11px] font-medium text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded-full">
                        General
                      </span>
                      <span :class="['text-[11px] font-semibold px-1.5 py-0.5 rounded-full', statusClass(t.status)]">
                        {{ t.status.toUpperCase() }}
                      </span>
                    </div>
                    <p class="text-xs text-gray-700 line-clamp-2 mb-1">{{ t.initial_text }}</p>
                    <p class="text-[11px] text-gray-400">
                      {{ fmtDatetime(t.created_at) }} · {{ t.created_by_name }}
                    </p>
                  </div>
                  <div class="flex items-center gap-3 flex-shrink-0 mt-1">
                    <div class="text-right">
                      <p class="text-xs font-bold text-gray-700">{{ t.messages.length }}</p>
                      <p class="text-[10px] text-gray-400">repl{{ t.messages.length !== 1 ? 'ies' : 'y' }}</p>
                    </div>
                    <div class="i-carbon-chevron-right text-gray-300 group-hover:text-[#1D5F5E] text-lg"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ── ITEM-WISE: items with SR thread counts ──────────────────── -->
        <div v-if="viewMode === 'item'" class="overflow-y-auto flex-1">
          <table class="w-full border-collapse">
            <thead class="bg-gray-50 sticky top-0 z-10">
              <tr class="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
                <th class="px-4 py-3 text-center w-14">Sch</th>
                <th class="px-4 py-3 text-center w-14">S.No</th>
                <th class="px-4 py-3 text-left">Item Description</th>
                <th class="px-4 py-3 text-right w-32">Required Qty</th>
                <th class="px-4 py-3 text-center w-32">SR Entries</th>
                <th class="px-4 py-3 text-center w-28">Action</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="itemsWithThreads.length === 0">
                <td colspan="6" class="p-8 text-center text-gray-400 text-xs font-medium">No items for this work.</td>
              </tr>
              <tr v-for="item in itemsWithThreads" :key="item.id"
                class="border-b border-gray-100 hover:bg-accent-soft/40 transition-colors">
                <td class="px-4 py-3.5 text-center">
                  <span class="rounded-md px-2 py-1 text-[10px] font-bold"
                    :class="String(item.schedule||'').toUpperCase().startsWith('A')
                      ? 'bg-teal-50 text-teal-700'
                      : 'bg-amber-50 text-amber-700'">
                    {{ item.schedule }}
                  </span>
                </td>
                <td class="px-4 py-3.5 text-center text-[11px] font-semibold text-gray-500">{{ item.serial_no }}</td>
                <td class="px-4 py-3.5">
                  <p class="text-xs font-medium line-clamp-2 leading-relaxed text-gray-800">{{ item.item_desc }}</p>
                </td>
                <td class="px-4 py-3.5 text-right text-xs font-semibold text-gray-600">
                  {{ item.qty ?? '—' }} <span class="font-normal text-gray-400">{{ item.unit }}</span>
                </td>
                <td class="px-4 py-3.5 text-center">
                  <span class="text-[11px] font-bold"
                    :class="item.threads.length > 0 ? 'text-[#1D5F5E]' : 'text-gray-300'">
                    {{ item.threads.length }}
                  </span>
                  <p class="text-[10px] text-gray-400">entr{{ item.threads.length !== 1 ? 'ies' : 'y' }}</p>
                </td>
                <td class="px-4 py-3.5 text-center">
                  <button @click="selectItem(item)"
                    :disabled="item.threads.length === 0"
                    :class="item.threads.length > 0
                      ? 'bg-[#1D5F5E]/10 hover:bg-[#1D5F5E]/20 text-[#1D5F5E] cursor-pointer'
                      : 'bg-gray-50 text-gray-300 cursor-not-allowed'"
                    class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-[11px] font-semibold transition-all">
                    <div class="i-carbon-list text-xs"></div> View
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

      </div>
    </template>

  </div>
</template>
