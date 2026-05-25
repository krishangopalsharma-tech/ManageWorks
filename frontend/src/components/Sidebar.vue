<script setup>
import ManageWorksIcon from './ManageWorksIcon.vue'
import { ref, watchEffect, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
const route  = useRoute()
const { state, logout } = useAuth()

const isAdmin        = computed(() => state.user?.role === 'admin' || state.user?.is_staff)
const canSeeRegister = computed(() => isAdmin.value || state.user?.role === 'consignee')
const collapsed = ref(localStorage.getItem('sidebar-collapsed') === 'true')

const toggleCollapsed = () => {
  collapsed.value = !collapsed.value
  localStorage.setItem('sidebar-collapsed', collapsed.value)
}

const menuItems = ref([
  { name: 'Dashboard',    icon: 'i-carbon-dashboard', path: '/' },
  { name: 'Work Details', icon: 'i-carbon-catalog',   path: '/work-details' },
  { name: 'Item Progress',icon: 'i-carbon-chart-bar', path: '/item-progress' },
  { name: 'Update Work',  icon: 'i-carbon-edit',      path: '/update-work' },
  { name: 'Site Register', icon: 'i-carbon-map',       path: '/site-register', siteRegisterOnly: true },
  { name: 'MB Details',   icon: 'i-carbon-receipt',   path: '/mb-details' },
  {
    name: 'Document Generator',
    icon: 'i-carbon-document',
    expanded: false,
    subItems: [
      { name: 'Installation Certificate', path: '/installation-certificate' },
    ],
  },
  { name: 'Add New Work', icon: 'i-carbon-add-alt',   path: '/add-new-work' },
  {
    name: 'Settings',
    icon: 'i-carbon-settings',
    expanded: false,
    subItems: [
      { name: 'User Management', path: '/settings/user-management', adminOnly: true },
      { name: 'SMTP Settings',   path: '/settings/smtp',            adminOnly: true },
      { name: 'Telegram Bot',    path: '/settings/telegram',               adminOnly: true },
      { name: 'Site Supervisors', path: '/settings/site-register-parties', adminOnly: true },
      { name: 'Link Rly Official Telegram', path: '/settings/telegram-link' },
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
  if (collapsed.value) {
    // In collapsed mode: groups just navigate to first visible sub-item
    if (item.subItems) {
      const first = visibleSubItems(item)[0]
      if (first?.path) router.push(first.path)
    } else if (item.path) {
      router.push(item.path)
    }
    return
  }
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

const visibleMenuItems = computed(() =>
  menuItems.value.filter(item => !item.siteRegisterOnly || canSeeRegister.value)
)

// Tooltip: full name when collapsed
const itemTooltip = (item) => collapsed.value ? item.name : ''
</script>

<template>
  <aside
    class="h-full flex flex-col overflow-hidden transition-all duration-300"
    :class="collapsed ? 'w-16' : 'w-72'"
  >
    <!-- Logo + Toggle -->
    <div
      class="flex items-center shrink-0 pt-6 pb-4 px-3"
      :class="collapsed ? 'flex-col gap-3' : 'px-5 gap-2.5 justify-between'"
    >
      <div v-if="!collapsed" class="flex items-center gap-2.5">
        <ManageWorksIcon :size="28" style="color: var(--color-text-primary);" class="shrink-0" />
        <span
          class="text-xl font-bold tracking-tight whitespace-nowrap overflow-hidden transition-all duration-300"
          style="color: var(--color-text-primary);"
        >ManageWorks</span>
      </div>
      <button
        @click="toggleCollapsed"
        class="flex items-center justify-center w-7 h-7 rounded-lg transition-colors shrink-0"
        style="color: var(--color-text-tertiary);"
        :class="collapsed ? 'hover:bg-[#EEF4F3] mt-1' : 'hover:bg-[#EEF4F3]'"
        :title="collapsed ? 'Expand sidebar' : 'Collapse sidebar'"
      >
        <div :class="collapsed ? 'i-carbon-side-panel-open' : 'i-carbon-side-panel-close'" class="text-base"></div>
      </button>
    </div>

    <!-- Navigation -->
    <nav
      class="flex flex-col flex-1 overflow-y-auto pb-4"
      :class="collapsed ? 'px-2 gap-1' : 'px-4 gap-1'"
      style="scrollbar-width: thin;"
    >
      <div v-for="item in visibleMenuItems" :key="item.name" class="flex flex-col">

        <!-- Main Item -->
        <div
          @click="handleItemClick(item)"
          :title="itemTooltip(item)"
          :class="[
            activeItem === item.name ? 'nav-item-active' : 'nav-item',
            collapsed ? 'justify-center px-0 py-2.5' : 'justify-between',
            'select-none'
          ]"
        >
          <div class="flex items-center" :class="collapsed ? 'justify-center' : 'gap-3'">
            <div :class="item.icon" class="text-xl shrink-0"></div>
            <span v-if="!collapsed" class="text-sm font-semibold tracking-wide whitespace-nowrap">{{ item.name }}</span>
          </div>
          <div
            v-if="!collapsed && item.subItems && visibleSubItems(item).length"
            :class="[item.expanded ? 'i-carbon-chevron-up' : 'i-carbon-chevron-down', 'text-lg', activeItem === item.name ? 'text-white opacity-80' : 'text-gray-400']"
          ></div>
        </div>

        <!-- Sub Items (only when expanded) -->
        <div
          v-if="!collapsed"
          v-show="item.subItems && item.expanded && visibleSubItems(item).length"
          class="flex flex-col gap-1 pl-11 pr-2 pt-1 pb-2"
        >
          <div
            v-for="sub in visibleSubItems(item)"
            :key="sub.name"
            @click="handleSubItemClick(item, sub)"
            class="px-4 py-2.5 rounded-xl text-sm transition-all duration-300 font-medium cursor-pointer select-none"
            :class="activeSubItem === sub.name
              ? 'bg-[#1D5F5E] text-white shadow-md'
              : 'text-[#86868b] hover:text-[#1d1d1f] hover:bg-white/60'"
          >
            {{ sub.name }}
          </div>
        </div>

      </div>
    </nav>

    <!-- User Profile Area -->
    <div class="shrink-0 px-3 py-4" style="border-top: 1px solid var(--color-separator);">
      <!-- Collapsed: avatar + logout stacked -->
      <div v-if="collapsed" class="flex flex-col items-center gap-2">
        <div
          class="w-10 h-10 rounded-full flex items-center justify-center overflow-hidden"
          style="background-color: var(--color-surface-secondary);"
          :title="state.user?.name || 'User'"
        >
          <div class="i-carbon-user text-xl" style="color: var(--color-text-tertiary);"></div>
        </div>
        <button
          @click="handleLogout"
          title="Sign out"
          class="p-1.5 rounded-lg transition-colors cursor-pointer hover:bg-red-50 hover:text-red-500"
          style="color: var(--color-text-tertiary);"
        >
          <div class="i-carbon-logout text-base"></div>
        </button>
      </div>

      <!-- Expanded: avatar + name + logout -->
      <div v-else
        class="flex items-center gap-3 p-2 rounded-xl transition-all"
      >
        <div
          class="w-10 h-10 rounded-full flex items-center justify-center overflow-hidden shrink-0"
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
            class="p-1.5 rounded-lg transition-colors cursor-pointer hover:bg-red-50 hover:text-red-500 shrink-0"
            style="color: var(--color-text-tertiary);"
          >
            <div class="i-carbon-logout text-lg"></div>
          </button>
      </div>
    </div>
  </aside>
</template>
