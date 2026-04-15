<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Info, Play, CheckCircle2, XCircle, PauseCircle, RotateCcw, ShieldAlert, ShieldCheck, Activity, Mail, Layers, RefreshCw, AlertCircle, Search, Clock } from 'lucide-vue-next'

const { t } = useI18n()

const props = defineProps<{
  events: { time: string; event: string; data: any }[]
}>()

const historyEvents = ref<{ id: number; ts: string; event_type: string; agent_id: string | null; task_id: string | null; payload: any }[]>([])
const filterType = ref('')
const filterTask = ref('')
const filterAgent = ref('')
const historyLoading = ref(false)
const historyOffset = ref(0)
const historyLimit = 50
const hasMore = ref(true)
const showHistory = ref(false)

async function fetchHistory(reset = true) {
  historyLoading.value = true
  if (reset) {
    historyOffset.value = 0
    hasMore.value = true
  }
  const params = new URLSearchParams()
  params.set('limit', String(historyLimit))
  params.set('offset', String(historyOffset.value))
  if (filterType.value.trim()) params.set('event_type', filterType.value.trim())
  if (filterTask.value.trim()) params.set('task_id', filterTask.value.trim())
  if (filterAgent.value.trim()) params.set('agent_id', filterAgent.value.trim())
  try {
    const res = await fetch(`/events?${params.toString()}`)
    const data = await res.json()
    if (reset) {
      historyEvents.value = data
    } else {
      historyEvents.value.push(...data)
    }
    if (data.length < historyLimit) hasMore.value = false
    historyOffset.value += data.length
  } catch (e) {
    console.error('fetch history error', e)
  } finally {
    historyLoading.value = false
  }
}

function loadMore() {
  fetchHistory(false)
}

function isProgress(ev: { event_type: string; payload: any }) {
  return ev.event_type === 'task.progress' && ev.payload?.progress
}

function stepColor(step: string) {
  const map: Record<string, string> = {
    planning: '#a78bfa',
    reading: '#94a3b8',
    writing: '#22d3ee',
    testing: '#fbbf24',
    reviewing: '#f97316',
    completed: '#34d399',
  }
  return map[step] || '#94a3b8'
}

function stepLabel(step: string) {
  return step || 'progress'
}

function eventIcon(event: string) {
  if (event.includes('started')) return Play
  if (event.includes('completed')) return CheckCircle2
  if (event.includes('failed')) return XCircle
  if (event.includes('recovered')) return RotateCcw
  if (event.includes('quarantine')) return ShieldAlert
  if (event.includes('unquarantine')) return ShieldCheck
  if (event.includes('pause')) return PauseCircle
  if (event.includes('progress')) return Activity
  if (event.includes('mailbox')) return Mail
  if (event.includes('phase') || event.includes('milestone')) return Layers
  if (event.includes('config.reload_failed')) return AlertCircle
  if (event.includes('config.reloaded')) return RefreshCw
  return Info
}

function eventColor(event: string) {
  if (event.includes('started')) return 'var(--z-accent-cyan)'
  if (event.includes('completed')) return 'var(--z-success)'
  if (event.includes('failed')) return 'var(--z-danger)'
  if (event.includes('recovered')) return 'var(--z-violet)'
  if (event.includes('quarantine')) return 'var(--z-danger)'
  if (event.includes('progress')) return 'var(--z-accent-cyan)'
  if (event.includes('config.reload_failed')) return 'var(--z-danger)'
  if (event.includes('config.reloaded')) return 'var(--z-accent-cyan)'
  return 'var(--z-text-secondary)'
}

function formatTime(ts: string) {
  try {
    return new Date(ts).toLocaleTimeString()
  } catch {
    return ts
  }
}

onMounted(() => {
  fetchHistory()
})
</script>

<template>
  <section class="glass-card panel events-panel">
    <div class="panel-head">
      <h2>{{ showHistory ? t('events.history') : t('events.title') }}</h2>
      <div class="head-actions">
        <button class="tab-btn" :class="{ active: !showHistory }" @click="showHistory = false">
          Live
        </button>
        <button class="tab-btn" :class="{ active: showHistory }" @click="showHistory = true">
          {{ t('events.history') }}
        </button>
      </div>
    </div>

    <!-- Live stream -->
    <div v-if="!showHistory" class="events-body custom-scrollbar">
      <transition-group name="ev" tag="ul" class="events-list">
        <li v-for="(ev, idx) in events" :key="idx" class="event-row" :class="{ 'progress-row': isProgress({ event_type: ev.event, payload: ev.data }) }">
          <template v-if="isProgress({ event_type: ev.event, payload: ev.data })">
            <div class="progress-meta">
              <span class="timestamp">{{ ev.time }}</span>
              <span class="progress-source">{{ ev.data.source === 'http' ? 'HTTP' : 'FILE' }}</span>
            </div>
            <div class="progress-content">
              <span class="progress-step" :style="{ backgroundColor: stepColor(ev.data.progress.step) + '22', color: stepColor(ev.data.progress.step), borderColor: stepColor(ev.data.progress.step) + '44' }">
                {{ stepLabel(ev.data.progress.step) }}
              </span>
              <span class="progress-message">{{ ev.data.progress.message }}</span>
            </div>
            <div class="progress-task">Task: {{ ev.data.task_id }}</div>
          </template>
          <template v-else>
            <div class="event-meta">
              <span class="timestamp">{{ ev.time }}</span>
              <span class="event-badge" :style="{ color: eventColor(ev.event), borderColor: eventColor(ev.event) + '33', background: eventColor(ev.event) + '12' }">
                <component :is="eventIcon(ev.event)" :size="12" />
                <span>{{ ev.event }}</span>
              </span>
            </div>
            <div class="event-data">{{ JSON.stringify(ev.data) }}</div>
          </template>
        </li>
      </transition-group>
      <div v-if="events.length === 0" class="empty-events">
        <p>{{ t('events.empty') }}</p>
      </div>
    </div>

    <!-- History -->
    <div v-else class="events-body custom-scrollbar">
      <div class="history-filters">
        <div class="filter-field">
          <Search :size="12" />
          <input v-model="filterType" type="text" :placeholder="t('events.filterType')" @keydown.enter="fetchHistory()" />
        </div>
        <div class="filter-field">
          <Search :size="12" />
          <input v-model="filterTask" type="text" :placeholder="t('events.filterTask')" @keydown.enter="fetchHistory()" />
        </div>
        <div class="filter-field">
          <Search :size="12" />
          <input v-model="filterAgent" type="text" :placeholder="t('events.filterAgent')" @keydown.enter="fetchHistory()" />
        </div>
        <button class="btn-search" @click="fetchHistory()">
          <Search :size="13" /> {{ t('actions.search') }}
        </button>
      </div>

      <div v-if="historyLoading && historyEvents.length === 0" class="empty-events">Loading…</div>
      <ul v-else class="events-list">
        <li v-for="ev in historyEvents" :key="ev.id" class="event-row" :class="{ 'progress-row': isProgress(ev) }">
          <template v-if="isProgress(ev)">
            <div class="progress-meta">
              <span class="timestamp">{{ formatTime(ev.ts) }}</span>
              <span class="progress-source">{{ ev.payload.source === 'http' ? 'HTTP' : 'FILE' }}</span>
            </div>
            <div class="progress-content">
              <span class="progress-step" :style="{ backgroundColor: stepColor(ev.payload.progress.step) + '22', color: stepColor(ev.payload.progress.step), borderColor: stepColor(ev.payload.progress.step) + '44' }">
                {{ stepLabel(ev.payload.progress.step) }}
              </span>
              <span class="progress-message">{{ ev.payload.progress.message }}</span>
            </div>
            <div class="progress-task">Task: {{ ev.task_id }}</div>
          </template>
          <template v-else>
            <div class="event-meta">
              <span class="timestamp"><Clock :size="11" /> {{ formatTime(ev.ts) }}</span>
              <span class="event-badge" :style="{ color: eventColor(ev.event_type), borderColor: eventColor(ev.event_type) + '33', background: eventColor(ev.event_type) + '12' }">
                <component :is="eventIcon(ev.event_type)" :size="12" />
                <span>{{ ev.event_type }}</span>
              </span>
            </div>
            <div class="event-data">{{ JSON.stringify(ev.payload) }}</div>
            <div v-if="ev.task_id || ev.agent_id" class="event-tags">
              <span v-if="ev.task_id" class="ev-tag">Task: {{ ev.task_id }}</span>
              <span v-if="ev.agent_id" class="ev-tag">Agent: {{ ev.agent_id }}</span>
            </div>
          </template>
        </li>
      </ul>
      <div v-if="historyEvents.length === 0" class="empty-events">
        <p>{{ t('events.empty') }}</p>
      </div>
      <div v-else-if="hasMore" class="load-more">
        <button class="btn-more" :disabled="historyLoading" @click="loadMore">
          {{ t('events.loadMore') }}
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.panel {
  overflow: hidden;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--z-border);
}

.panel-head h2 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--z-text-primary);
  font-family: var(--font-display);
}

.head-actions {
  display: inline-flex;
  gap: 0.25rem;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--z-border);
  border-radius: 0.5rem;
  padding: 0.2rem;
}

.tab-btn {
  appearance: none;
  border: none;
  background: transparent;
  color: var(--z-text-secondary);
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.35rem 0.65rem;
  border-radius: 0.35rem;
  cursor: pointer;
  transition: all 0.2s ease;
}
.tab-btn:hover { color: #e2e8f0; }
.tab-btn.active {
  background: rgba(34,211,238,0.18);
  color: var(--z-accent-cyan);
}

.events-body {
  padding: 0.75rem 1rem 1rem;
  max-height: 520px;
  overflow-y: auto;
}

.history-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.filter-field {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--z-border);
  border-radius: 0.5rem;
  padding: 0.35rem 0.6rem;
  color: var(--z-text-muted);
  min-width: 140px;
  flex: 1;
}
.filter-field input {
  appearance: none;
  border: none;
  background: transparent;
  color: #e2e8f0;
  font-size: 0.8rem;
  width: 100%;
}
.filter-field input:focus { outline: none; }

.btn-search {
  appearance: none;
  border: 1px solid rgba(34,211,238,0.22);
  background: rgba(34,211,238,0.1);
  color: var(--z-accent-cyan);
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.4rem 0.8rem;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.btn-search:hover { background: rgba(34,211,238,0.16); border-color: rgba(34,211,238,0.3); }

.events-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.event-row {
  padding: 0.65rem 0.85rem;
  border-radius: 0.65rem;
  background: rgba(255,255,255,0.02);
  border: 1px solid rgba(255,255,255,0.04);
  font-size: 0.8rem;
  font-family: var(--font-mono);
  transition: background 0.2s ease;
}
.event-row:hover {
  background: rgba(255,255,255,0.03);
}

.event-row.progress-row {
  background: rgba(255,255,255,0.025);
  border-left: 3px solid rgba(34,211,238,0.35);
}

.event-meta {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.3rem;
  flex-wrap: wrap;
}

.timestamp { color: var(--z-text-secondary); white-space: nowrap; display: inline-flex; align-items: center; gap: 0.25rem; }

.event-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-weight: 600;
  font-size: 0.72rem;
  padding: 0.2rem 0.5rem;
  border-radius: 0.35rem;
  border: 1px solid;
  font-family: var(--font-mono);
}

.event-data {
  color: #cbd5e1;
  opacity: 0.95;
  word-break: break-all;
}

.event-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.35rem;
}

.ev-tag {
  font-size: 0.7rem;
  padding: 0.15rem 0.4rem;
  border-radius: 0.3rem;
  background: rgba(255,255,255,0.06);
  color: var(--z-text-secondary);
}

.progress-meta {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.35rem;
}

.progress-source {
  font-size: 0.65rem;
  padding: 0.15rem 0.4rem;
  border-radius: 0.25rem;
  background: rgba(255,255,255,0.06);
  color: var(--z-text-secondary);
}

.progress-content {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
  margin-bottom: 0.25rem;
}

.progress-step {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.55rem;
  border-radius: 0.4rem;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  border: 1px solid;
}

.progress-message {
  color: #e2e8f0;
  font-weight: 500;
}

.progress-task {
  font-size: 0.7rem;
  color: var(--z-text-muted);
}

.empty-events {
  padding: 2.5rem;
  text-align: center;
  color: var(--z-text-muted);
  font-size: 0.9rem;
}

.load-more {
  display: flex;
  justify-content: center;
  padding: 0.75rem 0 0;
}

.btn-more {
  appearance: none;
  border: 1px solid var(--z-border);
  background: rgba(255,255,255,0.04);
  color: #e2e8f0;
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.4rem 0.9rem;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s ease;
}
.btn-more:hover { background: rgba(255,255,255,0.08); }

.ev-enter-active,
.ev-leave-active {
  transition: all 0.25s ease;
}
.ev-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}
.ev-leave-to {
  opacity: 0;
  transform: translateX(10px);
}
</style>
