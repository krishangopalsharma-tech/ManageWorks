import { reactive, readonly } from 'vue'
import axios from 'axios'

const API = 'http://localhost:8000/api/auth'

axios.defaults.withCredentials = true

function getCsrfToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/)
  return match ? match[1] : ''
}

function authHeaders() {
  return { 'X-CSRFToken': getCsrfToken() }
}

const state = reactive({
  user:          null,
  authenticated: false,
  loading:       true,
})

async function fetchMe() {
  try {
    const { data } = await axios.get(`${API}/me/`)
    if (data.authenticated) {
      state.user          = data
      state.authenticated = true
    } else {
      state.user          = null
      state.authenticated = false
    }
  } catch {
    state.user          = null
    state.authenticated = false
  } finally {
    state.loading = false
  }
}

async function login(hrms_id, password) {
  const { data } = await axios.post(`${API}/login/`, { hrms_id, password }, { headers: authHeaders() })
  state.user          = data
  state.authenticated = true
  return data
}

async function register(payload) {
  const { data } = await axios.post(`${API}/register/`, payload, { headers: authHeaders() })
  return data
}

async function logout() {
  await axios.post(`${API}/logout/`, {}, { headers: authHeaders() })
  state.user          = null
  state.authenticated = false
}

export function useAuth() {
  return {
    state: readonly(state),
    fetchMe,
    login,
    register,
    logout,
  }
}
