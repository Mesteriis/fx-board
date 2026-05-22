<script setup lang="ts">
import type { AdsBySideResponse, AuthResponse, RatesResponse } from '~/types/api'

const { apiFetch } = useApi()
const auth = useState<AuthResponse | null>('auth', () => null)
const ads = ref<AdsBySideResponse | null>(null)
const rates = ref<RatesResponse | null>(null)
const loadingAds = ref(true)
const loadingRates = ref(true)

watch(auth, async (value) => {
  if (value) {
    await Promise.all([loadAds(), loadRates()])
  }
}, { immediate: true })

async function loadAds() {
  loadingAds.value = true
  try {
    ads.value = await apiFetch<AdsBySideResponse>('/ads')
  } finally {
    loadingAds.value = false
  }
}

async function loadRates() {
  loadingRates.value = true
  try {
    rates.value = await apiFetch<RatesResponse>('/rates')
  } finally {
    loadingRates.value = false
  }
}
</script>

<template>
  <TelegramAuthGate>
    <AppShell>
      <div class="dashboard-layout">
        <section class="hero-panel">
          <div>
            <h1>Покупка и продажа валюты</h1>
            <p>USD, EUR, RUB, USDT и USDC. Объявления без платежей и эскроу.</p>
          </div>
          <NuxtLink class="primary-button" to="/app/new">Создать объявление</NuxtLink>
        </section>
        <RatesWidget :rates="rates" :loading="loadingRates" />
      </div>
      <AdsBoard :ads="ads" :loading="loadingAds" />
    </AppShell>
  </TelegramAuthGate>
</template>
