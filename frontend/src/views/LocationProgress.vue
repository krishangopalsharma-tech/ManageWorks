<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'

const allWorks       = ref([])
const allRows        = ref([])   // flat (location, work_item) rows from server
const isLoadingWorks = ref(true)
const isLoadingData  = ref(false)
const workSearch     = ref('')
const itemSearch     = ref('')
const locationSearch = ref('')
const selectedIds    = ref([])
const dropdownOpen   = ref(false)
const dropdownRef    = ref(null)
const expandedKey    = ref(null)  // "loc__wiId" string

const fmtDateTime = (val) => {
  if (!val) return '—'
  const d = new Date(val)
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// ── Works dropdown ────────────────────────────────────────────────────────────
const loadWorks = async () => {
  isLoadingWorks.value = true
  try {
    const res = await axios.get('/api/location-progress/works/')
    allWorks.value = res.data
  } catch (e) { console.error(e) }
  finally { isLoadingWorks.value = false }
}

const filteredWorksDropdown = computed(() => {
  const q = workSearch.value.toLowerCase().trim()
  if (!q) return allWorks.value
  return allWorks.value.filter(w =>
    (w.loa_number          && w.loa_number.toLowerCase().includes(q)) ||
    (w.contractor_name     && w.contractor_name.toLowerCase().includes(q)) ||
    (w.contractor_nickname && w.contractor_nickname.toLowerCase().includes(q)) ||
    (w.tender_number       && w.tender_number.toLowerCase().includes(q))
  )
})

const allSelected   = computed(() => selectedIds.value.length === allWorks.value.length && allWorks.value.length > 0)
const noneSelected  = computed(() => selectedIds.value.length === 0)
const dropdownLabel = computed(() => {
  if (noneSelected.value || allSelected.value) return 'All Works'
  const n = selectedIds.value.length
  if (n === 1) { const w = allWorks.value.find(w => w.id === selectedIds.value[0]); return w?.loa_number || w?.contractor_name || '1 work' }
  return `${n} works selected`
})
const toggleWork = (id) => {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

// ── Load data ─────────────────────────────────────────────────────────────────
let loadTimer = null
const loadData = async () => {
  isLoadingData.value = true
  expandedKey.value = null
  try {
    const params = {}
    if (!noneSelected.value && !allSelected.value) params.work_ids = selectedIds.value.join(',')
    const res = await axios.get('/api/location-progress/data/', { params })
    allRows.value = res.data
  } catch (e) { console.error(e) }
  finally { isLoadingData.value = false }
}

watch(selectedIds, () => {
  clearTimeout(loadTimer)
  loadTimer = setTimeout(loadData, 300)
}, { deep: true })

// ── Category filter ───────────────────────────────────────────────────────────
const selectedCategories = ref(['supply', 'supply_installation', 'execution'])
const toggleCategory = (cat) => {
  const idx = selectedCategories.value.indexOf(cat)
  if (idx >= 0) selectedCategories.value.splice(idx, 1)
  else selectedCategories.value.push(cat)
}

// ── Progress filter ───────────────────────────────────────────────────────────
const progressMin   = ref(0)
const progressMax   = ref(100)
const includeExcess = ref(true)
const progressFilterActive = computed(() => progressMin.value > 0 || progressMax.value < 100 || !includeExcess.value)
const resetProgress = () => { progressMin.value = 0; progressMax.value = 100; includeExcess.value = true }
const onMinInput    = () => { if (progressMin.value > progressMax.value) progressMax.value = progressMin.value }
const onMaxInput    = () => { if (progressMax.value < progressMin.value) progressMin.value = progressMax.value }

// ── Filtered rows ─────────────────────────────────────────────────────────────
const filteredRows = computed(() => {
  let rows = allRows.value

  // Category
  if (selectedCategories.value.length < 3) {
    rows = rows.filter(r => selectedCategories.value.includes(r.category || 'supply'))
  }

  // Item search
  const iq = itemSearch.value.toLowerCase().trim()
  if (iq) {
    rows = rows.filter(r =>
      (r.item_desc     && r.item_desc.toLowerCase().includes(iq)) ||
      (r.serial_number && r.serial_number.toLowerCase().includes(iq)) ||
      (r.schedule      && r.schedule.toLowerCase().includes(iq))
    )
  }

  // Location search
  const lq = locationSearch.value.toUpperCase().trim()
  if (lq) {
    rows = rows.filter(r => r.location.includes(lq))
  }

  // Progress filter
  if (progressFilterActive.value) {
    rows = rows.filter(r => {
      const pct = r.progress_pct
      if (pct > 100) return includeExcess.value
      return pct >= progressMin.value && pct <= progressMax.value
    })
  }

  return rows
})

// ── Sorting ───────────────────────────────────────────────────────────────────
const sortKey = ref('')
const sortDir = ref('desc')
const toggleSort = (key) => {
  if (sortKey.value === key) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else { sortKey.value = key; sortDir.value = 'desc' }
}
const sortIcon = (key) => {
  if (sortKey.value !== key) return 'i-carbon-arrows-vertical'
  return sortDir.value === 'asc' ? 'i-carbon-arrow-up' : 'i-carbon-arrow-down'
}
const sortedRows = computed(() => {
  if (!sortKey.value) return filteredRows.value
  return [...filteredRows.value].sort((a, b) => {
    let av, bv
    if      (sortKey.value === 'executed') { av = a.executed_here;  bv = b.executed_here }
    else if (sortKey.value === 'scope')    { av = a.scope;          bv = b.scope }
    else if (sortKey.value === 'remaining'){ av = a.remaining;      bv = b.remaining }
    else if (sortKey.value === 'progress') { av = a.progress_pct;   bv = b.progress_pct }
    else if (sortKey.value === 'entries')  { av = a.entries_count;  bv = b.entries_count }
    else if (sortKey.value === 'location') { av = a.location;       bv = b.location; return sortDir.value === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av) }
    else { av = 0; bv = 0 }
    return sortDir.value === 'asc' ? av - bv : bv - av
  })
})

// ── Stats ─────────────────────────────────────────────────────────────────────
const stats = computed(() => {
  const rows = filteredRows.value
  const sections = rows.filter(r => r.location_type === 'section').length
  const stations = rows.filter(r => r.location_type === 'station').length
  const siCount  = rows.filter(r => r.category === 'supply_installation').length
  const exCount  = rows.filter(r => r.category === 'execution').length
  const avgProg  = rows.length ? Math.round(rows.reduce((s, r) => s + r.progress_pct, 0) / rows.length) : 0
  return { sections, stations, siCount, exCount, avgProg }
})

// ── Expand toggle ─────────────────────────────────────────────────────────────
const rowKey = (r) => `${r.location}__${r.work_item_id}`
const toggleExpand = (r) => {
  const k = rowKey(r)
  expandedKey.value = expandedKey.value === k ? null : k
}

// ── Dropdown close ────────────────────────────────────────────────────────────
const closeDropdown = (e) => {
  if (dropdownRef.value && !dropdownRef.value.contains(e.target)) dropdownOpen.value = false
}
onMounted(() => { loadWorks(); loadData(); document.addEventListener('click', closeDropdown) })
onBeforeUnmount(() => { document.removeEventListener('click', closeDropdown); clearTimeout(loadTimer) })
</script>

<template>
  <div class="bg-white rounded-2xl soft-shadow h-full w-full flex flex-col overflow-hidden">

    <!-- Header -->
    <div class="flex-shrink-0 px-8 pt-7 pb-5 border-b border-gray-100">
      <h1 class="text-2xl font-bold text-gray-900 tracking-tight mb-1">Location Progress</h1>
      <p class="text-gray-400 text-sm font-medium mb-4">Execution entries grouped by location — station or section.</p>

      <!-- Filter row -->
      <div class="flex items-center gap-3 mb-3">

        <!-- LOA multi-select dropdown -->
        <div class="relative flex-shrink-0 w-72" ref="dropdownRef">
          <button @click.stop="dropdownOpen = !dropdownOpen"
            class="w-full flex items-center justify-between bg-gray-50 border border-gray-200 rounded-2xl px-4 py-2.5 text-sm font-medium text-gray-700 hover:border-[#1D5F5E] hover:bg-white transition-all"
            :class="{ 'border-[#1D5F5E] bg-white ring-2 ring-[#1D5F5E]/10': dropdownOpen }">
            <div class="flex items-center gap-2 min-w-0">
              <div v-if="isLoadingWorks || isLoadingData" class="i-carbon-circle-dash animate-spin text-gray-400 text-base flex-shrink-0"></div>
              <div v-else class="i-carbon-building text-gray-400 text-base flex-shrink-0"></div>
              <span class="truncate text-sm">{{ isLoadingWorks ? 'Loading…' : dropdownLabel }}</span>
            </div>
            <div :class="dropdownOpen ? 'i-carbon-chevron-up' : 'i-carbon-chevron-down'" class="text-gray-400 text-sm flex-shrink-0 ml-2"></div>
          </button>

          <div v-if="dropdownOpen"
            class="absolute top-full mt-2 left-0 w-[520px] bg-white rounded-2xl border border-gray-200 shadow-xl z-50 overflow-hidden">
            <div class="p-3 border-b border-gray-100">
              <div class="flex items-center bg-gray-50 rounded-xl px-3 py-2 gap-2">
                <div class="i-carbon-search text-gray-400 text-sm flex-shrink-0"></div>
                <input v-model="workSearch" type="text"
                  placeholder="Search by name, LOA number, tender, nickname…"
                  class="bg-transparent outline-none text-xs text-gray-700 w-full placeholder-gray-400 font-medium" @click.stop>
                <button v-if="workSearch" @click.stop="workSearch = ''" class="text-gray-300 hover:text-gray-500 transition-colors">
                  <div class="i-carbon-close text-xs"></div>
                </button>
              </div>
            </div>
            <div class="px-4 py-2 border-b border-gray-100 flex items-center gap-3">
              <button @click.stop="selectedIds = allWorks.map(w => w.id)"
                class="text-xs font-semibold text-[#1D5F5E] hover:underline flex items-center gap-1">
                <div class="i-carbon-checkmark-filled text-[11px]"></div> Select All
              </button>
              <span class="text-gray-200">·</span>
              <button @click.stop="selectedIds = []"
                class="text-xs font-semibold text-gray-400 hover:text-gray-600 hover:underline flex items-center gap-1">
                <div class="i-carbon-close text-[11px]"></div> Clear
              </button>
              <span class="ml-auto text-[11px] text-gray-400 font-medium">
                {{ selectedIds.length }} / {{ allWorks.length }} selected
              </span>
            </div>
            <div class="max-h-72 overflow-y-auto" style="scrollbar-width: thin;">
              <div v-if="filteredWorksDropdown.length === 0" class="px-4 py-6 text-center text-xs text-gray-400">No works found</div>
              <div class="grid grid-cols-2">
                <label v-for="work in filteredWorksDropdown" :key="work.id"
                  class="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors border-b border-gray-50 border-r border-r-gray-50">
                  <input type="checkbox" :checked="selectedIds.includes(work.id)" @change="toggleWork(work.id)"
                    class="mt-0.5 accent-[#1D5F5E] flex-shrink-0" @click.stop>
                  <div class="min-w-0">
                    <div class="flex flex-wrap items-center gap-1.5 min-w-0">
                      <span class="text-xs font-bold text-gray-900 shrink-0">{{ work.loa_number || '—' }}</span>
                      <span class="text-[10px] font-semibold bg-sky-100 text-sky-950 px-2 py-0.5 rounded-full truncate max-w-[120px]">{{ work.contractor_name || '—' }}</span>
                      <span v-if="work.contractor_nickname" class="text-[10px] font-semibold bg-[#fac9b8] text-[#7c3d2a] px-2 py-0.5 rounded-full truncate max-w-[100px]">{{ work.contractor_nickname }}</span>
                      <span v-if="work.tender_number" class="text-[10px] font-semibold bg-amber-100 text-emerald-900 px-2 py-0.5 rounded-full truncate max-w-[120px]">{{ work.tender_number }}</span>
                    </div>
                  </div>
                </label>
              </div>
            </div>
          </div>
        </div>

        <!-- Category filter pills -->
        <div class="flex items-center gap-1.5 flex-shrink-0">
          <button @click="toggleCategory('supply')"
            class="px-3 py-2 rounded-xl text-[11px] font-bold border transition-all"
            :class="selectedCategories.includes('supply')
              ? 'bg-teal-50 border-teal-300 text-teal-700'
              : 'bg-white border-gray-200 text-gray-400'">
            Supply
          </button>
          <button @click="toggleCategory('supply_installation')"
            class="px-3 py-2 rounded-xl text-[11px] font-bold border transition-all"
            :class="selectedCategories.includes('supply_installation')
              ? 'bg-violet-50 border-violet-300 text-violet-700'
              : 'bg-white border-gray-200 text-gray-400'">
            S+I
          </button>
          <button @click="toggleCategory('execution')"
            class="px-3 py-2 rounded-xl text-[11px] font-bold border transition-all"
            :class="selectedCategories.includes('execution')
              ? 'bg-orange-50 border-orange-300 text-orange-700'
              : 'bg-white border-gray-200 text-gray-400'">
            Execution
          </button>
        </div>

        <div class="w-px h-6 bg-gray-200 flex-shrink-0"></div>

        <!-- Item search -->
        <div class="flex-1 flex items-center bg-gray-50 border border-gray-200 rounded-2xl px-4 py-2.5 focus-within:ring-2 focus-within:ring-[#1D5F5E]/20 focus-within:border-[#1D5F5E] focus-within:bg-white transition-all">
          <div class="i-carbon-search text-gray-400 text-base mr-3 flex-shrink-0"></div>
          <input v-model="itemSearch" type="text"
            placeholder="Search items by description, schedule, serial no…"
            class="bg-transparent outline-none w-full text-gray-700 font-medium placeholder-gray-400 text-sm">
          <button v-if="itemSearch" @click="itemSearch = ''" class="ml-2 text-gray-300 hover:text-gray-500 transition-colors">
            <div class="i-carbon-close text-sm"></div>
          </button>
        </div>

        <!-- Location search -->
        <div class="flex items-center bg-gray-50 border border-gray-200 rounded-2xl px-4 py-2.5 focus-within:ring-2 focus-within:ring-[#1D5F5E]/20 focus-within:border-[#1D5F5E] focus-within:bg-white transition-all w-44 flex-shrink-0">
          <div class="i-carbon-location text-gray-400 text-base mr-2 flex-shrink-0"></div>
          <input v-model="locationSearch" type="text"
            placeholder="Location…"
            style="text-transform:uppercase"
            class="bg-transparent outline-none w-full text-gray-700 font-medium placeholder-gray-400 text-sm">
          <button v-if="locationSearch" @click="locationSearch = ''" class="ml-2 text-gray-300 hover:text-gray-500 transition-colors">
            <div class="i-carbon-close text-sm"></div>
          </button>
        </div>
      </div>

      <!-- Progress range slider -->
      <div v-if="allRows.length > 0" class="flex items-center gap-3 mt-2.5">
        <span class="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex-shrink-0">Progress</span>
        <div class="flex items-center gap-2 flex-1 max-w-sm">
          <span class="text-[11px] font-bold text-gray-600 w-8 text-right flex-shrink-0 tabular-nums">{{ progressMin }}%</span>
          <div class="relative flex-1 h-5 flex items-center">
            <div class="absolute w-full h-1.5 bg-gray-200 rounded-full"></div>
            <div class="absolute h-1.5 bg-[#1D5F5E] rounded-full pointer-events-none"
              :style="{ left: progressMin + '%', width: (progressMax - progressMin) + '%' }"></div>
            <input type="range" min="0" max="100" step="1" v-model.number="progressMin"
              @input="onMinInput" class="progress-thumb absolute w-full">
            <input type="range" min="0" max="100" step="1" v-model.number="progressMax"
              @input="onMaxInput" class="progress-thumb absolute w-full">
          </div>
          <span class="text-[11px] font-bold text-gray-600 w-8 flex-shrink-0 tabular-nums">{{ progressMax }}%</span>
        </div>
        <button @click="includeExcess = !includeExcess"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-bold border transition-all flex-shrink-0"
          :class="includeExcess ? 'bg-orange-50 border-orange-300 text-orange-700' : 'bg-white border-gray-200 text-gray-400 line-through'">
          <div class="i-carbon-overflow-menu-horizontal text-[11px]"></div>
          +Excess
        </button>
        <button v-if="progressFilterActive" @click="resetProgress"
          class="flex items-center gap-1 text-[10px] font-semibold text-gray-400 hover:text-gray-600 transition-colors flex-shrink-0">
          <div class="i-carbon-reset text-[11px]"></div> Reset
        </button>
      </div>

      <!-- Stats pills -->
      <div v-if="filteredRows.length > 0" class="flex flex-wrap items-center gap-3 mt-2.5">
        <div class="flex items-center gap-2 bg-violet-50 border border-violet-200 rounded-xl px-4 py-2">
          <div class="w-2 h-2 rounded-full bg-violet-500"></div>
          <span class="text-xs font-semibold text-violet-700">S+I: {{ stats.siCount }}</span>
        </div>
        <div class="flex items-center gap-2 bg-orange-50 border border-orange-200 rounded-xl px-4 py-2">
          <div class="w-2 h-2 rounded-full bg-orange-500"></div>
          <span class="text-xs font-semibold text-orange-700">Execution: {{ stats.exCount }}</span>
        </div>
        <div class="flex items-center gap-2 bg-blue-50 border border-blue-200 rounded-xl px-4 py-2">
          <div class="i-carbon-location text-blue-400 text-sm"></div>
          <span class="text-xs font-semibold text-blue-700">
            {{ stats.sections }} section{{ stats.sections !== 1 ? 's' : '' }}
          </span>
        </div>
        <div class="flex items-center gap-2 bg-green-50 border border-green-200 rounded-xl px-4 py-2">
          <div class="i-carbon-radio-button text-green-400 text-sm"></div>
          <span class="text-xs font-semibold text-green-700">
            {{ stats.stations }} station{{ stats.stations !== 1 ? 's' : '' }}
          </span>
        </div>
        <div class="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-4 py-2">
          <div class="i-carbon-list text-gray-400 text-sm"></div>
          <span class="text-xs font-semibold text-gray-600">
            {{ filteredRows.length }}
            <span v-if="filteredRows.length < allRows.length" class="font-normal text-gray-400"> of {{ allRows.length }}</span>
            rows
          </span>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="isLoadingData" class="flex-1 flex flex-col items-center justify-center py-24 text-center">
      <div class="i-carbon-circle-dash animate-spin text-4xl text-gray-300 mb-4"></div>
      <p class="text-sm font-semibold text-gray-400">Loading location data…</p>
    </div>

    <!-- Empty -->
    <div v-else-if="!isLoadingData && allRows.length === 0" class="flex-1 flex flex-col items-center justify-center py-24 text-center">
      <div class="i-carbon-location text-5xl text-gray-200 mb-4"></div>
      <p class="text-sm font-semibold text-gray-400">No location data yet.</p>
      <p class="text-xs text-gray-300 mt-1">Execution entries with a location will appear here.</p>
    </div>

    <!-- No match -->
    <div v-else-if="!isLoadingData && allRows.length > 0 && filteredRows.length === 0" class="flex-1 flex flex-col items-center justify-center py-24 text-center">
      <div class="i-carbon-search text-5xl text-gray-200 mb-4"></div>
      <p class="text-sm font-semibold text-gray-400">No rows match your filters.</p>
      <p class="text-xs text-gray-300 mt-1">Try adjusting search or category filters.</p>
    </div>

    <!-- Table -->
    <div v-else-if="!isLoadingData && filteredRows.length > 0" class="overflow-auto flex-1">
      <table class="w-full border-collapse">
        <thead class="bg-gray-50 sticky top-0 z-10">
          <tr class="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
            <th @click="toggleSort('location')" class="px-4 py-3 text-left w-36 cursor-pointer select-none hover:text-gray-600 transition-colors">
              <div class="flex items-center gap-1">Location <div :class="sortIcon('location')" class="text-[9px]" :style="{ opacity: sortKey === 'location' ? 1 : 0.35 }"></div></div>
            </th>
            <th class="px-4 py-3 text-left w-44">LOA Contractor</th>
            <th class="px-4 py-3 text-center w-14">SCH</th>
            <th class="px-4 py-3 text-center w-14">S.No</th>
            <th class="px-4 py-3 text-left">Item Description</th>
            <th @click="toggleSort('executed')" class="px-4 py-3 text-right w-28 cursor-pointer select-none hover:text-gray-600 transition-colors">
              <div class="flex items-center justify-end gap-1">Executed <div :class="sortIcon('executed')" class="text-[9px]" :style="{ opacity: sortKey === 'executed' ? 1 : 0.35 }"></div></div>
            </th>
            <th @click="toggleSort('scope')" class="px-4 py-3 text-right w-28 cursor-pointer select-none hover:text-gray-600 transition-colors">
              <div class="flex items-center justify-end gap-1">Scope <div :class="sortIcon('scope')" class="text-[9px]" :style="{ opacity: sortKey === 'scope' ? 1 : 0.35 }"></div></div>
            </th>
            <th @click="toggleSort('remaining')" class="px-4 py-3 text-right w-28 cursor-pointer select-none hover:text-gray-600 transition-colors">
              <div class="flex items-center justify-end gap-1">Remaining <div :class="sortIcon('remaining')" class="text-[9px]" :style="{ opacity: sortKey === 'remaining' ? 1 : 0.35 }"></div></div>
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
          <template v-for="row in sortedRows" :key="rowKey(row)">
            <!-- Main row -->
            <tr @click="toggleExpand(row)"
              class="border-b border-gray-100 hover:bg-accent-soft/40 transition-colors cursor-pointer select-none"
              :class="expandedKey === rowKey(row) ? 'bg-accent-soft/30 border-accent/20' : ''">

              <!-- Location -->
              <td class="px-4 py-3">
                <div class="flex flex-col gap-1">
                  <span :class="row.location_type === 'section'
                      ? 'bg-blue-50 text-blue-600 border border-blue-200'
                      : 'bg-green-50 text-green-600 border border-green-200'"
                    class="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded self-start">
                    {{ row.location_type }}
                  </span>
                  <span class="text-xs font-bold text-gray-800 tracking-wide">{{ row.location }}</span>
                </div>
              </td>

              <!-- LOA Contractor -->
              <td class="px-4 py-3">
                <div class="flex flex-col gap-0.5">
                  <div class="flex items-center gap-1.5 flex-wrap">
                    <span class="text-[11px] font-semibold text-accent bg-accent-soft px-2 py-0.5 rounded-full whitespace-nowrap">
                      {{ row.loa_number || '—' }}
                    </span>
                    <span v-if="row.contractor_nickname"
                      class="text-[10px] font-bold bg-[#fac9b8] text-[#7c3d2a] px-1.5 py-0.5 rounded-full">
                      {{ row.contractor_nickname }}
                    </span>
                  </div>
                  <span class="text-[10px] text-gray-400 truncate max-w-[140px]">{{ row.contractor_name }}</span>
                </div>
              </td>

              <!-- SCH -->
              <td class="px-4 py-3 text-center">
                <span class="rounded-md px-2 py-1 text-[10px] font-bold bg-accent-b-soft text-accent-b">
                  {{ row.schedule || '—' }}
                </span>
              </td>

              <!-- S.No -->
              <td class="px-4 py-3 text-center text-[11px] text-gray-500 font-semibold">
                {{ row.serial_number }}
              </td>

              <!-- Item Description -->
              <td class="px-4 py-3">
                <p class="text-xs font-medium text-gray-800 line-clamp-2 leading-relaxed">{{ row.item_desc || '—' }}</p>
              </td>

              <!-- Executed at location -->
              <td class="px-4 py-3 text-right text-xs font-semibold"
                :class="row.executed_here > row.scope ? 'text-orange-500' : 'text-gray-800'">
                {{ row.executed_here }}
                <span class="text-gray-400 font-normal">{{ row.unit }}</span>
              </td>

              <!-- Scope -->
              <td class="px-4 py-3 text-right text-xs font-semibold text-gray-600">
                {{ row.scope }} <span class="text-gray-400 font-normal">{{ row.unit }}</span>
              </td>

              <!-- Remaining -->
              <td class="px-4 py-3 text-right text-xs font-semibold"
                :class="row.remaining < 0 ? 'text-orange-500' : 'text-gray-600'">
                {{ row.remaining }} <span class="text-gray-400 font-normal">{{ row.unit }}</span>
              </td>

              <!-- Progress -->
              <td class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div class="h-full rounded-full transition-all duration-500"
                      :class="row.progress_pct > 100 ? 'bg-orange-400' : 'bg-accent-b'"
                      :style="{ width: Math.min(row.progress_pct, 100) + '%' }"></div>
                  </div>
                  <span class="text-[10px] font-bold w-8 text-right"
                    :class="row.progress_pct > 100 ? 'text-orange-500' : 'text-gray-500'">
                    {{ row.progress_pct }}%
                  </span>
                </div>
              </td>

              <!-- Entries -->
              <td class="px-4 py-3 text-center">
                <div class="flex items-center justify-center gap-1">
                  <span class="text-[11px] font-bold"
                    :class="row.entries_count > 0 ? 'text-accent' : 'text-gray-300'">
                    {{ row.entries_count }}
                  </span>
                  <div class="text-gray-300 text-[10px] transition-transform duration-200"
                    :class="expandedKey === rowKey(row) ? 'i-carbon-chevron-up' : 'i-carbon-chevron-down'"></div>
                </div>
              </td>
            </tr>

            <!-- Expanded entries panel -->
            <tr v-if="expandedKey === rowKey(row)" class="bg-gray-50/60">
              <td colspan="10" class="px-6 pb-5 pt-0 border-b border-accent/10">
                <div class="rounded-xl border border-gray-100 bg-white overflow-hidden mt-3 shadow-sm">

                  <!-- Panel header -->
                  <div class="px-4 py-3 bg-gray-50 border-b border-gray-100 flex items-center gap-3 flex-wrap">
                    <span :class="row.location_type === 'section' ? 'bg-blue-50 text-blue-600 border-blue-200' : 'bg-green-50 text-green-600 border-green-200'"
                      class="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border">
                      {{ row.location_type }}
                    </span>
                    <span class="text-sm font-bold text-gray-800 tracking-wide">{{ row.location }}</span>
                    <span class="rounded-md px-2 py-0.5 text-[10px] font-bold bg-accent-b-soft text-accent-b">{{ row.schedule }}</span>
                    <span class="text-[10px] font-semibold text-gray-400">S.No {{ row.serial_number }}</span>
                    <span class="text-[11px] font-semibold text-accent bg-accent-soft px-2 py-0.5 rounded-full">{{ row.loa_number }}</span>
                    <p class="text-xs font-semibold text-gray-700 line-clamp-1 ml-1 flex-1">{{ row.item_desc }}</p>
                    <div class="flex items-center gap-3 flex-shrink-0">
                      <span class="text-[10px] text-gray-500">Executed here: <strong class="text-accent-b">{{ row.executed_here }}</strong> <span class="text-gray-400">{{ row.unit }}</span></span>
                      <span class="text-gray-200">·</span>
                      <span class="text-[10px] text-gray-500">Total scope: <strong class="text-gray-700">{{ row.scope }}</strong> <span class="text-gray-400">{{ row.unit }}</span></span>
                    </div>
                    <span class="text-[10px] text-gray-400 font-medium flex-shrink-0">
                      {{ row.entries.length }} visible entr{{ row.entries.length === 1 ? 'y' : 'ies' }}
                      <span v-if="row.visible_entries_count < row.entries_count" class="text-gray-300"> of {{ row.entries_count }}</span>
                    </span>
                  </div>

                  <!-- No entries -->
                  <div v-if="!row.entries.length" class="px-4 py-8 text-center text-xs text-gray-400 font-medium">
                    No entries to display.
                  </div>

                  <!-- Entries grid -->
                  <div v-else class="p-3 flex flex-wrap gap-2">
                    <div v-for="(entry, idx) in [...row.entries].reverse()" :key="entry.id"
                      class="border border-gray-100 rounded-xl px-3 py-2.5 min-w-[200px] flex-1 max-w-[280px] hover:border-accent/30 transition-colors">
                      <div class="flex items-center gap-2 mb-1.5">
                        <span class="w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center flex-shrink-0 bg-accent-b-soft text-accent-b">
                          {{ row.entries.length - idx }}
                        </span>
                        <span class="text-xs font-bold text-gray-800">
                          {{ entry.quantity }} <span class="text-gray-400 font-normal text-[10px]">{{ row.unit }}</span>
                        </span>
                        <span class="ml-auto text-[10px] text-gray-400 font-medium flex-shrink-0">
                          {{ fmtDateTime(entry.submitted_at) }}
                        </span>
                      </div>
                      <div class="flex flex-col gap-0.5 pl-7">
                        <span class="flex items-center gap-1 text-[10px] text-gray-500 font-medium">
                          <div class="i-carbon-user text-gray-400" style="font-size:10px;"></div>
                          {{ entry.submitted_by_name || '—' }}
                          <span v-if="entry.submitted_by_designation" class="text-gray-400"> · {{ entry.submitted_by_designation }}</span>
                        </span>
                        <span v-if="entry.remarks" class="flex items-center gap-1 text-[10px] text-gray-500 font-medium line-clamp-1">
                          <div class="i-carbon-chat text-gray-300" style="font-size:10px;"></div>
                          {{ entry.remarks }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.progress-thumb {
  -webkit-appearance: none;
  appearance: none;
  pointer-events: none;
  background: transparent;
  height: 20px;
}
.progress-thumb::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  pointer-events: all;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #1D5F5E;
  cursor: pointer;
  border: 2px solid white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.progress-thumb::-moz-range-thumb {
  pointer-events: all;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #1D5F5E;
  cursor: pointer;
  border: 2px solid white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
</style>
