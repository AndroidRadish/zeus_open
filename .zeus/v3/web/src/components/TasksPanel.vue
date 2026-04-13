<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

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
</script>

<template>
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
                  <button class="btn-action btn-warn" @click="onCancel(task.id)">{{ t('actions.cancel') }}</button>
                  <button class="btn-action btn-danger" @click="onQuarantine(task.id)">{{ t('actions.quarantine') }}</button>
                </template>
                <template v-else-if="task.status === 'pending'">
                  <button class="btn-action btn-warn" @click="onPause(task.id)">{{ t('actions.pause') }}</button>
                  <button class="btn-action btn-danger" @click="onQuarantine(task.id)">{{ t('actions.quarantine') }}</button>
                </template>
                <template v-else-if="task.status === 'paused'">
                  <button class="btn-action btn-primary" @click="onResume(task.id)">{{ t('actions.resume') }}</button>
                  <button class="btn-action btn-warn" @click="onCancel(task.id)">{{ t('actions.cancel') }}</button>
                </template>
                <template v-else-if="task.status === 'failed'">
                  <button class="btn-action btn-primary" @click="onRetry(task.id)">{{ t('actions.retry') }}</button>
                  <button class="btn-action btn-danger" @click="onUnquarantine(task.id)">{{ t('actions.unquarantine') }}</button>
                </template>
                <template v-else-if="task.status === 'completed'">
                  <button class="btn-action btn-danger" @click="onQuarantine(task.id)">{{ t('actions.quarantine') }}</button>
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
  border-radius: 1rem;
  overflow: hidden;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
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
.dot-paused { background: #a78bfa; color: #a78bfa; }

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

.action-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.btn-action {
  appearance: none;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: #e2e8f0;
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.3rem 0.6rem;
  border-radius: 0.4rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-action:hover {
  background: rgba(255,255,255,0.08);
  border-color: rgba(255,255,255,0.14);
}

.btn-primary { color: #22d3ee; }
.btn-primary:hover { background: rgba(34,211,238,0.12); }

.btn-warn { color: #fbbf24; }
.btn-warn:hover { background: rgba(251,191,36,0.12); }

.btn-danger { color: #fb7185; }
.btn-danger:hover { background: rgba(251,113,133,0.12); }
</style>
