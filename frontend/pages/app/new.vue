<script setup lang="ts">
import type { AdResponse } from '~/types/api'

const created = ref<AdResponse | null>(null)
</script>

<template>
  <TelegramAuthGate>
    <AppShell>
      <section class="content-section content-section--narrow">
        <div class="section-heading">
          <h1>Новое объявление</h1>
          <NuxtLink v-if="created" class="ghost-button" :to="`/app/ad/${created.id}`">
            Открыть #{{ created.id }}
          </NuxtLink>
        </div>
        <AdCreateForm @created="created = $event" />
      </section>
    </AppShell>
  </TelegramAuthGate>
</template>
