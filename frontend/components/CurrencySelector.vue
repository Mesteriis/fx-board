<script setup lang="ts">
import type { Currency } from '~/types/api'

defineProps<{
  label: string
}>()

const model = defineModel<Currency>({ required: true })
const currencies: Currency[] = ['USD', 'EUR', 'RUB', 'USDT', 'USDC']
</script>

<template>
  <label class="field">
    <span>{{ label }}</span>
    <select v-model="model">
      <option v-for="currency in currencies" :key="currency" :value="currency">
        {{ currency }}
      </option>
    </select>
  </label>
</template>
