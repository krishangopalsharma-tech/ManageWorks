<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import axios from 'axios'
import { Chart as ChartJS, Title, Tooltip, Legend, ArcElement } from 'chart.js'
import { Doughnut } from 'vue-chartjs'

ChartJS.register(Title, Tooltip, Legend, ArcElement)

const stats = ref(null)
const loas = ref([])
const activeLoa = ref(null)

const isLoading = ref(true)

const chartOptions = { responsive: true, maintainAspectRatio: false, cutout: '75%', plugins: { legend: { display: false } } }

const fetchStats = async () => {
    isLoading.value = true
    try {
        let url = '/api/dashboard/'
        if (activeLoa.value) {
            url += `?loa_id=${activeLoa.value}`
        }
        const res = await axios.get(url)
        stats.value = res.data
        loas.value = res.data.loas
    } catch(e) {
        console.error(e)
    } finally {
        isLoading.value = false
    }
}

watch(activeLoa, () => {
    fetchStats()
})

onMounted(() => {
    fetchStats()
})

const createChartData = (val, color) => {
    const remaining = Math.max(0, 100 - val)
    return {
        labels: ['Completed', 'Remaining'],
        datasets: [{
            data: [val, remaining],
            backgroundColor: [color, '#e5e5ea'],
            borderWidth: 0,
            hoverOffset: 2
        }]
    }
}

const supplyData = computed(() => createChartData(stats.value?.supply || 0, '#0071e3'))
const execData = computed(() => createChartData(stats.value?.execution || 0, '#34c759'))
const overallData = computed(() => createChartData(stats.value?.overall || 0, '#5856d6'))
const finData = computed(() => createChartData(stats.value?.financial || 0, '#ff9500'))

</script>

<template>
  <div class="h-full flex gap-6 animate-fade-in" style="animation-fill-mode: forwards;">
    <!-- Main Left Pane for Charts -->
    <div class="w-[60%] bg-light-surface rounded-2xl soft-shadow p-8 flex flex-col">
       <div class="w-full flex justify-between items-center mb-8 border-b border-gray-100 pb-4">
         <div>
            <h1 class="text-2xl font-bold text-gray-800 tracking-tight">Analytics Dashboard</h1>
         </div>
       </div>

       <div v-if="isLoading" class="flex-1 flex-center w-full">
           <div class="i-carbon-circle-dash animate-spin text-4xl text-[#0071e3]"></div>
       </div>
       <div v-else class="flex-1 w-full max-w-3xl mx-auto flex flex-col justify-center gap-10">
            
            <div class="grid grid-cols-2 gap-12 w-full">
                <!-- Supply Chart -->
                <div class="flex flex-col items-center bg-white border border-gray-100 rounded-2xl p-6 soft-shadow">
                    <h3 class="text-gray-800 font-bold mb-4 tracking-wide text-sm uppercase">Supply Progress</h3>
                    <div class="relative w-48 h-48 flex-center">
                        <h2 class="absolute text-3xl font-extrabold text-gray-800 z-10 pointer-events-none">{{ stats?.supply || 0 }}%</h2>
                        <Doughnut :data="supplyData" :options="chartOptions" />
                    </div>
                </div>

                <!-- Execution Chart -->
                <div class="flex flex-col items-center bg-white border border-gray-100 rounded-2xl p-6 soft-shadow">
                    <h3 class="text-gray-800 font-bold mb-4 tracking-wide text-sm uppercase">Execution Progress</h3>
                    <div class="relative w-48 h-48 flex-center">
                        <h2 class="absolute text-3xl font-extrabold text-gray-800 z-10 pointer-events-none">{{ stats?.execution || 0 }}%</h2>
                        <Doughnut :data="execData" :options="chartOptions" />
                    </div>
                </div>

                <!-- Overall Chart -->
                <div class="flex flex-col items-center bg-white border border-gray-100 rounded-2xl p-6 soft-shadow">
                    <h3 class="text-gray-800 font-bold mb-4 tracking-wide text-sm uppercase">Overall Progress</h3>
                    <div class="relative w-48 h-48 flex-center">
                        <h2 class="absolute text-3xl font-extrabold text-gray-800 z-10 pointer-events-none">{{ stats?.overall || 0 }}%</h2>
                        <Doughnut :data="overallData" :options="chartOptions" />
                    </div>
                </div>

                <!-- Financial Chart -->
                <div class="flex flex-col items-center bg-white border border-gray-100 rounded-2xl p-6 soft-shadow">
                    <h3 class="text-gray-800 font-bold mb-4 tracking-wide text-sm uppercase">Financial Progress</h3>
                    <div class="relative w-48 h-48 flex-center">
                        <h2 class="absolute text-3xl font-extrabold text-gray-800 z-10 pointer-events-none">{{ stats?.financial || 0 }}%</h2>
                        <Doughnut :data="finData" :options="chartOptions" />
                    </div>
                </div>
            </div>

       </div>
    </div>
    
    <!-- Right Pane for LOA Selection -->
    <div class="w-[40%] bg-light-surface rounded-2xl soft-shadow p-8 flex flex-col h-full bg-white border border-gray-100">
        <h2 class="text-lg font-bold text-gray-800 mb-4 px-1">View Context</h2>
        
        <div 
            @click="activeLoa = null"
            class="p-4 rounded-xl cursor-pointer border transition-all mb-5"
            :class="activeLoa === null ? 'bg-[#0071e3]/10 border-[#0071e3] text-[#0071e3] shadow-sm' : 'bg-[#f5f5f7] border-transparent text-gray-600 hover:border-gray-300'"
        >
            <div class="font-bold text-sm tracking-wide">Total Aggregation</div>
            <div class="text-xs mt-1" :class="activeLoa === null ? 'text-[#0071e3]/80' : 'text-gray-400'">All works combined</div>
        </div>

        <h3 class="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3 px-1">Specific Active LOAs</h3>
        
        <div class="flex flex-col gap-2 overflow-y-auto flex-1 pr-2">
            <div 
                v-for="loa in loas" :key="loa.id"
                @click="activeLoa = loa.id"
                class="p-4 rounded-xl cursor-pointer border transition-all text-sm leading-snug"
                :class="activeLoa === loa.id ? 'bg-[#0071e3] text-white border-[#0071e3] shadow-lg shadow-[#0071e3]/20' : 'bg-white border-gray-200 hover:border-[#0071e3]/40 text-gray-700'"
            >
                {{ loa.label }}
            </div>
            
            <div v-if="loas.length === 0 && !isLoading" class="text-center p-4 text-xs font-medium text-gray-400 bg-gray-50 rounded-lg border border-dashed border-gray-200">
                No configured LOAs found. Upload data first.
            </div>
        </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes fade-in {
  from { opacity: 0; transform: translateY(5px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-fade-in {
  animation: fade-in 0.3s ease-out;
}
</style>
