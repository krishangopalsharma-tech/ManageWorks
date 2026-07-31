<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { useAuth } from '../composables/useAuth'

const { updateProfile, changePassword } = useAuth()

const me    = ref(null)
const works = ref([])
const loading = ref(true)

const editing  = ref(false)
const saving   = ref(false)
const editForm = ref({ hrms_id: '', email: '', designation: '', mobile_number: '' })
const toast    = ref({ show: false, msg: '', type: 'success' })

// Password change
const changingPassword = ref(false)
const savingPassword   = ref(false)
const pwForm = ref({ current_password: '', new_password: '', confirm_password: '' })

function showToast(msg, type = 'success') {
  toast.value = { show: true, msg, type }
  setTimeout(() => { toast.value.show = false }, 3000)
}

async function load() {
  loading.value = true
  try {
    const [meRes, worksRes] = await Promise.all([
      axios.get('/api/auth/me/'),
      axios.get('/api/auth/my-works/'),
    ])
    me.value    = meRes.data
    works.value = worksRes.data
  } catch { /* ignore */ } finally {
    loading.value = false
  }
}

function startEdit() {
  editForm.value = {
    hrms_id:       me.value.hrms_id || '',
    email:         me.value.email || '',
    designation:   me.value.designation || '',
    mobile_number: me.value.mobile_number || '',
  }
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

async function saveProfile() {
  saving.value = true
  try {
    const data = await updateProfile(editForm.value)
    me.value = { ...me.value, ...data }
    editing.value = false
    showToast('Profile updated.')
  } catch (err) {
    showToast(err.response?.data?.error || 'Update failed.', 'error')
  } finally {
    saving.value = false
  }
}

function startChangePassword() {
  pwForm.value = { current_password: '', new_password: '', confirm_password: '' }
  changingPassword.value = true
}

function cancelChangePassword() {
  changingPassword.value = false
}

async function savePassword() {
  if (pwForm.value.new_password !== pwForm.value.confirm_password) {
    showToast('New passwords do not match.', 'error')
    return
  }
  savingPassword.value = true
  try {
    await changePassword(pwForm.value.current_password, pwForm.value.new_password)
    changingPassword.value = false
    showToast('Password changed.')
  } catch (err) {
    showToast(err.response?.data?.error || 'Password change failed.', 'error')
  } finally {
    savingPassword.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="h-full overflow-y-auto px-6 py-6">
    <div class="max-w-3xl">

      <div class="mb-6">
        <h1 class="text-xl font-bold text-gray-800 dark:text-white tracking-tight">My Account</h1>
        <p class="text-sm text-gray-500 mt-0.5">Your profile and assigned LOAs.</p>
      </div>

      <div v-if="loading" class="flex items-center gap-2 text-sm text-gray-400 mt-8">
        <div class="i-carbon-circle-dash animate-spin text-lg"></div> Loading…
      </div>

      <template v-else-if="me">

        <!-- Profile card -->
        <div class="bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] shadow-sm overflow-hidden mb-6">
          <div class="px-5 py-4 border-b border-gray-100 dark:border-[#2c2c2e] flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-[#1D5F5E]/10 flex items-center justify-center shrink-0">
              <span class="text-[#1D5F5E] text-xl font-bold">{{ (me.name || me.hrms_id || '?')[0].toUpperCase() }}</span>
            </div>
            <div class="min-w-0 flex-1">
              <p class="text-base font-bold text-gray-800 dark:text-white truncate">{{ me.name || '—' }}</p>
              <span class="text-xs font-semibold px-2 py-0.5 rounded-full capitalize"
                :class="me.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-amber-100 text-amber-700'">
                {{ me.role }}
              </span>
            </div>
            <button v-if="!editing" @click="startEdit"
              class="shrink-0 flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-gray-200 dark:border-[#3a3a3c] text-gray-500 text-xs font-semibold hover:text-[#1D5F5E] hover:border-[#1D5F5E] transition-colors">
              <div class="i-carbon-edit text-xs"></div> Edit
            </button>
          </div>

          <!-- View mode -->
          <div v-if="!editing" class="divide-y divide-gray-50 dark:divide-[#2c2c2e]">
            <div class="px-5 py-3 flex items-center gap-4">
              <span class="text-xs text-gray-400 w-28 shrink-0">User ID</span>
              <span class="text-sm font-mono font-semibold text-gray-800 dark:text-white">{{ me.hrms_id || '—' }}</span>
            </div>
            <div class="px-5 py-3 flex items-center gap-4">
              <span class="text-xs text-gray-400 w-28 shrink-0">Designation</span>
              <span class="text-sm text-gray-700 dark:text-gray-200">{{ me.designation || '—' }}</span>
            </div>
            <div class="px-5 py-3 flex items-center gap-4">
              <span class="text-xs text-gray-400 w-28 shrink-0">Mobile Number</span>
              <span class="text-sm font-mono text-gray-700 dark:text-gray-200">{{ me.mobile_number || '—' }}</span>
            </div>
            <div class="px-5 py-3 flex items-center gap-4">
              <span class="text-xs text-gray-400 w-28 shrink-0">Email</span>
              <span class="text-sm text-gray-700 dark:text-gray-200">{{ me.email || '—' }}</span>
            </div>
            <div class="px-5 py-3 flex items-center gap-4">
              <span class="text-xs text-gray-400 w-28 shrink-0">Telegram</span>
              <div class="flex items-center gap-2">
                <span v-if="me.telegram_linked"
                  class="flex items-center gap-1.5 text-xs font-semibold text-green-700 bg-green-50 dark:bg-green-900/20 dark:text-green-400 px-2.5 py-1 rounded-full">
                  <div class="i-carbon-checkmark-filled text-sm"></div>
                  Linked
                  <span v-if="me.telegram_chat_id" class="font-mono font-normal text-green-600 dark:text-green-500">
                    · {{ me.telegram_chat_id }}
                  </span>
                </span>
                <span v-else class="flex items-center gap-1.5 text-xs text-gray-400 bg-gray-50 dark:bg-[#2c2c2e] px-2.5 py-1 rounded-full">
                  <div class="i-carbon-warning text-sm"></div>
                  Not linked — go to Link Rly Official Telegram in Settings
                </span>
              </div>
            </div>
          </div>

          <!-- Edit mode -->
          <div v-else class="divide-y divide-gray-50 dark:divide-[#2c2c2e]">
            <div class="px-5 py-3 flex items-center gap-4">
              <span class="text-xs text-gray-400 w-28 shrink-0">User ID</span>
              <div class="flex-1">
                <input v-model="editForm.hrms_id"
                  class="w-full text-sm font-mono px-2.5 py-1.5 rounded-lg border border-gray-200 dark:border-[#3a3a3c] bg-white dark:bg-[#2c2c2e] outline-none focus:border-[#1D5F5E]"
                  placeholder="User ID" />
                <p class="text-[11px] text-gray-400 mt-1">Changing this also changes your login ID. Must be unique.</p>
              </div>
            </div>
            <div class="px-5 py-3 flex items-center gap-4">
              <span class="text-xs text-gray-400 w-28 shrink-0">Designation</span>
              <input v-model="editForm.designation"
                class="flex-1 text-sm px-2.5 py-1.5 rounded-lg border border-gray-200 dark:border-[#3a3a3c] bg-white dark:bg-[#2c2c2e] outline-none focus:border-[#1D5F5E]"
                placeholder="Designation" />
            </div>
            <div class="px-5 py-3 flex items-center gap-4">
              <span class="text-xs text-gray-400 w-28 shrink-0">Mobile Number</span>
              <input v-model="editForm.mobile_number"
                class="flex-1 text-sm px-2.5 py-1.5 rounded-lg border border-gray-200 dark:border-[#3a3a3c] bg-white dark:bg-[#2c2c2e] outline-none focus:border-[#1D5F5E]"
                placeholder="Mobile Number" />
            </div>
            <div class="px-5 py-3 flex items-center gap-4">
              <span class="text-xs text-gray-400 w-28 shrink-0">Email</span>
              <input v-model="editForm.email" type="email"
                class="flex-1 text-sm px-2.5 py-1.5 rounded-lg border border-gray-200 dark:border-[#3a3a3c] bg-white dark:bg-[#2c2c2e] outline-none focus:border-[#1D5F5E]"
                placeholder="Email" />
            </div>
            <div class="px-5 py-3 flex items-center justify-end gap-2">
              <button @click="cancelEdit"
                class="px-3 py-1.5 rounded-lg border border-gray-200 dark:border-[#3a3a3c] text-gray-500 text-xs font-semibold hover:bg-gray-100 dark:hover:bg-[#3a3a3c] transition-colors">
                Cancel
              </button>
              <button @click="saveProfile" :disabled="saving"
                class="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#1D5F5E] text-white text-xs font-semibold hover:bg-[#174E4D] disabled:opacity-50 transition-colors">
                <div v-if="saving" class="i-carbon-circle-dash animate-spin text-xs"></div>
                <div v-else class="i-carbon-checkmark text-xs"></div>
                Save
              </button>
            </div>
          </div>
        </div>

        <!-- Change Password card -->
        <div class="bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] shadow-sm overflow-hidden mb-6">
          <div class="px-5 py-4 border-b border-gray-100 dark:border-[#2c2c2e] flex items-center gap-3">
            <div class="i-carbon-password text-[#1D5F5E] text-lg"></div>
            <h2 class="text-sm font-bold text-gray-700 dark:text-gray-200 flex-1">Password</h2>
            <button v-if="!changingPassword" @click="startChangePassword"
              class="shrink-0 flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-gray-200 dark:border-[#3a3a3c] text-gray-500 text-xs font-semibold hover:text-[#1D5F5E] hover:border-[#1D5F5E] transition-colors">
              <div class="i-carbon-edit text-xs"></div> Change
            </button>
          </div>

          <div v-if="!changingPassword" class="px-5 py-3">
            <span class="text-sm text-gray-400">••••••••</span>
          </div>

          <div v-else class="divide-y divide-gray-50 dark:divide-[#2c2c2e]">
            <div class="px-5 py-3 flex items-center gap-4">
              <span class="text-xs text-gray-400 w-32 shrink-0">Current Password</span>
              <input v-model="pwForm.current_password" type="password"
                class="flex-1 text-sm px-2.5 py-1.5 rounded-lg border border-gray-200 dark:border-[#3a3a3c] bg-white dark:bg-[#2c2c2e] outline-none focus:border-[#1D5F5E]"
                placeholder="Current password" />
            </div>
            <div class="px-5 py-3 flex items-center gap-4">
              <span class="text-xs text-gray-400 w-32 shrink-0">New Password</span>
              <input v-model="pwForm.new_password" type="password"
                class="flex-1 text-sm px-2.5 py-1.5 rounded-lg border border-gray-200 dark:border-[#3a3a3c] bg-white dark:bg-[#2c2c2e] outline-none focus:border-[#1D5F5E]"
                placeholder="At least 6 characters" />
            </div>
            <div class="px-5 py-3 flex items-center gap-4">
              <span class="text-xs text-gray-400 w-32 shrink-0">Confirm Password</span>
              <input v-model="pwForm.confirm_password" type="password"
                class="flex-1 text-sm px-2.5 py-1.5 rounded-lg border border-gray-200 dark:border-[#3a3a3c] bg-white dark:bg-[#2c2c2e] outline-none focus:border-[#1D5F5E]"
                placeholder="Re-enter new password" />
            </div>
            <div class="px-5 py-3 flex items-center justify-end gap-2">
              <button @click="cancelChangePassword"
                class="px-3 py-1.5 rounded-lg border border-gray-200 dark:border-[#3a3a3c] text-gray-500 text-xs font-semibold hover:bg-gray-100 dark:hover:bg-[#3a3a3c] transition-colors">
                Cancel
              </button>
              <button @click="savePassword" :disabled="savingPassword"
                class="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#1D5F5E] text-white text-xs font-semibold hover:bg-[#174E4D] disabled:opacity-50 transition-colors">
                <div v-if="savingPassword" class="i-carbon-circle-dash animate-spin text-xs"></div>
                <div v-else class="i-carbon-checkmark text-xs"></div>
                Save
              </button>
            </div>
          </div>
        </div>

        <!-- Toast -->
        <Transition name="fade">
          <div v-if="toast.show"
            class="fixed bottom-6 right-6 px-4 py-2.5 rounded-xl shadow-lg text-sm font-semibold z-50"
            :class="toast.type === 'error' ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-green-50 text-green-700 border border-green-200'">
            {{ toast.msg }}
          </div>
        </Transition>

        <!-- Assigned LOAs -->
        <div class="bg-white dark:bg-[#1c1c1e] rounded-2xl border border-gray-100 dark:border-[#3a3a3c] shadow-sm overflow-hidden">
          <div class="px-5 py-4 border-b border-gray-100 dark:border-[#2c2c2e] flex items-center gap-3">
            <div class="i-carbon-document text-[#1D5F5E] text-lg"></div>
            <div>
              <h2 class="text-sm font-bold text-gray-700 dark:text-gray-200">Assigned LOAs</h2>
              <p class="text-xs text-gray-400 mt-0.5">LOAs where you are the consignee</p>
            </div>
            <span class="ml-auto text-xs font-semibold text-[#1D5F5E] bg-[#1D5F5E]/10 px-2 py-0.5 rounded-full">
              {{ works.length }}
            </span>
          </div>

          <div v-if="!works.length" class="px-5 py-8 text-center text-sm text-gray-400">
            No LOAs assigned to you yet.
          </div>

          <div v-else class="divide-y divide-gray-50 dark:divide-[#2c2c2e]">
            <div v-for="w in works" :key="w.id" class="px-5 py-3">
              <div class="flex items-start gap-3">
                <span class="shrink-0 text-xs font-bold text-[#1D5F5E] bg-[#1D5F5E]/10 px-2 py-0.5 rounded-full mt-0.5">
                  {{ w.loa_number || '—' }}
                </span>
                <div class="min-w-0 flex-1">
                  <p class="text-xs font-semibold text-gray-800 dark:text-white">{{ w.tender_number || '—' }}</p>
                  <p class="text-xs text-gray-500 truncate mt-0.5">{{ w.name_of_work || '—' }}</p>
                  <p class="text-xs text-gray-400 mt-0.5">{{ w.contractor_name || '—' }}</p>
                </div>
                <span v-if="w.date_of_completion" class="shrink-0 text-[10px] text-gray-400">
                  Due: {{ w.date_of_completion }}
                </span>
              </div>
            </div>
          </div>
        </div>

      </template>
    </div>
  </div>
</template>
