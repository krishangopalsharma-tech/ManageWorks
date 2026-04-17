<script setup>
import Sidebar from './components/Sidebar.vue'
import Topbar from './components/Topbar.vue'
</script>

<template>
  <div class="h-screen w-screen bg-light-bg font-sans flex overflow-hidden text-gray-800">
    <!-- Sidebar Container -->
    <div class="h-full py-6 pl-6 shrink-0 z-10 relative">
      <div class="h-full bg-light-surface rounded-2xl soft-shadow overflow-hidden">
        <Sidebar />
      </div>
    </div>

    <!-- Main Content Area -->
    <div class="flex-1 flex flex-col overflow-hidden pt-6">
      <Topbar />
      
      <!-- Page Content -->
      <main class="flex-1 w-full px-8 pb-6 overflow-y-auto">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>
