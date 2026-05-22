<script setup lang="ts">
defineProps<{
  isAdmin?: boolean
}>()

const items = [
  { to: '/app', label: 'Доска' },
  { to: '/app/new', label: 'Новое' },
  { to: '/app/my', label: 'Мои' },
  { to: '/app/rates', label: 'Курсы' }
]
</script>

<template>
  <nav class="bottom-nav" aria-label="Быстрая навигация">
    <NuxtLink v-for="item in items" :key="item.to" :to="item.to">
      {{ item.label }}
    </NuxtLink>
    <NuxtLink v-if="isAdmin" to="/app/admin">Админ</NuxtLink>
  </nav>
</template>
