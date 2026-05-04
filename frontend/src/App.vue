<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Sidebar from './components/Sidebar.vue'
import { useTheme } from './composables/useTheme'

useTheme()

const route = useRoute()
const authRoutes = ['/login', '/register']
const showSidebar = computed(() => !authRoutes.includes(route.path))
</script>

<template>
  <div
    class="h-screen w-screen font-sans flex overflow-hidden"
    style="background-color: var(--color-bg); color: var(--color-text-primary);"
  >
    <!-- Sidebar (hidden on auth pages) -->
    <div v-if="showSidebar" class="h-full py-6 pl-6 shrink-0 z-10 relative">
      <div
        class="h-full rounded-2xl soft-shadow overflow-hidden"
        style="background-color: var(--color-surface);"
      >
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
