<script setup>
import { ref } from 'vue'
import { useAuth } from '../composables/useAuth'

const { forgotPassword } = useAuth()

const hrms_id = ref('')
const error   = ref('')
const success = ref(false)
const loading = ref(false)

async function handleSubmit() {
  error.value   = ''
  success.value = false
  loading.value = true
  try {
    await forgotPassword(hrms_id.value.trim())
    success.value = true
    hrms_id.value = ''
  } catch (e) {
    error.value = e.response?.data?.error || 'Something went wrong.'
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

      <!-- Success state -->
      <div v-if="success" class="bg-light-surface rounded-2xl soft-shadow p-8 text-center">
        <div class="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
          <div class="i-carbon-email text-2xl text-green-600"></div>
        </div>
        <h2 class="text-lg font-bold text-gray-800 mb-2">Check Your Email</h2>
        <p class="text-sm text-gray-500 mb-6">
          If that HRMS ID is registered, your password has been sent to the associated email address.
        </p>
        <router-link
          to="/login"
          class="inline-block px-6 py-2.5 rounded-xl bg-gray-800 text-white text-sm font-semibold hover:bg-gray-700 transition-colors"
        >
          Back to Login
        </router-link>
      </div>

      <!-- Form card -->
      <div v-else class="bg-light-surface rounded-2xl soft-shadow p-8">
        <h1 class="text-xl font-bold text-gray-800 mb-1">Forgot Password</h1>
        <p class="text-sm text-gray-500 mb-8">Enter your HRMS ID and we'll send your password to your registered email.</p>

        <form @submit.prevent="handleSubmit" class="flex flex-col gap-5">
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
              Sending…
            </span>
            <span v-else>Send Password</span>
          </button>
        </form>

        <div class="mt-6 pt-6 border-t border-gray-200 text-center">
          <p class="text-sm text-gray-500">
            <router-link to="/login" class="font-semibold text-gray-800 hover:underline">Back to Login</router-link>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
