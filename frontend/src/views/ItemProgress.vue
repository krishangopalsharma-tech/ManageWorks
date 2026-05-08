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

const fmtDate = (val) => {
  if (!val) return '—'
  const s = String(val).split('T')[0].split(' ')[0]
  if (/^\d{2}[\/\-]\d{2}[\/\-]\d{4}$/.test(s)) return s.replace(/-/g, '/')
  const m = s.match(/^(\d{4})[\/\-](\d{2})[\/\-](\d{2})$/)
  if (m) return `${m[3]}/${m[2]}/${m[1]}`
  return s
}
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

// ── PDF Export ─────────────────────────────────────────────────────────────
const isGeneratingPDF = ref(false)

const generateItemPDF = async () => {
  if (!sortedResults.value.length) return
  isGeneratingPDF.value = true
  try {
    const { jsPDF } = await import('jspdf')
    const { default: autoTable } = await import('jspdf-autotable')

    const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' })
    const pw = doc.internal.pageSize.getWidth()
    const ph = doc.internal.pageSize.getHeight()
    const mg = 12
    const cw = pw - mg * 2

    const C_TEAL  = [29, 95, 94]
    const C_AMBER = [193, 120, 65]
    const C_BLUE  = [0, 113, 227]
    const C_GRAY  = [107, 114, 128]

    const items = sortedResults.value
    const st    = stats.value
    const today = new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })

    const addPageHeader = () => {
      doc.setFillColor(...C_TEAL)
      doc.rect(0, 0, pw, 12, 'F')
      doc.setTextColor(255, 255, 255)
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(8.5)
      doc.text('Item Progress Report', mg, 8)
      if (itemSearch.value) {
        doc.setFont('helvetica', 'normal')
        doc.setFontSize(7.5)
        doc.text(`Search: "${itemSearch.value}"`, pw / 2, 8, { align: 'center' })
      }
      doc.setFontSize(7)
      doc.text(today, pw - mg, 8, { align: 'right' })
    }

    addPageHeader()

    // Stats summary
    autoTable(doc, {
      startY: 16,
      margin: { left: mg, right: mg },
      head: [['Supply Progress (Sch A)', 'Execution Progress (Sch B)', 'Supply Items', 'Exec Items', 'Total Items Found']],
      body: [[
        `${st.supplyPct}%`,
        `${st.execPct}%`,
        String(st.supplyCount),
        String(st.execCount),
        String(items.length),
      ]],
      headStyles: { fillColor: C_TEAL, textColor: [255, 255, 255], fontSize: 8, fontStyle: 'bold', halign: 'center' },
      bodyStyles: { fontSize: 10, fontStyle: 'bold', halign: 'center', minCellHeight: 9 },
      columnStyles: {
        0: { textColor: C_TEAL },
        1: { textColor: C_AMBER },
      },
      tableLineColor: [229, 231, 235],
      tableLineWidth: 0.2,
    })

    let y = doc.lastAutoTable.finalY + 6

    for (const item of items) {
      const sch = String(item.schedule || '').toUpperCase().trim()
      const isB = sch.startsWith('B')
      const done = isB ? (item.executed_quantity || 0) : (item.supplied_quantity || 0)
      const pct = item.qty ? Math.min(done / item.qty * 100, 999).toFixed(0) : '0'
      const pctNum = parseFloat(pct)

      // Estimate space needed: item header ~7mm + entries * ~5mm + gap 4mm
      const neededH = 8 + (item.entries || []).length * 5 + 4
      if (y + Math.min(neededH, 30) > ph - 12) {
        doc.addPage()
        addPageHeader()
        y = 16
      }

      // Item header block
      autoTable(doc, {
        startY: y,
        margin: { left: mg, right: mg },
        head: [[
          { content: `${item.loa_number || '—'}  ·  ${item.schedule}  ·  S.No ${item.serial_number}`, styles: { fillColor: [235, 245, 244], textColor: C_TEAL, fontStyle: 'bold', fontSize: 7.5 } },
          { content: `Required: ${item.qty} ${item.unit}`, styles: { fillColor: [235, 245, 244], textColor: C_GRAY, fontSize: 7.5, halign: 'right' } },
          { content: `${isB ? 'Executed' : 'Supplied'}: ${done} ${item.unit}`, styles: { fillColor: [235, 245, 244], textColor: C_GRAY, fontSize: 7.5, halign: 'right' } },
          { content: `${pct}%`, styles: { fillColor: [235, 245, 244], textColor: pctNum >= 99 ? C_TEAL : pctNum > 0 ? C_BLUE : C_GRAY, fontStyle: 'bold', fontSize: 8, halign: 'right' } },
        ]],
        body: [[{ content: item.item_desc || '', colSpan: 4, styles: { fontSize: 7.5, textColor: [50, 50, 50], cellPadding: { top: 2, bottom: 2, left: 3, right: 3 } } }]],
        columnStyles: {
          0: { cellWidth: 'auto' },
          1: { cellWidth: 38 },
          2: { cellWidth: 40 },
          3: { cellWidth: 22 },
        },
        tableLineColor: [209, 231, 229],
        tableLineWidth: 0.2,
      })

      y = doc.lastAutoTable.finalY

      if ((item.entries || []).length > 0) {
        autoTable(doc, {
          startY: y,
          margin: { left: mg + 3, right: mg },
          head: [['#', 'Type', 'Qty', 'Receive Note / Challan', 'UDM Entry', 'Submitted By', 'Date']],
          body: item.entries.map((e, idx) => [
            idx + 1,
            e.entry_type === 'execution' ? 'Exec' : 'Supply',
            `${e.quantity} ${item.unit}`,
            [e.receive_note_no, e.challan_no].filter(Boolean).join(' / ') || '—',
            e.udm_entry || '—',
            (() => {
              const u = e.submitted_by_user
              if (!u) return '—'
              const name = u.full_name || u.username
              const desig = u.designation
              return desig ? `${name}\n(${desig})` : name
            })(),
            e.date_of_receipt ? fmtDate(e.date_of_receipt) : fmtDateTime(e.submitted_at),
          ]),
          headStyles: { fillColor: [241, 245, 249], textColor: C_GRAY, fontSize: 7, fontStyle: 'bold' },
          bodyStyles: { fontSize: 7 },
          columnStyles: {
            0: { cellWidth: 8, halign: 'center' },
            1: { cellWidth: 16 },
            2: { cellWidth: 24, halign: 'right' },
            3: { cellWidth: 'auto' },
            4: { cellWidth: 28 },
            5: { cellWidth: 30 },
            6: { cellWidth: 28 },
          },
          tableLineColor: [229, 231, 235],
          tableLineWidth: 0.15,
          didParseCell: (data) => {
            if (data.column.index === 1 && data.section === 'body') {
              data.cell.styles.textColor = data.cell.raw === 'Exec' ? C_AMBER : C_TEAL
              data.cell.styles.fontStyle = 'bold'
            }
          },
        })
        y = doc.lastAutoTable.finalY + 5
      } else {
        y += 5
      }
    }

    // Page numbers
    const totalPages = doc.getNumberOfPages()
    for (let i = 1; i <= totalPages; i++) {
      doc.setPage(i)
      doc.setFont('helvetica', 'normal')
      doc.setFontSize(7)
      doc.setTextColor(...C_GRAY)
      doc.text(`Page ${i} of ${totalPages}`, pw - mg, ph - 4, { align: 'right' })
      doc.text('ManageWorks — Item Progress Report', mg, ph - 4)
    }

    const safeName = (itemSearch.value || 'export').replace(/[^a-z0-9]/gi, '_').substring(0, 30)
    doc.save(`Item_Progress_${safeName}_${new Date().toISOString().substring(0, 10)}.pdf`)
  } finally {
    isGeneratingPDF.value = false
  }
}
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
        <div class="flex-1 flex items-center bg-gray-50 border border-gray-200 rounded-2xl px-5 py-3 focus-within:ring-2 focus-within:ring-[#1D5F5E]/20 focus-within:border-[#1D5F5E] focus-within:bg-white transition-all">
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
            class="w-full flex items-center justify-between bg-gray-50 border border-gray-200 rounded-2xl px-5 py-3 text-sm font-medium text-gray-700 hover:border-[#1D5F5E] hover:bg-white transition-all">
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
              <button @click="selectedIds = allWorks.map(w => w.id)" class="text-xs font-semibold text-[#1D5F5E] hover:underline">Select All</button>
              <span class="text-gray-200">·</span>
              <button @click="selectedIds = []" class="text-xs font-semibold text-gray-400 hover:text-gray-600 hover:underline">Clear All</button>
            </div>
            <div class="max-h-60 overflow-y-auto" style="scrollbar-width: thin;">
              <div v-if="filteredWorksDropdown.length === 0" class="px-4 py-6 text-center text-xs text-gray-400">No works found</div>
              <label v-for="work in filteredWorksDropdown" :key="work.id"
                class="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors border-b border-gray-50 last:border-0">
                <input type="checkbox" :checked="selectedIds.includes(work.id)" @change="toggleWork(work.id)"
                  class="mt-0.5 accent-[#1D5F5E] flex-shrink-0" @click.stop>
                <div class="min-w-0">
                  <p class="text-xs font-semibold text-gray-800 truncate">{{ work.loa_number || '—' }}</p>
                  <p class="text-[11px] text-gray-400 truncate">{{ work.contractor_name || '—' }}</p>
                </div>
              </label>
            </div>
          </div>
        </div>
      </div>

      <!-- Progress stats pills + Export -->
      <div v-if="searchResults.length > 0" class="mt-4 flex flex-wrap items-center gap-3">
        <div class="flex items-center gap-2 bg-accent-soft border border-accent/20 rounded-xl px-4 py-2">
          <div class="w-2 h-2 rounded-full bg-accent"></div>
          <span class="text-xs font-semibold text-accent">
            Supply (Sch A): {{ stats.supplyPct }}%
            <span class="font-normal opacity-70">({{ stats.supplyCount }} items)</span>
          </span>
        </div>
        <div class="flex items-center gap-2 bg-accent-b-soft border border-accent-b/20 rounded-xl px-4 py-2">
          <div class="w-2 h-2 rounded-full bg-accent-b"></div>
          <span class="text-xs font-semibold text-accent-b">
            Execution (Sch B): {{ stats.execPct }}%
            <span class="font-normal opacity-70">({{ stats.execCount }} items)</span>
          </span>
        </div>
        <div class="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-4 py-2">
          <div class="i-carbon-list text-gray-400 text-sm"></div>
          <span class="text-xs font-semibold text-gray-600">{{ searchResults.length }} items found</span>
        </div>

        <button @click="generateItemPDF" :disabled="isGeneratingPDF"
          class="ml-auto flex items-center gap-1.5 px-4 py-2 rounded-xl border border-gray-300 text-xs font-semibold text-gray-600 hover:bg-gray-100 hover:border-gray-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0">
          <div :class="isGeneratingPDF ? 'i-carbon-circle-dash animate-spin' : 'i-carbon-document-pdf'" class="text-sm"></div>
          {{ isGeneratingPDF ? 'Generating…' : 'Export PDF' }}
        </button>
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
              <span class="text-[11px] font-semibold text-accent bg-accent-soft px-2 py-0.5 rounded-full whitespace-nowrap">
                {{ item.loa_number || '—' }}
              </span>
            </td>
            <td class="px-4 py-3 text-center">
              <span class="rounded-md px-2 py-1 text-[10px] font-bold"
                :class="isSchB(item) ? 'bg-accent-b-soft text-accent-b' : 'bg-accent-soft text-accent'">
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
                    :class="progressPct(item) > 100 ? 'bg-orange-400' : (isSchB(item) ? 'bg-accent-b' : 'bg-accent')"
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
                :class="(item.entries||[]).length > 0 ? 'text-accent' : 'text-gray-300'">
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
                  :class="isSchB(hoveredItem) ? 'bg-accent-b-soft text-accent-b' : 'bg-accent-soft text-accent'">
                  {{ hoveredItem.schedule }}
                </span>
                <span class="text-[10px] font-semibold text-gray-400">S.No {{ hoveredItem.serial_number }}</span>
                <span class="ml-auto text-[10px] font-semibold text-accent bg-accent-soft px-2 py-0.5 rounded-full">
                  {{ hoveredItem.loa_number }}
                </span>
              </div>
              <p class="text-xs font-semibold text-gray-800 leading-snug line-clamp-2">{{ hoveredItem.item_desc }}</p>
              <!-- Sch-B: show supply + execution totals -->
              <div v-if="isSchB(hoveredItem)" class="mt-2 flex gap-3">
                <span class="text-[10px] text-gray-500">
                  Supplied: <strong class="text-accent">{{ hoveredItem.supplied_quantity || 0 }}</strong>
                  <span class="text-gray-400"> {{ hoveredItem.unit }}</span>
                </span>
                <span class="text-gray-200">·</span>
                <span class="text-[10px] text-gray-500">
                  Executed: <strong class="text-accent-b">{{ hoveredItem.executed_quantity || 0 }}</strong>
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
                      :class="entry.entry_type === 'supply' ? 'bg-accent-soft text-accent' : 'bg-accent-b-soft text-accent-b'">
                      {{ (hoveredItem.entries || []).length - idx }}
                    </span>
                    <span class="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide"
                      :class="entry.entry_type === 'supply' ? 'bg-accent-soft text-accent' : 'bg-accent-b-soft text-accent-b'">
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
                    {{ entry.submitted_by_user?.full_name || entry.submitted_by_user?.username || '—' }}
                    <span v-if="entry.submitted_by_user?.designation" class="text-gray-400"> · {{ entry.submitted_by_user.designation }}</span>
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
                    <span v-if="entry.location" class="flex items-center gap-1 text-[10px] text-accent-b font-medium truncate">
                      <div class="i-carbon-location text-accent-b/60" style="font-size:10px;"></div>
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
                <span class="text-[10px] font-bold text-accent">
                  {{ hoveredItem.supplied_quantity || 0 }}
                  <span class="text-gray-400 font-normal">{{ hoveredItem.unit }} sup</span>
                </span>
                <template v-if="isSchB(hoveredItem)">
                  <span class="text-gray-200">·</span>
                  <span class="text-[10px] font-bold text-accent-b">
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
