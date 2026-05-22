<script setup lang="ts">
import type { AdsBySideResponse } from '~/types/api'

const props = defineProps<{
  ads: AdsBySideResponse | null
  loading?: boolean
}>()

const boardAds = computed(() => [
  ...(props.ads?.sell || []),
  ...(props.ads?.buy || [])
])
</script>

<template>
  <section class="board-section">
    <div v-if="loading" class="auth-state">Загружаем объявления...</div>
    <AdsColumn v-else :ads="boardAds" />
  </section>
</template>
