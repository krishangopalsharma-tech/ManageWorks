<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

// ── State ─────────────────────────────────────────────────────────────────
const allWorks      = ref([])
const isLoading     = ref(false)
const searchQuery   = ref('')

const selectedWork   = ref(null)
const selectedThread = ref(null)
const activeTab      = ref('date')
const selectedItem   = ref(null)

// ── Load ──────────────────────────────────────────────────────────────────
const load = async () => {
  isLoading.value = true
  try {
    const res = await axios.get('/api/site-register/')
    allWorks.value = res.data.works || []
  } catch {
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

// Threads sorted newest → oldest for the register table
const workThreads = computed(() => {
  if (!selectedWork.value) return []
  return [...(selectedWork.value.threads || [])].sort((a, b) =>
    a.created_at > b.created_at ? -1 : 1
  )
})

// Item-wise: all LOA items sorted by ref
const sortedItems = computed(() => {
  if (!selectedWork.value?.items) return []
  return [...selectedWork.value.items].sort((a, b) => {
    const ra = `${a.schedule}-${a.serial_no}`
    const rb = `${b.schedule}-${b.serial_no}`
    return ra.localeCompare(rb, undefined, { numeric: true })
  })
})

const itemRef = (item) => `${item.schedule}-${item.serial_no}`

const selectedItemThreads = computed(() => {
  if (!selectedItem.value) return []
  const ref = itemRef(selectedItem.value)
  return workThreads.value.filter(t => t.work_item_ref === ref)
})

const entryCountForItem = (item) =>
  workThreads.value.filter(t => t.work_item_ref === itemRef(item)).length

// ── SR-level search ───────────────────────────────────────────────────────
const srSearch = ref('')

const filteredWorkThreads = computed(() => {
  const q = srSearch.value.trim().toLowerCase()
  if (!q) return workThreads.value
  return workThreads.value.filter(t => {
    if (t.sr_number?.toLowerCase().includes(q)) return true
    if (t.instruction_type?.toLowerCase().includes(q)) return true
    if (t.work_item_ref?.toLowerCase().includes(q)) return true
    if (t.initial_text?.toLowerCase().includes(q)) return true
    if (t.messages?.some(m => m.text?.toLowerCase().includes(q))) return true
    return false
  })
})

const filteredSelectedItemThreads = computed(() => {
  if (!selectedItem.value) return []
  const ref = itemRef(selectedItem.value)
  const q = srSearch.value.trim().toLowerCase()
  const threads = workThreads.value.filter(t => t.work_item_ref === ref)
  if (!q) return threads
  return threads.filter(t => {
    if (t.sr_number?.toLowerCase().includes(q)) return true
    if (t.initial_text?.toLowerCase().includes(q)) return true
    if (t.messages?.some(m => m.text?.toLowerCase().includes(q))) return true
    return false
  })
})

// ── Navigation ────────────────────────────────────────────────────────────
const selectWork  = (work)   => { selectedWork.value = work; selectedThread.value = null; activeTab.value = 'date'; selectedItem.value = null; srSearch.value = '' }
const backToList  = ()       => { selectedWork.value = null; selectedThread.value = null }
const openThread  = (thread) => { selectedThread.value = thread }
const closeThread = ()       => { selectedThread.value = null }

// ── Helpers ───────────────────────────────────────────────────────────────
const fmtDate = (val) => {
  if (!val) return '—'
  const s = String(val).split('T')[0].split(' ')[0]
  if (/^\d{2}[\/\-]\d{2}[\/\-]\d{4}$/.test(s)) return s.replace(/-/g, '/')
  const m = s.match(/^(\d{4})[\/\-](\d{2})[\/\-](\d{2})$/)
  if (m) return `${m[3]}/${m[2]}/${m[1]}`
  return s
}

const fmtDatetime = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso)
  const dd   = String(d.getDate()).padStart(2, '0')
  const mm   = String(d.getMonth() + 1).padStart(2, '0')
  const yyyy = d.getFullYear()
  const hh   = String(d.getHours()).padStart(2, '0')
  const min  = String(d.getMinutes()).padStart(2, '0')
  return `${dd}/${mm}/${yyyy} ${hh}:${min}`
}

const statusClass = (s) => ({
  open:     'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400',
  replied:  'bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400',
  verified: 'bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400',
  closed:   'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400',
}[s] || 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400')

const roleClass = (r) => r === 'rly_official'
  ? 'bg-blue-100 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400'
  : 'bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400'

const roleLabel = (r) => r === 'rly_official' ? 'Rly Official' : 'Site Supervisor'

const truncate = (str, n) => {
  if (!str) return '—'
  return str.length > n ? str.slice(0, n) + '…' : str
}

// ── PDF Export ────────────────────────────────────────────────────────────
const showExportMenu  = ref(false)
const showPdfOptions  = ref(false)
const pdfMode         = ref('')         // 'date' | 'item'
const pdfRangeType    = ref('comprehensive')  // 'comprehensive' | 'week' | 'month' | 'custom'
const pdfDateFrom     = ref('')
const pdfDateTo       = ref('')

function openPdfOptions(mode) {
  showExportMenu.value = false
  pdfMode.value        = mode
  pdfRangeType.value   = 'comprehensive'
  pdfDateFrom.value    = ''
  pdfDateTo.value      = ''
  showPdfOptions.value = true
}

function getThreadsForRange(threads) {
  if (pdfRangeType.value === 'comprehensive') return threads
  const now = new Date()
  let from, to = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59)
  if (pdfRangeType.value === 'week') {
    from = new Date(now); from.setDate(from.getDate() - from.getDay()); from.setHours(0, 0, 0, 0)
  } else if (pdfRangeType.value === 'month') {
    from = new Date(now.getFullYear(), now.getMonth(), 1)
  } else {
    from = pdfDateFrom.value ? new Date(pdfDateFrom.value) : null
    to   = pdfDateTo.value   ? new Date(pdfDateTo.value + 'T23:59:59') : to
  }
  return threads.filter(t => {
    const d = new Date(t.created_at)
    if (from && d < from) return false
    if (d > to)           return false
    return true
  })
}

// rly_official → light blue, site_supervisor → light green
const ROLE_FILL = {
  rly_official:    [239, 246, 255],
  site_supervisor: [240, 253, 244],
}

// Sender name+designation cell (untitled column, Entry side)
function senderCell(thread) {
  const name  = thread.created_by_name || '—'
  const desig = thread.created_by_designation || ''
  return {
    content: desig ? `${name}\n${desig}` : name,
    styles: { fillColor: ROLE_FILL[thread.initiated_by_role] || [248, 250, 252], fontStyle: 'bold' },
  }
}

// Entry message only (no name)
function entryCell(thread) {
  return {
    content: thread.initial_text || '—',
    styles: { fillColor: ROLE_FILL[thread.initiated_by_role] || [248, 250, 252] },
  }
}

// All Responses: serial + date + name + designation + message — all in one column
function responsesCell(thread) {
  const msgs = (thread.status === 'open') ? [] : (thread.messages || [])
  if (!msgs.length) {
    return { content: 'Pending', styles: { textColor: [156, 163, 175] } }
  }
  const content = msgs.map((m, i) => {
    const name  = m.sender_name || '—'
    const desig = m.sender_designation || ''
    const header = `${i + 1}. ${fmtDate(m.created_at)}  ${name}`
    const line2  = desig ? `${desig}` : null
    const msg    = m.text || '—'
    return [header, line2, msg].filter(Boolean).join('\n')
  }).join('\n\n')
  const roles = [...new Set(msgs.map(m => m.sender_role).filter(Boolean))]
  const fillColor = roles.length === 1 ? (ROLE_FILL[roles[0]] || [250, 250, 250]) : [250, 250, 250]
  return { content, styles: { fillColor } }
}

// First reply date for "Date Response" column
function firstReplyDate(thread) {
  const msgs = (thread.status === 'open') ? [] : (thread.messages || [])
  if (!msgs.length) return '—'
  return fmtDate(msgs[0].created_at)
}

function buildPdfHeader(doc, work) {
  const pw = doc.internal.pageSize.getWidth()
  doc.setFontSize(14)
  doc.setFont('helvetica', 'bold')
  doc.setTextColor(29, 95, 94)
  doc.text('Site Register', 14, 16)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(8)
  doc.setTextColor(90)
  doc.text(`LOA: ${work.loa_number || '—'}   Tender: ${work.tender_number || '—'}`, 14, 23)
  doc.text(`Contractor: ${work.contractor_name || '—'}`, 14, 28)
  doc.text(`Consignee: ${work.consignee || '—'}   Completion: ${fmtDate(work.date_of_completion)}`, 14, 33)
  doc.text(`Generated: ${fmtDatetime(new Date().toISOString())}`, pw - 14, 16, { align: 'right' })
  doc.setDrawColor(220)
  doc.line(14, 37, pw - 14, 37)
  doc.setTextColor(0)
  return 42
}

async function exportPdf() {
  showPdfOptions.value = false
  const work = selectedWork.value
  if (!work) return

  const { jsPDF }    = await import('jspdf')
  const { autoTable } = await import('jspdf-autotable')
  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' })
  const loaSlug    = (work.loa_number || 'UNKNOWN').replace(/[^a-zA-Z0-9]/g, '')
  const now        = new Date()
  const dateSuffix = `${String(now.getDate()).padStart(2, '0')}${String(now.getMonth() + 1).padStart(2, '0')}${now.getFullYear()}`

  const rangeThreads = getThreadsForRange(workThreads.value)

  if (pdfMode.value === 'date') {
    const startY = buildPdfHeader(doc, work)
    autoTable(doc, {
      startY,
      head: [['SR No.', 'Entry Date', 'Category', 'Location', '', 'Entry', 'All Responses', 'Status']],
      body: rangeThreads.map(t => [
        t.sr_number || '—',
        fmtDate(t.created_at),
        t.instruction_type === 'item' ? `Item\n${t.work_item_ref || ''}` : 'General',
        t.location || '—',
        senderCell(t),
        entryCell(t),
        responsesCell(t),
        (t.status || '').toUpperCase(),
      ]),
      styles: { fontSize: 7, cellPadding: 2.5, overflow: 'linebreak', valign: 'top' },
      headStyles: { fillColor: [29, 95, 94], textColor: 255, fontStyle: 'bold', fontSize: 7 },
      columnStyles: {
        0: { cellWidth: 22 },
        1: { cellWidth: 18 },
        2: { cellWidth: 16 },
        3: { cellWidth: 16 },
        4: { cellWidth: 28 },
        5: { cellWidth: 55 },
        6: { cellWidth: 'auto' },
        7: { cellWidth: 14, fontSize: 6, halign: 'center' },
      },
    })
    doc.save(`SR-DateWise-${loaSlug}-${dateSuffix}.pdf`)

  } else {
    const itemsWithEntries = sortedItems.value.filter(item =>
      rangeThreads.some(t => t.work_item_ref === itemRef(item))
    )
    if (!itemsWithEntries.length) return

    let currentY = buildPdfHeader(doc, work)
    const pageH = doc.internal.pageSize.getHeight()
    let isFirstItem = true

    itemsWithEntries.forEach((item) => {
      const threads = rangeThreads.filter(t => t.work_item_ref === itemRef(item))
      if (!threads.length) return

      if (!isFirstItem && currentY > pageH - 45) {
        doc.addPage()
        currentY = buildPdfHeader(doc, work)
      }

      doc.setFontSize(9)
      doc.setFont('helvetica', 'bold')
      doc.setTextColor(29, 95, 94)
      doc.text(itemRef(item), 14, currentY)
      doc.setFontSize(8)
      doc.setFont('helvetica', 'normal')
      doc.setTextColor(60)
      const pw = doc.internal.pageSize.getWidth()
      const descLines = doc.splitTextToSize(item.item_desc || '', pw - 52)
      doc.text(descLines, 38, currentY)
      doc.setTextColor(0)

      const descHeight = descLines.length * 4
      autoTable(doc, {
        startY: currentY + Math.max(descHeight, 3) + 3,
        head: [['SR No.', 'Entry Date', '', 'Entry', 'All Responses', 'Status']],
        body: threads.map(t => [
          t.sr_number || '—',
          fmtDate(t.created_at),
          senderCell(t),
          entryCell(t),
          responsesCell(t),
          (t.status || '').toUpperCase(),
        ]),
        styles: { fontSize: 7, cellPadding: 2.5, overflow: 'linebreak', valign: 'top' },
        headStyles: { fillColor: [29, 95, 94], textColor: 255, fontStyle: 'bold', fontSize: 7 },
        columnStyles: {
          0: { cellWidth: 22 },
          1: { cellWidth: 18 },
          2: { cellWidth: 28 },
          3: { cellWidth: 55 },
          4: { cellWidth: 'auto' },
          5: { cellWidth: 14, fontSize: 6, halign: 'center' },
        },
      })

      currentY = (doc.lastAutoTable?.finalY || currentY) + 10
      isFirstItem = false
    })

    doc.save(`SR-ItemWise-${loaSlug}-${dateSuffix}.pdf`)
  }
}
</script>

<template>
  <div class="bg-white rounded-2xl soft-shadow h-full w-full flex flex-col overflow-hidden">

    <!-- ══ WORK LIST ══════════════════════════════════════════════════════ -->
    <template v-if="!selectedWork">

      <div class="flex-shrink-0 px-8 pt-7 pb-5 border-b border-gray-100">
        <h1 class="text-2xl font-bold text-gray-900 tracking-tight mb-1">Site Register</h1>
        <p class="text-gray-400 text-sm font-medium mb-5">
          All works — bot instructions and contractor replies.
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
                  </div>
                </div>
                <div class="flex items-center gap-4 flex-shrink-0">
                  <div class="text-right">
                    <p class="text-sm font-bold text-gray-800">{{ work.thread_count || 0 }}</p>
                    <p class="text-[10px] text-gray-400">SR entries</p>
                  </div>
                  <div class="text-right">
                    <p class="text-sm font-bold text-gray-800">{{ work.items.length }}</p>
                    <p class="text-[10px] text-gray-400">items</p>
                  </div>
                  <div class="i-carbon-chevron-right text-gray-300 group-hover:text-[#1D5F5E] transition-colors text-lg"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </template>

    <!-- ══ THREAD DETAIL ══════════════════════════════════════════════════ -->
    <template v-else-if="selectedWork && selectedThread">
      <div class="flex flex-col h-full overflow-hidden animate-fade-in">

        <div class="flex-shrink-0 px-6 pt-5 pb-4 border-b border-gray-100">
          <div class="flex items-start gap-4 min-w-0">
            <button @click="closeThread"
              class="mt-0.5 w-9 h-9 flex-shrink-0 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 transition-all">
              <div class="i-carbon-arrow-left text-base"></div>
            </button>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-[11px] font-bold text-[#1D5F5E] bg-[#1D5F5E]/10 px-2 py-0.5 rounded-full">
                  {{ selectedThread.sr_number }}
                </span>
                <span v-if="selectedThread.work_item_ref"
                  class="text-[11px] font-semibold text-[#1D5F5E] bg-[#1D5F5E]/5 px-2 py-0.5 rounded-full">
                  {{ selectedThread.work_item_ref }}
                </span>
                <span v-else class="text-[11px] font-medium text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                  General
                </span>
                <span :class="['text-[11px] font-semibold px-2 py-0.5 rounded-full', statusClass(selectedThread.status)]">
                  {{ selectedThread.status.toUpperCase() }}
                </span>
              </div>
              <p class="text-xs text-gray-500 mt-1">
                {{ selectedWork.loa_number }} · {{ selectedWork.contractor_name }} ·
                {{ fmtDatetime(selectedThread.created_at) }} by {{ selectedThread.created_by_name }}
                <template v-if="selectedThread.created_by_designation">
                  · {{ selectedThread.created_by_designation }}
                </template>
              </p>
            </div>
          </div>
        </div>

        <div class="flex-1 overflow-auto px-6 py-5 space-y-0">

          <!-- Original instruction -->
          <div class="flex gap-3 mb-0">
            <div class="flex flex-col items-center">
              <div :class="['w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
                selectedThread.initiated_by_role === 'rly_official' ? 'bg-blue-100' : 'bg-green-100']">
                <span :class="['i-carbon-user-avatar text-sm',
                  selectedThread.initiated_by_role === 'rly_official' ? 'text-blue-600' : 'text-green-600']"></span>
              </div>
              <div class="w-0.5 bg-gray-200 flex-1 mt-1"></div>
            </div>
            <div class="flex-1 pb-5">
              <div class="flex items-center gap-2 mb-1.5">
                <span :class="['text-xs font-bold',
                  selectedThread.initiated_by_role === 'rly_official' ? 'text-blue-700' : 'text-green-700']">
                  {{ selectedThread.created_by_name }}
                </span>
                <span :class="['text-[11px] font-semibold px-1.5 py-0.5 rounded-full',
                  selectedThread.initiated_by_role === 'rly_official' ? 'text-blue-600 bg-blue-50' : 'text-green-600 bg-green-50']">
                  {{ selectedThread.created_by_designation || 'Desig: N/A' }}
                </span>
                <span class="text-[11px] text-gray-400">{{ fmtDatetime(selectedThread.created_at) }}</span>
              </div>
              <div :class="['border rounded-xl px-4 py-3',
                selectedThread.initiated_by_role === 'rly_official'
                  ? 'bg-blue-50 border-blue-100'
                  : 'bg-green-50 border-green-100']">
                <p class="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{{ selectedThread.initial_text || '—' }}</p>
              </div>
            </div>
          </div>

          <!-- Replies -->
          <div v-for="(msg, idx) in selectedThread.messages" :key="msg.id" class="flex gap-3 mb-0">
            <div class="flex flex-col items-center">
              <div :class="['w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
                msg.sender_role === 'rly_official' ? 'bg-blue-100' : 'bg-green-100']">
                <span :class="['i-carbon-user-avatar text-sm',
                  msg.sender_role === 'rly_official' ? 'text-blue-600' : 'text-green-600']"></span>
              </div>
              <div v-if="idx < selectedThread.messages.length - 1"
                class="w-0.5 bg-gray-200 flex-1 mt-1"></div>
            </div>
            <div class="flex-1 pb-5">
              <div class="flex items-center gap-2 mb-1.5">
                <span :class="['text-xs font-bold',
                  msg.sender_role === 'rly_official' ? 'text-blue-700' : 'text-green-700']">
                  {{ msg.sender_name }}
                </span>
                <span :class="['text-[11px] font-semibold px-1.5 py-0.5 rounded-full', roleClass(msg.sender_role)]">
                  {{ msg.sender_designation || 'Desig: N/A' }}
                </span>
                <span class="text-[11px] text-gray-400">{{ fmtDatetime(msg.created_at) }}</span>
              </div>
              <div :class="['border rounded-xl px-4 py-3',
                msg.sender_role === 'rly_official'
                  ? 'bg-blue-50 border-blue-100'
                  : 'bg-green-50 border-green-100']">
                <p class="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{{ msg.text || '—' }}</p>
                <div v-if="msg.attachments && msg.attachments.length" class="mt-2 flex flex-wrap gap-1.5">
                  <span v-for="a in msg.attachments" :key="a.id"
                    :class="['inline-flex items-center gap-1 text-[10px] font-mono font-semibold px-2 py-0.5 rounded border',
                      msg.sender_role === 'rly_official'
                        ? 'bg-blue-100 border-blue-200 text-blue-700'
                        : 'bg-green-100 border-green-200 text-green-700']">
                    <span :class="a.file_type === 'photo' ? 'i-carbon-image' : 'i-carbon-document'"></span>
                    {{ a.att_number }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="!selectedThread.messages.length"
            class="text-center py-6 text-xs text-gray-400 font-medium">
            No replies yet from site supervisor.
          </div>
        </div>
      </div>
    </template>

    <!-- ══ WORK DETAIL — SR TABLE ════════════════════════════════════════ -->
    <template v-else-if="selectedWork">
      <!-- click-outside overlay for export menu -->
      <div v-if="showExportMenu" class="fixed inset-0 z-10" @click="showExportMenu = false"></div>

      <div class="flex flex-col h-full overflow-hidden animate-fade-in">

        <!-- Header -->
        <div class="px-8 pt-6 pb-5 border-b border-gray-100 flex-shrink-0">
          <div class="flex items-start gap-4 w-full">
            <button @click="backToList"
              class="mt-0.5 w-9 h-9 flex-shrink-0 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 transition-all">
              <div class="i-carbon-arrow-left text-base"></div>
            </button>
            <div class="min-w-0 flex-1">
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
              </div>
            </div>
            <!-- Export PDF dropdown -->
            <div class="relative flex-shrink-0 mt-0.5">
              <button @click.stop="showExportMenu = !showExportMenu"
                class="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-[#1D5F5E]/30 bg-[#1D5F5E]/5 hover:bg-[#1D5F5E]/10 text-[#1D5F5E] text-xs font-semibold transition-all focus:outline-none">
                <span class="i-carbon-document-pdf text-sm"></span>
                Export PDF
                <span :class="['i-carbon-chevron-down text-xs transition-transform', showExportMenu ? 'rotate-180' : '']"></span>
              </button>
              <div v-if="showExportMenu"
                class="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-xl shadow-lg z-20 overflow-hidden w-36">
                <button @click="openPdfOptions('date')"
                  class="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-600 hover:bg-[#1D5F5E]/5 hover:text-[#1D5F5E] transition-colors border-0 border-b border-gray-100 focus:outline-none">
                  <span class="i-carbon-calendar text-xs flex-shrink-0"></span>Date-wise
                </button>
                <button @click="openPdfOptions('item')"
                  class="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-600 hover:bg-[#1D5F5E]/5 hover:text-[#1D5F5E] transition-colors border-0 focus:outline-none">
                  <span class="i-carbon-list-boxes text-xs flex-shrink-0"></span>Item-wise
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Tabs + Search -->
        <div class="flex-shrink-0 border-b border-gray-100">
          <div class="flex items-center gap-2 px-8 py-3">
            <button @click="activeTab = 'date'"
              :class="['flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg border transition-all',
                activeTab === 'date'
                  ? 'bg-[#1D5F5E] text-white border-[#1D5F5E]'
                  : 'bg-white text-gray-500 border-gray-200 hover:border-[#1D5F5E] hover:text-[#1D5F5E]']">
              <span class="i-carbon-calendar text-sm"></span>Date-wise
            </button>
            <button @click="activeTab = 'item'; selectedItem = null"
              :class="['flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg border transition-all',
                activeTab === 'item'
                  ? 'bg-[#1D5F5E] text-white border-[#1D5F5E]'
                  : 'bg-white text-gray-500 border-gray-200 hover:border-[#1D5F5E] hover:text-[#1D5F5E]']">
              <span class="i-carbon-list-boxes text-sm"></span>Item-wise
              <span v-if="sortedItems.length"
                :class="['inline-flex items-center justify-center w-4 h-4 rounded-full text-[9px] font-bold',
                  activeTab === 'item' ? 'bg-white/20 text-white' : 'bg-[#1D5F5E]/10 text-[#1D5F5E]']">
                {{ sortedItems.length }}
              </span>
            </button>
            <!-- SR search -->
            <div class="flex-1 flex items-center bg-gray-50 border border-gray-200 rounded-xl px-3 py-1.5
                        focus-within:ring-2 focus-within:ring-[#1D5F5E]/20 focus-within:border-[#1D5F5E]
                        focus-within:bg-white transition-all ml-2">
              <span class="i-carbon-search text-gray-400 text-xs mr-2 flex-shrink-0"></span>
              <input v-model="srSearch" type="text"
                :placeholder="activeTab === 'date'
                  ? 'Search SR no, category, item ref, entry, response…'
                  : 'Search item no, entry, response…'"
                class="bg-transparent outline-none w-full text-gray-700 placeholder-gray-400 text-xs" />
              <button v-if="srSearch" @click="srSearch = ''" class="ml-1 text-gray-300 hover:text-gray-500 transition-colors">
                <span class="i-carbon-close text-xs"></span>
              </button>
            </div>
          </div>
        </div>

        <!-- ── DATE-WISE TAB ─────────────────────────────────────────── -->
        <template v-if="activeTab === 'date'">
          <div v-if="workThreads.length === 0"
            class="flex-1 flex flex-col items-center justify-center py-16 text-center">
            <div class="i-carbon-document-unknown text-5xl text-gray-200 mb-4"></div>
            <p class="text-sm font-semibold text-gray-400">No site register entries for this LOA yet.</p>
            <p class="text-xs text-gray-300 mt-1">Use the Telegram bot to create entries.</p>
          </div>
          <div v-else-if="filteredWorkThreads.length === 0"
            class="flex-1 flex flex-col items-center justify-center py-16 text-center">
            <div class="i-carbon-search text-4xl text-gray-200 mb-4"></div>
            <p class="text-sm font-semibold text-gray-400">No entries match "{{ srSearch }}".</p>
          </div>

          <div v-else class="flex-1 overflow-auto">
            <table class="w-full table-fixed border-collapse text-xs">
              <thead class="bg-gray-50 sticky top-0 z-10">
                <tr class="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
                  <th class="px-4 py-3 text-left w-[10%] whitespace-nowrap">SR No</th>
                  <th class="px-4 py-3 text-left w-[8%] whitespace-nowrap">Date</th>
                  <th class="px-4 py-3 text-center w-[12%] whitespace-nowrap">Category</th>
                  <th class="px-4 py-3 text-left w-[13%] whitespace-nowrap">Location</th>
                  <th class="px-4 py-3 text-left w-[27%]">Entry</th>
                  <th class="px-4 py-3 text-left w-[30%]">Response</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="t in filteredWorkThreads" :key="t.id"
                  class="border-b border-gray-100 hover:bg-[#1D5F5E]/5 cursor-pointer transition-colors group"
                  @click="openThread(t)">

                  <td class="px-4 py-3.5 align-top">
                    <span class="font-bold text-[#1D5F5E] font-mono text-[11px]">{{ t.sr_number }}</span>
                  </td>
                  <td class="px-4 py-3.5 align-top whitespace-nowrap text-gray-600">
                    {{ fmtDate(t.created_at) }}
                  </td>
                  <td class="px-4 py-3.5 align-top text-center">
                    <span v-if="t.instruction_type === 'item'"
                      class="inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 whitespace-nowrap">
                      Item
                    </span>
                    <span v-else
                      class="inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 whitespace-nowrap">
                      General
                    </span>
                    <div v-if="t.instruction_type === 'item' && t.work_item_ref"
                      class="font-mono font-semibold text-[#1D5F5E] text-[11px] mt-0.5">
                      {{ t.work_item_ref }}
                    </div>
                  </td>
                  <td class="px-4 py-3.5 align-top text-left">
                    <span v-if="t.location" class="text-gray-700 text-xs">{{ t.location }}</span>
                    <span v-else class="text-gray-300 text-xs">—</span>
                  </td>
                  <td class="px-4 py-3.5 align-top text-left">
                    <div class="text-gray-800 line-clamp-3 text-xs leading-normal">{{ t.initial_text }}</div>
                    <div class="text-[10px] text-gray-400 mt-1">
                      {{ t.created_by_name }}
                      <template v-if="t.created_by_designation"> · {{ t.created_by_designation }}</template>
                    </div>
                  </td>
                  <td class="px-4 py-3.5 align-top text-left">
                    <template v-if="t.messages && t.messages.length">
                      <div class="text-gray-700 line-clamp-3 text-xs leading-normal">
                        {{ truncate(t.messages[0].text, 120) }}
                        <sup v-if="t.messages.length > 1"
                          class="ml-0.5 inline-flex items-center justify-center w-4 h-4 rounded-full bg-[#1D5F5E] text-white text-[9px] font-bold leading-none"
                          :title="`${t.messages.length} replies`">
                          {{ t.messages.length }}
                        </sup>
                      </div>
                      <div class="text-[10px] text-gray-400 mt-1">{{ t.messages[0].sender_name }}</div>
                      <div v-if="t.messages[0].attachments && t.messages[0].attachments.length"
                        class="mt-1 flex flex-wrap gap-1">
                        <span v-for="a in t.messages[0].attachments" :key="a.id"
                          class="text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded bg-green-50 border border-green-200 text-green-700">
                          {{ a.att_number }}
                        </span>
                      </div>
                    </template>
                    <span v-else class="text-gray-300 italic text-[11px]">Pending</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <!-- ── ITEM-WISE TAB ─────────────────────────────────────────── -->
        <template v-else>

          <!-- Level 1: All LOA items list -->
          <template v-if="!selectedItem">
            <div v-if="sortedItems.length === 0"
              class="flex-1 flex flex-col items-center justify-center py-16 text-center">
              <div class="i-carbon-list-boxes text-5xl text-gray-200 mb-4"></div>
              <p class="text-sm font-semibold text-gray-400">No items found for this LOA.</p>
            </div>
            <div v-else class="flex-1 overflow-auto">
              <table class="w-full table-fixed border-collapse text-xs">
                <thead class="bg-gray-50 sticky top-0 z-10">
                  <tr class="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
                    <th class="px-4 py-3 text-left w-[10%] whitespace-nowrap">Item Ref</th>
                    <th class="px-4 py-3 text-left w-[62%]">Description</th>
                    <th class="px-4 py-3 text-right w-[10%] whitespace-nowrap">Qty</th>
                    <th class="px-4 py-3 text-left w-[10%]">Unit</th>
                    <th class="px-4 py-3 text-center w-[8%] whitespace-nowrap">Entries</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in sortedItems" :key="item.id"
                    class="border-b border-gray-100 hover:bg-[#1D5F5E]/5 cursor-pointer transition-colors group"
                    @click="selectedItem = item">
                    <td class="px-4 py-3.5 align-top">
                      <span class="font-mono font-bold text-[#1D5F5E] text-[11px]">{{ itemRef(item) }}</span>
                    </td>
                    <td class="px-4 py-3.5 align-top text-gray-700 leading-snug">{{ item.item_desc || '—' }}</td>
                    <td class="px-4 py-3.5 align-top text-right text-gray-600 font-mono">{{ item.qty ?? '—' }}</td>
                    <td class="px-4 py-3.5 align-top text-gray-500">{{ item.unit || '—' }}</td>
                    <td class="px-4 py-3.5 align-top text-center">
                      <span v-if="entryCountForItem(item) > 0"
                        class="inline-flex items-center justify-center px-2 py-0.5 rounded-full bg-[#1D5F5E]/10 text-[#1D5F5E] text-[10px] font-bold">
                        {{ entryCountForItem(item) }}
                      </span>
                      <span v-else class="text-gray-300 text-[11px]">—</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>

          <!-- Level 2: Threads for selected item -->
          <template v-else>
            <!-- Item header + back -->
            <div class="flex-shrink-0 flex items-center gap-3 px-6 py-3 bg-[#1D5F5E]/5 border-b border-[#1D5F5E]/15">
              <button @click="selectedItem = null"
                class="flex items-center gap-1 text-xs text-[#1D5F5E] hover:text-[#1D5F5E] font-semibold transition-colors">
                <span class="i-carbon-arrow-left text-sm"></span> Back
              </button>
              <span class="text-[#1D5F5E]/30">|</span>
              <span class="font-mono font-bold text-[#1D5F5E] text-xs">{{ itemRef(selectedItem) }}</span>
              <span class="text-xs text-gray-500 truncate max-w-md">{{ selectedItem.item_desc }}</span>
              <span class="ml-auto text-[10px] text-[#1D5F5E] font-semibold">
                {{ selectedItemThreads.length }} {{ selectedItemThreads.length === 1 ? 'entry' : 'entries' }}
              </span>
            </div>

            <div v-if="selectedItemThreads.length === 0"
              class="flex-1 flex flex-col items-center justify-center py-16 text-center">
              <div class="i-carbon-document-unknown text-5xl text-gray-200 mb-4"></div>
              <p class="text-sm font-semibold text-gray-400">No entries for this item yet.</p>
            </div>
            <div v-else-if="filteredSelectedItemThreads.length === 0"
              class="flex-1 flex flex-col items-center justify-center py-16 text-center">
              <div class="i-carbon-search text-4xl text-gray-200 mb-4"></div>
              <p class="text-sm font-semibold text-gray-400">No entries match "{{ srSearch }}".</p>
            </div>
            <div v-else class="flex-1 overflow-auto">
              <table class="w-full table-fixed border-collapse text-xs">
                <thead class="bg-gray-50 sticky top-0 z-10">
                  <tr class="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
                    <th class="px-4 py-3 text-left w-[10%] whitespace-nowrap">SR No</th>
                    <th class="px-4 py-3 text-left w-[9%] whitespace-nowrap">Date</th>
                    <th class="px-4 py-3 text-left w-[40%]">Entry</th>
                    <th class="px-4 py-3 text-left w-[41%]">Response</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="t in filteredSelectedItemThreads" :key="t.id"
                    class="border-b border-gray-100 hover:bg-[#1D5F5E]/5/50 cursor-pointer transition-colors"
                    @click="openThread(t)">
                    <td class="px-4 py-3.5 align-top">
                      <span class="font-bold text-[#1D5F5E] font-mono text-[11px]">{{ t.sr_number }}</span>
                    </td>
                    <td class="px-4 py-3.5 align-top whitespace-nowrap text-gray-600">
                      {{ fmtDate(t.created_at) }}
                    </td>
                    <td class="px-4 py-3.5 align-top text-left">
                      <div class="text-gray-800 line-clamp-3 text-xs leading-normal">{{ t.initial_text }}</div>
                      <div class="text-[10px] text-gray-400 mt-1">
                        {{ t.created_by_name }}
                        <template v-if="t.created_by_designation"> · {{ t.created_by_designation }}</template>
                      </div>
                    </td>
                    <td class="px-4 py-3.5 align-top text-left">
                      <template v-if="t.messages && t.messages.length">
                        <div class="text-gray-700 line-clamp-3 text-xs leading-normal">
                          {{ truncate(t.messages[0].text, 120) }}
                          <sup v-if="t.messages.length > 1"
                            class="ml-0.5 inline-flex items-center justify-center w-4 h-4 rounded-full bg-[#1D5F5E] text-white text-[9px] font-bold leading-none"
                            :title="`${t.messages.length} replies`">
                            {{ t.messages.length }}
                          </sup>
                        </div>
                        <div class="text-[10px] text-gray-400 mt-1">{{ t.messages[0].sender_name }}</div>
                      </template>
                      <span v-else class="text-gray-300 italic text-[11px]">Pending</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>

        </template>

      </div>
    </template>

  <!-- ══ PDF OPTIONS MODAL ════════════════════════════════════════════════ -->
  <Teleport to="body">
    <div v-if="showPdfOptions"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      @click.self="showPdfOptions = false">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        <div class="px-6 pt-6 pb-4 border-b border-gray-100">
          <h3 class="text-base font-bold text-gray-900">
            Export PDF — {{ pdfMode === 'date' ? 'Date-wise' : 'Item-wise' }}
          </h3>
          <p class="text-xs text-gray-400 mt-0.5">Choose the date range for this report.</p>
        </div>
        <div class="px-6 py-5 space-y-2">
          <!-- Comprehensive -->
          <label class="flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all"
            :class="pdfRangeType === 'comprehensive'
              ? 'border-[#1D5F5E] bg-[#1D5F5E]/5'
              : 'border-gray-200 hover:border-[#1D5F5E]/40'">
            <input type="radio" v-model="pdfRangeType" value="comprehensive" class="accent-[#1D5F5E]" />
            <div>
              <p class="text-sm font-semibold text-gray-800">Comprehensive</p>
              <p class="text-[11px] text-gray-400">All entries from start till today</p>
            </div>
          </label>
          <!-- This Week -->
          <label class="flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all"
            :class="pdfRangeType === 'week'
              ? 'border-[#1D5F5E] bg-[#1D5F5E]/5'
              : 'border-gray-200 hover:border-[#1D5F5E]/40'">
            <input type="radio" v-model="pdfRangeType" value="week" class="accent-[#1D5F5E]" />
            <div>
              <p class="text-sm font-semibold text-gray-800">This Week</p>
              <p class="text-[11px] text-gray-400">Entries from this calendar week (Sun–Sat)</p>
            </div>
          </label>
          <!-- This Month -->
          <label class="flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all"
            :class="pdfRangeType === 'month'
              ? 'border-[#1D5F5E] bg-[#1D5F5E]/5'
              : 'border-gray-200 hover:border-[#1D5F5E]/40'">
            <input type="radio" v-model="pdfRangeType" value="month" class="accent-[#1D5F5E]" />
            <div>
              <p class="text-sm font-semibold text-gray-800">This Month</p>
              <p class="text-[11px] text-gray-400">Entries from 1st of this month till today</p>
            </div>
          </label>
          <!-- Custom Range -->
          <label class="flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all"
            :class="pdfRangeType === 'custom'
              ? 'border-[#1D5F5E] bg-[#1D5F5E]/5'
              : 'border-gray-200 hover:border-[#1D5F5E]/40'">
            <input type="radio" v-model="pdfRangeType" value="custom" class="accent-[#1D5F5E] mt-0.5" />
            <div class="flex-1">
              <p class="text-sm font-semibold text-gray-800">Custom Date Range</p>
              <div v-if="pdfRangeType === 'custom'" class="flex items-center gap-2 mt-2">
                <input type="date" v-model="pdfDateFrom"
                  class="flex-1 border border-gray-200 rounded-lg px-2 py-1.5 text-xs text-gray-700 focus:outline-none focus:border-[#1D5F5E]" />
                <span class="text-xs text-gray-400">to</span>
                <input type="date" v-model="pdfDateTo"
                  class="flex-1 border border-gray-200 rounded-lg px-2 py-1.5 text-xs text-gray-700 focus:outline-none focus:border-[#1D5F5E]" />
              </div>
            </div>
          </label>
        </div>
        <div class="px-6 pb-6 flex items-center justify-end gap-3">
          <button @click="showPdfOptions = false"
            class="px-4 py-2 text-xs font-semibold text-gray-500 hover:text-gray-700 transition-colors">
            Cancel
          </button>
          <button @click="exportPdf()"
            class="flex items-center gap-1.5 px-5 py-2 rounded-lg bg-[#1D5F5E] hover:bg-[#1D5F5E]/90 text-white text-xs font-semibold transition-all">
            <span class="i-carbon-document-pdf text-sm"></span>
            Generate PDF
          </button>
        </div>
      </div>
    </div>
  </Teleport>

  </div>
</template>
