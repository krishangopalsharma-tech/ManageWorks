<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'

const allWorks       = ref([])
const allItems       = ref([])   // all items for selected LOAs (from server)
const isLoadingWorks = ref(true)
const isLoadingItems = ref(false)
const itemSearch     = ref('')
const workSearch     = ref('')
const selectedIds    = ref([])
const dropdownOpen   = ref(false)
const dropdownRef    = ref(null)

// ── Click-to-expand entries ────────────────────────────────────────────────
const expandedItemId = ref(null)
const toggleExpand = (id) => {
  expandedItemId.value = expandedItemId.value === id ? null : id
}

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
    allWorks.value = res.data
    // start with nothing selected — user picks LOAs explicitly
  } catch (e) {
    console.error(e)
  } finally {
    isLoadingWorks.value = false
  }
}

// ── Load items for selected LOAs (server fetch, no q required) ─────────────
let itemLoadTimer = null
const loadItems = async () => {
  if (!selectedIds.value.length) { allItems.value = []; return }
  isLoadingItems.value = true
  try {
    const res = await axios.get('/api/item-progress/search/', {
      params: { work_ids: selectedIds.value.join(',') },
    })
    allItems.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    isLoadingItems.value = false
  }
}

// Debounce rapid LOA toggles (avoid hammering on "Select All" then individual toggle)
watch(selectedIds, () => {
  clearTimeout(itemLoadTimer)
  itemLoadTimer = setTimeout(loadItems, 250)
}, { deep: true })

const closeDropdown = (e) => { if (dropdownRef.value && !dropdownRef.value.contains(e.target)) dropdownOpen.value = false }
onMounted(() => { loadWorks(); document.addEventListener('click', closeDropdown) })
onBeforeUnmount(() => { document.removeEventListener('click', closeDropdown); clearTimeout(itemLoadTimer) })

// ── Dropdown helpers ───────────────────────────────────────────────────────
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
const allSelected = computed(() => selectedIds.value.length === allWorks.value.length)
const noneSelected = computed(() => selectedIds.value.length === 0)
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

// ── Category helpers ───────────────────────────────────────────────────────
const isSchB = (item) => String(item.schedule || '').toUpperCase().trim().startsWith('B')
const isSI   = (item) => (item.category || '') === 'supply_installation'

const supplyPct   = (item) => { const r = item.qty || 0; if (!r) return 0; return Math.min(Math.round((item.supplied_quantity || 0) / r * 100), 999) }
const execPctItem = (item) => { const r = item.qty || 0; if (!r) return 0; return Math.min(Math.round((item.executed_quantity || 0) / r * 100), 999) }

const progressPct = (item) => {
  const req = item.qty || 0
  if (!req) return 0
  const cat = item.category || ''
  if (cat === 'supply_installation' || cat === 'execution') return Math.min(Math.round((item.executed_quantity || 0) / req * 100), 999)
  if (cat === 'supply') return Math.min(Math.round((item.supplied_quantity || 0) / req * 100), 999)
  const done = isSchB(item) ? (item.executed_quantity || 0) : (item.supplied_quantity || 0)
  return Math.min(Math.round((done / req) * 100), 999)
}

// ── Category filter ────────────────────────────────────────────────────────
const selectedCategories = ref(['supply', 'supply_installation', 'execution'])
const toggleCategory = (cat) => {
  const idx = selectedCategories.value.indexOf(cat)
  if (idx >= 0) selectedCategories.value.splice(idx, 1)
  else selectedCategories.value.push(cat)
}

// ── Progress range slider ──────────────────────────────────────────────────
const progressMin    = ref(0)
const progressMax    = ref(100)
const includeExcess  = ref(true)
const progressFilterActive = computed(() => progressMin.value > 0 || progressMax.value < 100 || !includeExcess.value)
const resetProgress  = () => { progressMin.value = 0; progressMax.value = 100; includeExcess.value = true }
const onMinInput     = () => { if (progressMin.value > progressMax.value) progressMax.value = progressMin.value }
const onMaxInput     = () => { if (progressMax.value < progressMin.value) progressMin.value = progressMax.value }

// ── Client-side search + category filter (instant, no API call) ────────────
const filteredBySearch = computed(() => {
  const q = itemSearch.value.toLowerCase().trim()
  if (!q) return allItems.value
  return allItems.value.filter(item =>
    (item.item_desc    && item.item_desc.toLowerCase().includes(q)) ||
    (item.schedule     && item.schedule.toLowerCase().includes(q)) ||
    (item.serial_number && item.serial_number.toLowerCase().includes(q)) ||
    (item.loa_number   && item.loa_number.toLowerCase().includes(q))
  )
})

const filteredByCat = computed(() => {
  if (selectedCategories.value.length === 3) return filteredBySearch.value
  return filteredBySearch.value.filter(item => selectedCategories.value.includes(item.category || 'supply'))
})

const filteredResults = computed(() => {
  if (!progressFilterActive.value) return filteredByCat.value
  const min = progressMin.value
  const max = progressMax.value
  const excess = includeExcess.value
  return filteredByCat.value.filter(item => {
    const pct = progressPct(item)
    if (pct > 100) return excess
    return pct >= min && pct <= max
  })
})

// ── Cumulative stats ───────────────────────────────────────────────────────
const stats = computed(() => {
  let supplyTotal = 0, supplyDone = 0, supplyCount = 0
  let execTotal   = 0, execDone   = 0, execCount   = 0
  for (const item of filteredResults.value) {
    const req = item.qty || 0
    const cat = item.category || ''
    if (cat === 'supply') {
      supplyTotal += req; supplyDone += item.supplied_quantity || 0; supplyCount++
    } else if (cat === 'execution' || cat === 'supply_installation') {
      execTotal += req; execDone += item.executed_quantity || 0; execCount++
    } else {
      if (!isSchB(item)) { supplyTotal += req; supplyDone += item.supplied_quantity || 0; supplyCount++ }
      else               { execTotal   += req; execDone   += item.executed_quantity  || 0; execCount++ }
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
  if (!sortKey.value) return filteredResults.value
  return [...filteredResults.value].sort((a, b) => {
    let av, bv
    if      (sortKey.value === 'qty')       { av = a.qty || 0;               bv = b.qty || 0 }
    else if (sortKey.value === 'submitted') { av = a.supplied_quantity || 0; bv = b.supplied_quantity || 0 }
    else if (sortKey.value === 'remaining') { av = remainingQty(a);          bv = remainingQty(b) }
    else if (sortKey.value === 'progress')  { av = progressPct(a);           bv = progressPct(b) }
    else if (sortKey.value === 'entries')   { av = (a.entries||[]).length;   bv = (b.entries||[]).length }
    return sortDir.value === 'asc' ? av - bv : bv - av
  })
})

// ── Remaining quantity ─────────────────────────────────────────────────────
const remainingQty = (item) => {
  const req = item.qty || 0
  const cat = item.category || ''
  if (cat === 'execution' || cat === 'supply_installation') return req - (item.executed_quantity || 0)
  if (cat === 'supply') return req - (item.supplied_quantity || 0)
  const done = isSchB(item) ? (item.executed_quantity || 0) : (item.supplied_quantity || 0)
  return req - done
}

// ── PDF Export ─────────────────────────────────────────────────────────────
const isGeneratingPDF = ref(false)
const showPdfModal    = ref(false)
const pdfIncludeEntries = ref(null)   // null = not decided yet

const onExportClick = () => {
  showPdfModal.value    = true
  pdfIncludeEntries.value = null
}
const confirmPdfExport = async (includeEntries) => {
  pdfIncludeEntries.value = includeEntries
  showPdfModal.value      = false
  await generateItemPDF(includeEntries)
}

const generateItemPDF = async (includeEntries = true) => {
  if (!filteredResults.value.length) return
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

    const items = sortedResults.value  // already uses filteredResults
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

      const remaining = (item.qty || 0) - done

      // Item header block
      autoTable(doc, {
        startY: y,
        margin: { left: mg, right: mg },
        head: [[
          { content: `${item.loa_number || '—'}  ·  ${item.schedule}  ·  S.No ${item.serial_number}`, styles: { fillColor: [235, 245, 244], textColor: C_TEAL, fontStyle: 'bold', fontSize: 7.5 } },
          { content: `${item.tender_number || '—'}\n${item.contractor_name || '—'}`, styles: { fillColor: [235, 245, 244], textColor: C_GRAY, fontSize: 7, halign: 'left' } },
          { content: `Required: ${item.qty} ${item.unit}`, styles: { fillColor: [235, 245, 244], textColor: C_GRAY, fontSize: 7.5, halign: 'right' } },
          { content: `${isB ? 'Executed' : 'Supplied'}: ${done} ${item.unit}`, styles: { fillColor: [235, 245, 244], textColor: C_GRAY, fontSize: 7.5, halign: 'right' } },
          { content: `Remaining: ${remaining} ${item.unit}`, styles: { fillColor: [235, 245, 244], textColor: remaining < 0 ? [220, 80, 30] : C_GRAY, fontSize: 7.5, halign: 'right' } },
          { content: `${pct}%`, styles: { fillColor: [235, 245, 244], textColor: pctNum >= 99 ? C_TEAL : pctNum > 0 ? C_BLUE : C_GRAY, fontStyle: 'bold', fontSize: 8, halign: 'right' } },
        ]],
        body: [[{ content: (() => { const d = item.item_desc || ''; return d.length > 130 ? d.substring(0, 127) + '…' : d })(), colSpan: 6, styles: { fontSize: 7.5, textColor: [50, 50, 50], cellPadding: { top: 2, bottom: 2, left: 3, right: 3 }, overflow: 'ellipsize', minCellHeight: 0 } }]],
        columnStyles: {
          0: { cellWidth: 'auto' },
          1: { cellWidth: 48 },
          2: { cellWidth: 32 },
          3: { cellWidth: 36 },
          4: { cellWidth: 36 },
          5: { cellWidth: 20 },
        },
        tableLineColor: [209, 231, 229],
        tableLineWidth: 0.2,
      })

      y = doc.lastAutoTable.finalY

      if (includeEntries && (item.entries || []).length > 0) {
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
              const desig = e.submitted_by_designation_display || u.designation
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

    const safeName = (itemSearch.value || dropdownLabel.value || 'export').replace(/[^a-z0-9]/gi, '_').substring(0, 30)
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
      <p class="text-gray-400 text-sm font-medium mb-4">Select LOAs → filter by category → search items.</p>

      <!-- Single filter row: LOA selector | category pills | search bar -->
      <div class="flex items-center gap-3 mb-3">

        <!-- LOA multi-select dropdown (fixed width) -->
        <div class="relative flex-shrink-0 w-72" ref="dropdownRef">
          <button @click.stop="dropdownOpen = !dropdownOpen"
            class="w-full flex items-center justify-between bg-gray-50 border border-gray-200 rounded-2xl px-4 py-2.5 text-sm font-medium text-gray-700 hover:border-[#1D5F5E] hover:bg-white transition-all"
            :class="{ 'border-[#1D5F5E] bg-white ring-2 ring-[#1D5F5E]/10': dropdownOpen }">
            <div class="flex items-center gap-2 min-w-0">
              <div v-if="isLoadingWorks || isLoadingItems" class="i-carbon-circle-dash animate-spin text-gray-400 text-base flex-shrink-0"></div>
              <div v-else class="i-carbon-building text-gray-400 text-base flex-shrink-0"></div>
              <span class="truncate text-sm">{{ isLoadingWorks ? 'Loading…' : dropdownLabel }}</span>
            </div>
            <div :class="dropdownOpen ? 'i-carbon-chevron-up' : 'i-carbon-chevron-down'" class="text-gray-400 text-sm flex-shrink-0 ml-2"></div>
          </button>

          <!-- Dropdown panel — wide, anchored left -->
          <div v-if="dropdownOpen"
            class="absolute top-full mt-2 left-0 w-[520px] bg-white rounded-2xl border border-gray-200 shadow-xl z-50 overflow-hidden">
            <!-- Search inside dropdown -->
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
            <!-- Select All / Clear + count -->
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
            <!-- Work list — 2 columns -->
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

        <!-- Divider -->
        <div class="w-px h-6 bg-gray-200 flex-shrink-0"></div>

        <!-- Item search (flex-1, client-side instant) -->
        <div class="flex-1 flex items-center bg-gray-50 border border-gray-200 rounded-2xl px-4 py-2.5 focus-within:ring-2 focus-within:ring-[#1D5F5E]/20 focus-within:border-[#1D5F5E] focus-within:bg-white transition-all">
          <div class="i-carbon-search text-gray-400 text-base mr-3 flex-shrink-0"></div>
          <input v-model="itemSearch" type="text"
            placeholder="Search items by description, LOA, schedule, serial no…"
            class="bg-transparent outline-none w-full text-gray-700 font-medium placeholder-gray-400 text-sm">
          <button v-if="itemSearch" @click="itemSearch = ''" class="ml-2 text-gray-300 hover:text-gray-500 transition-colors">
            <div class="i-carbon-close text-sm"></div>
          </button>
        </div>

      </div>

      <!-- Progress range slider (visible when items loaded) -->
      <div v-if="allItems.length > 0" class="flex items-center gap-3 mt-2.5">
        <span class="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex-shrink-0">Progress</span>

        <!-- Dual-handle slider -->
        <div class="flex items-center gap-2 flex-1 max-w-sm">
          <span class="text-[11px] font-bold text-gray-600 w-8 text-right flex-shrink-0 tabular-nums">{{ progressMin }}%</span>
          <div class="relative flex-1 h-5 flex items-center">
            <!-- Track background -->
            <div class="absolute w-full h-1.5 bg-gray-200 rounded-full"></div>
            <!-- Track fill -->
            <div class="absolute h-1.5 bg-[#1D5F5E] rounded-full pointer-events-none"
              :style="{ left: progressMin + '%', width: (progressMax - progressMin) + '%' }"></div>
            <!-- Min thumb -->
            <input type="range" min="0" max="100" step="1" v-model.number="progressMin"
              @input="onMinInput" class="progress-thumb absolute w-full">
            <!-- Max thumb -->
            <input type="range" min="0" max="100" step="1" v-model.number="progressMax"
              @input="onMaxInput" class="progress-thumb absolute w-full">
          </div>
          <span class="text-[11px] font-bold text-gray-600 w-8 flex-shrink-0 tabular-nums">{{ progressMax }}%</span>
        </div>

        <!-- Excess toggle -->
        <button @click="includeExcess = !includeExcess"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-bold border transition-all flex-shrink-0"
          :class="includeExcess
            ? 'bg-orange-50 border-orange-300 text-orange-700'
            : 'bg-white border-gray-200 text-gray-400 line-through'">
          <div class="i-carbon-overflow-menu-horizontal text-[11px]"></div>
          +Excess
        </button>

        <!-- Reset -->
        <button v-if="progressFilterActive" @click="resetProgress"
          class="flex items-center gap-1 text-[10px] font-semibold text-gray-400 hover:text-gray-600 transition-colors flex-shrink-0">
          <div class="i-carbon-reset text-[11px]"></div> Reset
        </button>
      </div>

      <!-- Stats pills + Export (visible when items exist) -->
      <div v-if="filteredResults.length > 0" class="flex flex-wrap items-center gap-3">
        <div class="flex items-center gap-2 bg-teal-50 border border-teal-200 rounded-xl px-4 py-2">
          <div class="w-2 h-2 rounded-full bg-teal-500"></div>
          <span class="text-xs font-semibold text-teal-700">
            Supply: {{ stats.supplyPct }}%
            <span class="font-normal opacity-70">({{ stats.supplyCount }})</span>
          </span>
        </div>
        <div class="flex items-center gap-2 bg-orange-50 border border-orange-200 rounded-xl px-4 py-2">
          <div class="w-2 h-2 rounded-full bg-orange-500"></div>
          <span class="text-xs font-semibold text-orange-700">
            Exec + S+I: {{ stats.execPct }}%
            <span class="font-normal opacity-70">({{ stats.execCount }})</span>
          </span>
        </div>
        <div class="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-4 py-2">
          <div class="i-carbon-list text-gray-400 text-sm"></div>
          <span class="text-xs font-semibold text-gray-600">
            {{ filteredResults.length }}
            <span v-if="filteredResults.length < allItems.length" class="font-normal text-gray-400"> of {{ allItems.length }}</span>
            items
          </span>
        </div>
        <button @click="onExportClick" :disabled="isGeneratingPDF || !sortedResults.length"
          class="ml-auto flex items-center gap-1.5 px-4 py-2 rounded-xl border border-gray-300 text-xs font-semibold text-gray-600 hover:bg-gray-100 hover:border-gray-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0">
          <div :class="isGeneratingPDF ? 'i-carbon-circle-dash animate-spin' : 'i-carbon-document-pdf'" class="text-sm"></div>
          {{ isGeneratingPDF ? 'Generating…' : 'Export PDF' }}
        </button>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="isLoadingItems" class="flex-1 flex flex-col items-center justify-center py-24 text-center">
      <div class="i-carbon-circle-dash animate-spin text-4xl text-gray-300 mb-4"></div>
      <p class="text-sm font-semibold text-gray-400">Loading items…</p>
    </div>

    <!-- No LOA selected -->
    <div v-else-if="noneSelected && !isLoadingWorks" class="flex-1 flex flex-col items-center justify-center py-24 text-center">
      <div class="i-carbon-building text-5xl text-gray-200 mb-4"></div>
      <p class="text-sm font-semibold text-gray-400">No LOA selected.</p>
      <p class="text-xs text-gray-300 mt-1">Select one or more LOAs above to load items.</p>
    </div>

    <!-- No items match filter/search -->
    <div v-else-if="!isLoadingItems && allItems.length > 0 && filteredResults.length === 0" class="flex-1 flex flex-col items-center justify-center py-24 text-center">
      <div class="i-carbon-search text-5xl text-gray-200 mb-4"></div>
      <p class="text-sm font-semibold text-gray-400">No items match your filters.</p>
      <p class="text-xs text-gray-300 mt-1">Try adjusting the search or enabling more category filters.</p>
    </div>

    <!-- Table -->
    <div v-else-if="!isLoadingItems && filteredResults.length > 0" class="overflow-auto flex-1">
      <table class="w-full border-collapse">
        <thead class="bg-gray-50 sticky top-0 z-10">
          <tr class="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
            <th class="px-4 py-3 text-left w-32">Work No.</th>
            <th class="px-4 py-3 text-left w-36">LOA Number</th>
            <th class="px-4 py-3 text-center w-16">Cat</th>
            <th class="px-4 py-3 text-center w-14">Sch</th>
            <th class="px-4 py-3 text-center w-14">S.No</th>
            <th class="px-4 py-3 text-left">Item Description</th>
            <th @click="toggleSort('qty')" class="px-4 py-3 text-right w-28 cursor-pointer select-none hover:text-gray-600 transition-colors">
              <div class="flex items-center justify-end gap-1">Required <div :class="sortIcon('qty')" class="text-[9px]" :style="{ opacity: sortKey === 'qty' ? 1 : 0.35 }"></div></div>
            </th>
            <th @click="toggleSort('submitted')" class="px-4 py-3 text-right w-28 cursor-pointer select-none hover:text-gray-600 transition-colors">
              <div class="flex items-center justify-end gap-1">Supplied <div :class="sortIcon('submitted')" class="text-[9px]" :style="{ opacity: sortKey === 'submitted' ? 1 : 0.35 }"></div></div>
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
          <template v-for="item in sortedResults" :key="item.id">
            <!-- Main row -->
            <tr @click="toggleExpand(item.id)"
              class="border-b border-gray-100 hover:bg-accent-soft/40 transition-colors cursor-pointer select-none"
              :class="expandedItemId === item.id ? 'bg-accent-soft/30 border-accent/20' : ''">
              <td class="px-4 py-3">
                <p class="text-xs font-semibold text-gray-700 line-clamp-1 leading-snug">{{ item.tender_number || '—' }}</p>
                <p class="text-[11px] text-gray-400 line-clamp-1 leading-snug mt-0.5">{{ item.contractor_name || '—' }}</p>
              </td>
              <td class="px-4 py-3">
                <span class="text-[11px] font-semibold text-accent bg-accent-soft px-2 py-0.5 rounded-full whitespace-nowrap">
                  {{ item.loa_number || '—' }}
                </span>
              </td>
              <td class="px-4 py-3 text-center">
                <span class="rounded-md px-2 py-0.5 text-[10px] font-bold whitespace-nowrap"
                  :class="{
                    'bg-teal-50 text-teal-600':     item.category === 'supply',
                    'bg-violet-50 text-violet-600': item.category === 'supply_installation',
                    'bg-orange-50 text-orange-600': item.category === 'execution',
                    'bg-gray-100 text-gray-400':    !item.category,
                  }">
                  {{ item.category === 'supply' ? 'Supply' : item.category === 'supply_installation' ? 'S+I' : item.category === 'execution' ? 'Exec' : '—' }}
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
              <td class="px-4 py-3 text-right text-xs font-semibold"
                :class="(item.supplied_quantity || 0) > (item.qty || 0) ? 'text-orange-500' : 'text-gray-800'">
                {{ item.supplied_quantity || 0 }}
                <span class="text-gray-400 font-normal">{{ item.unit }}</span>
                <span v-if="(item.supplied_quantity || 0) > (item.qty || 0)" class="ml-1 text-[9px] text-orange-400 font-bold">OVER</span>
              </td>
              <td class="px-4 py-3 text-right text-xs font-semibold"
                :class="remainingQty(item) < 0 ? 'text-orange-500' : 'text-gray-600'">
                {{ remainingQty(item) }} <span class="text-gray-400 font-normal">{{ item.unit }}</span>
              </td>
              <td class="px-4 py-3">
                <!-- S+I: two stacked bars -->
                <template v-if="isSI(item)">
                  <div class="flex flex-col gap-1">
                    <div class="flex items-center gap-1.5">
                      <div class="flex-1 h-1 bg-gray-100 rounded-full overflow-hidden">
                        <div class="h-full rounded-full transition-all duration-500 bg-teal-500"
                          :style="{ width: Math.min(supplyPct(item), 100) + '%' }"></div>
                      </div>
                      <span class="text-[9px] font-bold w-7 text-right text-teal-600">{{ supplyPct(item) }}%</span>
                    </div>
                    <div class="flex items-center gap-1.5">
                      <div class="flex-1 h-1 bg-gray-100 rounded-full overflow-hidden">
                        <div class="h-full rounded-full transition-all duration-500 bg-violet-500"
                          :style="{ width: Math.min(execPctItem(item), 100) + '%' }"></div>
                      </div>
                      <span class="text-[9px] font-bold w-7 text-right text-violet-600">{{ execPctItem(item) }}%</span>
                    </div>
                  </div>
                </template>
                <!-- Normal: single bar -->
                <template v-else>
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
                </template>
              </td>
              <td class="px-4 py-3 text-center">
                <div class="flex items-center justify-center gap-1">
                  <span class="text-[11px] font-bold"
                    :class="(item.entries||[]).length > 0 ? 'text-accent' : 'text-gray-300'">
                    {{ (item.entries || []).length }}
                  </span>
                  <div class="text-gray-300 text-[10px] transition-transform duration-200"
                    :class="expandedItemId === item.id ? 'i-carbon-chevron-up' : 'i-carbon-chevron-down'"></div>
                </div>
              </td>
            </tr>

            <!-- Expanded entries panel -->
            <tr v-if="expandedItemId === item.id" class="bg-gray-50/60">
              <td colspan="11" class="px-6 pb-5 pt-0 border-b border-accent/10">
                <div class="rounded-xl border border-gray-100 bg-white overflow-hidden mt-3 shadow-sm">

                  <!-- Panel header -->
                  <div class="px-4 py-3 bg-gray-50 border-b border-gray-100 flex items-center gap-3">
                    <span class="rounded-md px-2 py-0.5 text-[10px] font-bold"
                      :class="isSchB(item) ? 'bg-accent-b-soft text-accent-b' : 'bg-accent-soft text-accent'">
                      {{ item.schedule }}
                    </span>
                    <span class="text-[10px] font-semibold text-gray-400">S.No {{ item.serial_number }}</span>
                    <span class="text-[11px] font-semibold text-accent bg-accent-soft px-2 py-0.5 rounded-full">{{ item.loa_number }}</span>
                    <p class="text-xs font-semibold text-gray-700 line-clamp-1 ml-1 flex-1">{{ item.item_desc }}</p>
                    <div v-if="isSchB(item)" class="flex items-center gap-3 flex-shrink-0">
                      <span class="text-[10px] text-gray-500">Supplied: <strong class="text-accent">{{ item.supplied_quantity || 0 }}</strong> <span class="text-gray-400">{{ item.unit }}</span></span>
                      <span class="text-gray-200">·</span>
                      <span class="text-[10px] text-gray-500">Executed: <strong class="text-accent-b">{{ item.executed_quantity || 0 }}</strong> <span class="text-gray-400">{{ item.unit }}</span></span>
                    </div>
                    <span class="text-[10px] text-gray-400 font-medium flex-shrink-0">
                      {{ (item.entries || []).length }} entr{{ (item.entries || []).length === 1 ? 'y' : 'ies' }}
                    </span>
                  </div>

                  <!-- No entries -->
                  <div v-if="!(item.entries || []).length"
                    class="px-4 py-8 text-center text-xs text-gray-400 font-medium">
                    No entries submitted yet.
                  </div>

                  <!-- Entries grid -->
                  <div v-else class="p-3 flex flex-wrap gap-2">
                    <div v-for="(entry, idx) in [...(item.entries || [])].reverse()" :key="entry.id"
                      class="border border-gray-100 rounded-xl px-3 py-2.5 min-w-[200px] flex-1 max-w-[280px] hover:border-accent/30 transition-colors">
                      <div class="flex items-center gap-2 mb-1.5">
                        <span class="w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center flex-shrink-0"
                          :class="entry.entry_type === 'supply' ? 'bg-accent-soft text-accent' : 'bg-accent-b-soft text-accent-b'">
                          {{ (item.entries || []).length - idx }}
                        </span>
                        <span class="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide"
                          :class="entry.entry_type === 'supply' ? 'bg-accent-soft text-accent' : 'bg-accent-b-soft text-accent-b'">
                          {{ entry.entry_type === 'supply' ? 'Supply' : 'Exec' }}
                        </span>
                        <span class="text-xs font-bold text-gray-800">
                          {{ entry.quantity }} <span class="text-gray-400 font-normal text-[10px]">{{ item.unit }}</span>
                        </span>
                        <span class="ml-auto text-[10px] text-gray-400 font-medium flex-shrink-0">
                          {{ fmtDateTime(entry.submitted_at) }}
                        </span>
                      </div>
                      <div class="flex flex-col gap-0.5 pl-7">
                        <span class="flex items-center gap-1 text-[10px] text-gray-500 font-medium">
                          <div class="i-carbon-user text-gray-400" style="font-size:10px;"></div>
                          {{ entry.submitted_by_user?.full_name || entry.submitted_by_user?.username || '—' }}
                          <span v-if="entry.submitted_by_designation_display || entry.submitted_by_user?.designation" class="text-gray-400"> · {{ entry.submitted_by_designation_display || entry.submitted_by_user?.designation }}</span>
                        </span>
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

                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <!-- Footer -->
    <div v-if="filteredResults.length > 0" class="px-6 py-3 border-t border-gray-100 bg-gray-50 rounded-b-2xl">
      <p class="text-[11px] text-gray-400 font-medium">
        Showing {{ filteredResults.length }} of {{ allItems.length }} {{ allItems.length === 1 ? 'item' : 'items' }}
        across {{ selectedIds.length }} {{ selectedIds.length === 1 ? 'work' : 'works' }}
      </p>
    </div>

    <!-- PDF Export Modal -->
    <Teleport to="body">
      <Transition name="tip">
        <div v-if="showPdfModal" class="fixed inset-0 z-[10000] flex items-center justify-center bg-black/30 backdrop-blur-sm"
          @click.self="showPdfModal = false">
          <div class="bg-white rounded-2xl shadow-2xl border border-gray-200 w-[420px] overflow-hidden">
            <div class="px-6 py-5 border-b border-gray-100">
              <h3 class="text-base font-bold text-gray-900">Export PDF</h3>
              <p class="text-sm text-gray-400 mt-1">Include individual supply / execution entries in the report?</p>
            </div>
            <div class="p-6 flex flex-col gap-3">
              <button @click="confirmPdfExport(true)"
                class="w-full flex items-center gap-3 px-4 py-3.5 rounded-xl border-2 border-accent/30 bg-accent-soft hover:border-accent transition-all text-left">
                <div class="i-carbon-document-multiple-01 text-accent text-xl flex-shrink-0"></div>
                <div>
                  <p class="text-sm font-bold text-accent">Yes, include entries</p>
                  <p class="text-xs text-gray-400 mt-0.5">Each item will show all supply/execution entries with dates and quantities.</p>
                </div>
              </button>
              <button @click="confirmPdfExport(false)"
                class="w-full flex items-center gap-3 px-4 py-3.5 rounded-xl border-2 border-gray-200 hover:border-gray-400 transition-all text-left">
                <div class="i-carbon-document text-gray-400 text-xl flex-shrink-0"></div>
                <div>
                  <p class="text-sm font-bold text-gray-700">No, summary only</p>
                  <p class="text-xs text-gray-400 mt-0.5">Only item totals — required, supplied/executed, remaining, progress.</p>
                </div>
              </button>
            </div>
            <div class="px-6 pb-5 flex justify-end">
              <button @click="showPdfModal = false"
                class="text-xs font-semibold text-gray-400 hover:text-gray-600 transition-colors">Cancel</button>
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

/* Dual-handle range slider */
.progress-thumb {
  -webkit-appearance: none;
  appearance: none;
  background: transparent;
  pointer-events: none;
  height: 6px;
  position: absolute;
  width: 100%;
  margin: 0;
}
.progress-thumb::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #1D5F5E;
  border: 2.5px solid #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,0.18);
  cursor: pointer;
  pointer-events: all;
  transition: transform 0.1s ease, box-shadow 0.1s ease;
}
.progress-thumb::-webkit-slider-thumb:hover {
  transform: scale(1.15);
  box-shadow: 0 2px 8px rgba(29,95,94,0.35);
}
.progress-thumb::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #1D5F5E;
  border: 2.5px solid #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,0.18);
  cursor: pointer;
  pointer-events: all;
}
</style>
