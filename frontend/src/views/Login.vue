<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
const { login } = useAuth()

const hrms_id  = ref('')
const password = ref('')
const error    = ref('')
const loading  = ref(false)

async function handleLogin() {
  error.value   = ''
  loading.value = true
  try {
    await login(hrms_id.value.trim(), password.value)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.error || 'Login failed.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen w-full bg-light-bg flex items-center justify-center p-6">
    <div class="w-full max-w-md">
      <!-- Logo -->
      <div class="flex items-center gap-3 mb-10 justify-center">
        <div class="i-carbon-flash text-3xl text-dark-active"></div>
        <span class="text-2xl font-bold text-gray-800 tracking-tight">ManageWorks</span>
      </div>

      <!-- Card -->
      <div class="bg-light-surface rounded-2xl soft-shadow p-8">
        <h1 class="text-xl font-bold text-gray-800 mb-1">Welcome back</h1>
        <p class="text-sm text-gray-500 mb-8">Sign in with your HRMS ID</p>

        <form @submit.prevent="handleLogin" class="flex flex-col gap-5">
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-gray-600 uppercase tracking-wide">HRMS ID</label>
            <input
              v-model="hrms_id"
              type="text"
              autocomplete="username"
              placeholder="Enter your HRMS ID"
              required
              class="w-full px-4 py-3 rounded-xl bg-light-bg border border-gray-200 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:border-gray-400 transition-colors"
            />
          </div>

          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-gray-600 uppercase tracking-wide">Password</label>
            <input
              v-model="password"
              type="password"
              autocomplete="current-password"
              placeholder="Enter your password"
              required
              class="w-full px-4 py-3 rounded-xl bg-light-bg border border-gray-200 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:border-gray-400 transition-colors"
            />
          </div>

          <div v-if="error" class="flex items-center gap-2 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600">
            <div class="i-carbon-warning-filled text-base shrink-0"></div>
            {{ error }}
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="w-full py-3 rounded-xl bg-gray-800 text-white text-sm font-semibold tracking-wide hover:bg-gray-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-1"
          >
            <span v-if="loading" class="flex items-center justify-center gap-2">
              <div class="i-carbon-circle-dash animate-spin text-base"></div>
              Signing in…
            </span>
            <span v-else>Sign In</span>
          </button>
        </form>

        <div class="mt-6 pt-6 border-t border-gray-200 text-center">
          <p class="text-sm text-gray-500">
            New user?
            <router-link to="/register" class="font-semibold text-gray-800 hover:underline">Request access</router-link>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
