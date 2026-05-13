<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import axios from 'axios'

// ── Views: 'list' | 'work' ─────────────────────────────────────────────────
const view = ref('list')

// ── Right panel: 'history' | 'preview' ────────────────────────────────────
const rightPanel = ref('history')
const previewUrl = ref('')         // blob URL for iframe
const previewCertId = ref(null)    // id of saved cert being previewed (null = unsaved preview)

// ── LOA list ───────────────────────────────────────────────────────────────
const loas        = ref([])
const loaSearch   = ref('')
const isLoadingLoas = ref(false)
const loaError    = ref('')

const filteredLoas = computed(() => {
  const q = loaSearch.value.trim().toLowerCase()
  if (!q) return loas.value
  return loas.value.filter(l =>
    (l.loa_number      && l.loa_number.toLowerCase().includes(q)) ||
    (l.tender_number   && l.tender_number.toLowerCase().includes(q)) ||
    (l.contractor_name && l.contractor_name.toLowerCase().includes(q)) ||
    (l.name_of_work    && l.name_of_work.toLowerCase().includes(q))
  )
})

const loadLoas = async () => {
  isLoadingLoas.value = true
  loaError.value = ''
  try {
    const res = await axios.get('/api/installation-cert/loas/')
    loas.value = res.data
  } catch {
    loaError.value = 'Failed to load LOAs.'
  } finally {
    isLoadingLoas.value = false
  }
}

// ── Certificate history ────────────────────────────────────────────────────
const certs        = ref([])
const isLoadingCerts = ref(false)
const deletingId   = ref(null)

const loadCerts = async () => {
  isLoadingCerts.value = true
  try {
    const res = await axios.get('/api/installation-cert/certificates/')
    certs.value = res.data
  } catch {
    /* silent */
  } finally {
    isLoadingCerts.value = false
  }
}

const deleteCert = async (id) => {
  if (!confirm('Delete this certificate record?')) return
  deletingId.value = id
  try {
    await axios.delete(`/api/installation-cert/certificates/${id}/`)
    certs.value = certs.value.filter(c => c.id !== id)
    if (previewCertId.value === id) {
      rightPanel.value = 'history'
      clearPreview()
    }
  } catch {
    /* silent */
  } finally {
    deletingId.value = null
  }
}

const previewSavedCert = async (cert) => {
  previewCertId.value = cert.id
  rightPanel.value = 'preview'
  clearPreview()
  try {
    const res = await axios.get(`/api/installation-cert/certificates/${cert.id}/pdf/?inline=1`, { responseType: 'blob' })
    previewUrl.value = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
  } catch {
    /* silent */
  }
}

const downloadSavedCert = async (cert) => {
  try {
    const res = await axios.get(`/api/installation-cert/certificates/${cert.id}/pdf/`, { responseType: 'blob' })
    const url  = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `installation_certificate_${cert.cert_number.replace(/\//g, '_')}.pdf`
    link.click()
    URL.revokeObjectURL(url)
  } catch {
    /* silent */
  }
}

onMounted(() => {
  loadLoas()
  loadCerts()
})

// ── Work detail ────────────────────────────────────────────────────────────
const selectedLoa     = ref(null)
const loaItems        = ref([])
const itemSearch      = ref('')
const isLoadingItems  = ref(false)

const filterMode      = ref('item')
const selectedItemIds = ref(new Set())
const dateFrom        = ref('')
const dateTo          = ref('')

const entries         = ref([])
const selectedEntryIds = ref([])
const isLoadingEntries = ref(false)

const certNumber      = ref('')
const isGenerating    = ref(false)
const isPreviewing    = ref(false)
const workError       = ref('')
const showDupModal    = ref(false)
// conflict modals
const showOwnReplaceModal   = ref(false)
const showOtherConflictModal = ref(false)
const conflictMessage        = ref('')
const pendingReplaceCertId   = ref(null)

// Cert in history that has same cert_number (any LOA, not just current)
const duplicateCert = computed(() =>
  certNumber.value.trim()
    ? (certs.value.find(c => c.cert_number === certNumber.value.trim()) || null)
    : null
)

const filteredItems = computed(() => {
  const q = itemSearch.value.trim().toLowerCase()
  if (!q) return loaItems.value
  return loaItems.value.filter(it =>
    (it.item_desc     && it.item_desc.toLowerCase().includes(q)) ||
    (it.schedule      && it.schedule.toLowerCase().includes(q)) ||
    (it.serial_number && String(it.serial_number).toLowerCase().includes(q))
  )
})

const canFetch = computed(() => {
  if (filterMode.value === 'item') return selectedItemIds.value.size > 0
  return !!(dateFrom.value && dateTo.value)
})

const fmtDate = (v) => {
  if (!v) return '—'
  const s = String(v).split('T')[0]
  const m = s.match(/^(\d{4})[\/\-](\d{2})[\/\-](\d{2})$/)
  if (m) return `${m[3]}/${m[2]}/${m[1]}`
  return s
}

const fmtDateTime = (v) => {
  if (!v) return '—'
  const d = new Date(v)
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const clearPreview = () => {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
}

const enterWork = async (loa) => {
  selectedLoa.value     = loa
  loaItems.value        = []
  itemSearch.value      = ''
  selectedItemIds.value = new Set()
  entries.value         = []
  selectedEntryIds.value = []
  dateFrom.value        = ''
  dateTo.value          = ''
  filterMode.value      = 'item'
  workError.value       = ''
  certNumber.value      = ''
  view.value            = 'work'
  rightPanel.value      = 'history'
  clearPreview()

  isLoadingItems.value = true
  try {
    const itemsRes = await axios.get('/api/installation-cert/items/', { params: { loa_id: loa.id } })
    loaItems.value = itemsRes.data
  } catch {
    workError.value = 'Failed to load items.'
  } finally {
    isLoadingItems.value = false
  }
  // Suggest cert number independently — don't block item list on failure
  try {
    const numRes = await axios.get('/api/installation-cert/suggest-number/', { params: { loa_id: loa.id } })
    certNumber.value = numRes.data.cert_number
  } catch (e) {
    console.error('suggest-number failed:', e?.response?.data || e)
    /* cert number stays blank — user can type manually */
  }
}

const backToList = () => {
  view.value = 'list'
  rightPanel.value = 'history'
  clearPreview()
}

const toggleItem = (id) => {
  const s = new Set(selectedItemIds.value)
  s.has(id) ? s.delete(id) : s.add(id)
  selectedItemIds.value = s
  entries.value = []
  selectedEntryIds.value = []
  clearPreview()
}

const selectAllItems = () => {
  selectedItemIds.value = new Set(filteredItems.value.map(i => i.id))
  entries.value = []
  selectedEntryIds.value = []
}

const clearItemSelection = () => {
  selectedItemIds.value = new Set()
  entries.value = []
  selectedEntryIds.value = []
}

const fetchEntries = async () => {
  if (!canFetch.value) return
  entries.value = []
  selectedEntryIds.value = []
  isLoadingEntries.value = true
  workError.value = ''
  clearPreview()
  try {
    if (filterMode.value === 'item') {
      const requests = [...selectedItemIds.value].map(item_id =>
        axios.get('/api/installation-cert/entries/', { params: { loa_id: selectedLoa.value.id, item_id } })
      )
      const results = await Promise.all(requests)
      const merged = results.flatMap(r => r.data)
      merged.sort((a, b) => {
        const sa = (a.schedule || '') + String(a.serial_number || '') + (a.submitted_at || '')
        const sb = (b.schedule || '') + String(b.serial_number || '') + (b.submitted_at || '')
        return sa.localeCompare(sb)
      })
      entries.value = merged
    } else {
      const res = await axios.get('/api/installation-cert/entries/', {
        params: { loa_id: selectedLoa.value.id, date_from: dateFrom.value, date_to: dateTo.value },
      })
      entries.value = res.data
    }
    selectedEntryIds.value = entries.value.map(e => e.entry_id)
  } catch {
    workError.value = 'Failed to load entries.'
  } finally {
    isLoadingEntries.value = false
  }
}

const toggleEntry = (id) => {
  const idx = selectedEntryIds.value.indexOf(id)
  idx === -1 ? selectedEntryIds.value.push(id) : selectedEntryIds.value.splice(idx, 1)
}

const allEntriesSelected = computed(
  () => entries.value.length > 0 && selectedEntryIds.value.length === entries.value.length
)
const toggleAllEntries = () => {
  allEntriesSelected.value
    ? selectedEntryIds.value = []
    : selectedEntryIds.value = entries.value.map(e => e.entry_id)
}

// ── Preview (unsaved) ──────────────────────────────────────────────────────
const previewCert = async () => {
  if (!selectedEntryIds.value.length) { workError.value = 'Select at least one entry.'; return }
  isPreviewing.value = true
  workError.value = ''
  clearPreview()
  previewCertId.value = null
  try {
    const res = await axios.post(
      '/api/installation-cert/preview/',
      { loa_id: selectedLoa.value.id, entry_ids: selectedEntryIds.value, cert_number: certNumber.value },
      { responseType: 'blob' },
    )
    previewUrl.value = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    rightPanel.value = 'preview'
  } catch {
    workError.value = 'Failed to generate preview.'
  } finally {
    isPreviewing.value = false
  }
}

// ── Generate & Save ────────────────────────────────────────────────────────
const generate = () => {
  if (!selectedEntryIds.value.length) { workError.value = 'Select at least one entry.'; return }
  if (duplicateCert.value) { showDupModal.value = true; return }
  doGenerate(null)
}

const doGenerate = async (replaceCertId) => {
  showDupModal.value = false
  isGenerating.value = true
  workError.value = ''
  try {
    const payload = {
      loa_id: selectedLoa.value.id,
      entry_ids: selectedEntryIds.value,
      cert_number: certNumber.value,
    }
    if (replaceCertId) payload.replace_cert_id = replaceCertId
    const res = await axios.post('/api/installation-cert/generate/', payload, { responseType: 'blob' })
    const url  = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    const link = document.createElement('a')
    link.href  = url
    link.download = `installation_certificate_${certNumber.value.replace(/\//g, '_') || selectedLoa.value.id}.pdf`
    link.click()
    URL.revokeObjectURL(url)
    await loadCerts()
  } catch (e) {
    if (e.response?.status === 409) {
      // Parse JSON from blob response
      const text = await e.response.data.text()
      const data = JSON.parse(text)
      conflictMessage.value = data.message || 'Certificate conflict.'
      if (data.error === 'cert_belongs_to_other') {
        showOtherConflictModal.value = true
      } else if (data.error === 'cert_exists_own') {
        pendingReplaceCertId.value = data.existing_cert_id
        showOwnReplaceModal.value = true
      }
    } else {
      workError.value = 'Failed to generate certificate.'
    }
  } finally {
    isGenerating.value = false
  }
}

const confirmOwnReplace = () => {
  showOwnReplaceModal.value = false
  doGenerate(pendingReplaceCertId.value)
  pendingReplaceCertId.value = null
}

watch(filterMode, () => {
  entries.value = []
  selectedEntryIds.value = []
  clearPreview()
})

// active cert for preview panel header
const activeCert = computed(() => certs.value.find(c => c.id === previewCertId.value) || null)

// ── Resizable right panel ──────────────────────────────────────────────────
const rightPanelWidth = ref(320)
let dragStartX = 0
let dragStartW = 0

const isDragging = ref(false)

const onResizerMousedown = (e) => {
  e.preventDefault()
  dragStartX = e.clientX
  dragStartW = rightPanelWidth.value
  isDragging.value = true

  const onMove = (ev) => {
    if (!isDragging.value) return
    const delta = dragStartX - ev.clientX
    rightPanelWidth.value = Math.max(240, Math.min(900, dragStartW + delta))
  }
  const onUp = () => {
    isDragging.value = false
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}
</script>

<template>
<div style="display: contents;">
  <div class="flex h-full overflow-hidden">

    <!-- ════════════════════════════════════════════════════════════════════ -->
    <!-- LEFT / MAIN AREA                                                     -->
    <!-- ════════════════════════════════════════════════════════════════════ -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden">

      <!-- ── LOA List View ───────────────────────────────────────────────── -->
      <div v-if="view === 'list'" class="flex flex-col gap-5 p-6 overflow-y-auto h-full">

        <div class="flex items-center gap-3">
          <div class="i-carbon-certificate text-3xl" style="color: var(--color-accent);"></div>
          <div>
            <h1 class="text-2xl font-bold" style="color: var(--color-text-primary);">Installation Certificate</h1>
            <p class="text-sm mt-0.5" style="color: var(--color-text-secondary);">Select a work order to generate a certificate</p>
          </div>
        </div>

        <div v-if="loaError" class="flex items-center gap-2 px-4 py-3 rounded-xl text-sm text-red-700 bg-red-50 border border-red-200">
          <div class="i-carbon-warning-alt shrink-0"></div>{{ loaError }}
        </div>

        <div class="relative">
          <div class="absolute left-3 top-1/2 -translate-y-1/2 i-carbon-search text-base pointer-events-none" style="color: var(--color-text-tertiary);"></div>
          <input
            v-model="loaSearch" type="text"
            placeholder="Search by LOA number, contractor, tender…"
            class="w-full pl-9 pr-4 py-2.5 rounded-xl text-sm border"
            style="background: var(--color-surface); border-color: var(--color-separator); color: var(--color-text-primary);"
          />
        </div>

        <div v-if="isLoadingLoas" class="flex justify-center items-center gap-2 py-12 text-sm" style="color: var(--color-text-secondary);">
          <div class="i-carbon-renew animate-spin"></div> Loading works…
        </div>
        <div v-else-if="!loas.length" class="text-sm text-center py-12" style="color: var(--color-text-secondary);">No works found.</div>
        <div v-else-if="!filteredLoas.length" class="text-sm text-center py-12" style="color: var(--color-text-secondary);">No results for "{{ loaSearch }}"</div>

        <div v-else class="flex flex-col gap-2">
          <div
            v-for="loa in filteredLoas" :key="loa.id"
            @click="enterWork(loa)"
            class="flex items-center gap-4 px-5 py-4 rounded-xl border cursor-pointer transition-all group"
            style="background: var(--color-surface); border-color: var(--color-separator);"
            @mouseenter="$event.currentTarget.style.borderColor='var(--color-accent)'"
            @mouseleave="$event.currentTarget.style.borderColor='var(--color-separator)'"
          >
            <div class="i-carbon-document text-2xl shrink-0" style="color: var(--color-accent);"></div>
            <div class="flex-1 min-w-0">
              <div class="flex flex-wrap items-baseline gap-x-4 gap-y-0.5">
                <span class="text-sm font-bold" style="color: var(--color-text-primary);">{{ loa.loa_number }}</span>
                <span class="text-xs" style="color: var(--color-text-secondary);"><span class="font-medium">Tender:</span> {{ loa.tender_number }}</span>
                <span class="text-xs" style="color: var(--color-text-secondary);"><span class="font-medium">Date:</span> {{ fmtDate(loa.loa_date) }}</span>
              </div>
              <div class="mt-0.5 text-xs font-medium truncate" style="color: var(--color-text-secondary);">{{ loa.contractor_name }}</div>
              <div class="mt-0.5 text-xs truncate" style="color: var(--color-text-tertiary);">{{ loa.name_of_work }}</div>
            </div>
            <div class="i-carbon-chevron-right text-lg shrink-0" style="color: var(--color-text-tertiary);"></div>
          </div>
        </div>
      </div>

      <!-- ── Work Detail View ────────────────────────────────────────────── -->
      <div v-else class="flex flex-col h-full overflow-hidden">

        <!-- Top bar -->
        <div class="flex items-center gap-3 px-5 py-3 border-b shrink-0" style="border-color: var(--color-separator); background: var(--color-surface);">
          <button @click="backToList" class="flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-colors" style="color: var(--color-text-secondary);">
            <div class="i-carbon-arrow-left text-base"></div> All Works
          </button>
          <span class="text-sm font-semibold truncate" style="color: var(--color-text-primary);">{{ selectedLoa?.loa_number }}</span>
          <span class="text-xs px-2 py-0.5 rounded-full shrink-0" style="background: var(--color-surface-secondary); color: var(--color-text-secondary);">{{ selectedLoa?.contractor_name }}</span>
        </div>

        <!-- LOA info strip -->
        <div class="px-5 py-2 flex flex-wrap gap-x-6 gap-y-0.5 text-xs border-b shrink-0" style="background: var(--color-surface-secondary); border-color: var(--color-separator);">
          <span><b style="color: var(--color-text-secondary);">Tender:</b> <span style="color: var(--color-text-primary);">{{ selectedLoa?.tender_number }}</span></span>
          <span><b style="color: var(--color-text-secondary);">Date:</b> <span style="color: var(--color-text-primary);">{{ fmtDate(selectedLoa?.loa_date) }}</span></span>
          <span class="truncate"><b style="color: var(--color-text-secondary);">Work:</b> <span style="color: var(--color-text-primary);">{{ selectedLoa?.name_of_work }}</span></span>
        </div>

        <!-- Error -->
        <div v-if="workError" class="mx-5 mt-3 flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm text-red-700 bg-red-50 border border-red-200 shrink-0">
          <div class="i-carbon-warning-alt shrink-0"></div>{{ workError }}
        </div>

        <!-- Two-panel: items + entries -->
        <div class="flex flex-1 min-h-0">

          <!-- Items panel (left) -->
          <div class="w-72 shrink-0 flex flex-col border-r" style="border-color: var(--color-separator);">
            <!-- Mode tabs -->
            <div class="flex p-2.5 gap-1.5 border-b shrink-0" style="border-color: var(--color-separator);">
              <button @click="filterMode = 'item'" class="flex-1 px-2 py-1.5 rounded-lg text-xs font-semibold transition-all"
                :style="filterMode === 'item' ? 'background: var(--color-accent); color: white;' : 'background: var(--color-surface-secondary); color: var(--color-text-secondary);'">
                By Item
              </button>
              <button @click="filterMode = 'daterange'" class="flex-1 px-2 py-1.5 rounded-lg text-xs font-semibold transition-all"
                :style="filterMode === 'daterange' ? 'background: var(--color-accent); color: white;' : 'background: var(--color-surface-secondary); color: var(--color-text-secondary);'">
                By Date
              </button>
            </div>

            <!-- By Item -->
            <template v-if="filterMode === 'item'">
              <div class="p-2.5 flex flex-col gap-2 border-b shrink-0" style="border-color: var(--color-separator);">
                <div class="relative">
                  <div class="absolute left-2.5 top-1/2 -translate-y-1/2 i-carbon-search text-xs pointer-events-none" style="color: var(--color-text-tertiary);"></div>
                  <input v-model="itemSearch" type="text" placeholder="Search items…"
                    class="w-full pl-7 pr-3 py-1.5 rounded-lg text-xs border"
                    style="background: var(--color-surface); border-color: var(--color-separator); color: var(--color-text-primary);" />
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-xs" style="color: var(--color-text-tertiary);">{{ selectedItemIds.size }} selected</span>
                  <div class="flex gap-2">
                    <button @click="selectAllItems" class="text-xs font-medium" style="color: var(--color-accent);">All</button>
                    <button @click="clearItemSelection" class="text-xs font-medium" style="color: var(--color-text-tertiary);">Clear</button>
                  </div>
                </div>
              </div>

              <div v-if="isLoadingItems" class="flex justify-center py-8"><div class="i-carbon-renew animate-spin" style="color: var(--color-text-tertiary);"></div></div>
              <div v-else-if="!loaItems.length" class="text-xs text-center py-8 px-4" style="color: var(--color-text-tertiary);">No SI/Execution items found.</div>
              <div v-else class="flex-1 overflow-y-auto">
                <div v-for="item in filteredItems" :key="item.id"
                  @click="toggleItem(item.id)"
                  class="flex items-start gap-2.5 px-3 py-2.5 cursor-pointer border-b transition-colors"
                  :style="['border-color: var(--color-separator);', selectedItemIds.has(item.id) ? 'background: color-mix(in srgb, var(--color-accent) 8%, transparent);' : ''].join(' ')"
                >
                  <input type="checkbox" :checked="selectedItemIds.has(item.id)" @click.stop @change="toggleItem(item.id)" class="mt-0.5 cursor-pointer shrink-0" />
                  <div class="min-w-0">
                    <div class="flex flex-wrap items-center gap-1 mb-0.5">
                      <span v-if="item.schedule" class="px-1.5 py-0.5 rounded font-mono font-bold text-xs" style="background: var(--color-surface-secondary); color: var(--color-text-secondary);">{{ item.schedule }}</span>
                      <span v-if="item.serial_number" class="text-xs" style="color: var(--color-text-tertiary);">#{{ item.serial_number }}</span>
                      <span class="text-xs px-1.5 py-0.5 rounded"
                        :style="item.category === 'execution' ? 'background:#dcfce7;color:#166534;' : 'background:#dbeafe;color:#1e40af;'">
                        {{ item.category || 'N/A' }}
                      </span>
                    </div>
                    <p class="text-xs leading-snug" style="color: var(--color-text-primary);">{{ item.item_desc }}</p>
                    <p class="text-xs mt-0.5" style="color: var(--color-text-tertiary);">{{ item.unit }}</p>
                  </div>
                </div>
              </div>
            </template>

            <!-- By Date Range -->
            <template v-else>
              <div class="flex flex-col gap-4 p-4">
                <div class="flex flex-col gap-1.5">
                  <label class="text-xs font-medium" style="color: var(--color-text-secondary);">From Date</label>
                  <input v-model="dateFrom" type="date" class="px-3 py-2 rounded-lg text-sm border"
                    style="background: var(--color-surface); border-color: var(--color-separator); color: var(--color-text-primary);" />
                </div>
                <div class="flex flex-col gap-1.5">
                  <label class="text-xs font-medium" style="color: var(--color-text-secondary);">To Date</label>
                  <input v-model="dateTo" type="date" class="px-3 py-2 rounded-lg text-sm border"
                    style="background: var(--color-surface); border-color: var(--color-separator); color: var(--color-text-primary);" />
                </div>
              </div>
            </template>

            <!-- Fetch button -->
            <div class="p-2.5 border-t shrink-0 mt-auto" style="border-color: var(--color-separator);">
              <button @click="fetchEntries" :disabled="!canFetch || isLoadingEntries"
                class="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-semibold transition-all disabled:opacity-50"
                style="background: var(--color-accent); color: white;">
                <div v-if="isLoadingEntries" class="i-carbon-renew animate-spin"></div>
                <div v-else class="i-carbon-search"></div>
                {{ isLoadingEntries ? 'Loading…' : 'Fetch Entries' }}
              </button>
            </div>
          </div>

          <!-- Entries area (right of items) -->
          <div class="flex-1 flex flex-col min-w-0 overflow-hidden">

            <div v-if="!entries.length && !isLoadingEntries" class="flex flex-col items-center justify-center h-full gap-3 text-center px-8">
              <div class="i-carbon-table-of-contents text-4xl" style="color: var(--color-text-tertiary);"></div>
              <p class="text-sm" style="color: var(--color-text-secondary);">
                {{ filterMode === 'item' ? 'Select items, then click Fetch Entries.' : 'Set a date range, then click Fetch Entries.' }}
              </p>
            </div>

            <div v-else-if="isLoadingEntries" class="flex items-center justify-center h-full gap-2 text-sm" style="color: var(--color-text-secondary);">
              <div class="i-carbon-renew animate-spin text-lg"></div> Loading entries…
            </div>

            <template v-else-if="entries.length">
              <!-- Entries header -->
              <div class="flex items-center justify-between px-4 py-2.5 border-b shrink-0" style="border-color: var(--color-separator);">
                <span class="text-sm font-semibold" style="color: var(--color-text-primary);">{{ entries.length }} entr{{ entries.length === 1 ? 'y' : 'ies' }}</span>
                <span class="text-xs px-2 py-1 rounded-full" style="background: var(--color-surface-secondary); color: var(--color-text-secondary);">{{ selectedEntryIds.length }} selected</span>
              </div>

              <!-- Entries table -->
              <div class="flex-1 overflow-auto">
                <table class="w-full text-xs">
                  <thead class="sticky top-0 z-10">
                    <tr style="background: var(--color-surface-secondary);">
                      <th class="px-2 py-2 text-left border-b" style="border-color: var(--color-separator);">
                        <input type="checkbox" :checked="allEntriesSelected" @change="toggleAllEntries" class="cursor-pointer" />
                      </th>
                      <th v-for="h in ['Sch','S.No.','Item Description','Qty','Unit','Location','Remark','Date']" :key="h"
                        class="px-2 py-2 text-left font-semibold uppercase tracking-wider border-b" style="color: var(--color-text-tertiary); border-color: var(--color-separator);">{{ h }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(e, i) in entries" :key="e.entry_id" @click="toggleEntry(e.entry_id)" class="cursor-pointer transition-colors"
                      :style="[i%2===0?'background:var(--color-surface);':'background:var(--color-surface-secondary);', selectedEntryIds.includes(e.entry_id)?'outline:1.5px solid var(--color-accent);outline-offset:-1.5px;':''].join(' ')">
                      <td class="px-2 py-2 border-b" style="border-color: var(--color-separator);" @click.stop>
                        <input type="checkbox" :checked="selectedEntryIds.includes(e.entry_id)" @change="toggleEntry(e.entry_id)" class="cursor-pointer" />
                      </td>
                      <td class="px-2 py-2 border-b" style="color:var(--color-text-secondary);border-color:var(--color-separator);">{{ e.schedule||'—' }}</td>
                      <td class="px-2 py-2 border-b" style="color:var(--color-text-secondary);border-color:var(--color-separator);">{{ e.serial_number||'—' }}</td>
                      <td class="px-2 py-2 border-b max-w-[180px]" style="color:var(--color-text-primary);border-color:var(--color-separator);">
                        <span class="line-clamp-2">{{ e.item_desc }}</span>
                      </td>
                      <td class="px-2 py-2 border-b text-right font-medium" style="color:var(--color-text-primary);border-color:var(--color-separator);">{{ e.quantity }}</td>
                      <td class="px-2 py-2 border-b" style="color:var(--color-text-secondary);border-color:var(--color-separator);">{{ e.unit||'—' }}</td>
                      <td class="px-2 py-2 border-b" style="color:var(--color-text-secondary);border-color:var(--color-separator);">{{ e.location||'—' }}</td>
                      <td class="px-2 py-2 border-b max-w-[120px]" style="color:var(--color-text-secondary);border-color:var(--color-separator);">
                        <span class="line-clamp-1">{{ e.remarks||'—' }}</span>
                      </td>
                      <td class="px-2 py-2 border-b whitespace-nowrap" style="color:var(--color-text-tertiary);border-color:var(--color-separator);">{{ fmtDate(e.submitted_at) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <!-- Bottom action bar -->
              <div class="flex flex-col border-t shrink-0" style="border-color: var(--color-separator); background: var(--color-surface);">
                <!-- Duplicate warning -->
                <div v-if="duplicateCert" class="flex items-center gap-2 px-4 py-2 text-xs font-medium" style="background: #fef3c7; color: #92400e; border-bottom: 1px solid #fde68a;">
                  <div class="i-carbon-warning-alt shrink-0"></div>
                  Cert No. already used for <span class="font-bold mx-1">{{ duplicateCert.loa_number }}</span> on {{ fmtDateTime(duplicateCert.generated_at) }}.
                </div>
                <div class="flex items-center gap-3 px-4 py-3">
                <!-- Cert number field -->
                <div class="flex items-center gap-1.5 flex-1 min-w-0">
                  <label class="text-xs font-semibold shrink-0" style="color: var(--color-text-secondary);">Cert No.:</label>
                  <input v-model="certNumber" type="text" placeholder="e.g. Tele-01 of 25-26/001"
                    class="flex-1 min-w-0 px-2.5 py-1.5 rounded-lg text-xs border font-mono transition-colors"
                    :style="`background: var(--color-surface-secondary); color: var(--color-text-primary); border-color: ${duplicateCert ? '#f59e0b' : 'var(--color-separator)'};`" />
                </div>

                <button @click="previewCert" :disabled="!selectedEntryIds.length || isPreviewing"
                  class="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold transition-all disabled:opacity-50 border"
                  style="background: var(--color-surface); border-color: var(--color-separator); color: var(--color-text-primary);">
                  <div v-if="isPreviewing" class="i-carbon-renew animate-spin"></div>
                  <div v-else class="i-carbon-view"></div>
                  {{ isPreviewing ? 'Loading…' : 'Preview' }}
                </button>

                <button @click="generate" :disabled="!selectedEntryIds.length || isGenerating"
                  class="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold transition-all disabled:opacity-50"
                  :style="`color: white; background: ${duplicateCert ? '#f59e0b' : 'var(--color-accent)'};`">
                  <div v-if="isGenerating" class="i-carbon-renew animate-spin"></div>
                  <div v-else class="i-carbon-download"></div>
                  {{ isGenerating ? 'Saving…' : 'Generate & Save' }}
                </button>
                </div>
              </div>
            </template>

            <div v-else class="flex flex-col items-center justify-center h-full gap-2 text-center px-8">
              <div class="i-carbon-search text-3xl" style="color: var(--color-text-tertiary);"></div>
              <p class="text-sm" style="color: var(--color-text-secondary);">No entries found for the selected filters.</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ════════════════════════════════════════════════════════════════════ -->
    <!-- DRAG HANDLE                                                          -->
    <!-- ════════════════════════════════════════════════════════════════════ -->
    <div
      @mousedown="onResizerMousedown"
      class="w-1.5 shrink-0 cursor-col-resize select-none flex items-center justify-center group"
      style="background: var(--color-separator);"
    >
      <div class="w-0.5 h-8 rounded-full opacity-0 group-hover:opacity-100 transition-opacity" style="background: var(--color-accent);"></div>
    </div>

    <!-- ════════════════════════════════════════════════════════════════════ -->
    <!-- RIGHT PANEL — Generated Details                                      -->
    <!-- ════════════════════════════════════════════════════════════════════ -->
    <div class="shrink-0 flex flex-col" :style="`width: ${rightPanelWidth}px; background: var(--color-surface);`">

      <!-- Panel header -->
      <div class="flex items-center justify-between px-4 py-3.5 border-b shrink-0" style="border-color: var(--color-separator);">
        <h2 class="text-sm font-semibold" style="color: var(--color-text-primary);">Generated Details</h2>
        <div class="flex gap-1">
          <button @click="rightPanel = 'history'; clearPreview(); previewCertId = null"
            class="px-2.5 py-1 rounded-lg text-xs font-medium transition-all"
            :style="rightPanel === 'history' ? 'background: var(--color-accent); color: white;' : 'background: var(--color-surface-secondary); color: var(--color-text-secondary);'">
            History
          </button>
          <button v-if="previewUrl" @click="rightPanel = 'preview'"
            class="px-2.5 py-1 rounded-lg text-xs font-medium transition-all"
            :style="rightPanel === 'preview' ? 'background: var(--color-accent); color: white;' : 'background: var(--color-surface-secondary); color: var(--color-text-secondary);'">
            Preview
          </button>
        </div>
      </div>

      <!-- History list -->
      <div v-if="rightPanel === 'history'" class="flex-1 overflow-y-auto">
        <div v-if="isLoadingCerts" class="flex justify-center py-8">
          <div class="i-carbon-renew animate-spin" style="color: var(--color-text-tertiary);"></div>
        </div>
        <div v-else-if="!certs.length" class="flex flex-col items-center justify-center h-full gap-3 text-center px-6 py-8">
          <div class="i-carbon-document text-3xl" style="color: var(--color-text-tertiary);"></div>
          <p class="text-xs" style="color: var(--color-text-tertiary);">No certificates generated yet.</p>
        </div>
        <div v-else class="flex flex-col divide-y" style="divide-color: var(--color-separator);">
          <div v-for="cert in certs" :key="cert.id"
            @click="previewSavedCert(cert)"
            class="flex flex-col gap-1 px-4 py-3 cursor-pointer transition-colors hover:bg-gray-50"
            :style="previewCertId === cert.id ? 'background: color-mix(in srgb, var(--color-accent) 6%, transparent);' : ''"
          >
            <div class="flex items-start justify-between gap-2">
              <span class="text-xs font-bold font-mono truncate" style="color: var(--color-text-primary);">{{ cert.cert_number }}</span>
              <span class="text-xs shrink-0" style="color: var(--color-text-tertiary);">{{ cert.entry_count }} entries</span>
            </div>
            <div class="text-xs font-medium truncate" style="color: var(--color-text-secondary);">{{ cert.loa_number }}</div>
            <div class="text-xs truncate" style="color: var(--color-text-tertiary);">{{ cert.contractor }}</div>
            <div class="text-xs" style="color: var(--color-text-tertiary);">{{ fmtDateTime(cert.generated_at) }}</div>
          </div>
        </div>
      </div>

      <!-- Preview panel -->
      <div v-else-if="rightPanel === 'preview'" class="flex-1 flex flex-col min-h-0">
        <!-- Preview action bar -->
        <div class="flex items-center gap-2 px-3 py-2.5 border-b shrink-0" style="border-color: var(--color-separator); background: var(--color-surface-secondary);">
          <span class="flex-1 text-xs font-mono font-semibold truncate" style="color: var(--color-text-primary);">
            {{ activeCert?.cert_number || 'Preview' }}
          </span>
          <!-- Download saved cert -->
          <button v-if="activeCert" @click="downloadSavedCert(activeCert)"
            class="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all"
            style="background: var(--color-accent); color: white;">
            <div class="i-carbon-download text-xs"></div> Download
          </button>
          <!-- Download unsaved preview -->
          <a v-else-if="previewUrl" :href="previewUrl" download="preview_certificate.pdf"
            class="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold"
            style="background: var(--color-surface); border: 1px solid var(--color-separator); color: var(--color-text-primary);">
            <div class="i-carbon-download text-xs"></div> Save
          </a>
          <!-- Delete saved cert -->
          <button v-if="activeCert" @click="deleteCert(activeCert.id)" :disabled="deletingId === activeCert.id"
            class="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all disabled:opacity-50"
            style="background: #fee2e2; color: #dc2626;">
            <div v-if="deletingId === activeCert.id" class="i-carbon-renew animate-spin text-xs"></div>
            <div v-else class="i-carbon-trash-can text-xs"></div>
          </button>
        </div>

        <!-- iframe -->
        <iframe v-if="previewUrl" :src="previewUrl" class="flex-1 w-full border-0" :style="`min-height: 0; pointer-events: ${isDragging ? 'none' : 'auto'};`"></iframe>
        <div v-else class="flex items-center justify-center flex-1 text-xs" style="color: var(--color-text-tertiary);">
          <div class="i-carbon-renew animate-spin"></div>
        </div>
      </div>
    </div>

  </div>

  <!-- ── Duplicate Cert Number Modal ──────────────────────────────────────── -->
  <Teleport to="body">
    <div v-if="showDupModal" class="fixed inset-0 z-50 flex items-center justify-center" style="background: rgba(0,0,0,0.4);">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        <div class="flex items-center gap-3 px-6 py-4" style="background: #fef3c7;">
          <div class="i-carbon-warning-alt text-2xl" style="color: #d97706;"></div>
          <div>
            <p class="text-sm font-bold" style="color: #92400e;">Duplicate Certificate Number</p>
            <p class="text-xs mt-0.5" style="color: #b45309;">
              <span class="font-mono font-semibold">{{ certNumber }}</span> already exists in history.
            </p>
          </div>
        </div>
        <div class="px-6 py-4 text-sm" style="color: #374151;">
          <p class="mb-1">Existing record:</p>
          <div class="rounded-lg px-3 py-2.5 text-xs" style="background: #f9fafb; border: 1px solid #e5e7eb;">
            <p class="font-bold font-mono">{{ duplicateCert?.cert_number }}</p>
            <p class="mt-0.5">LOA: {{ duplicateCert?.loa_number }}</p>
            <p>{{ duplicateCert?.contractor }}</p>
            <p class="mt-0.5" style="color: #6b7280;">{{ fmtDateTime(duplicateCert?.generated_at) }} · {{ duplicateCert?.entry_count }} entries</p>
          </div>
          <p class="mt-3 text-xs" style="color: #6b7280;">
            <b>Replace</b> deletes the old record and saves this new one with the same number.<br/>
            <b>Cancel</b> keeps the old record — edit the Cert No. to use a different one.
          </p>
        </div>
        <div class="flex gap-2 px-6 pb-5">
          <button @click="showDupModal = false"
            class="flex-1 px-4 py-2.5 rounded-xl text-sm font-semibold border"
            style="border-color: #e5e7eb; color: #374151;">
            Cancel
          </button>
          <button @click="doGenerate(duplicateCert?.id)"
            class="flex-1 px-4 py-2.5 rounded-xl text-sm font-semibold"
            style="background: #dc2626; color: white;">
            Replace Old Certificate
          </button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Certificate belongs to another user — error -->
  <Teleport to="body">
    <div v-if="showOtherConflictModal" class="fixed inset-0 z-50 flex items-center justify-center" style="background: rgba(0,0,0,0.4);">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        <div class="flex items-center gap-3 px-6 py-4" style="background: #fee2e2;">
          <div class="i-carbon-warning text-2xl" style="color: #dc2626;"></div>
          <div>
            <p class="text-sm font-bold" style="color: #991b1b;">Certificate Not Yours</p>
            <p class="text-xs mt-0.5" style="color: #b91c1c;">{{ conflictMessage }}</p>
          </div>
        </div>
        <div class="px-6 py-4 text-sm" style="color: #374151;">
          <p class="text-xs" style="color: #6b7280;">Edit the Cert No. field to use a different number.</p>
        </div>
        <div class="flex px-6 pb-5">
          <button @click="showOtherConflictModal = false"
            class="flex-1 px-4 py-2.5 rounded-xl text-sm font-semibold border"
            style="border-color: #e5e7eb; color: #374151;">
            OK
          </button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Same user — replace own certificate warning -->
  <Teleport to="body">
    <div v-if="showOwnReplaceModal" class="fixed inset-0 z-50 flex items-center justify-center" style="background: rgba(0,0,0,0.4);">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        <div class="flex items-center gap-3 px-6 py-4" style="background: #fef3c7;">
          <div class="i-carbon-warning-alt text-2xl" style="color: #d97706;"></div>
          <div>
            <p class="text-sm font-bold" style="color: #92400e;">Replace Your Certificate?</p>
            <p class="text-xs mt-0.5" style="color: #b45309;">{{ conflictMessage }}</p>
          </div>
        </div>
        <div class="px-6 py-4 text-sm" style="color: #374151;">
          <p class="text-xs" style="color: #6b7280;">Old certificate record will be deleted and replaced with this new one.</p>
        </div>
        <div class="flex gap-2 px-6 pb-5">
          <button @click="showOwnReplaceModal = false; pendingReplaceCertId = null"
            class="flex-1 px-4 py-2.5 rounded-xl text-sm font-semibold border"
            style="border-color: #e5e7eb; color: #374151;">
            Cancel
          </button>
          <button @click="confirmOwnReplace"
            class="flex-1 px-4 py-2.5 rounded-xl text-sm font-semibold"
            style="background: #d97706; color: white;">
            Replace
          </button>
        </div>
      </div>
    </div>
  </Teleport>

</div>
</template>
