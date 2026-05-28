<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import { useNotifications, notifConfig } from '../composables/useNotifications'

const router = useRouter()
const { state: authState } = useAuth()
const { notifications, unreadCount, fetchNotifications, markRead, markAllRead } = useNotifications()

onMounted(fetchNotifications)

const isAdmin = computed(() => authState.user?.is_staff || authState.user?.role === 'admin')

const TYPE_ORDER = ['new_sr', 'ss_entry', 'si_entry', 'ee_entry', 'financial', 'loa_unassigned']

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

function relativeTime(isoString) {
  const diff = Date.now() - new Date(isoString).getTime()
  const mins  = Math.floor(diff / 60000)
  if (mins < 1)   return 'just now'
  if (mins < 60)  return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24)   return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 7)   return `${days}d ago`
  return new Date(isoString).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

async function handleClick(n) {
  if (!n.is_read) await markRead(n.id)
  if (n.notif_type === 'new_sr') router.push('/site-register')
  else if (n.notif_type === 'financial') router.push('/mb-details')
  else router.push('/item-progress')
}
</script>

<template>
  <div class="min-h-screen p-4 md:p-6" style="background: var(--color-background);">
    <!-- Header -->
    <div class="flex items-center justify-between mb-5">
      <div>
        <h1 class="text-2xl font-bold" style="color: var(--color-text-primary);">Notifications</h1>
        <p class="text-sm mt-0.5" style="color: var(--color-text-secondary);">
          {{ unreadCount > 0 ? `${unreadCount} unread` : 'All caught up' }}
        </p>
      </div>
      <button
        v-if="unreadCount > 0"
        @click="markAllRead"
        class="px-4 py-2 rounded-xl text-sm font-semibold transition-all"
        style="background: var(--color-surface-secondary); color: var(--color-text-secondary);"
      >
        Mark all read
      </button>
    </div>

    <!-- Empty state -->
    <div
      v-if="notifications.length === 0"
      class="flex flex-col items-center justify-center py-24 gap-3"
    >
      <div class="i-carbon-notification-off text-5xl" style="color: var(--color-text-tertiary);"></div>
      <p class="text-base font-medium" style="color: var(--color-text-secondary);">No notifications yet</p>
      <p class="text-sm" style="color: var(--color-text-tertiary);">Updates to your assigned works will appear here.</p>
    </div>

    <!-- Multi-column grid -->
    <div
      v-else
      class="grid gap-4"
      style="grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); align-items: start;"
    >
      <div
        v-for="col in columns"
        :key="col.type"
        class="rounded-2xl overflow-hidden border"
        :style="{ borderColor: col.cfg.border, background: 'var(--color-surface)' }"
      >
        <!-- Column header -->
        <div
          class="flex items-center justify-between px-4 py-3 border-b"
          :style="{ background: col.cfg.bg, borderColor: col.cfg.border }"
        >
          <div class="flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full shrink-0" :style="{ background: col.cfg.dot }"></span>
            <span class="text-sm font-bold" :style="{ color: col.cfg.text }">{{ col.cfg.label }}</span>
          </div>
          <div class="flex items-center gap-2">
            <span
              v-if="col.unread > 0"
              class="text-xs font-bold px-1.5 py-0.5 rounded-full"
              :style="{ background: col.cfg.dot, color: '#fff' }"
            >{{ col.unread }}</span>
            <span
              class="text-xs"
              :style="{ color: col.cfg.text, opacity: '0.7' }"
            >{{ col.items.length }} total</span>
          </div>
        </div>

        <!-- No items for admin empty column -->
        <div
          v-if="col.items.length === 0"
          class="px-4 py-6 text-center text-xs"
          style="color: var(--color-text-tertiary);"
        >
          No entries
        </div>

        <!-- Cards -->
        <div v-else class="flex flex-col">
          <div
            v-for="(n, idx) in col.items"
            :key="n.id"
            @click="handleClick(n)"
            class="px-4 py-3 cursor-pointer transition-colors hover:opacity-90 relative"
            :style="{
              background: n.is_read ? 'var(--color-surface)' : col.cfg.bg,
              opacity: n.is_read ? '0.7' : '1',
              borderTop: idx > 0 ? '1px solid var(--color-separator)' : 'none',
            }"
          >
            <!-- Unread indicator bar -->
            <div
              v-if="!n.is_read"
              class="absolute left-0 top-0 bottom-0 w-0.5 rounded-r"
              :style="{ background: col.cfg.dot }"
            ></div>

            <div class="flex items-start justify-between gap-2">
              <p class="text-xs font-semibold leading-tight flex-1 min-w-0" style="color: var(--color-text-primary);">
                {{ n.title }}
              </p>
              <span v-if="!n.is_read" class="w-1.5 h-1.5 rounded-full shrink-0 mt-0.5" :style="{ background: col.cfg.dot }"></span>
            </div>

            <p v-if="n.body" class="text-xs mt-0.5 line-clamp-2" style="color: var(--color-text-secondary);">
              {{ n.body }}
            </p>

            <div class="flex items-center gap-2 mt-1.5 flex-wrap">
              <span v-if="n.loa_number" class="text-xs font-mono" style="color: var(--color-text-tertiary);">{{ n.loa_number }}</span>
              <span v-if="n.sr_number" class="text-xs" style="color: var(--color-text-tertiary);">· {{ n.sr_number }}</span>
              <span class="text-xs ml-auto" style="color: var(--color-text-tertiary);">{{ relativeTime(n.created_at) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
