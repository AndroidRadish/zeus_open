<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  LayoutGrid,
  ListTodo,
  Radio,
  GitGraph,
  Layers,
  Mail,
  SlidersHorizontal,
} from 'lucide-vue-next'
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

const tabs = [
  { key: 'overview', label: t('tabs.overview'), icon: LayoutGrid },
  { key: 'tasks', label: t('tabs.tasks'), icon: ListTodo },
  { key: 'events', label: t('tabs.events'), icon: Radio },
  { key: 'graph', label: t('tabs.graph'), icon: GitGraph },
  { key: 'phases', label: t('tabs.phases'), icon: Layers },
  { key: 'mailbox', label: t('tabs.mailbox'), icon: Mail },
  { key: 'control', label: t('tabs.control'), icon: SlidersHorizontal },
] as const

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

let es: EventSource | null = null
let pollTimer: number | null = null

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
  recentProjects.value = JSON.parse(localStorage.getItem('zeus-recent-projects') || '[]')
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
    <!-- Orbital ambient background -->
    <div class="ambient-bg" aria-hidden="true">
      <div class="orb orb-1"></div>
      <div class="orb orb-2"></div>
      <div class="orb orb-3"></div>
    </div>

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
              <option value="" disabled>Recent</option>
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
          v-for="tab in tabs"
          :key="tab.key"
          :class="['tab-btn', { active: activeTab === tab.key }]"
          @click="activeTab = tab.key"
        >
          <component :is="tab.icon" class="tab-icon" :size="16" />
          <span>{{ tab.label }}</span>
        </button>
      </nav>

      <!-- Overview -->
      <section v-if="activeTab === 'overview'" class="animate-fade-in-up">
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
      </section>

      <!-- Tasks -->
      <section v-if="activeTab === 'tasks'" class="animate-fade-in-up">
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
      </section>

      <!-- Events -->
      <section v-if="activeTab === 'events'" class="animate-fade-in-up">
        <EventsPanel :events="events" />
      </section>

      <!-- Graph -->
      <section v-if="activeTab === 'graph'" class="animate-fade-in-up">
        <WorkflowGraphPanel />
      </section>

      <!-- Phases -->
      <section v-if="activeTab === 'phases'" class="animate-fade-in-up">
        <PhasesPanel />
      </section>

      <!-- Mailbox -->
      <section v-if="activeTab === 'mailbox'" class="animate-fade-in-up">
        <MailboxPanel />
      </section>

      <!-- Control -->
      <section v-if="activeTab === 'control'" class="animate-fade-in-up">
        <ControlCenter @refresh="onControlRefresh" />
      </section>
    </main>

    <!-- Logs Modal -->
    <Transition name="modal">
      <div v-if="logsModal.open" class="modal-overlay" @click.self="closeLogsModal">
        <div class="modal-content">
          <div class="modal-head">
            <h3>Logs: {{ logsModal.taskId }}</h3>
            <button class="modal-close" @click="closeLogsModal" aria-label="Close">×</button>
          </div>
          <div class="modal-body custom-scrollbar">
            <div v-if="logsModal.loading" class="modal-loading">Loading…</div>
            <pre v-else class="modal-pre">{{ logsModal.activity || 'No logs available.' }}</pre>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.dashboard {
  position: relative;
  min-height: 100dvh;
  color: var(--z-text-primary);
  overflow-x: hidden;
}

/* Ambient orbs */
.ambient-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.55;
}
.orb-1 {
  width: 600px;
  height: 600px;
  top: -180px;
  right: -120px;
  background: radial-gradient(circle at 30% 30%, rgba(34, 211, 238, 0.18), transparent 60%);
  animation: drift 18s ease-in-out infinite;
}
.orb-2 {
  width: 500px;
  height: 500px;
  bottom: -120px;
  left: -100px;
  background: radial-gradient(circle at 40% 40%, rgba(99, 102, 241, 0.14), transparent 60%);
  animation: drift 22s ease-in-out infinite reverse;
}
.orb-3 {
  width: 360px;
  height: 360px;
  top: 45%;
  left: 55%;
  background: radial-gradient(circle at 50% 50%, rgba(167, 139, 250, 0.10), transparent 60%);
  animation: drift 26s ease-in-out infinite;
}

.container {
  position: relative;
  z-index: 1;
  max-width: 1280px;
  margin: 0 auto;
  padding-left: 1.25rem;
  padding-right: 1.25rem;
}

/* Header */
.topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  border-bottom: 1px solid var(--z-border);
  background: rgba(2, 6, 23, 0.55);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
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
  gap: 0.85rem;
}

.logo {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 0.6rem;
  background: linear-gradient(135deg, var(--z-accent-cyan), var(--z-accent-indigo));
  display: grid;
  place-items: center;
  color: white;
  font-weight: 700;
  font-size: 1.25rem;
  font-family: var(--font-display);
  box-shadow: 0 6px 24px rgba(34, 211, 238, 0.28);
}

.title {
  font-size: 1.125rem;
  font-weight: 600;
  font-family: var(--font-display);
  color: #ffffff;
  letter-spacing: -0.2px;
}

.title .accent {
  color: var(--z-accent-cyan);
  font-weight: 500;
}

.subtitle {
  font-size: 0.75rem;
  color: var(--z-text-secondary);
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
  border: 1px solid var(--z-border);
  background: rgba(255, 255, 255, 0.03);
  color: #e2e8f0;
  font-size: 0.8rem;
  padding: 0.4rem 0.7rem;
  border-radius: 0.5rem;
  min-width: 180px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.project-input:focus {
  border-color: rgba(34, 211, 238, 0.35);
  box-shadow: 0 0 0 3px rgba(34, 211, 238, 0.08);
}
.project-input::placeholder { color: var(--z-text-muted); }

.project-btn {
  appearance: none;
  border: 1px solid rgba(34, 211, 238, 0.22);
  background: rgba(34, 211, 238, 0.10);
  color: var(--z-accent-cyan);
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.4rem 0.8rem;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s ease;
}
.project-btn:hover {
  background: rgba(34, 211, 238, 0.18);
  border-color: rgba(34, 211, 238, 0.35);
}

.project-select {
  appearance: none;
  border: 1px solid var(--z-border);
  background: rgba(255, 255, 255, 0.03);
  color: #e2e8f0;
  font-size: 0.75rem;
  padding: 0.4rem 1.6rem 0.4rem 0.7rem;
  border-radius: 0.5rem;
  background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%2394a3b8' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
  background-position: right 0.4rem center;
  background-repeat: no-repeat;
  background-size: 1rem;
}

.lang-switch {
  display: inline-flex;
  align-items: center;
  gap: 0.15rem;
  padding: 0.25rem;
  border-radius: 0.5rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--z-border);
}

.lang-btn {
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
.lang-btn:hover { color: #e2e8f0; }
.lang-btn.active {
  background: rgba(34, 211, 238, 0.18);
  color: var(--z-accent-cyan);
}

.connection {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.9rem;
  border-radius: 999px;
  border: 1px solid var(--z-border);
  background: rgba(255, 255, 255, 0.03);
  font-size: 0.85rem;
}
.connection.online { color: var(--z-success); border-color: rgba(52, 211, 153, 0.25); }
.connection.offline { color: var(--z-danger); border-color: rgba(251, 113, 133, 0.25); }

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
  padding-bottom: 2.5rem;
}

/* Tabs */
.tab-bar {
  display: flex;
  gap: 0.35rem;
  margin-bottom: 1.25rem;
  border-bottom: 1px solid var(--z-border);
  overflow-x: auto;
}

.tab-btn {
  appearance: none;
  border: none;
  background: transparent;
  color: var(--z-text-secondary);
  font-size: 0.9rem;
  font-weight: 500;
  padding: 0.7rem 1rem;
  cursor: pointer;
  position: relative;
  transition: color 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  white-space: nowrap;
}

.tab-btn:hover { color: #e2e8f0; }
.tab-btn.active { color: var(--z-accent-cyan); }

.tab-btn.active::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 2.5px;
  background: linear-gradient(90deg, var(--z-accent-cyan), var(--z-accent-indigo));
  border-radius: 2px 2px 0 0;
}

.tab-icon {
  opacity: 0.85;
}

/* Workspace */
.workspace {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}

@media (min-width: 1024px) {
  .workspace { grid-template-columns: 1.45fr 0.55fr; gap: 1.25rem; }
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(6px);
  display: grid;
  place-items: center;
  padding: 1rem;
}

.modal-content {
  width: 100%;
  max-width: 840px;
  max-height: 82vh;
  background: rgba(10, 12, 24, 0.98);
  border: 1px solid var(--z-border);
  border-radius: 1rem;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55);
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--z-border);
}

.modal-head h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--z-text-primary);
  font-family: var(--font-display);
}

.modal-close {
  appearance: none;
  border: none;
  background: transparent;
  color: var(--z-text-secondary);
  font-size: 1.6rem;
  line-height: 1;
  cursor: pointer;
  width: 2rem;
  height: 2rem;
  display: grid;
  place-items: center;
  border-radius: 0.4rem;
  transition: color 0.2s ease, background 0.2s ease;
}
.modal-close:hover { color: #e2e8f0; background: rgba(255,255,255,0.05); }

.modal-body {
  padding: 1rem 1.25rem;
  overflow: auto;
  flex: 1;
}

.modal-pre {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  line-height: 1.65;
  color: #e2e8f0;
  white-space: pre-wrap;
}

.modal-loading {
  color: var(--z-text-secondary);
  font-size: 0.9rem;
}

/* Modal transition */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.25s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-active .modal-content,
.modal-leave-active .modal-content {
  transition: transform 0.25s ease, opacity 0.25s ease;
}
.modal-enter-from .modal-content,
.modal-leave-to .modal-content {
  opacity: 0;
  transform: translateY(12px) scale(0.985);
}
</style>
