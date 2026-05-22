<script setup lang="ts">
import type {
  AdminDashboardResponse,
  AdminReportListResponse,
  AdminReportResponse,
  ReportStatus
} from '~/types/api'

const { apiFetch } = useApi()
const dashboard = ref<AdminDashboardResponse | null>(null)
const reports = ref<AdminReportResponse[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

onMounted(load)

async function load() {
  loading.value = true
  error.value = null
  try {
    const [dashboardResponse, reportsResponse] = await Promise.all([
      apiFetch<AdminDashboardResponse>('/admin/dashboard'),
      apiFetch<AdminReportListResponse>('/admin/reports')
    ])
    dashboard.value = dashboardResponse
    reports.value = reportsResponse.items
  } catch {
    error.value = 'Не удалось загрузить админ-панель'
  } finally {
    loading.value = false
  }
}

async function setStatus(report: AdminReportResponse, status: ReportStatus) {
  const updated = await apiFetch<AdminReportResponse>(`/admin/reports/${report.id}`, {
    method: 'PATCH',
    body: { status }
  })
  reports.value = reports.value.map((item) => (item.id === updated.id ? updated : item))
}
</script>

<template>
  <section class="content-section">
    <div class="section-heading">
      <h1>Админ-панель</h1>
      <button type="button" class="ghost-button" @click="load">Обновить</button>
    </div>

    <div v-if="dashboard" class="metrics-grid">
      <div class="metric-card">
        <span>Пользователи</span>
        <strong>{{ dashboard.users_total }}</strong>
      </div>
      <div class="metric-card">
        <span>Активные объявления</span>
        <strong>{{ dashboard.ads_active }}</strong>
      </div>
      <div class="metric-card">
        <span>Новые репорты</span>
        <strong>{{ dashboard.reports_new }}</strong>
      </div>
      <div class="metric-card">
        <span>Курсы</span>
        <strong>{{ dashboard.rates.status }}</strong>
      </div>
    </div>

    <div v-if="loading" class="auth-state">Загружаем...</div>
    <p v-else-if="error" class="danger-text">{{ error }}</p>
    <div v-else class="admin-list">
      <article v-for="report in reports" :key="report.id" class="admin-report">
        <div>
          <strong>#{{ report.id }} {{ report.reason }}</strong>
          <p>{{ report.comment || 'Без комментария' }}</p>
          <span>
            ad: {{ report.ad_id || '-' }} · reporter:
            {{ report.reporter.username || report.reporter.id }} · target:
            {{ report.target.username || report.target.id }}
          </span>
        </div>
        <div class="admin-actions">
          <span class="status-pill">{{ report.status }}</span>
          <button type="button" class="ghost-button" @click="setStatus(report, 'IN_REVIEW')">
            В работу
          </button>
          <button type="button" class="ghost-button" @click="setStatus(report, 'RESOLVED')">
            Решено
          </button>
          <button type="button" class="ghost-button" @click="setStatus(report, 'REJECTED')">
            Отклонить
          </button>
        </div>
      </article>
      <div v-if="!reports.length" class="empty-column">Новых репортов нет.</div>
    </div>
  </section>
</template>
