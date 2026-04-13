<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t, locale } = useI18n()

interface Task {
  id: string
  title?: string
  wave?: number
  status: string
  passes: boolean
}

interface Metrics {
  total_tasks: number
  completed: number
  failed: number
  pending: number
  running: number
  pass_rate: number
}

const tasks = ref<Task[]>([])
const metrics = ref<Metrics | null>(null)
const events = ref<{ time: string; event: string; data: any }[]>([])
const connected = ref(false)

let es: EventSource | null = null
let pollTimer: number | null = null

function setLang(lang: string) {
  locale.value = lang
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('zeus-lang', lang)
  }
}

async function fetchMetrics() {
  try {
    const res = await fetch('/metrics/summary')
    metrics.value = await res.json()
  } catch (e) {
    console.error('fetch metrics error', e)
  }
}

async function fetchTasks() {
  try {
    const res = await fetch('/tasks')
    tasks.value = await res.json()
  } catch (e) {
    console.error('fetch tasks error', e)
  }
}

function connectSSE() {
  es = new EventSource('/events/stream')
  es.onopen = () => { connected.value = true }
  es.onerror = () => { connected.value = false }
  es.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data)
      events.value.unshift({
        time: new Date().toLocaleTimeString(locale.value === 'zh' ? 'zh-CN' : 'en-US'),
        event: msg.event,
        data: msg.data,
      })
      if (events.value.length > 80) events.value.pop()
      if (msg.event && msg.event.startsWith('task.')) {
        fetchTasks()
        fetchMetrics()
      }
    } catch (e) {
      console.error('sse parse error', e)
    }
  }
}

onMounted(() => {
  fetchMetrics()
  fetchTasks()
  connectSSE()
  pollTimer = window.setInterval(() => {
    fetchMetrics()
    fetchTasks()
  }, 5000)
})

onUnmounted(() => {
  es?.close()
  if (pollTimer) clearInterval(pollTimer)
})

const statusList = ['pending', 'running', 'completed', 'failed'] as const

function statusLabel(status: string) {
  const key = statusList.includes(status as any) ? status : 'pending'
  return t(`status.${key}`)
}

function statusDotClass(status: string) {
  const s = statusList.includes(status as any) ? status : 'pending'
  return `dot-${s}`
}

const sortedTasks = computed(() => {
  const order = ['running', 'pending', 'failed', 'completed']
  return [...tasks.value].sort((a, b) => {
    const ia = order.indexOf(a.status)
    const ib = order.indexOf(b.status)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })
})

const totalTasksForPercent = computed(() => {
  const m = metrics.value
  if (!m || m.total_tasks === 0) return 1
  return m.total_tasks
})

const passRateCircumference = 2 * Math.PI * 18
</script>

<template>
  <div class="dashboard">
    <!-- Header -->
    <header class="topbar">
      <div class="container header-inner">
        <div class="brand">
          <div class="logo">Z</div>
          <div>
            <div class="title">{{ t('app.title') }} <span class="accent">{{ t('app.version') }}</span></div>
            <div class="subtitle">{{ t('app.subtitle') }}</div>
          </div>
        </div>

        <div class="header-right">
          <!-- Lang switch -->
          <div class="lang-switch">
            <button
              @click="setLang('zh')"
              :class="['lang-btn', { active: locale === 'zh' }]"
            >{{ t('lang.zh') }}</button>
            <button
              @click="setLang('en')"
              :class="['lang-btn', { active: locale === 'en' }]"
            >{{ t('lang.en') }}</button>
          </div>

          <div class="connection" :class="connected ? 'online' : 'offline'">
            <span class="pulse-dot"></span>
            <span class="text">{{ connected ? t('connection.online') : t('connection.offline') }}</span>
          </div>
        </div>
      </div>
    </header>

    <!-- Main -->
    <main class="container content">
      <!-- Stats Cards -->
      <section class="stats-grid" v-if="metrics">
        <div class="glass card">
          <div class="card-top">
            <div>
              <div class="card-label">{{ t('stats.total') }}</div>
              <div class="card-value">{{ metrics.total_tasks }}</div>
            </div>
            <div class="icon-wrap icon-total">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect width="20" height="14" x="2" y="3" rx="2"/>
                <line x1="8" x2="16" y1="21" y2="21"/>
                <line x1="12" x2="12" y1="17" y2="21"/>
              </svg>
            </div>
          </div>
          <div class="card-bar"><div class="bar-fill" :style="{ width: '100%' }"></div></div>
        </div>

        <div class="glass card">
          <div class="card-top">
            <div>
              <div class="card-label">{{ t('stats.completed') }}</div>
              <div class="card-value text-emerald">{{ metrics.completed }}</div>
            </div>
            <div class="icon-wrap icon-emerald">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
            </div>
          </div>
          <div class="card-bar"><div class="bar-fill bar-emerald" :style="{ width: (metrics.completed / totalTasksForPercent * 100) + '%' }"></div></div>
        </div>

        <div class="glass card">
          <div class="card-top">
            <div>
              <div class="card-label">{{ t('stats.failed') }}</div>
              <div class="card-value text-rose">{{ metrics.failed }}</div>
            </div>
            <div class="icon-wrap icon-rose">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="15" x2="9" y1="9" y2="15"/>
                <line x1="9" x2="15" y1="9" y2="15"/>
              </svg>
            </div>
          </div>
          <div class="card-bar"><div class="bar-fill bar-rose" :style="{ width: (metrics.failed / totalTasksForPercent * 100) + '%' }"></div></div>
        </div>

        <div class="glass card">
          <div class="card-top">
            <div>
              <div class="card-label">{{ t('stats.pending') }}</div>
              <div class="card-value text-amber">{{ metrics.pending }}</div>
            </div>
            <div class="icon-wrap icon-amber">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <polyline points="12 6 12 12 16 14"/>
              </svg>
            </div>
          </div>
          <div class="card-bar"><div class="bar-fill bar-amber" :style="{ width: (metrics.pending / totalTasksForPercent * 100) + '%' }"></div></div>
        </div>

        <div class="glass card">
          <div class="card-top">
            <div>
              <div class="card-label">{{ t('stats.running') }}</div>
              <div class="card-value text-cyan">{{ metrics.running }}</div>
            </div>
            <div class="icon-wrap icon-cyan">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
              </svg>
            </div>
          </div>
          <div class="card-bar"><div class="bar-fill bar-cyan" :style="{ width: (metrics.running / totalTasksForPercent * 100) + '%' }"></div></div>
        </div>

        <div class="glass card">
          <div class="card-top">
            <div>
              <div class="card-label">{{ t('stats.passRate') }}</div>
              <div class="card-value">{{ (metrics.pass_rate * 100).toFixed(0) }}<small>%</small></div>
            </div>
            <div class="ring">
              <svg viewBox="0 0 40 40">
                <circle cx="20" cy="20" r="18" class="track"></circle>
                <circle cx="20" cy="20" r="18" class="fill"
                  :stroke-dasharray="`${passRateCircumference * (metrics.pass_rate || 0)} ${passRateCircumference}`"></circle>
              </svg>
            </div>
          </div>
          <div class="card-bar"><div class="bar-fill bar-violet" :style="{ width: (metrics.pass_rate * 100) + '%' }"></div></div>
        </div>
      </section>

      <div class="workspace">
        <!-- Tasks Table -->
        <section class="glass panel tasks-panel">
          <div class="panel-head">
            <h2>{{ t('tasks.title') }}</h2>
            <span class="count-badge">{{ tasks.length }}</span>
          </div>
          <div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th>{{ t('tasks.id') }}</th>
                  <th>{{ t('tasks.titleCol') }}</th>
                  <th>{{ t('tasks.wave') }}</th>
                  <th>{{ t('tasks.status') }}</th>
                  <th>{{ t('tasks.result') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="task in sortedTasks" :key="task.id">
                  <td class="mono bold">{{ task.id }}</td>
                  <td>{{ task.title || t('tasks.unnamed') }}</td>
                  <td class="mono">{{ task.wave ?? '-' }}</td>
                  <td>
                    <div class="status-cell">
                      <span class="status-dot" :class="statusDotClass(task.status)"></span>
                      <span>{{ statusLabel(task.status) }}</span>
                    </div>
                  </td>
                  <td>
                    <span class="result-badge" :class="task.passes ? 'pass' : 'fail'">
                      {{ task.passes ? t('result.pass') : t('result.fail') }}
                    </span>
                  </td>
                </tr>
                <tr v-if="tasks.length === 0">
                  <td colspan="5" class="empty-cell">{{ t('tasks.empty') }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- Live Events -->
        <section class="glass panel events-panel">
          <div class="panel-head">
            <h2>{{ t('events.title') }}</h2>
          </div>
          <div class="events-body custom-scrollbar">
            <transition-group name="ev" tag="ul" class="events-list">
              <li v-for="(ev, idx) in events" :key="idx" class="event-row">
                <div class="event-meta">
                  <span class="timestamp">{{ ev.time }}</span>
                  <span class="event-name">{{ ev.event }}</span>
                </div>
                <div class="event-data">{{ JSON.stringify(ev.data) }}</div>
              </li>
            </transition-group>
            <div v-if="events.length === 0" class="empty-events">
              <p>{{ t('events.empty') }}</p>
            </div>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.dashboard {
  min-height: 100dvh;
  background-color: #0a0a0f;
  background-image:
    radial-gradient(ellipse 80% 50% at 50% -10%, rgba(6,182,212,0.12), transparent),
    radial-gradient(ellipse 60% 40% at 80% 90%, rgba(99,102,241,0.08), transparent);
  color: #f8fafc;
  font-family: 'DM Sans', 'Noto Sans SC', system-ui, sans-serif;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding-left: 1.25rem;
  padding-right: 1.25rem;
}

.glass {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

/* Header */
.topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  background: rgba(10,10,15,0.55);
  backdrop-filter: blur(12px);
}

.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 4rem;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.logo {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 0.5rem;
  background: linear-gradient(135deg, #06b6d4, #6366f1);
  display: grid;
  place-items: center;
  color: white;
  font-weight: 700;
  font-size: 1.125rem;
  box-shadow: 0 4px 20px rgba(6,182,212,0.25);
}

.title {
  font-size: 1.125rem;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.2px;
}

.title .accent { color: #22d3ee; }

.subtitle {
  font-size: 0.75rem;
  color: #94a3b8;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.lang-switch {
  display: inline-flex;
  align-items: center;
  gap: 0.15rem;
  padding: 0.2rem;
  border-radius: 0.5rem;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
}

.lang-btn {
  appearance: none;
  border: none;
  background: transparent;
  color: #94a3b8;
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.3rem 0.6rem;
  border-radius: 0.35rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.lang-btn:hover { color: #e2e8f0; }
.lang-btn.active {
  background: rgba(6,182,212,0.18);
  color: #22d3ee;
}

.connection {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.85rem;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.03);
  font-size: 0.85rem;
}

.connection.online { color: #34d399; border-color: rgba(52,211,153,0.25); }
.connection.offline { color: #fb7185; border-color: rgba(251,113,133,0.25); }

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 8px currentColor;
}

/* Content */
.content {
  padding-top: 1.5rem;
  padding-bottom: 2rem;
}

/* Stats */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
  margin-bottom: 1.25rem;
}

@media (min-width: 640px) {
  .stats-grid { grid-template-columns: repeat(3, 1fr); }
}

.card {
  border-radius: 1rem;
  padding: 1.1rem;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.card:hover {
  transform: translateY(-2px);
  background: rgba(255,255,255,0.045);
  border-color: rgba(255,255,255,0.10);
  box-shadow: 0 8px 30px rgba(0,0,0,0.35);
}

.card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.card-label {
  font-size: 0.875rem;
  color: #94a3b8;
  font-weight: 500;
}

.card-value {
  margin-top: 0.35rem;
  font-size: 1.75rem;
  font-weight: 700;
  color: #f8fafc;
}

.card-value small { font-size: 0.65rem; opacity: 0.8; margin-left: 2px; }

.text-emerald { color: #34d399; }
.text-rose { color: #fb7185; }
.text-amber { color: #fbbf24; }
.text-cyan { color: #22d3ee; }

.icon-wrap {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 0.75rem;
  display: grid;
  place-items: center;
}

.icon-wrap svg { width: 1.4rem; height: 1.4rem; }

.icon-total { background: rgba(148,163,184,0.10); color: #94a3b8; }
.icon-emerald { background: rgba(52,211,153,0.10); color: #34d399; }
.icon-rose { background: rgba(251,113,133,0.10); color: #fb7185; }
.icon-amber { background: rgba(251,191,36,0.10); color: #fbbf24; }
.icon-cyan { background: rgba(34,211,238,0.10); color: #22d3ee; }

.card-bar {
  margin-top: 0.9rem;
  height: 4px;
  width: 100%;
  background: rgba(255,255,255,0.05);
  border-radius: 999px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: #94a3b8;
  border-radius: 999px;
  transition: width 0.7s ease;
}

.bar-emerald { background: #34d399; }
.bar-rose { background: #fb7185; }
.bar-amber { background: #fbbf24; }
.bar-cyan { background: #22d3ee; }
.bar-violet { background: #a78bfa; }

.ring {
  position: relative;
  width: 44px;
  height: 44px;
}

.ring svg {
  width: 44px;
  height: 44px;
  transform: rotate(-90deg);
}

.ring .track {
  fill: none;
  stroke: rgba(255,255,255,0.08);
  stroke-width: 4;
}

.ring .fill {
  fill: none;
  stroke: #a78bfa;
  stroke-width: 4;
  stroke-linecap: round;
  transition: stroke-dasharray 0.6s ease;
}

/* Workspace */
.workspace {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}

@media (min-width: 1024px) {
  .workspace { grid-template-columns: 1.4fr 0.6fr; gap: 1.25rem; }
}

.panel {
  border-radius: 1rem;
  overflow: hidden;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}

.panel-head h2 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #f8fafc;
}

.count-badge {
  font-size: 0.75rem;
  padding: 0.25rem 0.6rem;
  border-radius: 0.375rem;
  background: rgba(255,255,255,0.05);
  color: #e2e8f0;
}

/* Table */
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
  padding: 0.75rem 1rem;
  text-align: left;
  font-size: 0.75rem;
  font-weight: 500;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.data-table td {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  color: #e2e8f0;
}

.data-table tbody tr:hover {
  background: rgba(255,255,255,0.02);
}

.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
.bold { font-weight: 700; }

.status-cell {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  box-shadow: 0 0 8px currentColor;
}

.dot-pending { background: #fbbf24; color: #fbbf24; }
.dot-running { background: #22d3ee; color: #22d3ee; animation: pulseDot 1.4s ease-in-out infinite; }
.dot-completed { background: #34d399; color: #34d399; }
.dot-failed { background: #fb7185; color: #fb7185; }

@keyframes pulseDot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.55; transform: scale(0.85); }
}

.result-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.6rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.result-badge.pass { background: rgba(52,211,153,0.10); color: #34d399; }
.result-badge.fail { background: rgba(251,113,133,0.10); color: #fb7185; }

.empty-cell {
  text-align: center;
  color: #64748b;
  padding: 2.5rem 1rem;
}

/* Events */
.events-body {
  padding: 0.75rem 1rem 1rem;
  max-height: 520px;
  overflow-y: auto;
}

.events-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.event-row {
  padding: 0.6rem 0.75rem;
  border-radius: 0.6rem;
  background: rgba(255,255,255,0.02);
  border: 1px solid rgba(255,255,255,0.04);
  font-size: 0.8rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.event-meta {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.25rem;
}

.timestamp { color: #94a3b8; white-space: nowrap; }

.event-name {
  color: #22d3ee;
  font-weight: 600;
}

.event-data {
  color: #cbd5e1;
  opacity: 0.95;
  word-break: break-all;
}

.empty-events {
  padding: 2.5rem;
  text-align: center;
  color: #64748b;
  font-size: 0.9rem;
}

/* Transitions */
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
