<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

// ── State ─────────────────────────────────────────────────────────────────
const allWorks    = ref([])
const isLoading   = ref(false)
const sheetErrors = ref([])
const searchQuery = ref('')

// Drill-down: selected work card
const selectedWork = ref(null)

// Inside work: view mode
const viewMode = ref('date')   // 'date' | 'item'

// Inside item-wise: selected item
const selectedItem = ref(null)

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

// ── Item-wise grouping ─────────────────────────────────────────────────────
// For each WorkItem in selectedWork.items, collect matching entries by schedule+serial
const itemsWithEntries = computed(() => {
  if (!selectedWork.value) return []
  const entries = selectedWork.value.entries
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
  selectedWork.value = work
  viewMode.value     = 'date'
  selectedItem.value = null
}
const backToList = () => {
  selectedWork.value = null
  selectedItem.value = null
}
const selectItem = (item) => { selectedItem.value = item }
const backToWork = () => { selectedItem.value = null }

// ── Helpers ───────────────────────────────────────────────────────────────
const fmtDate = (val) => {
  if (!val) return '—'
  const s = String(val).split('T')[0].split(' ')[0]
  if (/^\d{2}[\/\-]\d{2}[\/\-]\d{4}$/.test(s)) return s.replace(/-/g, '/')
  const m = s.match(/^(\d{4})[\/\-](\d{2})[\/\-](\d{2})$/)
  if (m) return `${m[3]}/${m[2]}/${m[1]}`
  return s
}
</script>

<template>
  <div class="bg-white rounded-2xl soft-shadow h-full w-full flex flex-col overflow-hidden">

    <!-- ══ WORK LIST ══════════════════════════════════════════════════════ -->
    <template v-if="!selectedWork">

      <div class="flex-shrink-0 px-8 pt-7 pb-5 border-b border-gray-100">
        <h1 class="text-2xl font-bold text-gray-900 tracking-tight mb-1">Site Register</h1>
        <p class="text-gray-400 text-sm font-medium mb-5">
          All works in system — open a work to see contractor activity from linked Google Sheets.
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
                    <p class="text-sm font-bold text-gray-800">{{ work.items.length }}</p>
                    <p class="text-[10px] text-gray-400">items</p>
                  </div>
                  <div class="text-right">
                    <p class="text-sm font-bold" :class="work.entry_count > 0 ? 'text-[#1D5F5E]' : 'text-gray-300'">
                      {{ work.entry_count }}
                    </p>
                    <p class="text-[10px] text-gray-400">site entries</p>
                  </div>
                  <div class="i-carbon-chevron-right text-gray-300 group-hover:text-[#1D5F5E] transition-colors text-lg"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </template>

    <!-- ══ WORK DETAIL — ITEM DRILL-DOWN ══════════════════════════════════ -->
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
                <span>{{ selectedItem.sheet_entries.length }} contractor remark{{ selectedItem.sheet_entries.length !== 1 ? 's' : '' }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Entries for this item -->
        <div class="flex-1 overflow-auto px-6 py-5">
          <div v-if="selectedItem.sheet_entries.length === 0"
            class="flex flex-col items-center justify-center py-16 text-center">
            <div class="i-carbon-document-unknown text-5xl text-gray-200 mb-4"></div>
            <p class="text-sm font-semibold text-gray-400">No contractor remarks for this item yet.</p>
          </div>
          <div v-else class="rounded-xl border border-gray-200 overflow-hidden">
            <table class="w-full text-sm">
              <thead>
                <tr class="bg-gray-50 border-b border-gray-200">
                  <th class="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wide whitespace-nowrap">Date & Time</th>
                  <th class="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wide">Contractor Remark</th>
                  <th class="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wide">Source Sheet</th>
                  <th class="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wide">Status</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(entry, idx) in selectedItem.sheet_entries" :key="idx"
                  class="border-t border-gray-100 hover:bg-accent-soft/40 transition-colors"
                  :class="entry.warnings.length > 0 ? 'bg-amber-50/40' : ''">
                  <td class="px-4 py-3 font-mono text-xs text-gray-500 whitespace-nowrap">{{ entry.datetime }}</td>
                  <td class="px-4 py-3 text-gray-700 max-w-md">
                    <span class="text-sm">{{ entry.remark || '—' }}</span>
                  </td>
                  <td class="px-4 py-3 text-xs text-gray-400">{{ entry.sheet_name }}</td>
                  <td class="px-4 py-3">
                    <span v-if="entry.warnings.length === 0"
                      class="text-[11px] font-semibold text-green-600 bg-green-50 px-2 py-0.5 rounded-full">Valid</span>
                    <div v-else class="flex flex-col gap-1">
                      <span v-for="(w, wi) in entry.warnings" :key="wi"
                        class="text-[11px] font-semibold text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full flex items-center gap-1 whitespace-nowrap">
                        <span class="i-carbon-warning-filled text-[10px]"></span>{{ w }}
                      </span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

    <!-- ══ WORK DETAIL — DATE / ITEM VIEW ═════════════════════════════════ -->
    <template v-else-if="selectedWork">
      <div class="flex flex-col h-full overflow-hidden animate-fade-in">

        <!-- Header — matches UpdateWork exactly -->
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
                  <span v-if="selectedWork.warning_count > 0"
                    class="text-[11px] font-semibold text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full flex items-center gap-1">
                    <span class="i-carbon-warning-filled text-[10px]"></span>
                    {{ selectedWork.warning_count }} warning{{ selectedWork.warning_count > 1 ? 's' : '' }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- View toggle tabs -->
          <div class="flex gap-1.5 mt-4">
            <button @click="viewMode = 'date'"
              :class="viewMode === 'date'
                ? 'bg-[#1D5F5E] text-white'
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200'"
              class="px-4 py-1.5 rounded-lg text-xs font-semibold transition-all">
              Date-wise
            </button>
            <button @click="viewMode = 'item'"
              :class="viewMode === 'item'
                ? 'bg-[#1D5F5E] text-white'
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200'"
              class="px-4 py-1.5 rounded-lg text-xs font-semibold transition-all">
              Item-wise
            </button>
          </div>
        </div>

        <!-- ── DATE-WISE VIEW ─────────────────────────────────────────── -->
        <div v-if="viewMode === 'date'" class="flex-1 overflow-auto px-6 py-5">
          <div v-if="selectedWork.entries.length === 0"
            class="flex flex-col items-center justify-center py-16 text-center">
            <div class="i-carbon-document-unknown text-5xl text-gray-200 mb-4"></div>
            <p class="text-sm font-semibold text-gray-400">No contractor remarks found for this LOA in any linked sheet.</p>
          </div>
          <div v-else>
            <p class="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-4">
              {{ selectedWork.entries.length }} entr{{ selectedWork.entries.length === 1 ? 'y' : 'ies' }}
            </p>
            <div class="rounded-xl border border-gray-200 overflow-hidden">
              <table class="w-full text-sm min-w-[800px]">
                <thead>
                  <tr class="bg-gray-50 border-b border-gray-200">
                    <th class="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wide whitespace-nowrap">Date & Time</th>
                    <th class="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wide">Schedule</th>
                    <th class="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wide">Serial No.</th>
                    <th class="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wide">Item Description</th>
                    <th class="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wide">Contractor Remark</th>
                    <th class="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wide">Status</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(entry, idx) in selectedWork.entries" :key="idx"
                    class="border-t border-gray-100 hover:bg-accent-soft/40 transition-colors"
                    :class="entry.warnings.length > 0 ? 'bg-amber-50/40' : ''">
                    <td class="px-4 py-3 font-mono text-xs text-gray-500 whitespace-nowrap">{{ entry.datetime }}</td>
                    <td class="px-4 py-3 font-semibold text-gray-800">{{ entry.schedule }}</td>
                    <td class="px-4 py-3 text-gray-700">{{ entry.serial_no }}</td>
                    <td class="px-4 py-3 max-w-xs">
                      <span class="text-xs text-gray-600 line-clamp-2">{{ entry.item_desc }}</span>
                    </td>
                    <td class="px-4 py-3 max-w-xs">
                      <span class="text-sm text-gray-700 line-clamp-2">{{ entry.remark || '—' }}</span>
                    </td>
                    <td class="px-4 py-3">
                      <span v-if="entry.warnings.length === 0"
                        class="text-[11px] font-semibold text-green-600 bg-green-50 px-2 py-0.5 rounded-full">Valid</span>
                      <div v-else class="flex flex-col gap-1">
                        <span v-for="(w, wi) in entry.warnings" :key="wi"
                          class="text-[11px] font-semibold text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full flex items-center gap-1 whitespace-nowrap">
                          <span class="i-carbon-warning-filled text-[10px]"></span>{{ w }}
                        </span>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- ── ITEM-WISE VIEW ─────────────────────────────────────────── -->
        <div v-if="viewMode === 'item'" class="overflow-y-auto flex-1">
          <table class="w-full border-collapse">
            <thead class="bg-gray-50 sticky top-0 z-10">
              <tr class="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
                <th class="px-4 py-3 text-center w-14">Sch</th>
                <th class="px-4 py-3 text-center w-14">S.No</th>
                <th class="px-4 py-3 text-left">Item Description</th>
                <th class="px-4 py-3 text-right w-32">Required</th>
                <th class="px-4 py-3 text-center w-32">Site Remarks</th>
                <th class="px-4 py-3 text-center w-28">Action</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="itemsWithEntries.length === 0">
                <td colspan="6" class="p-8 text-center text-gray-400 text-xs font-medium">No items for this work.</td>
              </tr>
              <tr v-for="item in itemsWithEntries" :key="item.id"
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
                  <span class="text-sm font-bold"
                    :class="item.sheet_entries.length > 0 ? 'text-[#1D5F5E]' : 'text-gray-300'">
                    {{ item.sheet_entries.length }}
                  </span>
                  <p class="text-[10px] text-gray-400">remark{{ item.sheet_entries.length !== 1 ? 's' : '' }}</p>
                </td>
                <td class="px-4 py-3.5 text-center">
                  <button @click="selectItem(item)"
                    class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#1D5F5E]/10 hover:bg-[#1D5F5E]/20 text-[#1D5F5E] text-[11px] font-semibold transition-all">
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
