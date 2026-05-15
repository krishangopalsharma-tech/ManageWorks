<script setup>
import { ref } from 'vue'
import { useAuth } from '../composables/useAuth'

const { register } = useAuth()

const form = ref({
  name:        '',
  designation: '',
  hrms_id:     '',
  pf_number:   '',
  email:       '',
  password:    '',
  confirm:     '',
})

const error   = ref('')
const success = ref(false)
const loading = ref(false)

async function handleRegister() {
  error.value   = ''
  success.value = false

  if (form.value.password !== form.value.confirm) {
    error.value = 'Passwords do not match.'
    return
  }
  if (form.value.password.length < 8) {
    error.value = 'Password must be at least 8 characters.'
    return
  }

  loading.value = true
  try {
    await register({
      name:        form.value.name.trim(),
      designation: form.value.designation.trim(),
      hrms_id:     form.value.hrms_id.trim(),
      pf_number:   form.value.pf_number.trim(),
      email:       form.value.email.trim(),
      password:    form.value.password,
    })
    success.value = true
    form.value = { name: '', designation: '', hrms_id: '', pf_number: '', email: '', password: '', confirm: '' }
  } catch (e) {
    error.value = e.response?.data?.error || 'Registration failed.'
  } finally {
    loading.value = false
  }
}

const fields = [
  { key: 'name',        label: 'Full Name',       type: 'text',     placeholder: 'Enter your full name',    autocomplete: 'name' },
  { key: 'designation', label: 'Designation',     type: 'text',     placeholder: 'e.g. Junior Engineer',    autocomplete: 'organization-title' },
  { key: 'hrms_id',     label: 'HRMS ID',         type: 'text',     placeholder: 'Your HRMS ID (username)', autocomplete: 'username' },
  { key: 'pf_number',   label: 'PF Number',       type: 'text',     placeholder: 'Enter your PF number',    autocomplete: 'off' },
  { key: 'email',       label: 'Email Address',   type: 'email',    placeholder: 'your@email.com',          autocomplete: 'email' },
  { key: 'password',    label: 'Password',        type: 'password', placeholder: 'Min 8 characters',        autocomplete: 'new-password' },
  { key: 'confirm',     label: 'Confirm Password',type: 'password', placeholder: 'Re-enter password',       autocomplete: 'new-password' },
]
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
          <div class="i-carbon-checkmark text-2xl text-green-600"></div>
        </div>
        <h2 class="text-lg font-bold text-gray-800 mb-2">Registration Submitted</h2>
        <p class="text-sm text-gray-500 mb-6">Your request is pending admin approval. You will be able to log in once approved.</p>
        <router-link to="/login" class="inline-block px-6 py-2.5 rounded-xl bg-gray-800 text-white text-sm font-semibold hover:bg-gray-700 transition-colors">
          Back to Login
        </router-link>
      </div>

      <!-- Form card -->
      <div v-else class="bg-light-surface rounded-2xl soft-shadow p-8">
        <h1 class="text-xl font-bold text-gray-800 mb-1">Request Access</h1>
        <p class="text-sm text-gray-500 mb-8">Fill in your details. Admin will approve your account.</p>

        <form @submit.prevent="handleRegister" class="flex flex-col gap-5">
          <div v-for="f in fields" :key="f.key" class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-gray-600 uppercase tracking-wide">{{ f.label }}</label>
            <input
              v-model="form[f.key]"
              :type="f.type"
              :placeholder="f.placeholder"
              :autocomplete="f.autocomplete"
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
              Submitting…
            </span>
            <span v-else>Submit Registration</span>
          </button>
        </form>

        <div class="mt-6 pt-6 border-t border-gray-200 text-center">
          <p class="text-sm text-gray-500">
            Already have an account?
            <router-link to="/login" class="font-semibold text-gray-800 hover:underline">Sign in</router-link>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
