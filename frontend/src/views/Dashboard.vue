<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import axios from 'axios'
import { Chart as ChartJS, Title, Tooltip, Legend, ArcElement, CategoryScale, LinearScale, BarElement } from 'chart.js'
import { Doughnut, Bar } from 'vue-chartjs'

ChartJS.register(Title, Tooltip, Legend, ArcElement, CategoryScale, LinearScale, BarElement)

const stats     = ref(null)
const loas      = ref([])
const trendData = ref([])
const activeLoa    = ref(null)
const activePeriod = ref('monthly')
const isLoading      = ref(true)
const isTrendLoading = ref(false)

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

const supplyData  = computed(() => mkDoughnut(stats.value?.supply     || 0, '#0071e3'))
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
      backgroundColor: 'rgba(0, 113, 227, 0.85)',
      hoverBackgroundColor: '#0071e3',
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
    const url = activeLoa.value ? `/api/dashboard/?loa_id=${activeLoa.value}` : '/api/dashboard/'
    const res = await axios.get(url)
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
    if (activeLoa.value) params.loa_id = activeLoa.value
    const res = await axios.get('/api/dashboard/trend/', { params })
    trendData.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    isTrendLoading.value = false
  }
}

watch(activeLoa,    () => { fetchStats(); fetchTrend() })
watch(activePeriod, () => fetchTrend())
onMounted(() => { fetchStats(); fetchTrend() })
</script>

<template>
  <div class="h-full flex gap-6 animate-fade-in" style="animation-fill-mode: forwards;">

    <!-- ── Left: Analytics Dashboard ─────────────────────────────────── -->
    <div class="w-[60%] bg-light-surface rounded-2xl soft-shadow flex flex-col overflow-hidden">

      <!-- Card header -->
      <div class="px-7 pt-6 pb-4 border-b border-gray-100 flex-shrink-0">
        <h1 class="text-xl font-bold text-gray-800 tracking-tight">Analytics Dashboard</h1>
      </div>

      <!-- Loading -->
      <div v-if="isLoading" class="flex-1 flex items-center justify-center">
        <div class="i-carbon-circle-dash animate-spin text-4xl text-[#0071e3]"></div>
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
            <div class="mt-2 w-2 h-2 rounded-full bg-[#0071e3]"></div>
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
            <div class="flex items-center gap-1 bg-gray-100 rounded-full p-1">
              <button
                v-for="p in periods" :key="p.value"
                @click="activePeriod = p.value"
                :class="activePeriod === p.value
                  ? 'bg-white text-[#0071e3] shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'"
                class="px-3 py-1 rounded-full text-xs font-semibold transition-all">
                {{ p.label }}
              </button>
            </div>
          </div>

          <!-- Chart area -->
          <div class="flex-1 min-h-0 px-5 py-4 relative">
            <div v-if="isTrendLoading" class="absolute inset-0 flex items-center justify-center">
              <div class="i-carbon-circle-dash animate-spin text-2xl text-[#0071e3]"></div>
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

    <!-- ── Right: LOA Selection ───────────────────────────────────────── -->
    <div class="w-[40%] bg-light-surface rounded-2xl soft-shadow flex flex-col overflow-hidden">

      <div class="px-7 pt-6 pb-4 border-b border-gray-100 flex-shrink-0">
        <h2 class="text-base font-bold text-gray-800">View Context</h2>
        <p class="text-xs text-gray-400 font-medium mt-0.5">Filter all charts by a specific work</p>
      </div>

      <div class="flex-1 min-h-0 flex flex-col overflow-hidden p-5 gap-3">

        <!-- Total aggregation option -->
        <div
          @click="activeLoa = null"
          class="px-4 py-3 rounded-xl cursor-pointer border transition-all flex-shrink-0"
          :class="activeLoa === null
            ? 'bg-[#0071e3]/10 border-[#0071e3] text-[#0071e3]'
            : 'bg-[#f5f5f7] border-transparent text-gray-600 hover:border-gray-300'">
          <div class="font-bold text-sm tracking-wide">Total Aggregation</div>
          <div class="text-xs mt-0.5" :class="activeLoa === null ? 'text-[#0071e3]/80' : 'text-gray-400'">
            All works combined
          </div>
        </div>

        <p class="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex-shrink-0">Specific Active LOAs</p>

        <!-- LOA list -->
        <div class="flex flex-col gap-2 overflow-y-auto flex-1 pr-1" style="scrollbar-width: thin;">
          <div
            v-for="loa in loas" :key="loa.id"
            @click="activeLoa = loa.id"
            class="px-4 py-3 rounded-xl cursor-pointer border transition-all text-sm leading-snug flex-shrink-0"
            :class="activeLoa === loa.id
              ? 'bg-[#0071e3] text-white border-[#0071e3] shadow-lg shadow-[#0071e3]/20'
              : 'bg-white border-gray-200 hover:border-[#0071e3]/40 text-gray-700'">
            {{ loa.label }}
          </div>

          <div v-if="loas.length === 0"
            class="text-center p-4 text-xs font-medium text-gray-400 bg-gray-50 rounded-lg border border-dashed border-gray-200">
            No configured LOAs found. Upload data first.
          </div>
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
