<script setup lang="ts">
import type { AuthResponse, RatesResponse } from '~/types/api'

const { apiFetch } = useApi()
const auth = useState<AuthResponse | null>('auth', () => null)
const rates = ref<RatesResponse | null>(null)
const loading = ref(true)

watch(auth, async (value) => {
  if (value) {
    try {
      rates.value = await apiFetch<RatesResponse>('/rates')
    } finally {
      loading.value = false
    }
  }
}, { immediate: true })
</script>

<template>
  <TelegramAuthGate>
    <AppShell>
      <section class="content-section">
        <RatesWidget :rates="rates" :loading="loading" />
      </section>
    </AppShell>
  </TelegramAuthGate>
</template>
