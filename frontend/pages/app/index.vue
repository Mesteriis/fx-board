<script setup lang="ts">
import type { AdsBySideResponse, AuthResponse } from '~/types/api'

const { apiFetch } = useApi()
const auth = useState<AuthResponse | null>('auth', () => null)
const ads = ref<AdsBySideResponse | null>(null)
const loadingAds = ref(true)

watch(auth, async (value) => {
  if (value) {
    await loadAds()
  }
}, { immediate: true })

async function loadAds() {
  loadingAds.value = true
  try {
    ads.value = await apiFetch<AdsBySideResponse>('/ads')
  } catch {
    ads.value = null
  } finally {
    loadingAds.value = false
  }
}
</script>

<template>
  <TelegramAuthGate>
    <AppShell>
      <AdsBoard :ads="ads" :loading="loadingAds" />
    </AppShell>
  </TelegramAuthGate>
</template>
