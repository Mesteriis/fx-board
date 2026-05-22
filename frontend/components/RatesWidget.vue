<script setup lang="ts">
import type { RatesResponse } from '~/types/api'

defineProps<{
  rates: RatesResponse | null
  loading?: boolean
}>()
</script>

<template>
  <section class="rates-widget">
    <div class="section-heading">
      <h2>Справочные курсы</h2>
      <span v-if="rates">{{ rates.date }}</span>
    </div>
    <div v-if="loading" class="muted">Обновляем курсы...</div>
    <div v-else-if="rates" class="rates-grid">
      <div v-for="rate in rates.rates" :key="rate.pair" class="rate-row">
        <span>{{ rate.pair }}</span>
        <strong>{{ rate.rate }}</strong>
      </div>
    </div>
    <div v-else class="muted">Курсы пока недоступны.</div>
    <p v-if="rates?.is_stale" class="warning-text">
      Google Sheet недоступен, показаны последние сохраненные значения.
    </p>
  </section>
</template>
