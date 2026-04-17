<script setup>
import { ref, watchEffect } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const menuItems = ref([
  { name: 'Dashboard', icon: 'i-carbon-dashboard', path: '/' },
  { name: 'Work Details', icon: 'i-carbon-catalog', path: '/work-details' },
  { name: 'Update Work', icon: 'i-carbon-edit', path: '/update-work' },
  { name: 'Document Generator', icon: 'i-carbon-document', path: '/document-generator' },
  { name: 'Add New Work', icon: 'i-carbon-add-alt', path: '/add-new-work' },
  { 
    name: 'Settings', 
    icon: 'i-carbon-settings',
    expanded: false,
    subItems: [
      { name: 'User Creation', path: '/settings/user-creation' },
      { name: 'User Management', path: '/settings/user-management' }
    ]
  },
])

const activeItem = ref('Dashboard')
const activeSubItem = ref('')

watchEffect(() => {
  for (const item of menuItems.value) {
    if (item.path && route.path === item.path) {
      activeItem.value = item.name
      activeSubItem.value = ''
      return
    }
    if (item.subItems) {
      for (const sub of item.subItems) {
        if (sub.path && route.path === sub.path) {
          activeItem.value = item.name
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

const handleSubItemClick = (parent, sub) => {
  if (sub.path) {
    router.push(sub.path)
  }
}
</script>

<template>
  <aside class="w-72 h-full p-6 flex flex-col gap-6">
    <!-- Logo -->
    <div class="flex flex-center gap-2 mb-6 pt-2">
      <div class="i-carbon-flash text-2xl text-dark-active"></div>
      <span class="text-xl font-bold text-gray-800 tracking-tight">ManageWorks</span>
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
          <div v-if="item.subItems" :class="[item.expanded ? 'i-carbon-chevron-up' : 'i-carbon-chevron-down', 'text-lg', activeItem === item.name ? 'text-white opacity-80' : 'text-gray-400']"></div>
        </div>
        
        <!-- Sub Items -->
        <div v-show="item.subItems && item.expanded" class="flex flex-col gap-1 pl-11 pr-2 pt-1 pb-2">
          <div 
            v-for="sub in item.subItems" 
            :key="sub.name"
            @click="handleSubItemClick(item, sub)"
            class="px-4 py-2.5 rounded-xl text-sm transition-all duration-300 font-medium cursor-pointer select-none"
            :class="activeSubItem === sub.name ? 'bg-[#111] text-white shadow-md' : 'text-gray-500 hover:text-gray-800 hover:bg-white/60'"
          >
            {{ sub.name }}
          </div>
        </div>

      </div>
    </nav>
    
    <!-- User Profile Area -->
    <div class="mt-auto pt-4 border-t border-gray-200">
      <div class="flex items-center gap-3 p-2 rounded-xl hover:bg-white soft-shadow transition-all cursor-pointer">
        <div class="w-10 h-10 rounded-full bg-light-bg soft-shadow-inset flex-center overflow-hidden">
          <div class="i-carbon-user text-xl text-gray-500"></div>
        </div>
        <div class="flex-1">
          <p class="text-sm font-semibold text-gray-800">Administrator</p>
          <p class="text-xs text-gray-500">System Admin</p>
        </div>
        <div class="i-carbon-overflow-menu-vertical text-gray-400"></div>
      </div>
    </div>
  </aside>
</template>
