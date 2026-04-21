<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const fmtDate = (val) => {
  if (!val) return '—'
  return String(val).split(' ')[0].split('T')[0]
}
const fmtDateTime = (val) => {
  if (!val) return '—'
  const d = new Date(val)
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}
const progressPct = (item) => {
  const total = item.supplied_quantity || 0
  const req   = item.qty || 0
  if (!req) return 0
  return Math.min(Math.round((total / req) * 100), 999)
}

// ── State ──────────────────────────────────────────────────────────────────
const allWorks     = ref([])
const selectedWork = ref(null)
const isLoading    = ref(true)
const searchQuery  = ref('')
const itemFilter   = ref('')
const expandedId   = ref(null)   // which item's entry history is open

// ── Load ──────────────────────────────────────────────────────────────────
const loadWorks = async () => {
  isLoading.value = true
  try {
    const res = await axios.get('/api/work-details/search/')
    allWorks.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    isLoading.value = false
  }
}
onMounted(loadWorks)

// ── Filtering ─────────────────────────────────────────────────────────────
const filteredWorks = computed(() => {
  if (!searchQuery.value.trim()) return allWorks.value
  const q = searchQuery.value.toLowerCase()
  return allWorks.value.filter(w =>
    (w.loa_number      && w.loa_number.toLowerCase().includes(q)) ||
    (w.contractor_name && w.contractor_name.toLowerCase().includes(q)) ||
    (w.tender_number   && w.tender_number.toLowerCase().includes(q)) ||
    (w.consignee       && w.consignee.toLowerCase().includes(q))
  )
})

const filteredItems = computed(() => {
  if (!selectedWork.value) return []
  if (!itemFilter.value.trim()) return selectedWork.value.items
  const q = itemFilter.value.toLowerCase()
  return selectedWork.value.items.filter(i =>
    (i.schedule  && i.schedule.toLowerCase().includes(q)) ||
    (i.item_desc && i.item_desc.toLowerCase().includes(q))
  )
})

// ── Summary stats for selected work ───────────────────────────────────────
const workStats = computed(() => {
  if (!selectedWork.value) return null
  const items = selectedWork.value.items
  let supplyTotal = 0, supplyDone = 0, supplyCount = 0
  let execTotal = 0,   execDone = 0,   execCount = 0

  for (const i of items) {
    const sch = String(i.schedule || '').toUpperCase().trim()
    const req  = i.qty || 0
    const done = i.supplied_quantity || 0
    if (sch.startsWith('A')) {
      supplyTotal += req; supplyDone += done; supplyCount++
    } else if (sch.startsWith('B')) {
      execTotal += req; execDone += done; execCount++
    }
  }

  const pct = (done, total) => total > 0 ? Math.round((done / total) * 100) : 0
  return {
    supplyPct: pct(supplyDone, supplyTotal),
    execPct:   pct(execDone, execTotal),
    supplyCount, execCount,
    totalEntries: items.reduce((s, i) => s + (i.entries || []).length, 0),
  }
})

// ── Sorting ────────────────────────────────────────────────────────────────
const sortKey = ref('')
const sortDir = ref('desc')

const toggleSort = (key) => {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'desc'
  }
}

const sortIcon = (key) => {
  if (sortKey.value !== key) return 'i-carbon-arrows-vertical'
  return sortDir.value === 'asc' ? 'i-carbon-arrow-up' : 'i-carbon-arrow-down'
}

const sortedItems = computed(() => {
  if (!sortKey.value) return filteredItems.value
  return [...filteredItems.value].sort((a, b) => {
    let av, bv
    if      (sortKey.value === 'qty')       { av = a.qty || 0;               bv = b.qty || 0 }
    else if (sortKey.value === 'submitted') { av = a.supplied_quantity || 0; bv = b.supplied_quantity || 0 }
    else if (sortKey.value === 'progress')  { av = progressPct(a);           bv = progressPct(b) }
    else if (sortKey.value === 'entries')   { av = (a.entries||[]).length;   bv = (b.entries||[]).length }
    return sortDir.value === 'asc' ? av - bv : bv - av
  })
})

const selectWork = (work) => {
  itemFilter.value   = ''
  expandedId.value   = null
  sortKey.value      = ''
  selectedWork.value = work
}

const toggleExpand = (itemId) => {
  expandedId.value = expandedId.value === itemId ? null : itemId
}
</script>

<template>
  <div class="bg-white rounded-2xl soft-shadow h-full w-full flex flex-col overflow-hidden">

    <!-- ══ WORK LIST ══════════════════════════════════════════════════ -->
    <template v-if="!selectedWork">

      <div class="flex-shrink-0 px-8 pt-7 pb-5 border-b border-gray-100">
        <h1 class="text-2xl font-bold text-gray-900 tracking-tight mb-1">Work Details</h1>
        <p class="text-gray-400 text-sm font-medium mb-5">Browse all works and inspect item-level lot entry history.</p>

        <div class="flex items-center bg-gray-50 border border-gray-200 rounded-2xl px-5 py-3 focus-within:ring-2 focus-within:ring-[#0071e3]/20 focus-within:border-[#0071e3] focus-within:bg-white transition-all">
          <div class="i-carbon-search text-gray-400 text-base mr-3 flex-shrink-0"></div>
          <input v-model="searchQuery" type="text"
            placeholder="Search by LOA, Contractor, Tender, Consignee..."
            class="bg-transparent outline-none w-full text-gray-700 font-medium placeholder-gray-400 text-sm">
          <button v-if="searchQuery" @click="searchQuery = ''" class="ml-2 text-gray-300 hover:text-gray-500 transition-colors">
            <div class="i-carbon-close text-sm"></div>
          </button>
        </div>
      </div>

      <div v-if="isLoading" class="flex-1 flex items-center justify-center py-24">
        <div class="i-carbon-circle-dash animate-spin text-3xl text-[#0071e3]"></div>
      </div>

      <div v-else-if="filteredWorks.length === 0" class="flex-1 flex flex-col items-center justify-center py-24 text-center">
        <div class="i-carbon-document-unknown text-5xl text-gray-200 mb-4"></div>
        <p class="text-sm font-semibold text-gray-400">
          {{ searchQuery ? 'No works match your search.' : 'No works uploaded yet.' }}
        </p>
      </div>

      <template v-else>
        <div class="flex-1 overflow-auto">
          <table class="w-full text-left border-collapse">
            <thead class="sticky top-0 z-10">
              <tr class="bg-gray-50 text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
                <th class="px-6 py-3">Contractor / LOA</th>
                <th class="px-4 py-3">Tender</th>
                <th class="px-4 py-3">Consignee</th>
                <th class="px-4 py-3">Completion</th>
                <th class="px-4 py-3 text-right">Items</th>
                <th class="px-4 py-3 text-right">Total Entries</th>
                <th class="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="work in filteredWorks" :key="work.id" class="hover:bg-gray-50/70 transition-colors">
                <td class="px-6 py-4">
                  <p class="text-sm font-semibold text-gray-900">{{ work.contractor_name || '—' }}</p>
                  <span class="mt-1 inline-block text-[11px] font-semibold text-[#0071e3] bg-[#0071e3]/10 px-2 py-0.5 rounded-full">
                    {{ work.loa_number || '—' }}
                  </span>
                </td>
                <td class="px-4 py-4 text-xs font-medium text-gray-600 max-w-[180px]">
                  <p class="truncate">{{ work.tender_number || '—' }}</p>
                </td>
                <td class="px-4 py-4 text-xs font-medium text-gray-600">{{ work.consignee || '—' }}</td>
                <td class="px-4 py-4 text-xs font-medium text-gray-600 whitespace-nowrap">{{ fmtDate(work.date_of_completion) }}</td>
                <td class="px-4 py-4 text-right text-xs font-semibold text-gray-700">{{ work.items.length }}</td>
                <td class="px-4 py-4 text-right text-xs font-semibold text-gray-700">
                  {{ work.items.reduce((s, i) => s + (i.entries || []).length, 0) }}
                </td>
                <td class="px-4 py-4 text-right">
                  <button @click="selectWork(work)"
                    class="px-3.5 py-2 rounded-full bg-dark-active text-white text-xs font-semibold shadow shadow-black/20 hover:shadow-md hover:-translate-y-0.5 transition-all flex items-center gap-1 ml-auto">
                    View Details <div class="i-carbon-chevron-right text-xs"></div>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="px-6 py-3 border-t border-gray-100 bg-gray-50 rounded-b-2xl">
          <p class="text-[11px] text-gray-400 font-medium">
            {{ filteredWorks.length }} {{ filteredWorks.length === 1 ? 'work' : 'works' }}
            <template v-if="searchQuery"> matching "{{ searchQuery }}"</template>
          </p>
        </div>
      </template>

    </template>

    <!-- ══ WORK DETAIL VIEW ══════════════════════════════════════════ -->
    <template v-else>
      <div class="flex flex-col h-full animate-fade-in">

        <!-- Header -->
        <div class="px-8 pt-6 pb-5 border-b border-gray-100">
          <div class="flex items-start justify-between gap-6">
            <div class="flex items-start gap-4 min-w-0">
              <button @click="selectedWork = null"
                class="mt-0.5 w-9 h-9 flex-shrink-0 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 transition-all">
                <div class="i-carbon-arrow-left text-base"></div>
              </button>
              <div class="min-w-0">
                <h2 class="text-xl font-bold text-gray-900 truncate">{{ selectedWork.contractor_name }}</h2>
                <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 mt-2 text-xs text-gray-500">
                  <span><span class="text-gray-400 font-medium">LOA</span> <span class="font-semibold text-gray-800">{{ selectedWork.loa_number || '—' }}</span></span>
                  <span class="text-gray-200">·</span>
                  <span><span class="text-gray-400 font-medium">Tender</span> <span class="font-semibold text-gray-800">{{ selectedWork.tender_number || '—' }}</span></span>
                  <span class="text-gray-200">·</span>
                  <span><span class="text-gray-400 font-medium">Consignee</span> <span class="font-semibold text-gray-800">{{ selectedWork.consignee || '—' }}</span></span>
                  <span class="text-gray-200">·</span>
                  <span><span class="text-gray-400 font-medium">Completion</span> <span class="font-semibold text-gray-800">{{ fmtDate(selectedWork.date_of_completion) }}</span></span>
                </div>
              </div>
            </div>
            <!-- Item filter -->
            <div class="flex-shrink-0 flex items-center bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 w-52 focus-within:ring-2 focus-within:ring-[#0071e3]/20 focus-within:border-[#0071e3] transition-all">
              <div class="i-carbon-filter text-gray-400 mr-2 text-sm"></div>
              <input v-model="itemFilter" type="text" placeholder="Filter items..."
                class="bg-transparent outline-none w-full text-xs text-gray-700 placeholder-gray-400 font-medium">
            </div>
          </div>

          <!-- Quick stats pills -->
          <div v-if="workStats" class="mt-5 flex flex-wrap gap-3">
            <div class="flex items-center gap-2 bg-blue-50 border border-blue-100 rounded-xl px-4 py-2">
              <div class="w-2 h-2 rounded-full bg-[#0071e3]"></div>
              <span class="text-xs font-semibold text-blue-700">Supply (Sch A): {{ workStats.supplyPct }}%</span>
            </div>
            <div class="flex items-center gap-2 bg-green-50 border border-green-100 rounded-xl px-4 py-2">
              <div class="w-2 h-2 rounded-full bg-[#34c759]"></div>
              <span class="text-xs font-semibold text-green-700">Execution (Sch B): {{ workStats.execPct }}%</span>
            </div>
            <div class="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-4 py-2">
              <div class="i-carbon-list text-gray-400 text-sm"></div>
              <span class="text-xs font-semibold text-gray-600">{{ workStats.totalEntries }} total lot entries</span>
            </div>
          </div>
        </div>

        <!-- Items table -->
        <div class="overflow-y-auto flex-1">
          <table class="w-full border-collapse">
            <thead class="bg-gray-50 sticky top-0 z-10">
              <tr class="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
                <th class="px-4 py-3 text-center w-14">Sch</th>
                <th class="px-4 py-3 text-center w-14">S.No</th>
                <th class="px-4 py-3 text-left">Item Description</th>
                <th @click="toggleSort('qty')" class="px-4 py-3 text-right w-28 cursor-pointer select-none hover:text-gray-600 transition-colors">
                  <div class="flex items-center justify-end gap-1">Required <div :class="sortIcon('qty')" class="text-[9px]" :style="{ opacity: sortKey === 'qty' ? 1 : 0.35 }"></div></div>
                </th>
                <th @click="toggleSort('submitted')" class="px-4 py-3 text-right w-28 cursor-pointer select-none hover:text-gray-600 transition-colors">
                  <div class="flex items-center justify-end gap-1">Submitted <div :class="sortIcon('submitted')" class="text-[9px]" :style="{ opacity: sortKey === 'submitted' ? 1 : 0.35 }"></div></div>
                </th>
                <th @click="toggleSort('progress')" class="px-4 py-3 w-36 cursor-pointer select-none hover:text-gray-600 transition-colors">
                  <div class="flex items-center gap-1">Progress <div :class="sortIcon('progress')" class="text-[9px]" :style="{ opacity: sortKey === 'progress' ? 1 : 0.35 }"></div></div>
                </th>
                <th @click="toggleSort('entries')" class="px-4 py-3 text-center w-24 cursor-pointer select-none hover:text-gray-600 transition-colors">
                  <div class="flex items-center justify-center gap-1">Entries <div :class="sortIcon('entries')" class="text-[9px]" :style="{ opacity: sortKey === 'entries' ? 1 : 0.35 }"></div></div>
                </th>
              </tr>
            </thead>
            <tbody>
              <template v-if="filteredItems.length === 0">
                <tr><td colspan="7" class="p-8 text-center text-gray-400 text-xs font-medium">No items match your filter.</td></tr>
              </template>

              <template v-for="item in sortedItems" :key="item.id">
                <!-- Main item row -->
                <tr
                  class="border-b border-gray-100 hover:bg-gray-50/60 transition-colors cursor-pointer"
                  :class="expandedId === item.id ? 'bg-gray-50/80' : ''"
                  @click="toggleExpand(item.id)"
                >
                  <td class="px-4 py-3 text-center">
                    <span class="bg-gray-100 text-gray-600 rounded-md px-2 py-1 text-[10px] font-bold">{{ item.schedule }}</span>
                  </td>
                  <td class="px-4 py-3 text-center text-[11px] text-gray-500 font-semibold">{{ item.serial_number }}</td>
                  <td class="px-4 py-3">
                    <p class="text-xs font-medium text-gray-800 line-clamp-2 leading-relaxed">{{ item.item_desc }}</p>
                  </td>
                  <td class="px-4 py-3 text-right text-xs font-semibold text-gray-600">
                    {{ item.qty }} <span class="text-gray-400 font-normal">{{ item.unit }}</span>
                  </td>
                  <td class="px-4 py-3 text-right text-xs font-semibold"
                    :class="(item.supplied_quantity || 0) > (item.qty || 0) ? 'text-orange-500' : 'text-gray-800'">
                    {{ item.supplied_quantity || 0 }}
                    <span class="text-gray-400 font-normal">{{ item.unit }}</span>
                    <span v-if="(item.supplied_quantity || 0) > (item.qty || 0)"
                      class="ml-1 text-[9px] text-orange-400 font-bold">OVER</span>
                  </td>
                  <td class="px-4 py-3">
                    <div class="flex items-center gap-2">
                      <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div class="h-full rounded-full transition-all duration-500"
                          :class="progressPct(item) > 100 ? 'bg-orange-400' : 'bg-[#0071e3]'"
                          :style="{ width: Math.min(progressPct(item), 100) + '%' }">
                        </div>
                      </div>
                      <span class="text-[10px] font-bold w-8 text-right"
                        :class="progressPct(item) > 100 ? 'text-orange-500' : 'text-gray-500'">
                        {{ progressPct(item) }}%
                      </span>
                    </div>
                  </td>
                  <td class="px-4 py-3 text-center">
                    <div class="flex items-center justify-center gap-1">
                      <span class="text-[11px] font-bold"
                        :class="(item.entries||[]).length > 0 ? 'text-[#0071e3]' : 'text-gray-300'">
                        {{ (item.entries || []).length }}
                      </span>
                      <div :class="expandedId === item.id ? 'i-carbon-chevron-up text-gray-400' : 'i-carbon-chevron-down text-gray-300'" class="text-xs"></div>
                    </div>
                  </td>
                </tr>

                <!-- Expanded entry history -->
                <tr v-if="expandedId === item.id">
                  <td colspan="7" class="bg-gray-50/60 border-b border-gray-100 px-6 py-4">

                    <div v-if="(item.entries || []).length === 0"
                      class="text-center py-4 text-xs text-gray-400 font-medium bg-white rounded-xl border border-dashed border-gray-200">
                      No lot entries recorded for this item yet.
                    </div>

                    <div v-else class="bg-white rounded-2xl border border-gray-200 overflow-hidden shadow-sm">
                      <div class="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
                        <div class="i-carbon-list text-gray-400 text-sm"></div>
                        <h4 class="text-xs font-bold text-gray-600 uppercase tracking-wide">
                          Lot History — {{ item.entries.length }} {{ item.entries.length === 1 ? 'entry' : 'entries' }}
                        </h4>
                      </div>
                      <table class="w-full text-xs">
                        <thead class="bg-gray-50 text-[10px] text-gray-400 font-bold uppercase tracking-widest">
                          <tr>
                            <th class="px-4 py-2 text-left w-8">#</th>
                            <th class="px-4 py-2 text-right w-28">Quantity</th>
                            <th class="px-4 py-2 text-left">Challan No.</th>
                            <th class="px-4 py-2 text-left">UDM Entry</th>
                            <th class="px-4 py-2 text-left">Submitted By</th>
                            <th class="px-4 py-2 text-left">Date & Time</th>
                          </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-50">
                          <tr v-for="(entry, idx) in item.entries" :key="entry.id"
                            class="hover:bg-gray-50/50 transition-colors">
                            <td class="px-4 py-2.5 text-gray-400 font-semibold">{{ idx + 1 }}</td>
                            <td class="px-4 py-2.5 text-right font-bold text-gray-800">
                              {{ entry.quantity }} <span class="text-gray-400 font-normal">{{ item.unit }}</span>
                            </td>
                            <td class="px-4 py-2.5 text-gray-600 font-medium">{{ entry.challan_no || '—' }}</td>
                            <td class="px-4 py-2.5 text-gray-600 font-medium">{{ entry.udm_entry || '—' }}</td>
                            <td class="px-4 py-2.5 text-gray-600 font-medium">{{ entry.submitted_by_user?.username || '—' }}</td>
                            <td class="px-4 py-2.5 text-gray-400">{{ fmtDateTime(entry.submitted_at) }}</td>
                          </tr>
                        </tbody>
                        <tfoot class="bg-gray-50 border-t border-gray-100">
                          <tr>
                            <td class="px-4 py-2.5 text-[10px] font-bold text-gray-400 uppercase tracking-wide">Total</td>
                            <td class="px-4 py-2.5 text-right font-bold text-gray-800 text-xs">
                              {{ item.supplied_quantity || 0 }} <span class="text-gray-400 font-normal">{{ item.unit }}</span>
                              <span v-if="(item.supplied_quantity || 0) > (item.qty || 0)"
                                class="ml-1 text-[9px] font-bold text-orange-500">EXCEEDS SCHEDULE</span>
                            </td>
                            <td colspan="4"></td>
                          </tr>
                        </tfoot>
                      </table>
                    </div>

                  </td>
                </tr>

              </template>
            </tbody>
          </table>
        </div>

      </div>
    </template>

  </div>
</template>

<style scoped>
@keyframes fade-in { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
.animate-fade-in { animation: fade-in 0.3s cubic-bezier(.4,0,.2,1); }
</style>
