import { ref } from 'vue'

const notifications = ref([])
const unreadCount   = ref(0)
let _pollInterval   = null

export const NOTIF_CONFIG = {
  new_sr:         { label: 'Site Register',           dot: '#0D9488', bg: '#F0FDFA', border: '#99F6E4', text: '#0F766E' },
  ss_entry:       { label: 'Supply',                  dot: '#16A34A', bg: '#F0FDF4', border: '#86EFAC', text: '#15803D' },
  si_entry:       { label: 'Supply and Installation', dot: '#D97706', bg: '#FFFBEB', border: '#FDE68A', text: '#B45309' },
  ee_entry:       { label: 'Execution',               dot: '#7C3AED', bg: '#F5F3FF', border: '#C4B5FD', text: '#6D28D9' },
  financial:      { label: 'Financial',               dot: '#EA580C', bg: '#FFF7ED', border: '#FED7AA', text: '#C2410C' },
  loa_unassigned: { label: 'LOA Unassigned',          dot: '#DC2626', bg: '#FEF2F2', border: '#FECACA', text: '#B91C1C' },
}

export function notifConfig(type) {
  return NOTIF_CONFIG[type] || { label: type, dot: '#6B7280', bg: '#F9FAFB', border: '#E5E7EB', text: '#374151' }
}

async function fetchNotifications() {
  try {
    const res = await fetch('/api/notifications/', { credentials: 'include' })
    if (!res.ok) return
    const data = await res.json()
    notifications.value = data.notifications || []
    unreadCount.value   = data.unread_count  || 0
  } catch (_) { /* network error - silently ignore */ }
}

async function markRead(id) {
  try {
    await fetch(`/api/notifications/${id}/read/`, {
      method: 'POST', credentials: 'include',
      headers: { 'X-CSRFToken': getCsrf() },
    })
    const n = notifications.value.find(x => x.id === id)
    if (n) {
      n.is_read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    }
  } catch (_) { /* ignore */ }
}

async function markAllRead() {
  try {
    await fetch('/api/notifications/', {
      method: 'POST', credentials: 'include',
      headers: { 'X-CSRFToken': getCsrf() },
    })
    notifications.value.forEach(n => { n.is_read = true })
    unreadCount.value = 0
  } catch (_) { /* ignore */ }
}

function startPolling(interval = 30000) {
  fetchNotifications()
  _pollInterval = setInterval(fetchNotifications, interval)
}

function stopPolling() {
  if (_pollInterval) { clearInterval(_pollInterval); _pollInterval = null }
}

function getCsrf() {
  return document.cookie.split('; ').find(r => r.startsWith('csrftoken='))?.split('=')[1] || ''
}

export function useNotifications() {
  return { notifications, unreadCount, fetchNotifications, markRead, markAllRead, startPolling, stopPolling }
}
