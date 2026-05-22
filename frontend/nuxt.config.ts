export default defineNuxtConfig({
  compatibilityDate: '2026-05-22',
  css: ['~/assets/css/main.css'],
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || '/api',
      botUsername: process.env.NUXT_PUBLIC_TELEGRAM_BOT_USERNAME || ''
    }
  },
  typescript: {
    strict: true
  }
})
