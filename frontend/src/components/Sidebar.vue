<script setup>
import ManageWorksIcon from './ManageWorksIcon.vue'
import { ref, watchEffect, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
const route  = useRoute()
const { state, logout } = useAuth()

const isAdmin = computed(() => state.user?.role === 'admin' || state.user?.is_staff)

const menuItems = ref([
  { name: 'Dashboard',    icon: 'i-carbon-dashboard', path: '/' },
  { name: 'Work Details', icon: 'i-carbon-catalog',   path: '/work-details' },
  { name: 'Item Progress',icon: 'i-carbon-chart-bar', path: '/item-progress' },
  { name: 'Update Work',  icon: 'i-carbon-edit',      path: '/update-work' },
  { name: 'MB Details',   icon: 'i-carbon-receipt',   path: '/mb-details' },
  { name: 'Document Generator', icon: 'i-carbon-document', path: '/document-generator' },
  { name: 'Add New Work', icon: 'i-carbon-add-alt',   path: '/add-new-work' },
  {
    name: 'Settings',
    icon: 'i-carbon-settings',
    expanded: false,
    subItems: [
      { name: 'User Management', path: '/settings/user-management', adminOnly: true },
    ],
  },
])

const activeItem    = ref('Dashboard')
const activeSubItem = ref('')

watchEffect(() => {
  for (const item of menuItems.value) {
    if (item.path && route.path === item.path) {
      activeItem.value    = item.name
      activeSubItem.value = ''
      return
    }
    if (item.subItems) {
      for (const sub of item.subItems) {
        if (sub.path && route.path === sub.path) {
          activeItem.value    = item.name
          activeSubItem.value = sub.name
          item.expanded = true
          return
        }
      }
    }
  }
})

const handleItemClick = (item) => {
  if (item.subItems) {
    item.expanded = !item.expanded
  } else if (item.path) {
    router.push(item.path)
  }
}

const handleSubItemClick = (_, sub) => {
  if (sub.path) router.push(sub.path)
}

async function handleLogout() {
  await logout()
  router.push('/login')
}

const visibleSubItems = (item) => {
  if (!item.subItems) return []
  return item.subItems.filter(s => !s.adminOnly || isAdmin.value)
}
</script>

<template>
  <aside class="w-72 h-full p-6 flex flex-col gap-6">
    <!-- Logo -->
    <div class="flex items-center gap-2.5 mb-6 pt-2">
      <ManageWorksIcon :size="28" style="color: var(--color-text-primary);" />
      <span class="text-xl font-bold tracking-tight" style="color: var(--color-text-primary);">ManageWorks</span>
    </div>

    <!-- Navigation -->
    <nav class="flex flex-col gap-3 flex-1 overflow-y-auto pr-2 pb-6" style="scrollbar-width: thin;">
      <div v-for="item in menuItems" :key="item.name" class="flex flex-col gap-1">

        <!-- Main Item -->
        <div
          @click="handleItemClick(item)"
          :class="[activeItem === item.name ? 'nav-item-active' : 'nav-item', 'justify-between select-none']"
        >
          <div class="flex items-center gap-3">
            <div :class="item.icon" class="text-xl"></div>
            <span class="text-sm font-semibold tracking-wide">{{ item.name }}</span>
          </div>
          <div v-if="item.subItems && visibleSubItems(item).length"
            :class="[item.expanded ? 'i-carbon-chevron-up' : 'i-carbon-chevron-down', 'text-lg', activeItem === item.name ? 'text-white opacity-80' : 'text-gray-400']">
          </div>
        </div>

        <!-- Sub Items -->
        <div v-show="item.subItems && item.expanded && visibleSubItems(item).length" class="flex flex-col gap-1 pl-11 pr-2 pt-1 pb-2">
          <div
            v-for="sub in visibleSubItems(item)"
            :key="sub.name"
            @click="handleSubItemClick(item, sub)"
            class="px-4 py-2.5 rounded-xl text-sm transition-all duration-300 font-medium cursor-pointer select-none"
            :class="activeSubItem === sub.name
              ? 'bg-[#111] text-white shadow-md'
              : 'text-[#86868b] hover:text-[#1d1d1f] hover:bg-white/60'"
          >
            {{ sub.name }}
          </div>
        </div>

      </div>
    </nav>

    <!-- User Profile Area -->
    <div class="mt-auto pt-4" style="border-top: 1px solid var(--color-separator);">
<div
        class="flex items-center gap-3 p-2 rounded-xl transition-all cursor-default"
        style="hover-bg: var(--color-surface-secondary);"
        :style="{ '&:hover': { backgroundColor: 'var(--color-surface-secondary)' } }"
      >
        <div
          class="w-10 h-10 rounded-full flex-center overflow-hidden shrink-0"
          style="background-color: var(--color-surface-secondary);"
        >
          <div class="i-carbon-user text-xl" style="color: var(--color-text-tertiary);"></div>
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-semibold truncate" style="color: var(--color-text-primary);">{{ state.user?.name || 'User' }}</p>
          <p class="text-xs truncate" style="color: var(--color-text-secondary);">{{ state.user?.designation || state.user?.hrms_id }}</p>
        </div>
        <button
          @click="handleLogout"
          title="Sign out"
          class="p-1.5 rounded-lg transition-colors cursor-pointer hover:bg-red-50 hover:text-red-500"
          style="color: var(--color-text-tertiary);"
        >
          <div class="i-carbon-logout text-lg"></div>
        </button>
      </div>
    </div>
  </aside>
</template>
