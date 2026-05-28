import { ref } from 'vue'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import Notifications from './Notifications.vue'

const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush
  })
}))

const mockAuthState = {
  user: { role: 'consignee', is_staff: false }
}
vi.mock('../composables/useAuth.js', () => ({
  useAuth: () => ({
    state: mockAuthState
  })
}))

const mockNotifications = ref([])
const mockUnreadCount = ref(0)
const mockFetch = vi.fn()
const mockMarkRead = vi.fn()
const mockMarkAllRead = vi.fn()

vi.mock('../composables/useNotifications.js', () => ({
  useNotifications: () => ({
    notifications: mockNotifications,
    unreadCount: mockUnreadCount,
    fetchNotifications: mockFetch,
    markRead: mockMarkRead,
    markAllRead: mockMarkAllRead
  }),
  notifConfig: (type) => ({
    label: type === 'new_sr' ? 'Site Register' : 'Other',
    dot: '#fff',
    bg: '#fff',
    border: '#fff',
    text: '#000'
  })
}))

describe('Notifications.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockNotifications.value = []
    mockUnreadCount.value = 0
    mockAuthState.user = { role: 'consignee', is_staff: false }
  })

  it('renders empty state when there are no notifications', () => {
    const wrapper = mount(Notifications)
    expect(wrapper.text()).toContain('No notifications yet')
    expect(mockFetch).toHaveBeenCalledOnce()
  })

  it('renders only populated columns for non-admin consignee', () => {
    mockNotifications.value = [
      { id: 1, notif_type: 'new_sr', title: 'New Thread', is_read: false, created_at: new Date().toISOString() }
    ]
    mockUnreadCount.value = 1

    const wrapper = mount(Notifications)
    
    // Renders the notifications, not empty state
    expect(wrapper.text()).not.toContain('No notifications yet')
    expect(wrapper.text()).toContain('New Thread')
    
    // It should render only 1 column (Site Register) because others are empty and user is not admin
    expect(wrapper.findAll('.overflow-hidden').length).toBe(1)
  })

  it('renders all columns for admin even if some are empty', () => {
    mockAuthState.user = { role: 'admin', is_staff: true }
    mockNotifications.value = [
      { id: 1, notif_type: 'new_sr', title: 'New Thread', is_read: false, created_at: new Date().toISOString() }
    ]
    mockUnreadCount.value = 1

    const wrapper = mount(Notifications)
    expect(wrapper.findAll('.overflow-hidden').length).toBe(6)
  })

  it('renders correct unread badge count', () => {
    mockNotifications.value = [
      { id: 1, notif_type: 'new_sr', title: 'Notif 1', is_read: false, created_at: new Date().toISOString() },
      { id: 2, notif_type: 'new_sr', title: 'Notif 2', is_read: false, created_at: new Date().toISOString() }
    ]
    mockUnreadCount.value = 2

    const wrapper = mount(Notifications)
    expect(wrapper.text()).toContain('2') // Badge count
  })

  it('calls markRead and routes to correct view when clicking notification', async () => {
    const notif = { id: 10, notif_type: 'new_sr', title: 'New SR Notif', is_read: false, created_at: new Date().toISOString() }
    mockNotifications.value = [notif]
    mockUnreadCount.value = 1

    const wrapper = mount(Notifications)
    
    // Find the card and click it
    const card = wrapper.find('.cursor-pointer')
    await card.trigger('click')

    expect(mockMarkRead).toHaveBeenCalledWith(10)
    expect(mockPush).toHaveBeenCalledWith('/site-register')
  })

  it('routes to financial page when clicking financial notification', async () => {
    const notif = { id: 11, notif_type: 'financial', title: 'New Finance Notif', is_read: true, created_at: new Date().toISOString() }
    mockNotifications.value = [notif]

    const wrapper = mount(Notifications)
    const card = wrapper.find('.cursor-pointer')
    await card.trigger('click')

    // Already read, so markRead shouldn't be called
    expect(mockMarkRead).not.toHaveBeenCalled()
    expect(mockPush).toHaveBeenCalledWith('/mb-details')
  })

  it('renders Mark all read button only when unreadCount > 0', async () => {
    mockNotifications.value = [{ id: 1, notif_type: 'new_sr', title: 'N', is_read: false }]
    mockUnreadCount.value = 1

    let wrapper = mount(Notifications)
    const markAllBtn = () => wrapper.findAll('button').find(b => b.text().includes('Mark all read'))
    expect(markAllBtn()).toBeTruthy()

    mockUnreadCount.value = 0
    wrapper = mount(Notifications)
    expect(wrapper.findAll('button').find(b => b.text().includes('Mark all read'))).toBeFalsy()
  })
})
