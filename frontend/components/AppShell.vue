<script setup lang="ts">
import type { AuthResponse } from '~/types/api'

const auth = useState<AuthResponse | null>('auth', () => null)

const navItems = [
  { to: '/app', label: 'Доска' },
  { to: '/app/new', label: 'Новое' },
  { to: '/app/my', label: 'Мои' },
  { to: '/app/rates', label: 'Курсы' },
  { to: '/app/rules', label: 'Правила' }
]
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <NuxtLink to="/app" class="brand-link" aria-label="FX Board">
        <span class="brand-mark">FX</span>
        <span class="brand-text">Board</span>
      </NuxtLink>
      <nav class="top-nav" aria-label="Основная навигация">
        <NuxtLink v-for="item in navItems" :key="item.to" :to="item.to">
          {{ item.label }}
        </NuxtLink>
        <NuxtLink v-if="auth?.user.is_admin" to="/app/admin">Админ</NuxtLink>
      </nav>
      <div class="user-chip">
        {{ auth?.user.username ? `@${auth.user.username}` : 'Telegram' }}
      </div>
    </header>

    <main class="app-main">
      <slot />
    </main>

    <BottomNavigation :is-admin="Boolean(auth?.user.is_admin)" />
  </div>
</template>
