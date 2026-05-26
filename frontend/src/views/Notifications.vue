<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useNotifications, notifConfig, NOTIF_CONFIG } from '../composables/useNotifications'

const router = useRouter()
const { notifications, unreadCount, fetchNotifications, markRead, markAllRead } = useNotifications()

onMounted(fetchNotifications)

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

function dateLabel(isoString) {
  const d = new Date(isoString)
  const today = new Date()
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1)
  if (d.toDateString() === today.toDateString())     return 'Today'
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })
}

const grouped = computed(() => {
  const groups = []
  let currentLabel = null
  for (const n of notifications.value) {
    const label = dateLabel(n.created_at)
    if (label !== currentLabel) {
      groups.push({ label, items: [] })
      currentLabel = label
    }
    groups[groups.length - 1].items.push(n)
  }
  return groups
})

async function handleClick(n) {
  if (!n.is_read) await markRead(n.id)
  if (n.thread_id) router.push('/site-register')
}

function navDest(type) {
  if (type === 'new_sr') return '/site-register'
  if (type === 'financial') return '/mb-details'
  return '/item-progress'
}
</script>

<template>
  <div class="min-h-screen p-6" style="background: var(--color-background);">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
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

    <!-- Type legend -->
    <div class="flex flex-wrap gap-2 mb-6">
      <span
        v-for="(cfg, key) in NOTIF_CONFIG"
        :key="key"
        class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border"
        :style="{ background: cfg.bg, borderColor: cfg.border, color: cfg.text }"
      >
        <span class="w-2 h-2 rounded-full inline-block" :style="{ background: cfg.dot }"></span>
        {{ cfg.label }}
      </span>
    </div>

    <!-- Empty state -->
    <div
      v-if="notifications.length === 0"
      class="flex flex-col items-center justify-center py-24 gap-3"
    >
      <div class="i-carbon-notification-off text-5xl" style="color: var(--color-text-tertiary);"></div>
      <p class="text-base font-medium" style="color: var(--color-text-secondary);">No notifications yet</p>
      <p class="text-sm" style="color: var(--color-text-tertiary);">You'll be notified when site register entries or updates are made.</p>
    </div>

    <!-- Grouped list -->
    <div v-else class="flex flex-col gap-6">
      <div v-for="group in grouped" :key="group.label">
        <!-- Date heading -->
        <p class="text-xs font-semibold uppercase tracking-widest mb-2" style="color: var(--color-text-tertiary);">
          {{ group.label }}
        </p>

        <div class="flex flex-col gap-2">
          <div
            v-for="n in group.items"
            :key="n.id"
            @click="handleClick(n)"
            class="flex items-start gap-3 p-4 rounded-2xl border cursor-pointer transition-all hover:shadow-sm"
            :style="{
              background: n.is_read ? 'var(--color-surface)' : notifConfig(n.notif_type).bg,
              borderColor: n.is_read ? 'var(--color-separator)' : notifConfig(n.notif_type).border,
              opacity: n.is_read ? '0.75' : '1',
            }"
          >
            <!-- Color dot -->
            <span
              class="w-2.5 h-2.5 rounded-full mt-1.5 shrink-0"
              :style="{ background: notifConfig(n.notif_type).dot }"
            ></span>

            <!-- Content -->
            <div class="flex-1 min-w-0">
              <div class="flex items-start justify-between gap-2">
                <div class="flex items-center gap-2 flex-wrap">
                  <span
                    class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border"
                    :style="{
                      background: notifConfig(n.notif_type).bg,
                      borderColor: notifConfig(n.notif_type).border,
                      color: notifConfig(n.notif_type).text,
                    }"
                  >{{ notifConfig(n.notif_type).label }}</span>
                  <span v-if="n.sr_number" class="text-xs font-mono" style="color: var(--color-text-tertiary);">{{ n.sr_number }}</span>
                  <span v-if="n.loa_number" class="text-xs" style="color: var(--color-text-tertiary);">{{ n.loa_number }}</span>
                </div>
                <div class="flex items-center gap-2 shrink-0">
                  <span class="text-xs whitespace-nowrap" style="color: var(--color-text-tertiary);">{{ relativeTime(n.created_at) }}</span>
                  <span v-if="!n.is_read" class="w-2 h-2 rounded-full bg-blue-500 shrink-0"></span>
                </div>
              </div>
              <p class="text-sm font-semibold mt-1" style="color: var(--color-text-primary);">{{ n.title }}</p>
              <p v-if="n.body" class="text-sm mt-0.5 truncate" style="color: var(--color-text-secondary);">{{ n.body }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
