<script setup lang="ts">
import type { AdResponse, AdSide } from '~/types/api'

defineProps<{
  title: string
  side: AdSide
  ads: AdResponse[]
}>()
</script>

<template>
  <section class="ads-column">
    <div class="column-title">
      <h2>{{ title }}</h2>
      <span>{{ ads.length }}</span>
    </div>
    <div v-if="ads.length" class="ad-list">
      <AdCard v-for="ad in ads" :key="ad.id" :ad="ad" />
    </div>
    <div v-else class="empty-column">Активных объявлений пока нет.</div>
  </section>
</template>
