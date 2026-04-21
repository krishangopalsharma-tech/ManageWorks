<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'

const allWorks      = ref([])
const searchResults = ref([])
const isLoadingWorks = ref(true)
const isSearching   = ref(false)
const itemSearch    = ref('')
const workSearch    = ref('')
const selectedIds   = ref([])
const dropdownOpen  = ref(false)
const dropdownRef   = ref(null)

// ── Hover tooltip ──────────────────────────────────────────────────────────
const hoveredItem = ref(null)
const tooltipPos  = ref({ x: 0, y: 0 })
let hideTimer = null

const showTooltip = (item, e) => { clearTimeout(hideTimer); hoveredItem.value = item; tooltipPos.value = { x: e.clientX, y: e.clientY } }
const moveTooltip = (e) => { tooltipPos.value = { x: e.clientX, y: e.clientY } }
const hideTooltip = () => { hideTimer = setTimeout(() => { hoveredItem.value = null }, 120) }
const keepTooltip = () => { clearTimeout(hideTimer) }

const fmtDateTime = (val) => {
  if (!val) return '—'
  const d = new Date(val)
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// ── Load works list ────────────────────────────────────────────────────────
const loadWorks = async () => {
  isLoadingWorks.value = true
  try {
    const res = await axios.get('/api/item-progress/works/')
    allWorks.value    = res.data
    selectedIds.value = res.data.map(w => w.id)
  } catch (e) {
    console.error(e)
  } finally {
    isLoadingWorks.value = false
  }
}

// ── Item search ────────────────────────────────────────────────────────────
let debounceTimer = null
const doSearch = async () => {
  const q = itemSearch.value.trim()
  if (!q) { searchResults.value = []; return }
  isSearching.value = true
  try {
    const params = { q }
    if (selectedIds.value.length && selectedIds.value.length < allWorks.value.length)
      params.work_ids = selectedIds.value.join(',')
    const res = await axios.get('/api/item-progress/search/', { params })
    searchResults.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    isSearching.value = false
  }
}

watch(itemSearch, () => {
  clearTimeout(debounceTimer)
  if (!itemSearch.value.trim()) { searchResults.value = []; return }
  debounceTimer = setTimeout(doSearch, 350)
})
watch(selectedIds, () => {
  if (itemSearch.value.trim()) { clearTimeout(debounceTimer); debounceTimer = setTimeout(doSearch, 200) }
}, { deep: true })

const closeDropdown = (e) => { if (dropdownRef.value && !dropdownRef.value.contains(e.target)) dropdownOpen.value = false }
onMounted(() => { loadWorks(); document.addEventListener('click', closeDropdown) })
onBeforeUnmount(() => { document.removeEventListener('click', closeDropdown); clearTimeout(debounceTimer) })

// ── Dropdown helpers ───────────────────────────────────────────────────────
const filteredWorksDropdown = computed(() => {
  const q = workSearch.value.toLowerCase().trim()
  if (!q) return allWorks.value
  return allWorks.value.filter(w =>
    (w.loa_number      && w.loa_number.toLowerCase().includes(q)) ||
    (w.contractor_name && w.contractor_name.toLowerCase().includes(q)) ||
    (w.tender_number   && w.tender_number.toLowerCase().includes(q))
  )
})
const allSelected = computed(() => selectedIds.value.length === allWorks.value.length)
const dropdownLabel = computed(() => {
  if (allSelected.value) return 'All Works'
  const n = selectedIds.value.length
  if (n === 0) return 'No works selected'
  if (n === 1) { const w = allWorks.value.find(w => w.id === selectedIds.value[0]); return w?.loa_number || w?.contractor_name || '1 work' }
  return `${n} works selected`
})
const toggleWork = (id) => {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

// ── Progress helpers ───────────────────────────────────────────────────────
const isSchB = (item) => String(item.schedule || '').toUpperCase().trim().startsWith('B')

// Sch-A progress = supply entries; Sch-B progress = execution entries
const progressPct = (item) => {
  const req  = item.qty || 0
  if (!req) return 0
  const done = isSchB(item) ? (item.executed_quantity || 0) : (item.supplied_quantity || 0)
  return Math.min(Math.round((done / req) * 100), 999)
}

// ── Cumulative stats ───────────────────────────────────────────────────────
const stats = computed(() => {
  let supplyTotal = 0, supplyDone = 0, supplyCount = 0
  let execTotal   = 0, execDone   = 0, execCount   = 0
  for (const item of searchResults.value) {
    const req = item.qty || 0
    if (!isSchB(item)) {
      supplyTotal += req; supplyDone += item.supplied_quantity || 0; supplyCount++
    } else {
      execTotal += req; execDone += item.executed_quantity || 0; execCount++
    }
  }
  const pct = (d, t) => t > 0 ? Math.round(d / t * 100) : 0
  return { supplyPct: pct(supplyDone, supplyTotal), execPct: pct(execDone, execTotal), supplyCount, execCount }
})

// ── Sorting ────────────────────────────────────────────────────────────────
const sortKey = ref('')
const sortDir = ref('desc')
const toggleSort = (key) => {
  if (sortKey.value === key) { sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc' }
  else { sortKey.value = key; sortDir.value = 'desc' }
}
const sortIcon = (key) => {
  if (sortKey.value !== key) return 'i-carbon-arrows-vertical'
  return sortDir.value === 'asc' ? 'i-carbon-arrow-up' : 'i-carbon-arrow-down'
}
const sortedResults = computed(() => {
  if (!sortKey.value) return searchResults.value
  return [...searchResults.value].sort((a, b) => {
    let av, bv
    if      (sortKey.value === 'qty')       { av = a.qty || 0;               bv = b.qty || 0 }
    else if (sortKey.value === 'submitted') { av = a.supplied_quantity || 0; bv = b.supplied_quantity || 0 }
    else if (sortKey.value === 'progress')  { av = progressPct(a);           bv = progressPct(b) }
    else if (sortKey.value === 'entries')   { av = (a.entries||[]).length;   bv = (b.entries||[]).length }
    return sortDir.value === 'asc' ? av - bv : bv - av
  })
})
</script>

<template>
  <div class="bg-white rounded-2xl soft-shadow h-full w-full flex flex-col overflow-hidden">

    <!-- Header -->
    <div class="flex-shrink-0 px-8 pt-7 pb-5 border-b border-gray-100">
      <h1 class="text-2xl font-bold text-gray-900 tracking-tight mb-1">Item Progress</h1>
      <p class="text-gray-400 text-sm font-medium mb-5">Search and filter individual item progress across works.</p>

      <!-- Filters -->
      <div class="flex gap-3">
        <!-- Item search -->
        <div class="flex-1 flex items-center bg-gray-50 border border-gray-200 rounded-2xl px-5 py-3 focus-within:ring-2 focus-within:ring-[#0071e3]/20 focus-within:border-[#0071e3] focus-within:bg-white transition-all">
          <div v-if="isSearching" class="i-carbon-circle-dash animate-spin text-gray-400 text-base mr-3 flex-shrink-0"></div>
          <div v-else class="i-carbon-search text-gray-400 text-base mr-3 flex-shrink-0"></div>
          <input v-model="itemSearch" type="text"
            placeholder="Search items by description, schedule, serial no..."
            class="bg-transparent outline-none w-full text-gray-700 font-medium placeholder-gray-400 text-sm">
          <button v-if="itemSearch" @click="itemSearch = ''" class="ml-2 text-gray-300 hover:text-gray-500 transition-colors">
            <div class="i-carbon-close text-sm"></div>
          </button>
        </div>

        <!-- Work multi-select dropdown -->
        <div class="relative w-72 flex-shrink-0" ref="dropdownRef">
          <button @click.stop="dropdownOpen = !dropdownOpen"
            class="w-full flex items-center justify-between bg-gray-50 border border-gray-200 rounded-2xl px-5 py-3 text-sm font-medium text-gray-700 hover:border-[#0071e3] hover:bg-white transition-all">
            <div class="flex items-center gap-2 min-w-0">
              <div class="i-carbon-filter text-gray-400 text-base flex-shrink-0"></div>
              <span class="truncate">{{ isLoadingWorks ? 'Loading...' : dropdownLabel }}</span>
            </div>
            <div :class="dropdownOpen ? 'i-carbon-chevron-up' : 'i-carbon-chevron-down'" class="text-gray-400 text-sm flex-shrink-0 ml-2"></div>
          </button>

          <div v-if="dropdownOpen"
            class="absolute top-full mt-2 right-0 w-80 bg-white rounded-2xl border border-gray-200 shadow-xl z-50 overflow-hidden">
            <div class="p-3 border-b border-gray-100">
              <div class="flex items-center bg-gray-50 rounded-xl px-3 py-2 gap-2">
                <div class="i-carbon-search text-gray-400 text-sm"></div>
                <input v-model="workSearch" type="text" placeholder="Search works..."
                  class="bg-transparent outline-none text-xs text-gray-700 w-full placeholder-gray-400 font-medium" @click.stop>
              </div>
            </div>
            <div class="px-4 py-2 border-b border-gray-100 flex gap-3">
              <button @click="selectedIds = allWorks.map(w => w.id)" class="text-xs font-semibold text-[#0071e3] hover:underline">Select All</button>
              <span class="text-gray-200">·</span>
              <button @click="selectedIds = []" class="text-xs font-semibold text-gray-400 hover:text-gray-600 hover:underline">Clear All</button>
            </div>
            <div class="max-h-60 overflow-y-auto" style="scrollbar-width: thin;">
              <div v-if="filteredWorksDropdown.length === 0" class="px-4 py-6 text-center text-xs text-gray-400">No works found</div>
              <label v-for="work in filteredWorksDropdown" :key="work.id"
                class="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors border-b border-gray-50 last:border-0">
                <input type="checkbox" :checked="selectedIds.includes(work.id)" @change="toggleWork(work.id)"
                  class="mt-0.5 accent-[#0071e3] flex-shrink-0" @click.stop>
                <div class="min-w-0">
                  <p class="text-xs font-semibold text-gray-800 truncate">{{ work.loa_number || '—' }}</p>
                  <p class="text-[11px] text-gray-400 truncate">{{ work.contractor_name || '—' }}</p>
                </div>
              </label>
            </div>
          </div>
        </div>
      </div>

      <!-- Progress stats pills -->
      <div v-if="searchResults.length > 0" class="mt-4 flex flex-wrap gap-3">
        <div class="flex items-center gap-2 bg-blue-50 border border-blue-100 rounded-xl px-4 py-2">
          <div class="w-2 h-2 rounded-full bg-[#0071e3]"></div>
          <span class="text-xs font-semibold text-blue-700">
            Supply (Sch A): {{ stats.supplyPct }}%
            <span class="font-normal opacity-70">({{ stats.supplyCount }} items)</span>
          </span>
        </div>
        <div class="flex items-center gap-2 bg-green-50 border border-green-100 rounded-xl px-4 py-2">
          <div class="w-2 h-2 rounded-full bg-[#34c759]"></div>
          <span class="text-xs font-semibold text-green-700">
            Execution (Sch B): {{ stats.execPct }}%
            <span class="font-normal opacity-70">({{ stats.execCount }} items)</span>
          </span>
        </div>
        <div class="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-4 py-2">
          <div class="i-carbon-list text-gray-400 text-sm"></div>
          <span class="text-xs font-semibold text-gray-600">{{ searchResults.length }} items found</span>
        </div>
      </div>
    </div>

    <!-- Empty / prompt state -->
    <div v-if="!isSearching && searchResults.length === 0" class="flex-1 flex flex-col items-center justify-center py-24 text-center">
      <div class="i-carbon-search text-5xl text-gray-200 mb-4"></div>
      <p class="text-sm font-semibold text-gray-400">
        {{ !itemSearch.trim() ? 'Type in the search box above to find items.' : 'No items match your search.' }}
      </p>
      <p v-if="!itemSearch.trim()" class="text-xs text-gray-300 mt-1">e.g. "switch", "cable", "transformer"</p>
    </div>

    <!-- Table -->
    <div v-else-if="searchResults.length > 0" class="overflow-auto flex-1">
      <table class="w-full border-collapse">
        <thead class="bg-gray-50 sticky top-0 z-10">
          <tr class="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
            <th class="px-4 py-3 text-left w-36">LOA Number</th>
            <th class="px-4 py-3 text-center w-14">Sch</th>
            <th class="px-4 py-3 text-center w-14">S.No</th>
            <th class="px-4 py-3 text-left">Item Description</th>
            <th @click="toggleSort('qty')" class="px-4 py-3 text-right w-28 cursor-pointer select-none hover:text-gray-600 transition-colors">
              <div class="flex items-center justify-end gap-1">Required <div :class="sortIcon('qty')" class="text-[9px]" :style="{ opacity: sortKey === 'qty' ? 1 : 0.35 }"></div></div>
            </th>
            <th @click="toggleSort('submitted')" class="px-4 py-3 text-right w-28 cursor-pointer select-none hover:text-gray-600 transition-colors">
              <div class="flex items-center justify-end gap-1">Supplied <div :class="sortIcon('submitted')" class="text-[9px]" :style="{ opacity: sortKey === 'submitted' ? 1 : 0.35 }"></div></div>
            </th>
            <th @click="toggleSort('progress')" class="px-4 py-3 w-36 cursor-pointer select-none hover:text-gray-600 transition-colors">
              <div class="flex items-center gap-1">Progress <div :class="sortIcon('progress')" class="text-[9px]" :style="{ opacity: sortKey === 'progress' ? 1 : 0.35 }"></div></div>
            </th>
            <th @click="toggleSort('entries')" class="px-4 py-3 text-center w-20 cursor-pointer select-none hover:text-gray-600 transition-colors">
              <div class="flex items-center justify-center gap-1">Entries <div :class="sortIcon('entries')" class="text-[9px]" :style="{ opacity: sortKey === 'entries' ? 1 : 0.35 }"></div></div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in sortedResults" :key="item.id"
            class="border-b border-gray-100 hover:bg-gray-50/60 transition-colors">
            <td class="px-4 py-3">
              <span class="text-[11px] font-semibold text-[#0071e3] bg-[#0071e3]/10 px-2 py-0.5 rounded-full whitespace-nowrap">
                {{ item.loa_number || '—' }}
              </span>
            </td>
            <td class="px-4 py-3 text-center">
              <span class="rounded-md px-2 py-1 text-[10px] font-bold"
                :class="isSchB(item) ? 'bg-green-50 text-green-700' : 'bg-blue-50 text-blue-600'">
                {{ item.schedule }}
              </span>
            </td>
            <td class="px-4 py-3 text-center text-[11px] text-gray-500 font-semibold">{{ item.serial_number }}</td>
            <td class="px-4 py-3">
              <p class="text-xs font-medium text-gray-800 line-clamp-2 leading-relaxed">{{ item.item_desc }}</p>
            </td>
            <td class="px-4 py-3 text-right text-xs font-semibold text-gray-600">
              {{ item.qty }} <span class="text-gray-400 font-normal">{{ item.unit }}</span>
            </td>
            <td class="px-4 py-3 text-right text-xs font-semibold cursor-help"
              :class="(item.supplied_quantity || 0) > (item.qty || 0) ? 'text-orange-500' : 'text-gray-800'"
              @mouseenter="showTooltip(item, $event)" @mousemove="moveTooltip($event)" @mouseleave="hideTooltip">
              {{ item.supplied_quantity || 0 }}
              <span class="text-gray-400 font-normal">{{ item.unit }}</span>
              <span v-if="(item.supplied_quantity || 0) > (item.qty || 0)" class="ml-1 text-[9px] text-orange-400 font-bold">OVER</span>
            </td>
            <td class="px-4 py-3 cursor-help"
              @mouseenter="showTooltip(item, $event)" @mousemove="moveTooltip($event)" @mouseleave="hideTooltip">
              <div class="flex items-center gap-2">
                <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div class="h-full rounded-full transition-all duration-500"
                    :class="progressPct(item) > 100 ? 'bg-orange-400' : (isSchB(item) ? 'bg-[#34c759]' : 'bg-[#0071e3]')"
                    :style="{ width: Math.min(progressPct(item), 100) + '%' }">
                  </div>
                </div>
                <span class="text-[10px] font-bold w-8 text-right"
                  :class="progressPct(item) > 100 ? 'text-orange-500' : 'text-gray-500'">
                  {{ progressPct(item) }}%
                </span>
              </div>
            </td>
            <td class="px-4 py-3 text-center cursor-help"
              @mouseenter="showTooltip(item, $event)" @mousemove="moveTooltip($event)" @mouseleave="hideTooltip">
              <span class="text-[11px] font-bold"
                :class="(item.entries||[]).length > 0 ? 'text-[#0071e3]' : 'text-gray-300'">
                {{ (item.entries || []).length }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Footer -->
    <div v-if="searchResults.length > 0" class="px-6 py-3 border-t border-gray-100 bg-gray-50 rounded-b-2xl">
      <p class="text-[11px] text-gray-400 font-medium">
        {{ searchResults.length }} {{ searchResults.length === 1 ? 'item' : 'items' }}
        across {{ selectedIds.length }} {{ selectedIds.length === 1 ? 'work' : 'works' }}
      </p>
    </div>

    <!-- ── Hover tooltip ── -->
    <Teleport to="body">
      <Transition name="tip">
        <div v-if="hoveredItem"
          class="fixed z-[9999] w-84 pointer-events-auto"
          :style="{
            left: (tooltipPos.x + 340 > (typeof window !== 'undefined' ? window.innerWidth : 1440))
                    ? (tooltipPos.x - 344) + 'px'
                    : (tooltipPos.x + 12) + 'px',
            top: Math.min(tooltipPos.y - 16, (typeof window !== 'undefined' ? window.innerHeight : 900) - 380) + 'px',
          }"
          @mouseenter="keepTooltip"
          @mouseleave="hideTooltip">

          <div class="bg-white rounded-2xl border border-gray-200 shadow-[0_16px_40px_rgba(0,0,0,0.12)] overflow-hidden" style="width:336px;">

            <!-- Tooltip header -->
            <div class="px-4 py-3 border-b border-gray-100 bg-gray-50/80">
              <div class="flex items-center gap-2 mb-1">
                <span class="rounded-md px-2 py-0.5 text-[10px] font-bold"
                  :class="isSchB(hoveredItem) ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'">
                  {{ hoveredItem.schedule }}
                </span>
                <span class="text-[10px] font-semibold text-gray-400">S.No {{ hoveredItem.serial_number }}</span>
                <span class="ml-auto text-[10px] font-semibold text-[#0071e3] bg-[#0071e3]/10 px-2 py-0.5 rounded-full">
                  {{ hoveredItem.loa_number }}
                </span>
              </div>
              <p class="text-xs font-semibold text-gray-800 leading-snug line-clamp-2">{{ hoveredItem.item_desc }}</p>
              <!-- Sch-B: show supply + execution totals -->
              <div v-if="isSchB(hoveredItem)" class="mt-2 flex gap-3">
                <span class="text-[10px] text-gray-500">
                  Supplied: <strong class="text-blue-600">{{ hoveredItem.supplied_quantity || 0 }}</strong>
                  <span class="text-gray-400"> {{ hoveredItem.unit }}</span>
                </span>
                <span class="text-gray-200">·</span>
                <span class="text-[10px] text-gray-500">
                  Executed: <strong class="text-[#34c759]">{{ hoveredItem.executed_quantity || 0 }}</strong>
                  <span class="text-gray-400"> {{ hoveredItem.unit }}</span>
                </span>
              </div>
            </div>

            <!-- No entries -->
            <div v-if="!(hoveredItem.entries || []).length"
              class="px-4 py-6 text-center text-xs text-gray-400 font-medium">
              No entries submitted yet.
            </div>

            <!-- Entry list -->
            <div v-else class="max-h-64 overflow-y-auto" style="scrollbar-width: thin;">
              <div v-for="(entry, idx) in [...(hoveredItem.entries || [])].reverse()" :key="entry.id"
                class="px-4 py-2.5 border-b border-gray-50 last:border-0 hover:bg-gray-50/60 transition-colors">
                <div class="flex items-center justify-between gap-2">
                  <div class="flex items-center gap-2 min-w-0">
                    <!-- Index bubble + type badge -->
                    <span class="flex-shrink-0 w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center"
                      :class="entry.entry_type === 'supply' ? 'bg-blue-100 text-blue-600' : 'bg-green-100 text-green-700'">
                      {{ (hoveredItem.entries || []).length - idx }}
                    </span>
                    <span class="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide"
                      :class="entry.entry_type === 'supply' ? 'bg-blue-50 text-blue-600' : 'bg-green-50 text-green-700'">
                      {{ entry.entry_type === 'supply' ? 'Supply' : 'Exec' }}
                    </span>
                    <span class="text-xs font-bold text-gray-800">
                      {{ entry.quantity }}
                      <span class="text-gray-400 font-normal text-[10px]">{{ hoveredItem.unit }}</span>
                    </span>
                  </div>
                  <span class="text-[10px] text-gray-400 font-medium flex-shrink-0">
                    {{ fmtDateTime(entry.submitted_at) }}
                  </span>
                </div>
                <div class="mt-1 pl-7 flex flex-col gap-0.5">
                  <!-- Submitted by -->
                  <span class="flex items-center gap-1 text-[10px] text-gray-500 font-medium">
                    <div class="i-carbon-user text-gray-400" style="font-size:10px;"></div>
                    {{ entry.submitted_by_user?.username || '—' }}
                  </span>
                  <!-- Supply fields -->
                  <template v-if="entry.entry_type === 'supply'">
                    <span v-if="entry.challan_no" class="flex items-center gap-1 text-[10px] text-gray-400 font-medium truncate">
                      <div class="i-carbon-document text-gray-300" style="font-size:10px;"></div>
                      {{ entry.challan_no }}
                    </span>
                    <span v-if="entry.udm_entry" class="flex items-center gap-1 text-[10px] text-gray-400 font-medium truncate">
                      <div class="i-carbon-tag text-gray-300" style="font-size:10px;"></div>
                      {{ entry.udm_entry }}
                    </span>
                  </template>
                  <!-- Execution fields -->
                  <template v-else>
                    <span v-if="entry.location" class="flex items-center gap-1 text-[10px] text-green-600 font-medium truncate">
                      <div class="i-carbon-location text-green-400" style="font-size:10px;"></div>
                      {{ entry.location }}
                    </span>
                    <span v-if="entry.remarks" class="flex items-center gap-1 text-[10px] text-gray-500 font-medium line-clamp-1">
                      <div class="i-carbon-chat text-gray-300" style="font-size:10px;"></div>
                      {{ entry.remarks }}
                    </span>
                  </template>
                </div>
              </div>
            </div>

            <!-- Footer summary -->
            <div v-if="(hoveredItem.entries || []).length"
              class="px-4 py-2 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
              <span class="text-[10px] text-gray-400 font-medium">
                {{ (hoveredItem.entries || []).length }} entr{{ (hoveredItem.entries || []).length === 1 ? 'y' : 'ies' }}
              </span>
              <div class="flex items-center gap-3">
                <span class="text-[10px] font-bold text-blue-600">
                  {{ hoveredItem.supplied_quantity || 0 }}
                  <span class="text-gray-400 font-normal">{{ hoveredItem.unit }} sup</span>
                </span>
                <template v-if="isSchB(hoveredItem)">
                  <span class="text-gray-200">·</span>
                  <span class="text-[10px] font-bold text-[#34c759]">
                    {{ hoveredItem.executed_quantity || 0 }}
                    <span class="text-gray-400 font-normal">{{ hoveredItem.unit }} exe</span>
                  </span>
                </template>
              </div>
            </div>

          </div>
        </div>
      </Transition>
    </Teleport>

  </div>
</template>

<style scoped>
.tip-enter-active { transition: opacity 0.12s ease, transform 0.12s ease; }
.tip-leave-active { transition: opacity 0.08s ease; }
.tip-enter-from  { opacity: 0; transform: translateY(4px) scale(0.98); }
.tip-leave-to    { opacity: 0; }
</style>
