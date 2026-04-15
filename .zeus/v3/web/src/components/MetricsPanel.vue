<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Timer, AlertTriangle, Activity } from 'lucide-vue-next'

const { t } = useI18n()

interface TaskMetric {
  task_id: string
  status: string
  passes: boolean
  avg_duration_ms: number
  min_duration_ms: number
  max_duration_ms: number
  call_count: number
}

interface Bottleneck {
  task_id: string
  avg_duration_ms: number
  max_duration_ms: number
  call_count: number
}

interface BlockedChain {
  blocked_task_id: string
  blocker_task_id: string
  blocker_status: string
  depth: number
}

const taskMetrics = ref<TaskMetric[]>([])
const bottlenecks = ref<Bottleneck[]>([])
const blocked = ref<BlockedChain[]>([])
const loading = ref<Record<string, boolean>>({
  tasks: false,
  bottleneck: false,
  blocked: false,
})

async function fetchTasks() {
  loading.value.tasks = true
  try {
    const res = await fetch('/metrics/tasks')
    taskMetrics.value = await res.json()
  } catch (e) {
    console.error('fetch task metrics error', e)
  } finally {
    loading.value.tasks = false
  }
}

async function fetchBottleneck() {
  loading.value.bottleneck = true
  try {
    const res = await fetch('/metrics/bottleneck?top_n=10')
    bottlenecks.value = await res.json()
  } catch (e) {
    console.error('fetch bottleneck error', e)
  } finally {
    loading.value.bottleneck = false
  }
}

async function fetchBlocked() {
  loading.value.blocked = true
  try {
    const res = await fetch('/metrics/blocked')
    blocked.value = await res.json()
  } catch (e) {
    console.error('fetch blocked error', e)
  } finally {
    loading.value.blocked = false
  }
}

function formatMs(ms: number) {
  if (!ms && ms !== 0) return '-'
  if (ms < 1000) return `${ms.toFixed(0)}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

onMounted(() => {
  fetchTasks()
  fetchBottleneck()
  fetchBlocked()
})
</script>

<template>
  <div class="metrics-root">
    <!-- Task Metrics -->
    <section class="glass-card metric-section">
      <div class="section-head">
        <h2><Activity :size="18" class="head-icon" /> {{ t('metrics.taskMetrics') }}</h2>
        <button class="btn-refresh" @click="fetchTasks">
          {{ t('actions.refresh') }}
        </button>
      </div>
      <div class="section-body">
        <div v-if="loading.tasks" class="empty">Loading…</div>
        <div v-else-if="taskMetrics.length === 0" class="empty">{{ t('metrics.noData') }}</div>
        <div v-else class="table-wrap custom-scrollbar">
          <table class="data-table">
            <thead>
              <tr>
                <th>{{ t('tasks.id') }}</th>
                <th>{{ t('tasks.status') }}</th>
                <th>{{ t('metrics.calls') }}</th>
                <th>{{ t('metrics.avgDuration') }}</th>
                <th>{{ t('metrics.minDuration') }}</th>
                <th>{{ t('metrics.maxDuration') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in taskMetrics" :key="m.task_id">
                <td class="mono">{{ m.task_id }}</td>
                <td>
                  <span class="badge" :class="m.status">{{ m.status }}</span>
                </td>
                <td class="mono">{{ m.call_count ?? 0 }}</td>
                <td class="mono">{{ formatMs(m.avg_duration_ms) }}</td>
                <td class="mono">{{ formatMs(m.min_duration_ms) }}</td>
                <td class="mono">{{ formatMs(m.max_duration_ms) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- Bottleneck -->
    <section class="glass-card metric-section">
      <div class="section-head">
        <h2><Timer :size="18" class="head-icon" /> {{ t('metrics.bottleneck') }}</h2>
        <button class="btn-refresh" @click="fetchBottleneck">
          {{ t('actions.refresh') }}
        </button>
      </div>
      <div class="section-body">
        <div v-if="loading.bottleneck" class="empty">Loading…</div>
        <div v-else-if="bottlenecks.length === 0" class="empty">{{ t('metrics.noData') }}</div>
        <div v-else class="cards-grid">
          <div v-for="b in bottlenecks" :key="b.task_id" class="info-card">
            <div class="info-id mono">{{ b.task_id }}</div>
            <div class="info-row">
              <span class="info-label">{{ t('metrics.avgDuration') }}</span>
              <span class="info-value">{{ formatMs(b.avg_duration_ms) }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">{{ t('metrics.maxDuration') }}</span>
              <span class="info-value">{{ formatMs(b.max_duration_ms) }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">{{ t('metrics.calls') }}</span>
              <span class="info-value">{{ b.call_count ?? 0 }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Blocked -->
    <section class="glass-card metric-section">
      <div class="section-head">
        <h2><AlertTriangle :size="18" class="head-icon" /> {{ t('metrics.blocked') }}</h2>
        <button class="btn-refresh" @click="fetchBlocked">
          {{ t('actions.refresh') }}
        </button>
      </div>
      <div class="section-body">
        <div v-if="loading.blocked" class="empty">Loading…</div>
        <div v-else-if="blocked.length === 0" class="empty">{{ t('metrics.noData') }}</div>
        <div v-else class="table-wrap custom-scrollbar">
          <table class="data-table">
            <thead>
              <tr>
                <th>{{ t('tasks.id') }}</th>
                <th>{{ t('metrics.blockedBy') }}</th>
                <th>{{ t('tasks.status') }}</th>
                <th>Depth</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="b in blocked" :key="b.blocked_task_id + b.blocker_task_id">
                <td class="mono">{{ b.blocked_task_id }}</td>
                <td class="mono">{{ b.blocker_task_id }}</td>
                <td>
                  <span class="badge" :class="b.blocker_status">{{ b.blocker_status }}</span>
                </td>
                <td class="mono">{{ b.depth }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.metrics-root {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.metric-section {
  overflow: hidden;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--z-border);
}

.section-head h2 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--z-text-primary);
  font-family: var(--font-display);
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.head-icon { color: var(--z-accent-cyan); opacity: 0.9; }

.btn-refresh {
  appearance: none;
  border: 1px solid var(--z-border);
  background: rgba(255,255,255,0.04);
  color: #e2e8f0;
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.35rem 0.7rem;
  border-radius: 0.4rem;
  cursor: pointer;
  transition: all 0.2s ease;
}
.btn-refresh:hover { background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.14); }

.section-body {
  padding: 1rem 1.25rem;
}

.empty {
  color: var(--z-text-muted);
  font-size: 0.9rem;
  padding: 1rem 0;
}

.table-wrap {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.data-table thead {
  background: rgba(255,255,255,0.02);
}

.data-table th {
  padding: 0.7rem 0.8rem;
  text-align: left;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--z-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.data-table td {
  padding: 0.75rem 0.8rem;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  color: #e2e8f0;
}

.data-table tbody tr:hover {
  background: rgba(255,255,255,0.025);
}

.mono { font-family: var(--font-mono); }

.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  background: rgba(255,255,255,0.08);
  color: #e2e8f0;
}
.badge.completed { background: rgba(52,211,153,0.15); color: var(--z-success); }
.badge.running { background: rgba(34,211,238,0.15); color: var(--z-accent-cyan); }
.badge.failed { background: rgba(251,113,133,0.15); color: var(--z-danger); }
.badge.pending { background: rgba(148,163,184,0.15); color: var(--z-text-secondary); }
.badge.paused { background: rgba(167,139,250,0.15); color: var(--z-violet); }

.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.75rem;
}

.info-card {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 0.75rem;
  padding: 0.9rem;
}

.info-id {
  font-weight: 600;
  color: var(--z-accent-cyan);
  margin-bottom: 0.5rem;
}

.info-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.85rem;
  padding: 0.25rem 0;
}

.info-label {
  color: var(--z-text-secondary);
}

.info-value {
  color: #e2e8f0;
  font-weight: 500;
  font-family: var(--font-mono);
}
</style>
