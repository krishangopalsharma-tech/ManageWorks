<script setup>
import Sidebar from './components/Sidebar.vue'
</script>

<template>
  <div class="h-screen w-screen bg-light-bg font-sans flex overflow-hidden text-gray-800">
    <!-- Sidebar -->
    <div class="h-full py-6 pl-6 shrink-0 z-10 relative">
      <div class="h-full bg-light-surface rounded-2xl soft-shadow overflow-hidden">
        <Sidebar />
      </div>
    </div>

    <!-- Main Content -->
    <div class="flex-1 overflow-hidden py-6 pr-6">
      <main class="h-full w-full pl-2 overflow-y-auto">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>
