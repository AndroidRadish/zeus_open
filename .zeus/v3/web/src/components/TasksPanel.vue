<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  RotateCcw,
  CircleX,
  Pause,
  Play,
  ShieldAlert,
  ShieldCheck,
  FileText,
  Info,
} from 'lucide-vue-next'

const { t } = useI18n()

export interface Task {
  id: string
  title?: string
  wave?: number
  status: string
  passes: boolean
  quarantined?: boolean
}

const props = defineProps<{
  tasks: Task[]
}>()

const emit = defineEmits<{
  (e: 'retry', id: string): void
  (e: 'cancel', id: string): void
  (e: 'pause', id: string): void
  (e: 'resume', id: string): void
  (e: 'quarantine', id: string): void
  (e: 'unquarantine', id: string): void
  (e: 'viewLogs', id: string): void
  (e: 'viewDetail', id: string): void
}>()

const statusList = ['pending', 'running', 'completed', 'failed', 'paused'] as const

function statusLabel(status: string) {
  const key = statusList.includes(status as any) ? status : 'pending'
  return t(`status.${key}`)
}

function statusDotClass(status: string) {
  const s = statusList.includes(status as any) ? status : 'pending'
  return `dot-${s}`
}

const sortedTasks = computed(() => {
  const order = ['running', 'pending', 'failed', 'paused', 'completed']
  return [...props.tasks].sort((a, b) => {
    const ia = order.indexOf(a.status)
    const ib = order.indexOf(b.status)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })
})

function onRetry(id: string) { emit('retry', id) }
function onCancel(id: string) { emit('cancel', id) }
function onPause(id: string) { emit('pause', id) }
function onResume(id: string) { emit('resume', id) }
function onQuarantine(id: string) { emit('quarantine', id) }
function onUnquarantine(id: string) { emit('unquarantine', id) }
function onViewLogs(id: string) { emit('viewLogs', id) }
function onViewDetail(id: string) { emit('viewDetail', id) }
</script>

<template>
  <section class="glass-card panel tasks-panel">
    <div class="panel-head">
      <h2>{{ t('tasks.title') }}</h2>
      <span class="count-badge">{{ tasks.length }}</span>
    </div>
    <div class="table-wrap custom-scrollbar">
      <table class="data-table">
        <thead>
          <tr>
            <th>{{ t('tasks.id') }}</th>
            <th>{{ t('tasks.titleCol') }}</th>
            <th>{{ t('tasks.wave') }}</th>
            <th>{{ t('tasks.status') }}</th>
            <th>{{ t('tasks.result') }}</th>
            <th>{{ t('tasks.actions') }}</th>
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
            <td>
              <div class="action-btns">
                <template v-if="task.status === 'running'">
                  <button class="btn-action btn-warn" @click="onCancel(task.id)">
                    <CircleX :size="13" /> {{ t('actions.cancel') }}
                  </button>
                  <button class="btn-action btn-danger" @click="onQuarantine(task.id)">
                    <ShieldAlert :size="13" /> {{ t('actions.quarantine') }}
                  </button>
                  <button class="btn-action btn-secondary" @click="onViewDetail(task.id)">
                    <Info :size="13" /> {{ t('tasks.detail') }}
                  </button>
                </template>
                <template v-else-if="task.status === 'pending'">
                  <button class="btn-action btn-warn" @click="onPause(task.id)">
                    <Pause :size="13" /> {{ t('actions.pause') }}
                  </button>
                  <button class="btn-action btn-danger" @click="onQuarantine(task.id)">
                    <ShieldAlert :size="13" /> {{ t('actions.quarantine') }}
                  </button>
                  <button class="btn-action btn-secondary" @click="onViewLogs(task.id)">
                    <FileText :size="13" /> {{ t('actions.logs') }}
                  </button>
                  <button class="btn-action btn-secondary" @click="onViewDetail(task.id)">
                    <Info :size="13" /> {{ t('tasks.detail') }}
                  </button>
                </template>
                <template v-else-if="task.status === 'paused'">
                  <button class="btn-action btn-primary" @click="onResume(task.id)">
                    <Play :size="13" /> {{ t('actions.resume') }}
                  </button>
                  <button class="btn-action btn-warn" @click="onCancel(task.id)">
                    <CircleX :size="13" /> {{ t('actions.cancel') }}
                  </button>
                  <button class="btn-action btn-secondary" @click="onViewLogs(task.id)">
                    <FileText :size="13" /> {{ t('actions.logs') }}
                  </button>
                  <button class="btn-action btn-secondary" @click="onViewDetail(task.id)">
                    <Info :size="13" /> {{ t('tasks.detail') }}
                  </button>
                </template>
                <template v-else-if="task.status === 'failed'">
                  <button class="btn-action btn-primary" @click="onRetry(task.id)">
                    <RotateCcw :size="13" /> {{ t('actions.retry') }}
                  </button>
                  <button class="btn-action btn-danger" @click="onUnquarantine(task.id)">
                    <ShieldCheck :size="13" /> {{ t('actions.unquarantine') }}
                  </button>
                  <button class="btn-action btn-secondary" @click="onViewLogs(task.id)">
                    <FileText :size="13" /> {{ t('actions.logs') }}
                  </button>
                  <button class="btn-action btn-secondary" @click="onViewDetail(task.id)">
                    <Info :size="13" /> {{ t('tasks.detail') }}
                  </button>
                </template>
                <template v-else-if="task.status === 'completed'">
                  <button class="btn-action btn-danger" @click="onQuarantine(task.id)">
                    <ShieldAlert :size="13" /> {{ t('actions.quarantine') }}
                  </button>
                  <button class="btn-action btn-secondary" @click="onViewLogs(task.id)">
                    <FileText :size="13" /> {{ t('actions.logs') }}
                  </button>
                  <button class="btn-action btn-secondary" @click="onViewDetail(task.id)">
                    <Info :size="13" /> {{ t('tasks.detail') }}
                  </button>
                </template>
              </div>
            </td>
          </tr>
          <tr v-if="tasks.length === 0">
            <td colspan="6" class="empty-cell">{{ t('tasks.empty') }}</td>
          </tr>
        </tbody>
      </table>
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

.count-badge {
  font-size: 0.75rem;
  padding: 0.25rem 0.6rem;
  border-radius: 0.375rem;
  background: rgba(255,255,255,0.05);
  color: #e2e8f0;
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
  padding: 0.8rem 1rem;
  text-align: left;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--z-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.data-table td {
  padding: 0.9rem 1rem;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  color: #e2e8f0;
}

.data-table tbody tr:hover {
  background: rgba(255,255,255,0.025);
}

.mono { font-family: var(--font-mono); }
.bold { font-weight: 600; }

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

.dot-pending { background: var(--z-warning); color: var(--z-warning); }
.dot-running { background: var(--z-accent-cyan); color: var(--z-accent-cyan); animation: pulseDot 1.4s ease-in-out infinite; }
.dot-completed { background: var(--z-success); color: var(--z-success); }
.dot-failed { background: var(--z-danger); color: var(--z-danger); }
.dot-paused { background: var(--z-violet); color: var(--z-violet); }

@keyframes pulseDot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.55; transform: scale(0.85); }
}

.result-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.result-badge.pass { background: rgba(52,211,153,0.10); color: var(--z-success); }
.result-badge.fail { background: rgba(251,113,133,0.10); color: var(--z-danger); }

.empty-cell {
  text-align: center;
  color: var(--z-text-muted);
  padding: 2.5rem 1rem;
}

.action-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.btn-action {
  appearance: none;
  border: 1px solid var(--z-border);
  background: rgba(255,255,255,0.04);
  color: #e2e8f0;
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.35rem 0.65rem;
  border-radius: 0.45rem;
  cursor: pointer;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.btn-action:hover {
  background: rgba(255,255,255,0.08);
  border-color: rgba(255,255,255,0.14);
}

.btn-primary { color: var(--z-accent-cyan); border-color: rgba(34, 211, 238, 0.18); }
.btn-primary:hover { background: rgba(34, 211, 238, 0.12); border-color: rgba(34, 211, 238, 0.35); }

.btn-warn { color: var(--z-warning); border-color: rgba(251, 191, 36, 0.18); }
.btn-warn:hover { background: rgba(251, 191, 36, 0.12); border-color: rgba(251, 191, 36, 0.35); }

.btn-danger { color: var(--z-danger); border-color: rgba(251, 113, 133, 0.18); }
.btn-danger:hover { background: rgba(251, 113, 133, 0.12); border-color: rgba(251, 113, 133, 0.35); }

.btn-secondary { color: var(--z-text-secondary); border-color: rgba(148, 163, 184, 0.18); }
.btn-secondary:hover { background: rgba(148, 163, 184, 0.12); border-color: rgba(148, 163, 184, 0.35); }
</style>
