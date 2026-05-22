<script setup lang="ts">
defineProps<{
  label?: string
}>()

const model = defineModel<string>({ required: true })
</script>

<template>
  <label class="field">
    <span>{{ label || 'Курс' }}</span>
    <input v-model="model" type="number" min="0" step="0.00000001" inputmode="decimal" />
  </label>
</template>
