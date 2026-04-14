<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import StatsPanel from './StatsPanel.vue'
import TasksPanel from './TasksPanel.vue'
import EventsPanel from './EventsPanel.vue'
import ControlCenter from './ControlCenter.vue'
import WorkflowGraphPanel from './WorkflowGraphPanel.vue'
import PhasesPanel from './PhasesPanel.vue'
import MailboxPanel from './MailboxPanel.vue'
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
const activeTab = ref<'overview' | 'tasks' | 'events' | 'graph' | 'phases' | 'mailbox' | 'control'>('overview')

const logsModal = ref<{ open: boolean; taskId: string; activity: string; loading: boolean }>({
  open: false,
  taskId: '',
  activity: '',
  loading: false,
})

const projectRoot = ref('')
const recentProjects = ref<string[]>([])

async function switchProject() {
  if (!projectRoot.value.trim()) return
  try {
    const res = await fetch('/control/project/switch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_root: projectRoot.value.trim() }),
    })
    if (!res.ok) throw new Error(`${res.status}`)
    const list = JSON.parse(localStorage.getItem('zeus-recent-projects') || '[]') as string[]
    const updated = [projectRoot.value.trim(), ...list.filter(p => p !== projectRoot.value.trim())].slice(0, 5)
    localStorage.setItem('zeus-recent-projects', JSON.stringify(updated))
    recentProjects.value = updated
    await fetchMetrics()
    await fetchTasks()
    projectRoot.value = ''
  } catch (e: any) {
    console.error('switch project error', e)
  }
}

function selectRecentProject(path: string) {
  projectRoot.value = path
  switchProject()
}

onMounted(() => {
  fetchMetrics()
  fetchTasks()
  connectSSE()
  recentProjects.value = JSON.parse(localStorage.getItem('zeus-recent-projects') || '[]')
  pollTimer = window.setInterval(() => {
    fetchMetrics()
    fetchTasks()
  }, 5000)
})

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

async function onViewLogs(taskId: string) {
  logsModal.value = { open: true, taskId, activity: '', loading: true }
  try {
    const res = await fetch(`/agents/zeus-agent-${taskId}/logs`)
    const data = await res.json()
    logsModal.value.activity = data.activity || ''
  } catch (e: any) {
    logsModal.value.activity = `Error: ${e?.message || String(e)}`
  } finally {
    logsModal.value.loading = false
  }
}

function closeLogsModal() {
  logsModal.value.open = false
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
          <!-- Project switch -->
          <div class="project-switch">
            <input
              v-model="projectRoot"
              type="text"
              class="project-input"
              placeholder="Switch project root..."
              @keydown.enter="switchProject"
            />
            <button class="project-btn" @click="switchProject">Switch</button>
            <select v-if="recentProjects.length" v-model="projectRoot" class="project-select" @change="selectRecentProject(projectRoot)">
              <option value="" disabled>Recent projects</option>
              <option v-for="p in recentProjects" :key="p" :value="p">{{ p }}</option>
            </select>
          </div>

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
          v-for="tab in (['overview', 'tasks', 'events', 'graph', 'phases', 'mailbox', 'control'] as const)"
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
            @view-logs="onViewLogs"
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
          @view-logs="onViewLogs"
        />
      </template>

      <!-- Events -->
      <template v-if="activeTab === 'events'">
        <EventsPanel :events="events" />
      </template>

      <!-- Graph -->
      <template v-if="activeTab === 'graph'">
        <WorkflowGraphPanel />
      </template>

      <!-- Phases -->
      <template v-if="activeTab === 'phases'">
        <PhasesPanel />
      </template>

      <!-- Mailbox -->
      <template v-if="activeTab === 'mailbox'">
        <MailboxPanel />
      </template>

      <!-- Control -->
      <template v-if="activeTab === 'control'">
        <ControlCenter @refresh="onControlRefresh" />
      </template>
    </main>

    <!-- Logs Modal -->
    <div v-if="logsModal.open" class="modal-overlay" @click.self="closeLogsModal">
      <div class="modal-content">
        <div class="modal-head">
          <h3>Logs: {{ logsModal.taskId }}</h3>
          <button class="modal-close" @click="closeLogsModal">×</button>
        </div>
        <div class="modal-body custom-scrollbar">
          <div v-if="logsModal.loading" class="modal-loading">Loading...</div>
          <pre v-else class="modal-pre">{{ logsModal.activity || 'No logs available.' }}</pre>
        </div>
      </div>
    </div>
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

.project-switch {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.project-input {
  appearance: none;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.03);
  color: #e2e8f0;
  font-size: 0.8rem;
  padding: 0.35rem 0.6rem;
  border-radius: 0.4rem;
  min-width: 180px;
}

.project-input::placeholder { color: #64748b; }

.project-btn {
  appearance: none;
  border: 1px solid rgba(34,211,238,0.2);
  background: rgba(34,211,238,0.1);
  color: #22d3ee;
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.35rem 0.7rem;
  border-radius: 0.4rem;
  cursor: pointer;
}

.project-select {
  appearance: none;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.03);
  color: #e2e8f0;
  font-size: 0.75rem;
  padding: 0.35rem 1.5rem 0.35rem 0.6rem;
  border-radius: 0.4rem;
  background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%2394a3b8' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
  background-position: right 0.35rem center;
  background-repeat: no-repeat;
  background-size: 1rem;
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

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0,0,0,0.55);
  backdrop-filter: blur(4px);
  display: grid;
  place-items: center;
  padding: 1rem;
}

.modal-content {
  width: 100%;
  max-width: 800px;
  max-height: 80vh;
  background: rgba(16,16,24,0.95);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 1rem;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

.modal-head h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #f8fafc;
}

.modal-close {
  appearance: none;
  border: none;
  background: transparent;
  color: #94a3b8;
  font-size: 1.5rem;
  line-height: 1;
  cursor: pointer;
}

.modal-close:hover { color: #e2e8f0; }

.modal-body {
  padding: 1rem 1.25rem;
  overflow: auto;
  flex: 1;
}

.modal-pre {
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.85rem;
  line-height: 1.6;
  color: #e2e8f0;
  white-space: pre-wrap;
}

.modal-loading {
  color: #94a3b8;
  font-size: 0.9rem;
}

.custom-scrollbar::-webkit-scrollbar { width: 8px; height: 8px; }
.custom-scrollbar::-webkit-scrollbar-track { background: rgba(255,255,255,0.03); border-radius: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.20); }
</style>
