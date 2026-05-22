<script setup lang="ts">
import type { Currency } from '~/types/api'
import { SUPPORTED_CURRENCIES } from '~/utils/rates'

defineProps<{
  label: string
}>()

const model = defineModel<Currency>({ required: true })
</script>

<template>
  <label class="field">
    <span>{{ label }}</span>
    <select v-model="model">
      <option v-for="currency in SUPPORTED_CURRENCIES" :key="currency" :value="currency">
        {{ currency }}
      </option>
    </select>
  </label>
</template>
