<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const emit = defineEmits<{
  (e: 'refresh'): void
}>()

interface ControlStatus {
  scheduler: { running: boolean; pid?: number }
  workers: { count: number; pids?: number[] }
  queue: { size: number }
}

const status = ref<ControlStatus | null>(null)
const scaleTarget = ref(3)
const loading = ref<Record<string, boolean>>({})

async function fetchStatus() {
  try {
    const res = await fetch('/control/status')
    if (res.ok) {
      status.value = await res.json()
      if (status.value) {
        scaleTarget.value = status.value.workers.count || 1
      }
    }
  } catch (e) {
    console.error('fetch control status error', e)
  }
}

async function apiPost(path: string, body?: object) {
  loading.value[path] = true
  try {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!res.ok) throw new Error(`${res.status}`)
    await fetchStatus()
    emit('refresh')
  } catch (e) {
    console.error(`POST ${path} error`, e)
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

onMounted(() => {
  fetchStatus()
})
</script>

<template>
  <section class="control-grid">
    <!-- Plan -->
    <div class="glass card">
      <div class="card-head">
        <div class="card-title">{{ t('control.plan') }}</div>
      </div>
      <div class="card-body">
        <button class="btn-primary" :disabled="loading['/control/import']" @click="planImport">
          {{ t('control.import') }}
        </button>
      </div>
    </div>

    <!-- Scheduler -->
    <div class="glass card">
      <div class="card-head">
        <div class="card-title">{{ t('control.scheduler') }}</div>
        <span
          class="status-pill"
          :class="status?.scheduler?.running ? 'online' : 'offline'"
        >
          {{ status?.scheduler?.running ? t('control.running') : t('control.stopped') }}
        </span>
      </div>
      <div class="card-body row">
        <button
          class="btn-primary"
          :disabled="loading['/control/scheduler/start'] || status?.scheduler?.running"
          @click="schedulerStart"
        >{{ t('control.start') }}</button>
        <button
          class="btn-warn"
          :disabled="loading['/control/scheduler/stop'] || !status?.scheduler?.running"
          @click="schedulerStop"
        >{{ t('control.stop') }}</button>
        <button
          class="btn-secondary"
          :disabled="loading['/control/scheduler/tick']"
          @click="schedulerTick"
        >{{ t('control.tick') }}</button>
      </div>
    </div>

    <!-- Workers -->
    <div class="glass card">
      <div class="card-head">
        <div class="card-title">{{ t('control.workers') }}</div>
        <span class="count-pill">{{ t('control.current') }}: {{ status?.workers?.count ?? '-' }}</span>
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
            />
          </label>
          <button
            class="btn-primary"
            :disabled="loading['/control/workers/scale']"
            @click="workersScale"
          >{{ t('control.scale') }}</button>
        </div>
        <button
          class="btn-warn"
          :disabled="loading['/control/workers/stop']"
          @click="workersStop"
        >{{ t('control.stop') }}</button>
      </div>
    </div>

    <!-- Global -->
    <div class="glass card">
      <div class="card-head">
        <div class="card-title">{{ t('control.global') }}</div>
      </div>
      <div class="card-body">
        <button class="btn-primary" :disabled="loading['/control/global/run']" @click="globalRun">
          {{ t('control.runAll') }}
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.control-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}

@media (min-width: 640px) {
  .control-grid { grid-template-columns: repeat(2, 1fr); }
}

.card {
  border-radius: 1rem;
  padding: 1.1rem;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.card-title {
  font-size: 1rem;
  font-weight: 600;
  color: #f8fafc;
}

.status-pill {
  font-size: 0.75rem;
  padding: 0.25rem 0.6rem;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.03);
}

.status-pill.online { color: #34d399; border-color: rgba(52,211,153,0.25); }
.status-pill.offline { color: #fb7185; border-color: rgba(251,113,133,0.25); }

.count-pill {
  font-size: 0.75rem;
  padding: 0.25rem 0.6rem;
  border-radius: 0.375rem;
  background: rgba(255,255,255,0.05);
  color: #e2e8f0;
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  align-items: flex-start;
}

.card-body.row {
  flex-direction: row;
  flex-wrap: wrap;
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
  gap: 0.35rem;
  flex: 1;
  color: #94a3b8;
  font-size: 0.85rem;
}

.slider-label b { color: #f8fafc; }

.slider {
  width: 100%;
  accent-color: #22d3ee;
}

button {
  appearance: none;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: #e2e8f0;
  font-size: 0.85rem;
  font-weight: 500;
  padding: 0.45rem 0.9rem;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary { color: #22d3ee; }
.btn-primary:hover:not(:disabled) { background: rgba(34,211,238,0.12); border-color: rgba(34,211,238,0.25); }

.btn-warn { color: #fbbf24; }
.btn-warn:hover:not(:disabled) { background: rgba(251,191,36,0.12); border-color: rgba(251,191,36,0.25); }

.btn-secondary { color: #94a3b8; }
.btn-secondary:hover:not(:disabled) { background: rgba(148,163,184,0.12); border-color: rgba(148,163,184,0.25); }
</style>
