import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useNotifications, notifConfig } from './useNotifications'

describe('useNotifications Composable', () => {
  const { notifications, unreadCount, fetchNotifications, markRead, markAllRead, startPolling, stopPolling } = useNotifications()

  beforeEach(() => {
    notifications.value = []
    unreadCount.value = 0
    // Mock document.cookie
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: 'csrftoken=testcsrftoken'
    })
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
    stopPolling()
  })

  it('fetchNotifications sets notifications and unreadCount state on success', async () => {
    const mockData = {
      notifications: [
        { id: 1, notif_type: 'new_sr', title: 'SR 1', is_read: false },
        { id: 2, notif_type: 'financial', title: 'MB 1', is_read: true }
      ],
      unread_count: 1
    }

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData
    })
    vi.stubGlobal('fetch', mockFetch)

    await fetchNotifications()

    expect(mockFetch).toHaveBeenCalledWith('/api/notifications/', expect.any(Object))
    expect(notifications.value).toEqual(mockData.notifications)
    expect(unreadCount.value).toBe(1)
  })

  it('fetchNotifications handles network error gracefully', async () => {
    const mockFetch = vi.fn().mockRejectedValue(new Error('Network Error'))
    vi.stubGlobal('fetch', mockFetch)

    // Set some initial state
    notifications.value = [{ id: 1 }]
    unreadCount.value = 5

    await fetchNotifications()

    // State remains unchanged
    expect(notifications.value).toEqual([{ id: 1 }])
    expect(unreadCount.value).toBe(5)
  })

  it('markRead updates local notification state and decrements unreadCount', async () => {
    notifications.value = [
      { id: 1, is_read: false },
      { id: 2, is_read: false }
    ]
    unreadCount.value = 2

    const mockFetch = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', mockFetch)

    await markRead(1)

    expect(mockFetch).toHaveBeenCalledWith('/api/notifications/1/read/', expect.objectContaining({
      method: 'POST',
      headers: { 'X-CSRFToken': 'testcsrftoken' }
    }))
    expect(notifications.value[0].is_read).toBe(true)
    expect(notifications.value[1].is_read).toBe(false)
    expect(unreadCount.value).toBe(1)
  })

  it('markAllRead marks all notifications as read and sets unreadCount to 0', async () => {
    notifications.value = [
      { id: 1, is_read: false },
      { id: 2, is_read: false }
    ]
    unreadCount.value = 2

    const mockFetch = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', mockFetch)

    await markAllRead()

    expect(mockFetch).toHaveBeenCalledWith('/api/notifications/', expect.objectContaining({
      method: 'POST'
    }))
    expect(notifications.value[0].is_read).toBe(true)
    expect(notifications.value[1].is_read).toBe(true)
    expect(unreadCount.value).toBe(0)
  })

  it('notifConfig returns styles for known and unknown types', () => {
    const srConfig = notifConfig('new_sr')
    expect(srConfig.label).toBe('Site Register')
    expect(srConfig.dot).toBe('#0D9488')

    const unknownConfig = notifConfig('unknown_type')
    expect(unknownConfig.label).toBe('unknown_type')
    expect(unknownConfig.dot).toBe('#6B7280')
  })

  it('polling starts, calls fetch, and stops correctly', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ notifications: [], unread_count: 0 })
    })
    vi.stubGlobal('fetch', mockFetch)

    startPolling(1000)
    expect(mockFetch).toHaveBeenCalledTimes(1)

    // Advance timer by 1s
    await vi.advanceTimersByTimeAsync(1000)
    expect(mockFetch).toHaveBeenCalledTimes(2)

    stopPolling()
    await vi.advanceTimersByTimeAsync(1000)
    expect(mockFetch).toHaveBeenCalledTimes(2) // No further calls
  })
})
