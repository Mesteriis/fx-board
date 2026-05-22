<script setup lang="ts">
import type { AdResponse } from '~/types/api'

defineProps<{
  ads: AdResponse[]
}>()
</script>

<template>
  <section class="ads-column" aria-label="Объявления">
    <div v-if="ads.length" class="ad-list">
      <AdCard v-for="ad in ads" :key="ad.id" :ad="ad" />
    </div>
    <div v-else class="empty-column">Активных объявлений пока нет.</div>
  </section>
</template>
