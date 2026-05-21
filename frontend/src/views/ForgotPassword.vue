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
  <div class="min-h-screen w-full bg-light-bg dark:bg-gray-900 flex items-center justify-center p-6">
    <div class="w-full max-w-md">
      <!-- Logo -->
      <div class="flex items-center gap-3 mb-10 justify-center">
        <div class="i-carbon-flash text-3xl text-[#1D5F5E]"></div>
        <span class="text-2xl font-bold text-gray-800 dark:text-white tracking-tight">ManageWorks</span>
      </div>

      <!-- Success state -->
      <div v-if="success" class="bg-light-surface dark:bg-[#1c1c1e] rounded-2xl soft-shadow p-8 text-center border border-gray-100 dark:border-[#3a3a3c]">
        <div class="w-14 h-14 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mx-auto mb-4">
          <div class="i-carbon-email text-2xl text-green-600 dark:text-green-400"></div>
        </div>
        <h2 class="text-lg font-bold text-gray-800 dark:text-white mb-2">Check Your Email</h2>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-6">
          If that HRMS ID is registered, your password has been sent to the associated email address.
        </p>
        <router-link
          to="/login"
          class="inline-block px-6 py-2.5 rounded-xl bg-[#1D5F5E] text-white text-sm font-semibold hover:bg-[#174E4D] transition-colors"
        >
          Back to Login
        </router-link>
      </div>

      <!-- Form card -->
      <div v-else class="bg-light-surface dark:bg-[#1c1c1e] rounded-2xl soft-shadow p-8 border border-gray-100 dark:border-[#3a3a3c]">
        <h1 class="text-xl font-bold text-gray-800 dark:text-white mb-1">Forgot Password</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-8">Enter your HRMS ID and we'll send your password to your registered email.</p>

        <form @submit.prevent="handleSubmit" class="flex flex-col gap-5">
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide">HRMS ID</label>
            <input
              v-model="hrms_id"
              type="text"
              autocomplete="username"
              placeholder="Enter your HRMS ID"
              required
              class="w-full px-4 py-3 rounded-xl bg-light-bg dark:bg-[#2c2c2e] border border-gray-200 dark:border-[#3a3a3c] text-sm text-gray-800 dark:text-white placeholder-gray-400 focus:outline-none focus:border-[#1D5F5E] focus:ring-2 focus:ring-[#1D5F5E]/10 transition-colors"
            />
          </div>

          <div v-if="error" class="flex items-center gap-2 px-4 py-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl text-sm text-red-600 dark:text-red-400">
            <div class="i-carbon-warning-filled text-base shrink-0"></div>
            {{ error }}
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="w-full py-3 rounded-xl bg-[#1D5F5E] text-white text-sm font-semibold tracking-wide hover:bg-[#174E4D] transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-1"
          >
            <span v-if="loading" class="flex items-center justify-center gap-2">
              <div class="i-carbon-circle-dash animate-spin text-base"></div>
              Sending…
            </span>
            <span v-else>Send Password</span>
          </button>
        </form>

        <div class="mt-6 pt-6 border-t border-gray-200 dark:border-[#3a3a3c] text-center">
          <p class="text-sm text-gray-500 dark:text-gray-400">
            <router-link to="/login" class="font-semibold text-[#1D5F5E] hover:underline">Back to Login</router-link>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
