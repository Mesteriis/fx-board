<script setup lang="ts">
import type { AdsBySideResponse, AdSide } from '~/types/api'

defineProps<{
  ads: AdsBySideResponse | null
  loading?: boolean
}>()

const activeSide = ref<AdSide>('SELL')
</script>

<template>
  <section class="board-section">
    <div class="mobile-segments" role="tablist" aria-label="Тип объявления">
      <button
        type="button"
        :class="{ active: activeSide === 'SELL' }"
        @click="activeSide = 'SELL'"
      >
        Продажа
      </button>
      <button
        type="button"
        :class="{ active: activeSide === 'BUY' }"
        @click="activeSide = 'BUY'"
      >
        Покупка
      </button>
    </div>

    <div v-if="loading" class="auth-state">Загружаем объявления...</div>
    <div v-else class="board-grid">
      <AdsColumn
        title="Продажа"
        side="SELL"
        :ads="ads?.sell || []"
        :class="{ 'mobile-hidden': activeSide !== 'SELL' }"
      />
      <AdsColumn
        title="Покупка"
        side="BUY"
        :ads="ads?.buy || []"
        :class="{ 'mobile-hidden': activeSide !== 'BUY' }"
      />
    </div>
  </section>
</template>
