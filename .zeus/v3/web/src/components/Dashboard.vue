<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import StatsPanel from './StatsPanel.vue'
import TasksPanel from './TasksPanel.vue'
import EventsPanel from './EventsPanel.vue'
import ControlCenter from './ControlCenter.vue'
import type { Task } from './TasksPanel.vue'

const { t, locale } = useI18n()

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
const activeTab = ref<'overview' | 'tasks' | 'events' | 'control'>('overview')

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

async function taskAction(path: string, id: string) {
  try {
    const res = await fetch(`/tasks/${id}/${path}`, { method: 'POST' })
    if (!res.ok) throw new Error(`${res.status}`)
    await fetchTasks()
    await fetchMetrics()
  } catch (e) {
    console.error(`taskAction ${path} error`, e)
  }
}

function onRetry(id: string) { taskAction('retry', id) }
function onCancel(id: string) { taskAction('cancel', id) }
function onPause(id: string) { taskAction('pause', id) }
function onResume(id: string) { taskAction('resume', id) }
function onQuarantine(id: string) { taskAction('quarantine', id) }
function onUnquarantine(id: string) { taskAction('unquarantine', id) }

function onControlRefresh() {
  fetchTasks()
  fetchMetrics()
}
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
      <!-- Tabs -->
      <nav class="tab-bar">
        <button
          v-for="tab in (['overview', 'tasks', 'events', 'control'] as const)"
          :key="tab"
          :class="['tab-btn', { active: activeTab === tab }]"
          @click="activeTab = tab"
        >{{ t(`tabs.${tab}`) }}</button>
      </nav>

      <!-- Overview -->
      <template v-if="activeTab === 'overview'">
        <StatsPanel :metrics="metrics" />
        <div class="workspace">
          <TasksPanel
            :tasks="tasks"
            @retry="onRetry"
            @cancel="onCancel"
            @pause="onPause"
            @resume="onResume"
            @quarantine="onQuarantine"
            @unquarantine="onUnquarantine"
          />
          <EventsPanel :events="events" />
        </div>
      </template>

      <!-- Tasks -->
      <template v-if="activeTab === 'tasks'">
        <TasksPanel
          :tasks="tasks"
          @retry="onRetry"
          @cancel="onCancel"
          @pause="onPause"
          @resume="onResume"
          @quarantine="onQuarantine"
          @unquarantine="onUnquarantine"
        />
      </template>

      <!-- Events -->
      <template v-if="activeTab === 'events'">
        <EventsPanel :events="events" />
      </template>

      <!-- Control -->
      <template v-if="activeTab === 'control'">
        <ControlCenter @refresh="onControlRefresh" />
      </template>
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
  padding-top: 1.25rem;
  padding-bottom: 2rem;
}

/* Tabs */
.tab-bar {
  display: flex;
  gap: 0.25rem;
  margin-bottom: 1.25rem;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

.tab-btn {
  appearance: none;
  border: none;
  background: transparent;
  color: #94a3b8;
  font-size: 0.9rem;
  font-weight: 500;
  padding: 0.6rem 1rem;
  cursor: pointer;
  position: relative;
  transition: color 0.2s ease;
}

.tab-btn:hover { color: #e2e8f0; }

.tab-btn.active {
  color: #22d3ee;
}

.tab-btn.active::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 2px;
  background: #22d3ee;
  border-radius: 2px 2px 0 0;
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
</style>
