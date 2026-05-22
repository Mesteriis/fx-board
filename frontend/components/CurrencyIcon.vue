<script setup lang="ts">
import type { Currency } from '~/types/api'
import { CURRENCY_META } from '~/utils/rates'

const props = defineProps<{
  currency: Currency
}>()

const meta = computed(() => CURRENCY_META[props.currency])
</script>

<template>
  <span class="currency-icon" :title="meta.label" :aria-label="currency">
    {{ meta.symbol }}
  </span>
</template>
