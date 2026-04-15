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
  BarChart3,
  HeartPulse,
} from 'lucide-vue-next'
import { useTaskStore } from '../stores/taskStore'
import { useEventStore } from '../stores/eventStore'
import { useUiStore } from '../stores/uiStore'
import StatsPanel from './StatsPanel.vue'
import TasksPanel from './TasksPanel.vue'
import EventsPanel from './EventsPanel.vue'
import ControlCenter from './ControlCenter.vue'
import WorkflowGraphPanel from './WorkflowGraphPanel.vue'
import PhasesPanel from './PhasesPanel.vue'
import MailboxPanel from './MailboxPanel.vue'
import MetricsPanel from './MetricsPanel.vue'
import TaskDetailDrawer from './TaskDetailDrawer.vue'

const { t, locale } = useI18n()
const taskStore = useTaskStore()
const eventStore = useEventStore()
const uiStore = useUiStore()

const projectRoot = ref('')
const recentProjects = ref<string[]>([])

const tabs = [
  { key: 'overview', label: t('tabs.overview'), icon: LayoutGrid },
  { key: 'tasks', label: t('tabs.tasks'), icon: ListTodo },
  { key: 'events', label: t('tabs.events'), icon: Radio },
  { key: 'graph', label: t('tabs.graph'), icon: GitGraph },
  { key: 'phases', label: t('tabs.phases'), icon: Layers },
  { key: 'mailbox', label: t('tabs.mailbox'), icon: Mail },
  { key: 'metrics', label: t('tabs.metrics'), icon: BarChart3 },
  { key: 'control', label: t('tabs.control'), icon: SlidersHorizontal },
] as const

async function switchProject() {
  const ok = await taskStore.switchProject(projectRoot.value)
  if (!ok) return
  const list = JSON.parse(localStorage.getItem('zeus-recent-projects') || '[]') as string[]
  const updated = [projectRoot.value.trim(), ...list.filter(p => p !== projectRoot.value.trim())].slice(0, 5)
  localStorage.setItem('zeus-recent-projects', JSON.stringify(updated))
  recentProjects.value = updated
  projectRoot.value = ''
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

onMounted(() => {
  taskStore.fetchMetrics()
  taskStore.fetchTasks()
  taskStore.fetchHealth()
  taskStore.connectSSE(locale.value)
  taskStore.startPolling()
  eventStore.fetchHistory()
  recentProjects.value = JSON.parse(localStorage.getItem('zeus-recent-projects') || '[]')
})

onUnmounted(() => {
  taskStore.stopPolling()
})

function onControlRefresh() {
  taskStore.fetchTasks()
  taskStore.fetchMetrics()
  taskStore.fetchHealth()
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
          <!-- Health -->
          <div v-if="taskStore.health" class="health-badge" :class="taskStore.health.status === 'ok' ? 'ok' : 'error'">
            <HeartPulse :size="14" />
            <span>{{ taskStore.health.status === 'ok' ? t('health.ok') : t('health.error') }}</span>
          </div>

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

          <div class="connection" :class="taskStore.connected ? 'online' : 'offline'">
            <span class="pulse-dot"></span>
            <span class="text">{{ taskStore.connected ? t('connection.online') : t('connection.offline') }}</span>
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
          :class="['tab-btn', { active: uiStore.activeTab === tab.key }]"
          @click="uiStore.setTab(tab.key)"
        >
          <component :is="tab.icon" class="tab-icon" :size="16" />
          <span>{{ tab.label }}</span>
        </button>
      </nav>

      <!-- Overview -->
      <section v-if="uiStore.activeTab === 'overview'" class="animate-fade-in-up">
        <StatsPanel :metrics="taskStore.metrics" />
        <div class="workspace">
          <TasksPanel />
          <EventsPanel />
        </div>
      </section>

      <!-- Tasks -->
      <section v-if="uiStore.activeTab === 'tasks'" class="animate-fade-in-up">
        <TasksPanel />
      </section>

      <!-- Events -->
      <section v-if="uiStore.activeTab === 'events'" class="animate-fade-in-up">
        <EventsPanel />
      </section>

      <!-- Graph -->
      <section v-if="uiStore.activeTab === 'graph'" class="animate-fade-in-up">
        <WorkflowGraphPanel />
      </section>

      <!-- Phases -->
      <section v-if="uiStore.activeTab === 'phases'" class="animate-fade-in-up">
        <PhasesPanel />
      </section>

      <!-- Mailbox -->
      <section v-if="uiStore.activeTab === 'mailbox'" class="animate-fade-in-up">
        <MailboxPanel />
      </section>

      <!-- Metrics -->
      <section v-if="uiStore.activeTab === 'metrics'" class="animate-fade-in-up">
        <MetricsPanel />
      </section>

      <!-- Control -->
      <section v-if="uiStore.activeTab === 'control'" class="animate-fade-in-up">
        <ControlCenter @refresh="onControlRefresh" />
      </section>
    </main>

    <!-- Logs Modal -->
    <Transition name="modal">
      <div v-if="uiStore.logsModal.open" class="modal-overlay" @click.self="uiStore.closeLogs()">
        <div class="modal-content">
          <div class="modal-head">
            <h3>Logs: {{ uiStore.logsModal.taskId }}</h3>
            <button class="modal-close" @click="uiStore.closeLogs()" aria-label="Close">×</button>
          </div>
          <div class="modal-body custom-scrollbar">
            <div v-if="uiStore.logsModal.loading" class="modal-loading">Loading…</div>
            <pre v-else class="modal-pre">{{ uiStore.logsModal.activity || 'No logs available.' }}</pre>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Task Detail Drawer -->
    <TaskDetailDrawer
      :open="uiStore.detailDrawer.open"
      :task="uiStore.detailDrawer.task"
      @close="uiStore.closeDetail()"
    />
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

.health-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.7rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 500;
  border: 1px solid var(--z-border);
}
.health-badge.ok {
  background: rgba(52,211,153,0.1);
  color: var(--z-success);
  border-color: rgba(52,211,153,0.25);
}
.health-badge.error {
  background: rgba(251,113,133,0.1);
  color: var(--z-danger);
  border-color: rgba(251,113,133,0.25);
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
  outline: none;
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
