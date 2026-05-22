<script setup lang="ts">
import type { AdResponse, AuthResponse } from '~/types/api'

const route = useRoute()
const { apiFetch } = useApi()
const auth = useState<AuthResponse | null>('auth', () => null)
const ad = ref<AdResponse | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

watch(auth, (value) => {
  if (value) {
    void load()
  }
}, { immediate: true })

async function load() {
  loading.value = true
  error.value = null
  try {
    ad.value = await apiFetch<AdResponse>(`/ads/${route.params.id}`)
  } catch {
    error.value = 'Объявление не найдено'
  } finally {
    loading.value = false
  }
}

const isOwn = computed(() => Boolean(ad.value?.author?.id && ad.value.author.id === auth.value?.user.id))
</script>

<template>
  <TelegramAuthGate>
    <AppShell>
      <section class="content-section content-section--narrow">
        <div class="section-heading">
          <h1>Объявление</h1>
          <NuxtLink class="ghost-button" to="/app">К доске</NuxtLink>
        </div>
        <div v-if="loading" class="auth-state">Загружаем...</div>
        <p v-else-if="error" class="danger-text">{{ error }}</p>
        <AdCard v-else-if="ad" :ad="ad" :show-revoke="isOwn" @revoked="ad = $event" />
      </section>
    </AppShell>
  </TelegramAuthGate>
</template>
