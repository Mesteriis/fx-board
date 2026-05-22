<script setup lang="ts">
import type { AuthResponse } from '~/types/api'

const auth = useState<AuthResponse | null>('auth', () => null)
</script>

<template>
  <AppShell>
    <AccessDeniedScreen :channels="auth?.access.missing_channels || []" />
  </AppShell>
</template>
