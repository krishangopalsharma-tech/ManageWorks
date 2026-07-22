<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'

const allWorks       = ref([])
const allRows        = ref([])
const isLoadingWorks = ref(true)
const isLoadingData  = ref(false)
const workSearch     = ref('')
const itemSearch     = ref('')
const locationSearch = ref('')
const selectedIds    = ref([])
const dropdownOpen   = ref(false)
const dropdownRef    = ref(null)
const expandedKey    = ref(null)

const fmtDateTime = (val) => {
  if (!val) return '—'
  const d = new Date(val)
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}
const fmtDate = (val) => {
  if (!val) return '—'
  const d = new Date(val)
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

// ── Works dropdown ─────────────────────────────────────────────────────────────
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
  if (noneSelected.value) return 'Select Work…'
  if (allSelected.value)  return 'All Works'
  const n = selectedIds.value.length
  if (n === 1) { const w = allWorks.value.find(w => w.id === selectedIds.value[0]); return w?.loa_number || w?.contractor_name || '1 work' }
  return `${n} works selected`
})
const toggleWork = (id) => {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

// ── Load data ──────────────────────────────────────────────────────────────────
let loadTimer = null
const loadData = async () => {
  if (noneSelected.value) { allRows.value = []; return }
  isLoadingData.value = true
  expandedKey.value = null
  try {
    const params = {}
    if (!allSelected.value) params.work_ids = selectedIds.value.join(',')
    const res = await axios.get('/api/location-progress/data/', { params })
    allRows.value = res.data
  } catch (e) { console.error(e) }
  finally { isLoadingData.value = false }
}

watch(selectedIds, () => {
  clearTimeout(loadTimer)
  loadTimer = setTimeout(loadData, 300)
}, { deep: true })

// ── Category filter ────────────────────────────────────────────────────────────
const selectedCategories = ref(['supply_installation', 'execution'])
const toggleCategory = (cat) => {
  const idx = selectedCategories.value.indexOf(cat)
  if (idx >= 0) selectedCategories.value.splice(idx, 1)
  else selectedCategories.value.push(cat)
}

// ── Filtered rows ──────────────────────────────────────────────────────────────
const filteredRows = computed(() => {
  let rows = allRows.value

  if (selectedCategories.value.length < 2) {
    rows = rows.filter(r => selectedCategories.value.includes(r.category || 'supply'))
  }

  const iq = itemSearch.value.toLowerCase().trim()
  if (iq) {
    rows = rows.filter(r =>
      (r.item_desc     && r.item_desc.toLowerCase().includes(iq)) ||
      (r.serial_number && r.serial_number.toLowerCase().includes(iq)) ||
      (r.schedule      && r.schedule.toLowerCase().includes(iq))
    )
  }

  const lq = locationSearch.value.toUpperCase().trim()
  if (lq) {
    rows = rows.filter(r => r.location.includes(lq))
  }

  return rows
})

// ── Sorting ────────────────────────────────────────────────────────────────────
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
    else if (sortKey.value === 'location') { av = a.location; bv = b.location; return sortDir.value === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av) }
    else { av = 0; bv = 0 }
    return sortDir.value === 'asc' ? av - bv : bv - av
  })
})

// ── Stats ──────────────────────────────────────────────────────────────────────
const stats = computed(() => {
  const rows = filteredRows.value
  const sections = rows.filter(r => r.location_type === 'section').length
  const stations = rows.filter(r => r.location_type === 'station').length
  const siCount  = rows.filter(r => r.category === 'supply_installation').length
  const exCount  = rows.filter(r => r.category === 'execution').length
  return { sections, stations, siCount, exCount }
})

// ── Expand toggle ──────────────────────────────────────────────────────────────
const rowKey = (r) => `${r.location}__${r.work_item_id}`
const toggleExpand = (r) => {
  const k = rowKey(r)
  expandedKey.value = expandedKey.value === k ? null : k
}

// ── PDF Export ─────────────────────────────────────────────────────────────────
const isGeneratingPDF    = ref(false)
const showPdfModal       = ref(false)
const pdfIncludeEntries  = ref(null)

const onExportClick = () => { showPdfModal.value = true; pdfIncludeEntries.value = null }
const confirmPdfExport = async (includeEntries) => {
  pdfIncludeEntries.value = includeEntries
  showPdfModal.value = false
  await generateLocationPDF(includeEntries)
}

const generateLocationPDF = async (includeEntries = true) => {
  if (!filteredRows.value.length) return
  isGeneratingPDF.value = true
  try {
    const { jsPDF } = await import('jspdf')
    const { default: autoTable } = await import('jspdf-autotable')

    const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' })
    const pw = doc.internal.pageSize.getWidth()
    const ph = doc.internal.pageSize.getHeight()
    const mg = 12

    const C_TEAL  = [29, 95, 94]
    const C_AMBER = [193, 120, 65]
    const C_BLUE  = [0, 113, 227]
    const C_GRAY  = [107, 114, 128]

    const rows  = sortedRows.value
    const st    = stats.value
    const today = new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })

    const addPageHeader = () => {
      doc.setFillColor(...C_TEAL)
      doc.rect(0, 0, pw, 12, 'F')
      doc.setTextColor(255, 255, 255)
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(8.5)
      doc.text('Location Progress Report', mg, 8)
      const filters = [
        itemSearch.value     && `Item: "${itemSearch.value}"`,
        locationSearch.value && `Location: "${locationSearch.value}"`,
      ].filter(Boolean).join('  ·  ')
      if (filters) {
        doc.setFont('helvetica', 'normal')
        doc.setFontSize(7.5)
        doc.text(filters, pw / 2, 8, { align: 'center' })
      }
      doc.setFontSize(7)
      doc.text(today, pw - mg, 8, { align: 'right' })
    }

    addPageHeader()

    autoTable(doc, {
      startY: 16,
      margin: { left: mg, right: mg },
      head: [['S+I Rows', 'Execution Rows', 'Sections', 'Stations', 'Total Rows']],
      body: [[String(st.siCount), String(st.exCount), String(st.sections), String(st.stations), String(rows.length)]],
      headStyles: { fillColor: C_TEAL, textColor: [255, 255, 255], fontSize: 8, fontStyle: 'bold', halign: 'center' },
      bodyStyles: { fontSize: 10, fontStyle: 'bold', halign: 'center', minCellHeight: 9 },
      columnStyles: { 0: { textColor: [109, 40, 217] }, 1: { textColor: C_AMBER } },
      tableLineColor: [229, 231, 235],
      tableLineWidth: 0.2,
    })

    let y = doc.lastAutoTable.finalY + 6

    for (const row of rows) {
      const entryCount = (row.entries || []).length
      const neededH = 10 + (includeEntries ? entryCount * 5 + 4 : 0)
      if (y + Math.min(neededH, 30) > ph - 12) {
        doc.addPage()
        addPageHeader()
        y = 16
      }

      autoTable(doc, {
        startY: y,
        margin: { left: mg, right: mg },
        head: [[
          { content: `${row.location_type === 'section' ? 'SECTION' : 'STATION'}  ${row.location}`, styles: { fillColor: row.location_type === 'section' ? [219, 234, 254] : [220, 252, 231], textColor: row.location_type === 'section' ? [29, 78, 216] : [21, 128, 61], fontStyle: 'bold', fontSize: 7.5 } },
          { content: `${row.loa_number || '—'}\n${row.contractor_name || '—'}`, styles: { fillColor: [235, 245, 244], textColor: C_TEAL, fontSize: 7 } },
          { content: `${row.schedule || '—'}  ·  S.No ${row.serial_number || '—'}`, styles: { fillColor: [235, 245, 244], textColor: C_GRAY, fontSize: 7, halign: 'center' } },
          { content: `Executed here: ${row.executed_here} ${row.unit}`, styles: { fillColor: [235, 245, 244], textColor: C_AMBER, fontSize: 7.5, halign: 'right' } },
          { content: `Scope: ${row.scope} ${row.unit}`, styles: { fillColor: [235, 245, 244], textColor: C_GRAY, fontSize: 7.5, halign: 'right' } },
          { content: `Remaining: ${row.remaining} ${row.unit}`, styles: { fillColor: [235, 245, 244], textColor: row.remaining < 0 ? [220, 80, 30] : C_GRAY, fontSize: 7.5, halign: 'right' } },
          { content: `${row.progress_pct}%`, styles: { fillColor: [235, 245, 244], textColor: row.progress_pct > 100 ? C_AMBER : row.progress_pct >= 99 ? C_TEAL : C_BLUE, fontStyle: 'bold', fontSize: 8, halign: 'right' } },
        ]],
        body: [[{
          content: (() => { const d = row.item_desc || ''; return d.length > 160 ? d.substring(0, 157) + '…' : d })(),
          colSpan: 7,
          styles: { fontSize: 7.5, textColor: [50, 50, 50], cellPadding: { top: 2, bottom: 2, left: 3, right: 3 } },
        }]],
        columnStyles: {
          0: { cellWidth: 38 },
          1: { cellWidth: 44 },
          2: { cellWidth: 28, halign: 'center' },
          3: { cellWidth: 36, halign: 'right' },
          4: { cellWidth: 32, halign: 'right' },
          5: { cellWidth: 36, halign: 'right' },
          6: { cellWidth: 20, halign: 'right' },
        },
        tableLineColor: [209, 231, 229],
        tableLineWidth: 0.2,
      })

      y = doc.lastAutoTable.finalY

      if (includeEntries && entryCount > 0) {
        const hasPrivacyNote = row.visible_entries_count < row.entries_count
        autoTable(doc, {
          startY: y,
          margin: { left: mg + 3, right: mg },
          head: [['#', 'Qty', 'Submitted By', 'Designation', 'Date & Time', 'Remarks']],
          body: [
            ...row.entries.map((e, idx) => [
              idx + 1,
              `${e.quantity} ${row.unit}`,
              e.submitted_by_name || '—',
              e.submitted_by_designation || '—',
              fmtDateTime(e.submitted_at),
              e.remarks || '—',
            ]),
            ...(hasPrivacyNote ? [[{
              content: `(${row.visible_entries_count} of ${row.entries_count} entries shown — limited by access level)`,
              colSpan: 6,
              styles: { textColor: C_GRAY, fontSize: 6.5, fontStyle: 'italic', halign: 'center' },
            }]] : []),
          ],
          headStyles: { fillColor: [241, 245, 249], textColor: C_GRAY, fontSize: 7, fontStyle: 'bold' },
          bodyStyles: { fontSize: 7 },
          columnStyles: {
            0: { cellWidth: 8, halign: 'center' },
            1: { cellWidth: 24, halign: 'right' },
            2: { cellWidth: 36 },
            3: { cellWidth: 32 },
            4: { cellWidth: 34 },
            5: { cellWidth: 'auto' },
          },
          tableLineColor: [229, 231, 235],
          tableLineWidth: 0.15,
        })
        y = doc.lastAutoTable.finalY + 5
      } else {
        y += 5
      }
    }

    const totalPages = doc.getNumberOfPages()
    for (let i = 1; i <= totalPages; i++) {
      doc.setPage(i)
      doc.setFont('helvetica', 'normal')
      doc.setFontSize(7)
      doc.setTextColor(...C_GRAY)
      doc.text(`Page ${i} of ${totalPages}`, pw - mg, ph - 4, { align: 'right' })
      doc.text('ManageWorks — Location Progress Report', mg, ph - 4)
    }

    const safeName = (locationSearch.value || dropdownLabel.value || 'export').replace(/[^a-z0-9]/gi, '_').substring(0, 30)
    doc.save(`Location_Progress_${safeName}_${new Date().toISOString().substring(0, 10)}.pdf`)
  } finally {
    isGeneratingPDF.value = false
  }
}

// ── Dropdown close ─────────────────────────────────────────────────────────────
const closeDropdown = (e) => {
  if (dropdownRef.value && !dropdownRef.value.contains(e.target)) dropdownOpen.value = false
}
onMounted(() => { loadWorks(); document.addEventListener('click', closeDropdown) })
onBeforeUnmount(() => { document.removeEventListener('click', closeDropdown); clearTimeout(loadTimer) })
</script>

<template>
  <div class="bg-white rounded-2xl soft-shadow h-full w-full flex flex-col overflow-hidden">

    <!-- Header -->
    <div class="flex-shrink-0 px-8 pt-7 pb-5 border-b border-gray-100">
      <h1 class="text-2xl font-bold text-gray-900 tracking-tight mb-1">Location Progress</h1>
      <p class="text-gray-400 text-sm font-medium mb-4">S+I and Execution entries grouped by location — station or section.</p>

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
              <span class="truncate text-sm" :class="noneSelected ? 'text-gray-400' : 'text-gray-700'">
                {{ isLoadingWorks ? 'Loading…' : dropdownLabel }}
              </span>
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

        <!-- Category filter pills — S+I and Execution only -->
        <div class="flex items-center gap-1.5 flex-shrink-0">
          <button @click="toggleCategory('supply_installation')"
            class="px-3 py-2 rounded-xl text-[11px] font-bold border transition-all"
            :class="selectedCategories.includes('supply_installation')
              ? 'bg-data-si/10 border-data-si/30 text-data-si'
              : 'bg-white border-gray-200 text-gray-400'">
            S+I
          </button>
          <button @click="toggleCategory('execution')"
            class="px-3 py-2 rounded-xl text-[11px] font-bold border transition-all"
            :class="selectedCategories.includes('execution')
              ? 'bg-data-exec/10 border-data-exec/30 text-data-exec'
              : 'bg-white border-gray-200 text-gray-400'">
            Execution
          </button>
        </div>

        <div class="w-px h-6 bg-gray-200 flex-shrink-0"></div>

        <!-- Search bars: 50-50 split -->
        <div class="flex-1 flex gap-2">
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
          <div class="flex-1 flex items-center bg-gray-50 border border-gray-200 rounded-2xl px-4 py-2.5 focus-within:ring-2 focus-within:ring-[#1D5F5E]/20 focus-within:border-[#1D5F5E] focus-within:bg-white transition-all">
            <div class="i-carbon-location text-gray-400 text-base mr-2 flex-shrink-0"></div>
            <input v-model="locationSearch" type="text"
              placeholder="Search by location (e.g. ADI, ASV-NRD)…"
              style="text-transform:uppercase"
              class="bg-transparent outline-none w-full text-gray-700 font-medium placeholder-gray-400 text-sm">
            <button v-if="locationSearch" @click="locationSearch = ''" class="ml-2 text-gray-300 hover:text-gray-500 transition-colors">
              <div class="i-carbon-close text-sm"></div>
            </button>
          </div>
        </div>
      </div>

      <!-- Stats pills + Export PDF button -->
      <div v-if="filteredRows.length > 0" class="flex flex-wrap items-center gap-3 mt-2.5">
        <div class="flex items-center gap-2 bg-data-si/10 border border-data-si/25 rounded-xl px-4 py-2">
          <div class="w-2 h-2 rounded-full bg-data-si"></div>
          <span class="text-xs font-semibold text-data-si">S+I: {{ stats.siCount }}</span>
        </div>
        <div class="flex items-center gap-2 bg-data-exec/10 border border-data-exec/25 rounded-xl px-4 py-2">
          <div class="w-2 h-2 rounded-full bg-data-exec"></div>
          <span class="text-xs font-semibold text-data-exec">Execution: {{ stats.exCount }}</span>
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
        <button @click="onExportClick" :disabled="isGeneratingPDF"
          class="ml-auto flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold border transition-all bg-white border-gray-200 text-gray-600 hover:border-[#1D5F5E] hover:text-[#1D5F5E] hover:bg-accent-soft disabled:opacity-50 disabled:cursor-not-allowed">
          <div :class="isGeneratingPDF ? 'i-carbon-circle-dash animate-spin' : 'i-carbon-document-pdf'" class="text-sm"></div>
          {{ isGeneratingPDF ? 'Generating…' : 'Export PDF' }}
        </button>
      </div>
    </div>

    <!-- Select a work prompt -->
    <div v-if="noneSelected && !isLoadingData" class="flex-1 flex flex-col items-center justify-center py-24 text-center">
      <div class="i-carbon-building text-5xl text-gray-200 mb-4"></div>
      <p class="text-sm font-semibold text-gray-400">Select a work to view location data.</p>
      <p class="text-xs text-gray-300 mt-1">Use the dropdown above to choose one or more works.</p>
    </div>

    <!-- Loading -->
    <div v-else-if="isLoadingData" class="flex-1 flex flex-col items-center justify-center py-24 text-center">
      <div class="i-carbon-circle-dash animate-spin text-4xl text-gray-300 mb-4"></div>
      <p class="text-sm font-semibold text-gray-400">Loading location data…</p>
    </div>

    <!-- Empty — no entries for selected work(s) -->
    <div v-else-if="!isLoadingData && allRows.length === 0" class="flex-1 flex flex-col items-center justify-center py-24 text-center">
      <div class="i-carbon-location text-5xl text-gray-200 mb-4"></div>
      <p class="text-sm font-semibold text-gray-400">No location data for selected work(s).</p>
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
                <span class="rounded-md px-2 py-1 text-[10px] font-bold bg-data-exec/10 text-data-exec">
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
                :class="row.executed_here > row.scope ? 'text-status-critical' : 'text-gray-800'">
                {{ row.executed_here }}
                <span class="text-gray-400 font-normal">{{ row.unit }}</span>
              </td>

              <!-- Scope -->
              <td class="px-4 py-3 text-right text-xs font-semibold text-gray-600">
                {{ row.scope }} <span class="text-gray-400 font-normal">{{ row.unit }}</span>
              </td>

              <!-- Remaining -->
              <td class="px-4 py-3 text-right text-xs font-semibold"
                :class="row.remaining < 0 ? 'text-status-critical' : 'text-gray-600'">
                {{ row.remaining }} <span class="text-gray-400 font-normal">{{ row.unit }}</span>
              </td>

              <!-- Progress -->
              <td class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div class="h-full rounded-full transition-all duration-500"
                      :class="row.progress_pct > 100 ? 'bg-status-critical' : 'bg-data-exec'"
                      :style="{ width: Math.min(row.progress_pct, 100) + '%' }"></div>
                  </div>
                  <span class="text-[10px] font-bold w-8 text-right"
                    :class="row.progress_pct > 100 ? 'text-status-critical' : 'text-gray-500'">
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

                  <!-- No entries -->
                  <div v-if="!row.entries.length" class="px-4 py-8 text-center text-xs text-gray-400 font-medium">
                    No entries to display.
                  </div>

                  <!-- Entries table -->
                  <div v-else class="overflow-x-auto">
                    <table class="w-full text-xs">
                      <thead class="bg-gray-50 text-[10px] text-gray-400 font-bold uppercase tracking-widest">
                        <tr>
                          <th class="px-4 py-2 text-left w-10">#</th>
                          <th class="px-4 py-2 text-left w-24">Date</th>
                          <th class="px-4 py-2 text-left">Entry By</th>
                          <th class="px-4 py-2 text-left">Remarks</th>
                          <th class="px-4 py-2 text-right w-28">Quantity</th>
                        </tr>
                      </thead>
                      <tbody class="divide-y divide-gray-50">
                        <tr v-for="(entry, idx) in [...row.entries].reverse()" :key="entry.id"
                          class="hover:bg-gray-50/50 transition-colors">
                          <td class="px-4 py-2.5 text-gray-400 font-semibold">{{ row.entries.length - idx }}</td>
                          <td class="px-4 py-2.5 text-gray-500 font-medium whitespace-nowrap">{{ fmtDate(entry.submitted_at) }}</td>
                          <td class="px-4 py-2.5">
                            <span class="block font-semibold text-gray-800">{{ entry.submitted_by_name || '—' }}</span>
                            <span v-if="entry.submitted_by_designation" class="block text-[10px] text-gray-400">{{ entry.submitted_by_designation }}</span>
                          </td>
                          <td class="px-4 py-2.5 text-gray-500 font-medium">{{ entry.remarks || '—' }}</td>
                          <td class="px-4 py-2.5 text-right font-bold text-gray-800">
                            {{ entry.quantity }} <span class="text-gray-400 font-normal">{{ row.unit }}</span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <!-- PDF Export Modal -->
    <Teleport to="body">
      <div v-if="showPdfModal" class="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4" @click.self="showPdfModal = false">
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-xl bg-accent-soft flex items-center justify-center">
              <div class="i-carbon-document-pdf text-accent text-xl"></div>
            </div>
            <div>
              <h3 class="text-base font-bold text-gray-900">Export PDF</h3>
              <p class="text-xs text-gray-400">{{ filteredRows.length }} row{{ filteredRows.length !== 1 ? 's' : '' }} in current view</p>
            </div>
          </div>
          <p class="text-sm text-gray-600 mb-5">Include individual entries in the PDF?</p>
          <div class="flex gap-3">
            <button @click="confirmPdfExport(true)"
              class="flex-1 py-2.5 rounded-xl text-sm font-bold bg-accent text-white hover:bg-accent/90 transition-colors">
              Yes, include entries
            </button>
            <button @click="confirmPdfExport(false)"
              class="flex-1 py-2.5 rounded-xl text-sm font-bold border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors">
              Summary only
            </button>
          </div>
          <button @click="showPdfModal = false" class="mt-3 w-full py-2 text-xs font-medium text-gray-400 hover:text-gray-600 transition-colors">Cancel</button>
        </div>
      </div>
    </Teleport>
  </div>
</template>
