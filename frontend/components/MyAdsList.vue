<script setup lang="ts">
import type { AdResponse, MyAdsResponse } from '~/types/api'

const { apiFetch } = useApi()
const items = ref<AdResponse[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

onMounted(load)

async function load() {
  loading.value = true
  error.value = null
  try {
    const response = await apiFetch<MyAdsResponse>('/ads/my')
    items.value = response.items
  } catch {
    error.value = 'Не удалось загрузить объявления'
  } finally {
    loading.value = false
  }
}

function replaceAd(ad: AdResponse) {
  items.value = items.value.map((item) => (item.id === ad.id ? ad : item))
}
</script>

<template>
  <section class="content-section">
    <div class="section-heading">
      <h1>Мои объявления</h1>
      <button type="button" class="ghost-button" @click="load">Обновить</button>
    </div>
    <div v-if="loading" class="auth-state">Загружаем...</div>
    <p v-else-if="error" class="danger-text">{{ error }}</p>
    <div v-else-if="items.length" class="ad-list">
      <AdCard
        v-for="ad in items"
        :key="ad.id"
        :ad="ad"
        show-revoke
        @revoked="replaceAd"
      />
    </div>
    <div v-else class="empty-state empty-state--compact">
      <h2>У вас пока нет объявлений</h2>
      <NuxtLink class="primary-button" to="/app/new">Создать объявление</NuxtLink>
    </div>
  </section>
</template>
