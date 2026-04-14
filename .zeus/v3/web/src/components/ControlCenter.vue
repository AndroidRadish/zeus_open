<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Upload,
  Play,
  Square,
  Clock,
  Users,
  Rocket,
  Activity,
  CircleOff,
  Loader2,
  AlertCircle,
  Info,
} from 'lucide-vue-next'

const { t } = useI18n()

const emit = defineEmits<{
  (e: 'refresh'): void
}>()

interface Task {
  id: string
  title?: string
  worker_id?: string
  heartbeat_at?: string
  wave?: number
}

interface ControlStatus {
  scheduler: { running: boolean; pid?: number; state?: string; last_tick_at?: string | null }
  workers: { count: number; pids?: number[]; target?: number }
  queue: { size: number }
  last_import_at?: string | null
  last_event_at?: string | null
  running_tasks?: Task[]
}

const status = ref<ControlStatus | null>(null)
const scaleTarget = ref(3)
const loading = ref<Record<string, boolean>>({})
const available = ref<boolean | null>(null)
const error = ref<string | null>(null)

async function fetchStatus() {
  try {
    const res = await fetch('/control/status')
    if (res.status === 503) {
      available.value = false
      status.value = null
      return
    }
    if (!res.ok) {
      available.value = true
      error.value = `${t('feedback.error')} HTTP ${res.status}`
      return
    }
    available.value = true
    error.value = null
    const data = await res.json() as ControlStatus
    status.value = data
    if (data) {
      scaleTarget.value = data.workers?.count || 1
    }
  } catch (e: any) {
    console.error('fetch control status error', e)
    error.value = e?.message || String(e)
  }
}

async function apiPost(path: string, body?: object) {
  if (!available.value) return
  loading.value[path] = true
  error.value = null
  try {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new Error(`HTTP ${res.status}${text ? ': ' + text : ''}`)
    }
    await fetchStatus()
    emit('refresh')
  } catch (e: any) {
    console.error(`POST ${path} error`, e)
    error.value = e?.message || String(e)
  } finally {
    loading.value[path] = false
  }
}

function schedulerStart() { apiPost('/control/scheduler/start') }
function schedulerStop() { apiPost('/control/scheduler/stop') }
function schedulerTick() { apiPost('/control/scheduler/tick') }
function workersScale() { apiPost('/control/workers/scale', { count: scaleTarget.value }) }
function workersStop() { apiPost('/control/workers/stop') }
function planImport() { apiPost('/control/import') }
function globalRun() { apiPost('/control/global/run') }

const schedulerRunning = computed(() => !!status.value?.scheduler?.running)
const schedulerState = computed(() => status.value?.scheduler?.state ?? 'unknown')
const workerCount = computed(() => status.value?.workers?.count ?? 0)
const workerTarget = computed(() => status.value?.workers?.target ?? 0)
const queueSize = computed(() => status.value?.queue?.size ?? 0)
const lastImport = computed(() => status.value?.last_import_at || '-')
const lastTick = computed(() => status.value?.scheduler?.last_tick_at || '-')
const lastEvent = computed(() => status.value?.last_event_at || '-')
const ghostState = computed(() => schedulerRunning.value && schedulerState.value !== 'running')
const healthColor = computed(() => {
  if (ghostState.value) return 'warn'
  if (schedulerRunning.value) return 'ok'
  return 'neutral'
})

const runningTasks = computed(() => status.value?.running_tasks || [])
const workerCards = computed(() => {
  const map = new Map<string, Task[]>()
  for (const task of runningTasks.value) {
    const wid = task.worker_id || 'unknown'
    if (!map.has(wid)) map.set(wid, [])
    map.get(wid)!.push(task)
  }
  return Array.from(map.entries()).map(([worker_id, tasks]) => ({ worker_id, tasks }))
})

function formatAgo(iso: string | null | undefined) {
  if (!iso || iso === '-') return '-'
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 0) return 'just now'
  const sec = Math.floor(diff / 1000)
  if (sec < 60) return `${sec}s ago`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  return `${hr}h ago`
}

onMounted(() => {
  fetchStatus()
})
</script>

<template>
  <section class="control-root">
    <!-- Global error toast -->
    <div v-if="error" class="error-banner">
      <AlertCircle class="icon" :size="18" />
      <span class="error-text">{{ error }}</span>
      <button class="error-close" @click="error = null">×</button>
    </div>

    <!-- Health banner -->
    <div v-if="available !== false && status" class="health-banner" :class="healthColor">
      <div class="health-row">
        <div class="health-item">
          <span class="health-label">Scheduler</span>
          <span class="health-dot" :class="schedulerRunning ? 'ok' : 'off'" />
          <span class="health-value">{{ schedulerRunning ? 'Running' : 'Stopped' }}</span>
          <span v-if="ghostState" class="health-warn">(ghost: {{ schedulerState }})</span>
          <span v-else-if="schedulerState" class="health-meta">({{ schedulerState }})</span>
        </div>
        <div class="health-divider" />
        <div class="health-item">
          <span class="health-label">Workers</span>
          <span class="health-value">{{ workerCount }} / {{ workerTarget }}</span>
        </div>
        <div class="health-divider" />
        <div class="health-item">
          <span class="health-label">Queue</span>
          <span class="health-value">{{ queueSize }}</span>
        </div>
        <div class="health-divider" />
        <div class="health-item">
          <span class="health-label">Last Tick</span>
          <span class="health-value" :title="lastTick">{{ formatAgo(lastTick) }}</span>
        </div>
        <div class="health-divider" />
        <div class="health-item">
          <span class="health-label">Last Event</span>
          <span class="health-value" :title="lastEvent">{{ formatAgo(lastEvent) }}</span>
        </div>
      </div>
    </div>

    <!-- Worker status cards -->
    <div v-if="available !== false && workerCards.length" class="worker-cards">
      <div v-for="card in workerCards" :key="card.worker_id" class="worker-card">
        <div class="worker-head">
          <span class="worker-id">{{ card.worker_id }}</span>
          <span class="worker-badge">{{ card.tasks.length }} task{{ card.tasks.length > 1 ? 's' : '' }}</span>
        </div>
        <div class="worker-body">
          <div v-for="task in card.tasks" :key="task.id" class="worker-task">
            <span class="task-mono">{{ task.id }}</span>
            <span class="task-title">{{ task.title || t('tasks.unnamed') }}</span>
            <span class="task-hb" :title="task.heartbeat_at">HB {{ formatAgo(task.heartbeat_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Unavailable notice -->
    <div v-if="available === false" class="unavailable-banner">
      <Info class="icon" :size="18" />
      <div>
        <div class="unavailable-title">{{ t('control.unavailableTitle') }}</div>
        <div class="unavailable-desc">{{ t('control.unavailableDesc') }}</div>
      </div>
    </div>

    <div class="control-grid" :class="{ disabled: available === false }">
      <!-- Plan -->
      <div class="glass card">
        <div class="card-head">
          <div class="card-title">
            <Upload :size="16" class="head-icon" />
            {{ t('control.plan') }}
          </div>
        </div>
        <div class="card-body">
          <div class="meta-row">
            <span class="meta-label">{{ t('control.lastImport') }}</span>
            <span class="meta-value">{{ lastImport }}</span>
          </div>
          <button
            class="btn-primary"
            :disabled="loading['/control/import'] || available === false"
            @click="planImport"
          >
            <Loader2 v-if="loading['/control/import']" class="spinner" :size="14" />
            <Upload v-else :size="14" />
            <span>{{ t('control.import') }}</span>
          </button>
        </div>
      </div>

      <!-- Scheduler -->
      <div class="glass card">
        <div class="card-head">
          <div class="card-title">
            <Clock :size="16" class="head-icon" />
            {{ t('control.scheduler') }}
          </div>
          <span
            class="status-pill"
            :class="schedulerRunning ? 'online' : 'offline'"
          >
            <Activity v-if="schedulerRunning" :size="12" />
            <CircleOff v-else :size="12" />
            {{ schedulerRunning ? t('control.running') : t('control.stopped') }}
          </span>
        </div>
        <div class="card-body row">
          <button
            class="btn-primary"
            :disabled="loading['/control/scheduler/start'] || schedulerRunning || available === false"
            @click="schedulerStart"
          >
            <Loader2 v-if="loading['/control/scheduler/start']" class="spinner" :size="14" />
            <Play v-else :size="14" />
            <span>{{ t('control.start') }}</span>
          </button>
          <button
            class="btn-warn"
            :disabled="loading['/control/scheduler/stop'] || !schedulerRunning || available === false"
            @click="schedulerStop"
          >
            <Loader2 v-if="loading['/control/scheduler/stop']" class="spinner" :size="14" />
            <Square v-else :size="14" />
            <span>{{ t('control.stop') }}</span>
          </button>
          <button
            class="btn-secondary"
            :disabled="loading['/control/scheduler/tick'] || available === false"
            @click="schedulerTick"
          >
            <Loader2 v-if="loading['/control/scheduler/tick']" class="spinner" :size="14" />
            <Clock v-else :size="14" />
            <span>{{ t('control.tick') }}</span>
          </button>
        </div>
      </div>

      <!-- Workers -->
      <div class="glass card">
        <div class="card-head">
          <div class="card-title">
            <Users :size="16" class="head-icon" />
            {{ t('control.workers') }}
          </div>
          <div class="head-badges">
            <span class="count-pill">{{ t('control.current') }}: {{ workerCount }}</span>
            <span class="count-pill">{{ t('control.queue') }}: {{ queueSize }}</span>
          </div>
        </div>
        <div class="card-body">
          <div class="slider-row">
            <label class="slider-label">
              <span>{{ t('control.target') }}: <b>{{ scaleTarget }}</b></span>
              <input
                type="range"
                min="1"
                max="10"
                v-model.number="scaleTarget"
                class="slider"
                :disabled="available === false"
              />
            </label>
            <button
              class="btn-primary"
              :disabled="loading['/control/workers/scale'] || available === false"
              @click="workersScale"
            >
              <Loader2 v-if="loading['/control/workers/scale']" class="spinner" :size="14" />
              <Users v-else :size="14" />
              <span>{{ t('control.scale') }}</span>
            </button>
          </div>
          <button
            class="btn-warn"
            :disabled="loading['/control/workers/stop'] || available === false"
            @click="workersStop"
          >
            <Loader2 v-if="loading['/control/workers/stop']" class="spinner" :size="14" />
            <Square v-else :size="14" />
            <span>{{ t('control.stop') }}</span>
          </button>
        </div>
      </div>

      <!-- Global -->
      <div class="glass card card-global">
        <div class="card-head">
          <div class="card-title">
            <Rocket :size="16" class="head-icon" />
            {{ t('control.global') }}
          </div>
        </div>
        <div class="card-body">
          <p class="hint">{{ t('control.globalHint') }}</p>
          <button
            class="btn-primary btn-large"
            :disabled="loading['/control/global/run'] || available === false"
            @click="globalRun"
          >
            <Loader2 v-if="loading['/control/global/run']" class="spinner" :size="16" />
            <Rocket v-else :size="16" />
            <span>{{ t('control.runAll') }}</span>
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.control-root {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.control-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.85rem;
}

@media (min-width: 768px) {
  .control-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .card-global {
    grid-column: span 2;
  }
}

.control-grid.disabled {
  opacity: 0.65;
  pointer-events: none;
}

.card {
  border-radius: 0.875rem;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  transition: opacity 0.2s ease;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.65rem;
  gap: 0.5rem;
}

.card-title {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.95rem;
  font-weight: 600;
  color: #f8fafc;
}

.head-icon {
  color: #22d3ee;
  opacity: 0.9;
}

.head-badges {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.72rem;
  padding: 0.25rem 0.55rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
}

.status-pill.online {
  color: #34d399;
  border-color: rgba(52, 211, 153, 0.25);
  background: rgba(52, 211, 153, 0.08);
}
.status-pill.offline {
  color: #fb7185;
  border-color: rgba(251, 113, 133, 0.25);
  background: rgba(251, 113, 133, 0.08);
}

.count-pill {
  font-size: 0.72rem;
  padding: 0.25rem 0.5rem;
  border-radius: 0.375rem;
  background: rgba(255, 255, 255, 0.06);
  color: #e2e8f0;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  align-items: flex-start;
}

.card-body.row {
  flex-direction: row;
  flex-wrap: wrap;
}

.meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  font-size: 0.8rem;
  color: #94a3b8;
}

.meta-value {
  color: #e2e8f0;
  font-weight: 500;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
}

.slider-label {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  flex: 1;
  color: #94a3b8;
  font-size: 0.8rem;
}

.slider-label b {
  color: #f8fafc;
}

.slider {
  width: 100%;
  accent-color: #22d3ee;
}

.hint {
  margin: 0;
  font-size: 0.8rem;
  color: #94a3b8;
}

button {
  appearance: none;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #e2e8f0;
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.4rem 0.75rem;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn-large {
  padding: 0.55rem 1rem;
  font-size: 0.9rem;
}

.btn-primary {
  color: #22d3ee;
  border-color: rgba(34, 211, 238, 0.15);
}
.btn-primary:hover:not(:disabled) {
  background: rgba(34, 211, 238, 0.12);
  border-color: rgba(34, 211, 238, 0.3);
}

.btn-warn {
  color: #fbbf24;
  border-color: rgba(251, 191, 36, 0.15);
}
.btn-warn:hover:not(:disabled) {
  background: rgba(251, 191, 36, 0.12);
  border-color: rgba(251, 191, 36, 0.3);
}

.btn-secondary {
  color: #94a3b8;
  border-color: rgba(148, 163, 184, 0.15);
}
.btn-secondary:hover:not(:disabled) {
  background: rgba(148, 163, 184, 0.12);
  border-color: rgba(148, 163, 184, 0.3);
}

.spinner {
  animation: spin 1.2s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Banners */
.error-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 0.85rem;
  border-radius: 0.625rem;
  background: rgba(251, 113, 133, 0.12);
  border: 1px solid rgba(251, 113, 133, 0.25);
  color: #fb7185;
  font-size: 0.85rem;
}

.error-text {
  flex: 1;
}

.error-close {
  appearance: none;
  background: transparent;
  border: none;
  color: inherit;
  font-size: 1rem;
  padding: 0;
  width: 1.5rem;
  height: 1.5rem;
  display: grid;
  place-items: center;
  cursor: pointer;
  opacity: 0.8;
}
.error-close:hover {
  opacity: 1;
}

.unavailable-banner {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  padding: 0.85rem 1rem;
  border-radius: 0.625rem;
  background: rgba(148, 163, 184, 0.1);
  border: 1px solid rgba(148, 163, 184, 0.2);
  color: #e2e8f0;
}

.unavailable-title {
  font-weight: 600;
  font-size: 0.9rem;
  margin-bottom: 0.15rem;
}

.unavailable-desc {
  font-size: 0.8rem;
  color: #94a3b8;
  line-height: 1.4;
}

.unavailable-banner .icon {
  color: #94a3b8;
  margin-top: 0.1rem;
  flex-shrink: 0;
}

.error-banner .icon {
  flex-shrink: 0;
}

.health-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 0.85rem;
  border-radius: 0.625rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 0.85rem;
  background: rgba(255, 255, 255, 0.03);
  color: #e2e8f0;
}
.health-banner.ok {
  border-color: rgba(52, 211, 153, 0.2);
  background: rgba(52, 211, 153, 0.06);
}
.health-banner.warn {
  border-color: rgba(251, 191, 36, 0.25);
  background: rgba(251, 191, 36, 0.08);
  color: #fbbf24;
}
.health-banner.neutral {
  border-color: rgba(148, 163, 184, 0.2);
  background: rgba(148, 163, 184, 0.08);
}
.health-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}
.health-item {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.health-label {
  font-size: 0.75rem;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
.health-value {
  font-weight: 600;
  color: #f8fafc;
}
.health-meta {
  font-size: 0.75rem;
  color: #94a3b8;
}
.health-warn {
  font-size: 0.75rem;
  color: #fbbf24;
  font-weight: 500;
}
.health-dot {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 999px;
  background: #64748b;
}
.health-dot.ok {
  background: #34d399;
}
.health-dot.off {
  background: #fb7185;
}
.health-divider {
  width: 1px;
  height: 0.9rem;
  background: rgba(255, 255, 255, 0.1);
}

.worker-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.75rem;
}

.worker-card {
  border-radius: 0.75rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

.worker-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem 0.8rem;
  background: rgba(255, 255, 255, 0.025);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.worker-id {
  font-size: 0.8rem;
  font-weight: 600;
  color: #22d3ee;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.worker-badge {
  font-size: 0.7rem;
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
  border: 1px solid rgba(99, 102, 241, 0.25);
}

.worker-body {
  padding: 0.5rem 0.8rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.worker-task {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  font-size: 0.8rem;
}

.task-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-weight: 600;
  color: #f8fafc;
}

.task-title {
  color: #cbd5e1;
  flex: 1;
}

.task-hb {
  font-size: 0.7rem;
  color: #94a3b8;
}
</style>
