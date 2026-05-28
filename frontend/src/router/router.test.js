import { describe, it, expect, vi, beforeEach } from 'vitest'
import router from './index.js'

// Setup global mock for useAuth
const mockState = {
  authenticated: false,
  user: null,
  loading: false
}
const mockFetchMe = vi.fn()

vi.mock('../composables/useAuth.js', () => {
  return {
    useAuth: () => ({
      state: mockState,
      fetchMe: mockFetchMe
    })
  }
})

describe('Vue Router Guards', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset mockState properties
    mockState.authenticated = false
    mockState.user = null
  })

  it('redirects unauthenticated user visiting protected route to /login', async () => {
    mockState.authenticated = false
    await router.push('/')
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('redirects authenticated user visiting /login to /', async () => {
    mockState.authenticated = true
    mockState.user = { username: 'consignee1', role: 'consignee' }
    
    // Push to a non-login route first to trigger transition
    await router.push('/')
    await router.push('/login')
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('blocks non-admin from visiting adminOnly routes and redirects to /', async () => {
    mockState.authenticated = true
    mockState.user = { username: 'consignee1', role: 'consignee' }

    await router.push('/')
    await router.push('/settings/user-management')
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('allows admin to visit adminOnly routes', async () => {
    mockState.authenticated = true
    mockState.user = { username: 'admin1', role: 'admin' }

    await router.push('/')
    await router.push('/settings/user-management')
    expect(router.currentRoute.value.path).toBe('/settings/user-management')
  })

  it('allows consignee to visit site-register', async () => {
    mockState.authenticated = true
    mockState.user = { username: 'consignee1', role: 'consignee' }

    await router.push('/')
    await router.push('/site-register')
    expect(router.currentRoute.value.path).toBe('/site-register')
  })

  it('blocks other roles (e.g., observer) from site-register', async () => {
    mockState.authenticated = true
    mockState.user = { username: 'observer1', role: 'observer' }

    await router.push('/')
    await router.push('/site-register')
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('allows anyone to visit public routes', async () => {
    mockState.authenticated = false
    await router.push('/forgot-password')
    expect(router.currentRoute.value.path).toBe('/forgot-password')
  })
})
