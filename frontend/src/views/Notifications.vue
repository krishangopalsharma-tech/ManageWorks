<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import { useNotifications, notifConfig } from '../composables/useNotifications'

const router = useRouter()
const { state: authState } = useAuth()
const { notifications, unreadCount, fetchNotifications, markRead, markAllRead } = useNotifications()

onMounted(fetchNotifications)

const isAdmin = computed(() => authState.user?.is_staff || authState.user?.role === 'admin')

const TYPE_ORDER  = ['new_sr', 'ss_entry', 'si_entry', 'ee_entry', 'financial', 'loa_unassigned']
const COLS        = 3
const ROWS        = 2
const PADDING     = 16
const GAP         = 12
const CARD_RADIUS = '18px'
const MIN_W       = 180
const MIN_H       = 100
const MAX_W       = 900
const MAX_H       = 900

const POS_KEY  = 'notif-card-positions-v3'
const SIZE_KEY = 'notif-card-sizes-v2'

const canvasRef = ref(null)

const columns = computed(() => {
  const byType = {}
  for (const n of notifications.value) {
    if (!byType[n.notif_type]) byType[n.notif_type] = []
    byType[n.notif_type].push(n)
  }
  return TYPE_ORDER
    .filter(type => isAdmin.value || byType[type]?.length > 0)
    .map(type => ({
      type,
      cfg: notifConfig(type),
      items: byType[type] || [],
      unread: (byType[type] || []).filter(n => !n.is_read).length,
    }))
})

// ─── layout calc ─────────────────────────────────────────────
function containerSize() {
  const el = canvasRef.value
  const cw = el ? el.offsetWidth : (window.innerWidth - 320)
  // Don't use el.offsetHeight — it's inflated by its own minHeight when cards are dragged far down
  const ch = window.innerHeight - 120
  return { cw, ch }
}

function calcDefaults() {
  const { cw, ch } = containerSize()
  const cardW = Math.floor((cw - PADDING * 2 - GAP * (COLS - 1)) / COLS)
  const cardH = Math.floor((ch - PADDING * 2 - GAP * (ROWS - 1)) / ROWS)
  const pos = {}, size = {}
  TYPE_ORDER.forEach((type, i) => {
    const col = i % COLS
    const row = Math.floor(i / COLS)
    pos[type]  = { x: PADDING + col * (cardW + GAP), y: PADDING + row * (cardH + GAP) }
    size[type] = { w: cardW, h: cardH }
  })
  return { pos, size }
}

// ─── reactive state ──────────────────────────────────────────
const positions = reactive({})
const sizes     = reactive({})
const zIndexMap = reactive({})
let   maxZ      = 100

function loadState() {
  try {
    const savedPos  = JSON.parse(localStorage.getItem(POS_KEY)  || '{}')
    const savedSize = JSON.parse(localStorage.getItem(SIZE_KEY) || '{}')
    const { pos: defPos, size: defSize } = calcDefaults()
    TYPE_ORDER.forEach(type => {
      positions[type]  = savedPos[type]  || defPos[type]
      sizes[type]      = savedSize[type] || defSize[type]
      zIndexMap[type]  = 100
    })
  } catch {
    resetLayout(false)
  }
}

function resetLayout(save = true) {
  const { pos, size } = calcDefaults()
  TYPE_ORDER.forEach(type => {
    positions[type]  = pos[type]
    sizes[type]      = size[type]
    zIndexMap[type]  = 100
  })
  if (save) {
    localStorage.setItem(POS_KEY,  JSON.stringify({ ...positions }))
    localStorage.setItem(SIZE_KEY, JSON.stringify({ ...sizes }))
  }
}

function savePositions() { localStorage.setItem(POS_KEY,  JSON.stringify({ ...positions })) }
function saveSizes()     { localStorage.setItem(SIZE_KEY, JSON.stringify({ ...sizes }))     }

onMounted(async () => {
  await nextTick()
  loadState()
})

// ─── drag ────────────────────────────────────────────────────
const dragging   = ref(null)
const isDragging = ref(false)

function bringToFront(type) { maxZ++; zIndexMap[type] = maxZ }

function onDragDown(e, type) {
  if (e.button !== 0) return
  e.preventDefault()
  bringToFront(type)
  dragging.value   = { type, startX: e.clientX, startY: e.clientY, origX: positions[type].x, origY: positions[type].y }
  isDragging.value = false
  document.addEventListener('pointermove', onDragMove)
  document.addEventListener('pointerup',   onDragUp, { once: true })
}
function onDragMove(e) {
  if (!dragging.value) return
  const { type, startX, startY, origX, origY } = dragging.value
  if (Math.abs(e.clientX - startX) + Math.abs(e.clientY - startY) > 3) isDragging.value = true
  positions[type] = { x: Math.max(0, origX + e.clientX - startX), y: Math.max(0, origY + e.clientY - startY) }
}
function onDragUp() {
  if (dragging.value) savePositions()
  dragging.value   = null
  isDragging.value = false
  document.removeEventListener('pointermove', onDragMove)
}

// ─── resize ──────────────────────────────────────────────────
let resizing = null

function onResizeDown(e, type) {
  if (e.button !== 0) return
  e.preventDefault()
  e.stopPropagation()
  bringToFront(type)
  resizing = { type, startX: e.clientX, startY: e.clientY, origW: sizes[type].w, origH: sizes[type].h }
  document.addEventListener('pointermove', onResizeMove)
  document.addEventListener('pointerup',   onResizeUp, { once: true })
}
function onResizeMove(e) {
  if (!resizing) return
  const { type, startX, startY, origW, origH } = resizing
  sizes[type] = {
    w: Math.min(MAX_W, Math.max(MIN_W, origW + e.clientX - startX)),
    h: Math.min(MAX_H, Math.max(MIN_H, origH + e.clientY - startY)),
  }
}
function onResizeUp() {
  if (resizing) saveSizes()
  resizing = null
  document.removeEventListener('pointermove', onResizeMove)
}

onBeforeUnmount(() => {
  document.removeEventListener('pointermove', onDragMove)
  document.removeEventListener('pointermove', onResizeMove)
})

// ─── canvas height ───────────────────────────────────────────
const canvasHeight = computed(() => {
  let max = window.innerHeight - 120
  columns.value.forEach(col => {
    const pos = positions[col.type]
    const sz  = sizes[col.type]
    if (pos && sz) max = Math.max(max, pos.y + sz.h + 32)
  })
  return max
})

// ─── helpers ─────────────────────────────────────────────────
function relativeTime(isoString) {
  const diff = Date.now() - new Date(isoString).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1)  return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24)  return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 7)  return `${days}d ago`
  return new Date(isoString).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

async function handleClick(n) {
  if (isDragging.value) return
  if (!n.is_read) await markRead(n.id)
  if (n.notif_type === 'new_sr')         router.push('/site-register')
  else if (n.notif_type === 'financial') router.push('/mb-details')
  else                                   router.push('/item-progress')
}
</script>

<template>
  <div class="h-full flex flex-col" style="background: var(--color-background);">

    <!-- Inline title row — no box, no border, matches other pages -->
    <div class="flex items-center justify-between px-5 pt-5 pb-3 flex-shrink-0">
      <div>
        <h1 class="text-xl font-bold" style="color: var(--color-text-primary);">Notifications</h1>
        <p class="text-xs mt-0.5" style="color: var(--color-text-secondary);">
          {{ unreadCount > 0 ? `${unreadCount} unread` : 'All caught up' }}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="resetLayout()"
          class="px-3 py-1.5 text-xs font-medium flex items-center gap-1.5 transition-opacity hover:opacity-70"
          style="background: var(--color-surface-secondary); color: var(--color-text-tertiary); border-radius: 999px;"
        >
          <span class="i-carbon-reset text-sm"></span>
          Reset layout
        </button>
        <button
          v-if="unreadCount > 0"
          @click="markAllRead"
          class="px-3 py-1.5 text-xs font-semibold transition-opacity hover:opacity-70"
          style="background: var(--color-surface-secondary); color: var(--color-text-secondary); border-radius: 999px;"
        >
          Mark all read
        </button>
      </div>
    </div>

    <!-- Empty state -->
    <div
      v-if="notifications.length === 0"
      class="flex-1 flex flex-col items-center justify-center gap-3"
    >
      <div class="i-carbon-notification-off text-5xl" style="color: var(--color-text-tertiary);"></div>
      <p class="text-base font-medium" style="color: var(--color-text-secondary);">No notifications yet</p>
      <p class="text-sm" style="color: var(--color-text-tertiary);">Updates to your assigned works will appear here.</p>
    </div>

    <!-- Floating canvas -->
    <div
      v-else
      ref="canvasRef"
      class="flex-1 relative overflow-y-auto"
      :style="{ minHeight: canvasHeight + 'px' }"
    >
      <div
        v-for="col in columns"
        :key="col.type"
        class="absolute flex flex-col border overflow-hidden"
        :style="{
          left:         (positions[col.type]?.x ?? 16) + 'px',
          top:          (positions[col.type]?.y ?? 16) + 'px',
          width:        (sizes[col.type]?.w ?? 280) + 'px',
          height:       (sizes[col.type]?.h ?? 320) + 'px',
          zIndex:       zIndexMap[col.type] ?? 100,
          borderColor:  col.cfg.border,
          background:   'var(--color-surface)',
          borderRadius: CARD_RADIUS,
          boxShadow:    '0 2px 16px rgba(0,0,0,0.07), 0 1px 3px rgba(0,0,0,0.05)',
        }"
        @pointerdown.stop="bringToFront(col.type)"
      >
        <!-- Drag header -->
        <div
          class="flex items-center justify-between px-3 py-2 border-b flex-shrink-0 select-none"
          :style="{
            background:  col.cfg.bg,
            borderColor: col.cfg.border,
            cursor:      dragging?.type === col.type ? 'grabbing' : 'grab',
          }"
          @pointerdown="onDragDown($event, col.type)"
        >
          <div class="flex items-center gap-2">
            <div class="flex flex-col gap-0.5 opacity-40">
              <div v-for="_ in 3" :key="_" class="flex gap-0.5">
                <span class="w-1 h-1 rounded-full" :style="{ background: col.cfg.dot }"></span>
                <span class="w-1 h-1 rounded-full" :style="{ background: col.cfg.dot }"></span>
              </div>
            </div>
            <span class="w-2 h-2 rounded-full" :style="{ background: col.cfg.dot }"></span>
            <span class="text-xs font-bold" :style="{ color: col.cfg.text }">{{ col.cfg.label }}</span>
          </div>
          <div class="flex items-center gap-1.5">
            <span
              v-if="col.unread > 0"
              class="text-xs font-bold px-1.5 py-0.5 rounded-full"
              :style="{ background: col.cfg.dot, color: '#fff' }"
            >{{ col.unread }}</span>
            <span class="text-xs" :style="{ color: col.cfg.text, opacity: '0.6' }">{{ col.items.length }}</span>
          </div>
        </div>

        <!-- Scrollable body -->
        <div class="flex-1 overflow-y-auto min-h-0">
          <div
            v-if="col.items.length === 0"
            class="h-full flex items-center justify-center text-xs"
            style="color: var(--color-text-tertiary);"
          >
            No entries
          </div>
          <div v-else class="flex flex-col">
            <div
              v-for="(n, idx) in col.items"
              :key="n.id"
              @click="handleClick(n)"
              class="px-3 py-2.5 relative transition-opacity"
              :class="{ 'cursor-pointer hover:opacity-80': !isDragging }"
              :style="{
                background: n.is_read ? 'var(--color-surface)' : col.cfg.bg,
                opacity:    n.is_read ? '0.65' : '1',
                borderTop:  idx > 0 ? '1px solid var(--color-separator)' : 'none',
              }"
            >
              <div v-if="!n.is_read" class="absolute left-0 top-0 bottom-0 w-0.5 rounded-r" :style="{ background: col.cfg.dot }"></div>
              <div class="flex items-start justify-between gap-2">
                <p class="text-xs font-semibold leading-snug flex-1 min-w-0" style="color: var(--color-text-primary);">{{ n.title }}</p>
                <span v-if="!n.is_read" class="w-1.5 h-1.5 rounded-full shrink-0 mt-0.5" :style="{ background: col.cfg.dot }"></span>
              </div>
              <p v-if="n.body" class="text-xs mt-0.5 line-clamp-2" style="color: var(--color-text-secondary);">{{ n.body }}</p>
              <div class="flex items-center gap-2 mt-1 flex-wrap">
                <span v-if="n.loa_number" class="text-xs font-mono" style="color: var(--color-text-tertiary);">{{ n.loa_number }}</span>
                <span v-if="n.sr_number"  class="text-xs"            style="color: var(--color-text-tertiary);">· {{ n.sr_number }}</span>
                <span class="text-xs ml-auto" style="color: var(--color-text-tertiary);">{{ relativeTime(n.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Resize handle -->
        <div
          class="absolute bottom-0 right-0 w-5 h-5 flex items-end justify-end pb-1 pr-1"
          style="cursor: se-resize;"
          @pointerdown="onResizeDown($event, col.type)"
        >
          <svg width="10" height="10" viewBox="0 0 10 10">
            <circle cx="9" cy="9" r="1.5" :fill="col.cfg.dot" opacity="0.4"/>
            <circle cx="5" cy="9" r="1.5" :fill="col.cfg.dot" opacity="0.4"/>
            <circle cx="9" cy="5" r="1.5" :fill="col.cfg.dot" opacity="0.4"/>
          </svg>
        </div>
      </div>
    </div>

  </div>
</template>
