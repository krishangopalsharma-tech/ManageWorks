<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'
import { Chart as ChartJS, Title, Tooltip, Legend, ArcElement, CategoryScale, LinearScale, BarElement } from 'chart.js'
import { Doughnut, Bar } from 'vue-chartjs'

ChartJS.register(Title, Tooltip, Legend, ArcElement, CategoryScale, LinearScale, BarElement)

const stats     = ref(null)
const loas      = ref([])
const trendData = ref([])
const selectedLoas = ref([])
const searchQuery  = ref('')
const activePeriod = ref('monthly')
const isLoading      = ref(true)
const isTrendLoading = ref(false)

const seenLoas = ref(new Set(JSON.parse(localStorage.getItem('mw_seen_loas') || '[]')))

function markSeen(id) {
  seenLoas.value.add(id)
  localStorage.setItem('mw_seen_loas', JSON.stringify([...seenLoas.value]))
}

function hasUnseenUpdate(loa) {
  return (loa.supply_update || loa.execution_update) && !seenLoas.value.has(loa.id)
}

const filteredLoas = computed(() => {
  const q = searchQuery.value.toLowerCase()
  if (!q) return loas.value
  return loas.value.filter(l =>
    l.label.toLowerCase().includes(q) ||
    (l.contractor_nickname && l.contractor_nickname.toLowerCase().includes(q))
  )
})

const isAllSelected = computed(() => selectedLoas.value.length === 0)

function toggleLoa(id) {
  markSeen(id)
  const idx = selectedLoas.value.indexOf(id)
  if (idx === -1) selectedLoas.value.push(id)
  else selectedLoas.value.splice(idx, 1)
}

function selectAll() {
  selectedLoas.value = []
}

const loaIdsParam = computed(() =>
  selectedLoas.value.length > 0 ? selectedLoas.value.join(',') : null
)

const periods = [
  { label: 'Daily',   value: 'daily'   },
  { label: 'Weekly',  value: 'weekly'  },
  { label: 'Monthly', value: 'monthly' },
  { label: 'Yearly',  value: 'yearly'  },
]

// ── Doughnut charts ────────────────────────────────────────────────────────
const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: '75%',
  plugins: { legend: { display: false }, tooltip: { enabled: true } },
}

const mkDoughnut = (val, color) => ({
  labels: ['Completed', 'Remaining'],
  datasets: [{
    data: [val, Math.max(0, 100 - val)],
    backgroundColor: [color, '#e5e5ea'],
    borderWidth: 0,
    hoverOffset: 2,
  }],
})

const supplyData  = computed(() => mkDoughnut(stats.value?.supply     || 0, '#1D5F5E'))
const execData    = computed(() => mkDoughnut(stats.value?.execution  || 0, '#34c759'))
const overallData = computed(() => mkDoughnut(stats.value?.overall    || 0, '#5856d6'))
const finData     = computed(() => mkDoughnut(stats.value?.financial  || 0, '#ff9500'))

// ── Bar chart ──────────────────────────────────────────────────────────────
const barData = computed(() => ({
  labels: trendData.value.map(d => d.label),
  datasets: [
    {
      label: 'Supply',
      data:  trendData.value.map(d => d.supply ?? 0),
      backgroundColor: '#1D5F5E',
      hoverBackgroundColor: '#174a49',
      borderRadius: 6,
      borderSkipped: false,
      maxBarThickness: 32,
    },
    {
      label: 'Execution',
      data:  trendData.value.map(d => d.execution ?? 0),
      backgroundColor: 'rgba(52, 199, 89, 0.85)',
      hoverBackgroundColor: '#34c759',
      borderRadius: 6,
      borderSkipped: false,
      maxBarThickness: 32,
    },
    {
      label: 'Financial',
      data:  trendData.value.map(d => d.financial ?? 0),
      backgroundColor: 'rgba(255, 149, 0, 0.85)',
      hoverBackgroundColor: '#ff9500',
      borderRadius: 6,
      borderSkipped: false,
      maxBarThickness: 32,
    },
  ],
}))

const barOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: true,
      position: 'top',
      align: 'end',
      labels: {
        boxWidth: 10,
        boxHeight: 10,
        borderRadius: 3,
        useBorderRadius: true,
        font: { size: 11, family: '-apple-system, BlinkMacSystemFont, Inter, sans-serif' },
        color: '#6e6e73',
        padding: 16,
      },
    },
    tooltip: {
      callbacks: {
        label: ctx => ` ${ctx.dataset.label}: ${ctx.raw}%`,
      },
    },
  },
  scales: {
    x: {
      grid: { display: false },
      border: { display: false },
      ticks: { font: { size: 10, family: '-apple-system, BlinkMacSystemFont, Inter, sans-serif' }, color: '#86868b', maxRotation: 45 },
    },
    y: {
      grid: { color: '#f5f5f7', drawBorder: false },
      border: { display: false },
      ticks: {
        font: { size: 10, family: '-apple-system, BlinkMacSystemFont, Inter, sans-serif' },
        color: '#86868b',
        callback: val => val + '%',
      },
      beginAtZero: true,
    },
  },
}

// ── Data fetching ──────────────────────────────────────────────────────────
const fetchStats = async () => {
  isLoading.value = true
  try {
    const params = {}
    if (loaIdsParam.value) params.loa_ids = loaIdsParam.value
    const res = await axios.get('/api/dashboard/', { params })
    stats.value = res.data
    loas.value  = res.data.loas
  } catch (e) {
    console.error(e)
  } finally {
    isLoading.value = false
  }
}

const fetchTrend = async () => {
  isTrendLoading.value = true
  try {
    const params = { period: activePeriod.value }
    if (loaIdsParam.value) params.loa_ids = loaIdsParam.value
    const res = await axios.get('/api/dashboard/trend/', { params })
    trendData.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    isTrendLoading.value = false
  }
}

watch(selectedLoas, () => { fetchStats(); fetchTrend() }, { deep: true })
watch(activePeriod, () => fetchTrend())
// ── Drag-resize divider ────────────────────────────────────────────────────
const STORAGE_KEY = 'mw_dashboard_left_pct'
const leftPct  = ref(parseFloat(localStorage.getItem(STORAGE_KEY) || '72'))
const isDragging = ref(false)
const containerRef = ref(null)

function onDividerMouseDown(e) {
  e.preventDefault()
  isDragging.value = true
}
function onMouseMove(e) {
  if (!isDragging.value || !containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  const pct  = ((e.clientX - rect.left) / rect.width) * 100
  leftPct.value = Math.min(Math.max(pct, 25), 75)
}
function onMouseUp() {
  if (isDragging.value) {
    isDragging.value = false
    localStorage.setItem(STORAGE_KEY, leftPct.value.toFixed(1))
  }
}

onMounted(() => {
  fetchStats()
  fetchTrend()
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
})
onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
})
</script>

<template>
  <div ref="containerRef" class="h-full flex animate-fade-in" style="animation-fill-mode: forwards;" :class="isDragging ? 'select-none cursor-col-resize' : ''">

    <!-- ── Left: Analytics Dashboard ─────────────────────────────────── -->
    <div class="bg-light-surface rounded-2xl soft-shadow flex flex-col overflow-hidden flex-shrink-0"
      :style="{ width: leftPct + '%' }">

      <!-- Card header -->
      <div class="px-7 pt-6 pb-4 border-b border-gray-100 flex-shrink-0">
        <h1 class="text-xl font-bold text-gray-800 tracking-tight">Analytics Dashboard</h1>
      </div>

      <!-- Loading -->
      <div v-if="isLoading" class="flex-1 flex items-center justify-center">
        <div class="i-carbon-circle-dash animate-spin text-4xl text-[#1D5F5E]"></div>
      </div>

      <div v-else class="flex-1 min-h-0 flex flex-col p-6 gap-5 overflow-hidden">

        <!-- ── Doughnut charts — compact 2×2 ───────────────────────── -->
        <div class="grid grid-cols-4 gap-4 flex-shrink-0">

          <div class="flex flex-col items-center bg-white border border-gray-100 rounded-2xl py-4 px-3 soft-shadow">
            <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">Supply</p>
            <div class="relative w-24 h-24 flex-center">
              <span class="absolute text-base font-extrabold text-gray-800 z-10 pointer-events-none">{{ stats?.supply || 0 }}%</span>
              <Doughnut :data="supplyData" :options="doughnutOptions" />
            </div>
            <div class="mt-2 w-2 h-2 rounded-full bg-[#1D5F5E]"></div>
          </div>

          <div class="flex flex-col items-center bg-white border border-gray-100 rounded-2xl py-4 px-3 soft-shadow">
            <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">Execution</p>
            <div class="relative w-24 h-24 flex-center">
              <span class="absolute text-base font-extrabold text-gray-800 z-10 pointer-events-none">{{ stats?.execution || 0 }}%</span>
              <Doughnut :data="execData" :options="doughnutOptions" />
            </div>
            <div class="mt-2 w-2 h-2 rounded-full bg-[#34c759]"></div>
          </div>

          <div class="flex flex-col items-center bg-white border border-gray-100 rounded-2xl py-4 px-3 soft-shadow">
            <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">Overall</p>
            <div class="relative w-24 h-24 flex-center">
              <span class="absolute text-base font-extrabold text-gray-800 z-10 pointer-events-none">{{ stats?.overall || 0 }}%</span>
              <Doughnut :data="overallData" :options="doughnutOptions" />
            </div>
            <div class="mt-2 w-2 h-2 rounded-full bg-[#5856d6]"></div>
          </div>

          <div class="flex flex-col items-center bg-white border border-gray-100 rounded-2xl py-4 px-3 soft-shadow">
            <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">Financial</p>
            <div class="relative w-24 h-24 flex-center">
              <span class="absolute text-base font-extrabold text-gray-800 z-10 pointer-events-none">{{ stats?.financial || 0 }}%</span>
              <Doughnut :data="finData" :options="doughnutOptions" />
            </div>
            <div class="mt-2 w-2 h-2 rounded-full bg-[#ff9500]"></div>
          </div>

        </div>

        <!-- ── Bar chart: Submission Activity ──────────────────────── -->
        <div class="flex-1 min-h-0 bg-white border border-gray-100 rounded-2xl soft-shadow flex flex-col overflow-hidden">

          <!-- Bar chart header + period selector -->
          <div class="px-5 pt-4 pb-3 flex items-center justify-between flex-shrink-0 border-b border-gray-50">
            <div>
              <p class="text-sm font-bold text-gray-800 tracking-tight">Submission Activity</p>
              <p class="text-[11px] text-gray-400 font-medium mt-0.5">% of total work completed per period</p>
            </div>
            <div class="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
              <button
                v-for="p in periods" :key="p.value"
                @click="activePeriod = p.value"
                :class="activePeriod === p.value
                  ? 'bg-white text-[#1D5F5E] shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'"
                class="px-3 py-1 rounded-md text-xs font-semibold transition-all">
                {{ p.label }}
              </button>
            </div>
          </div>

          <!-- Chart area -->
          <div class="flex-1 min-h-0 px-5 py-4 relative">
            <div v-if="isTrendLoading" class="absolute inset-0 flex items-center justify-center">
              <div class="i-carbon-circle-dash animate-spin text-2xl text-[#1D5F5E]"></div>
            </div>
            <div v-else-if="trendData.length === 0" class="h-full flex flex-col items-center justify-center gap-2">
              <div class="i-carbon-chart-bar text-4xl text-gray-200"></div>
              <p class="text-xs font-semibold text-gray-400">No submissions recorded in this period.</p>
            </div>
            <Bar v-else :data="barData" :options="barOptions" class="h-full w-full" />
          </div>

        </div>

      </div>
    </div>

    <!-- ── Drag divider ──────────────────────────────────────────────── -->
    <div class="flex-shrink-0 flex items-center justify-center w-4 cursor-col-resize group mx-1"
      @mousedown="onDividerMouseDown">
      <div class="w-1 h-12 rounded-full transition-colors"
        :class="isDragging ? 'bg-[#1D5F5E]' : 'bg-gray-200 group-hover:bg-[#1D5F5E]/50'"></div>
    </div>

    <!-- ── Right: Work Context ───────────────────────────────────────── -->
    <div class="bg-light-surface rounded-2xl soft-shadow flex flex-col overflow-hidden flex-1 min-w-0">

      <div class="px-7 pt-6 pb-4 border-b border-gray-100 flex-shrink-0">
        <h2 class="text-base font-bold text-gray-800">Work Context</h2>
        <!-- Search bar -->
        <div class="relative mt-3">
          <div class="absolute inset-y-0 left-3 flex items-center pointer-events-none">
            <div class="i-carbon-search text-gray-400 text-sm"></div>
          </div>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search works..."
            class="w-full pl-8 pr-3 py-2 text-xs rounded-lg border border-gray-200 bg-white focus:outline-none focus:border-[#1D5F5E] transition-colors placeholder-gray-400"
          />
        </div>
      </div>

      <div class="flex-1 min-h-0 flex flex-col overflow-hidden p-5 gap-3">

        <!-- Total aggregation option -->
        <div
          @click="selectAll"
          class="px-4 py-3 rounded-xl cursor-pointer border transition-all flex-shrink-0 flex items-center gap-3"
          :class="isAllSelected
            ? 'bg-[#1D5F5E]/10 border-[#1D5F5E] text-[#1D5F5E]'
            : 'bg-[#f5f5f7] border-transparent text-gray-600 hover:border-gray-300'">
          <div
            class="w-4 h-4 rounded border-2 flex-shrink-0 flex items-center justify-center transition-all"
            :class="isAllSelected ? 'bg-[#1D5F5E] border-[#1D5F5E]' : 'border-gray-300 bg-white'">
            <div v-if="isAllSelected" class="i-carbon-checkmark text-white text-[10px]"></div>
          </div>
          <div>
            <div class="font-bold text-sm tracking-wide">Total Aggregation</div>
            <div class="text-xs mt-0.5" :class="isAllSelected ? 'text-[#1D5F5E]/80' : 'text-gray-400'">
              All works combined
            </div>
          </div>
        </div>

        <p class="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex-shrink-0">Specific Active LOAs</p>

        <!-- LOA list -->
        <div class="flex flex-col gap-2 overflow-y-auto flex-1 pr-1" style="scrollbar-width: thin;">
          <div
            v-for="loa in filteredLoas" :key="loa.id"
            @click="toggleLoa(loa.id)"
            class="relative px-4 py-3 rounded-xl cursor-pointer border transition-all flex-shrink-0"
            :class="selectedLoas.includes(loa.id)
              ? 'bg-[#1D5F5E]/5 border-[#1D5F5E]'
              : 'bg-white border-gray-200 hover:border-[#1D5F5E] hover:bg-[#1D5F5E]/5'">
            <div class="flex items-center justify-between gap-2">
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-1.5 min-w-0">
                  <span class="text-sm font-bold shrink-0"
                    :class="selectedLoas.includes(loa.id) ? 'text-[#1D5F5E]' : 'text-gray-900'">
                    {{ loa.label.split(' | ')[1] || loa.label }}
                  </span>
                  <span class="text-[11px] font-semibold bg-sky-100 text-sky-950 px-2 py-0.5 rounded-full truncate max-w-[160px]">{{ loa.label.split(' | ')[2] || '—' }}</span>
                  <span v-if="loa.contractor_nickname" class="text-[11px] font-semibold bg-[#fac9b8] text-[#7c3d2a] px-2 py-0.5 rounded-full truncate max-w-[120px]">{{ loa.contractor_nickname }}</span>
                  <span v-if="loa.label.split(' | ')[0]" class="text-[11px] font-semibold bg-amber-100 text-emerald-900 px-2 py-0.5 rounded-full truncate max-w-[160px]">{{ loa.label.split(' | ')[0] }}</span>
                </div>
              </div>
              <div class="flex items-center gap-1.5 flex-shrink-0">
                <div class="flex gap-1 items-center">
                  <div v-if="loa.supply_update && !seenLoas.has(loa.id)" class="w-2 h-2 rounded-full bg-[#1D5F5E]" title="Recent supply update"></div>
                  <div v-if="loa.execution_update && !seenLoas.has(loa.id)" class="w-2 h-2 rounded-full bg-[#34c759]" title="Recent execution update"></div>
                  <div v-if="loa.financial_update && !seenLoas.has(loa.id)" class="w-2 h-2 rounded-full bg-[#ff9500]" title="Recent bill upload"></div>
                </div>
                <div class="w-4 h-4 rounded border-2 flex-shrink-0 flex items-center justify-center transition-all"
                  :class="selectedLoas.includes(loa.id) ? 'bg-[#1D5F5E] border-[#1D5F5E]' : 'border-gray-300 bg-white'">
                  <div v-if="selectedLoas.includes(loa.id)" class="i-carbon-checkmark text-white text-[10px]"></div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="filteredLoas.length === 0 && loas.length > 0"
            class="text-center p-4 text-xs font-medium text-gray-400 bg-gray-50 rounded-lg border border-dashed border-gray-200">
            No works match search.
          </div>

          <div v-if="loas.length === 0"
            class="text-center p-4 text-xs font-medium text-gray-400 bg-gray-50 rounded-lg border border-dashed border-gray-200">
            No configured LOAs found. Upload data first.
          </div>
        </div>

        <!-- Multi-select summary -->
        <div v-if="selectedLoas.length > 0" class="flex-shrink-0 px-3 py-2 bg-[#1D5F5E]/5 rounded-lg border border-[#1D5F5E]/20 text-xs text-[#1D5F5E] font-medium">
          {{ selectedLoas.length }} work{{ selectedLoas.length > 1 ? 's' : '' }} selected — showing combined view
        </div>

      </div>
    </div>

  </div>
</template>

<style scoped>
@keyframes fade-in {
  from { opacity: 0; transform: translateY(5px); }
  to   { opacity: 1; transform: translateY(0); }
}
.animate-fade-in { animation: fade-in 0.3s ease-out; }
</style>
