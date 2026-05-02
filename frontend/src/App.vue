<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Sidebar from './components/Sidebar.vue'

const route = useRoute()
const authRoutes = ['/login', '/register']
const showSidebar = computed(() => !authRoutes.includes(route.path))
</script>

<template>
  <div class="h-screen w-screen bg-light-bg font-sans flex overflow-hidden text-gray-800">
    <!-- Sidebar (hidden on auth pages) -->
    <div v-if="showSidebar" class="h-full py-6 pl-6 shrink-0 z-10 relative">
      <div class="h-full bg-light-surface rounded-2xl soft-shadow overflow-hidden">
        <Sidebar />
      </div>
    </div>

    <!-- Main Content -->
    <div class="flex-1 overflow-hidden" :class="showSidebar ? 'py-6 pr-6' : ''">
      <main class="h-full w-full overflow-y-auto" :class="showSidebar ? 'pl-2' : ''">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>
