<script setup lang="ts">
defineProps<{
  label: string
  placeholder?: string
}>()

const model = defineModel<string>({ required: true })
</script>

<template>
  <label class="field">
    <span>{{ label }}</span>
    <input
      v-model="model"
      type="number"
      min="0"
      step="0.00000001"
      inputmode="decimal"
      :placeholder="placeholder || '0.00'"
    />
  </label>
</template>
