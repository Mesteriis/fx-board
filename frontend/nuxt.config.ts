export default defineNuxtConfig({
  compatibilityDate: '2026-05-22',
  css: ['~/assets/css/main.css'],
  app: {
    head: {
      script: [{ src: 'https://telegram.org/js/telegram-web-app.js' }]
    }
  },
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
