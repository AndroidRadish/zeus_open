<script setup lang="ts">
import { watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { X, GitBranch, FileText, Clock, Activity, Target, AlignLeft } from 'lucide-vue-next'

const { t } = useI18n()

export interface TaskDetail {
  id: string
  title?: string
  description?: string
  status: string
  passes: boolean
  wave?: number
  scheduled_wave?: number
  rescheduled_from?: number
  depends_on?: string[]
  files?: string[]
  commit_sha?: string
  worker_id?: string
  heartbeat_at?: string
  milestone_id?: string
  type?: string
  [key: string]: any
}

const props = defineProps<{
  open: boolean
  task: TaskDetail | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

watch(() => props.open, (val) => {
  if (typeof document !== 'undefined') {
    document.body.style.overflow = val ? 'hidden' : ''
  }
})

function onClose() {
  emit('close')
}

function statusClass(status: string) {
  return `status-${status || 'pending'}`
}
</script>

<template>
  <Transition name="drawer">
    <div v-if="open" class="drawer-overlay" @click.self="onClose">
      <aside class="drawer" role="dialog" aria-modal="true">
        <div class="drawer-head">
          <div class="drawer-title">
            <span class="title-mono">{{ task?.id }}</span>
            <span
              class="status-pill"
              :class="statusClass(task?.status || 'pending')"
            >
              {{ task?.status || 'pending' }}
            </span>
          </div>
          <button class="drawer-close" aria-label="Close" @click="onClose">
            <X :size="18" />
          </button>
        </div>

        <div v-if="task" class="drawer-body custom-scrollbar">
          <div class="detail-block">
            <div class="block-label"><AlignLeft :size="14" /> {{ t('tasks.titleCol') }}</div>
            <div class="block-value">{{ task.title || t('tasks.unnamed') }}</div>
          </div>

          <div v-if="task.description" class="detail-block">
            <div class="block-label"><AlignLeft :size="14" /> {{ t('tasks.description') }}</div>
            <div class="block-value text-secondary">{{ task.description }}</div>
          </div>

          <div class="detail-grid">
            <div class="detail-block">
              <div class="block-label"><Activity :size="14" /> {{ t('tasks.result') }}</div>
              <div class="block-value">
                <span class="result-pill" :class="task.passes ? 'pass' : 'fail'">
                  {{ task.passes ? t('result.pass') : t('result.fail') }}
                </span>
              </div>
            </div>
            <div class="detail-block">
              <div class="block-label"><Target :size="14" /> {{ t('tasks.wave') }}</div>
              <div class="block-value mono">{{ task.wave ?? '-' }}</div>
            </div>
            <div v-if="task.scheduled_wave !== undefined" class="detail-block">
              <div class="block-label"><Target :size="14" /> {{ t('tasks.scheduledWave') }}</div>
              <div class="block-value mono">{{ task.scheduled_wave }}</div>
            </div>
            <div v-if="task.rescheduled_from !== undefined" class="detail-block">
              <div class="block-label"><Target :size="14" /> {{ t('tasks.rescheduledFrom') }}</div>
              <div class="block-value mono">{{ task.rescheduled_from }}</div>
            </div>
          </div>

          <div v-if="task.depends_on?.length" class="detail-block">
            <div class="block-label"><GitBranch :size="14" /> {{ t('tasks.dependsOn') }}</div>
            <div class="tag-list">
              <span v-for="d in task.depends_on" :key="d" class="tag mono">{{ d }}</span>
            </div>
          </div>

          <div v-if="task.files?.length" class="detail-block">
            <div class="block-label"><FileText :size="14" /> {{ t('tasks.files') }}</div>
            <ul class="file-list">
              <li v-for="f in task.files" :key="f" class="file-item mono">{{ f }}</li>
            </ul>
          </div>

          <div class="detail-grid">
            <div v-if="task.commit_sha" class="detail-block">
              <div class="block-label"><Activity :size="14" /> {{ t('tasks.commitSha') }}</div>
              <div class="block-value mono">{{ task.commit_sha }}</div>
            </div>
            <div v-if="task.worker_id" class="detail-block">
              <div class="block-label"><Activity :size="14" /> {{ t('tasks.worker') }}</div>
              <div class="block-value mono">{{ task.worker_id }}</div>
            </div>
            <div v-if="task.heartbeat_at" class="detail-block">
              <div class="block-label"><Clock :size="14" /> {{ t('tasks.heartbeat') }}</div>
              <div class="block-value mono">{{ new Date(task.heartbeat_at).toLocaleString() }}</div>
            </div>
            <div v-if="task.milestone_id" class="detail-block">
              <div class="block-label"><Target :size="14" /> {{ t('tasks.milestone') }}</div>
              <div class="block-value mono">{{ task.milestone_id }}</div>
            </div>
          </div>
        </div>

        <div v-else class="drawer-body empty">
          {{ t('tasks.empty') }}
        </div>
      </aside>
    </div>
  </Transition>
</template>

<style scoped>
.drawer-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(6px);
  display: flex;
  justify-content: flex-end;
}

.drawer {
  width: 100%;
  max-width: 520px;
  height: 100%;
  background: rgba(10, 12, 24, 0.98);
  border-left: 1px solid var(--z-border);
  display: flex;
  flex-direction: column;
  box-shadow: -16px 0 48px rgba(0,0,0,0.45);
}

.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--z-border);
}

.drawer-title {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.title-mono {
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 1rem;
  color: #ffffff;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  background: rgba(255,255,255,0.08);
  color: #e2e8f0;
}
.status-pill.status-completed { background: rgba(52,211,153,0.15); color: var(--z-success); }
.status-pill.status-running { background: rgba(34,211,238,0.15); color: var(--z-accent-cyan); }
.status-pill.status-failed { background: rgba(251,113,133,0.15); color: var(--z-danger); }
.status-pill.status-pending { background: rgba(148,163,184,0.15); color: var(--z-text-secondary); }
.status-pill.status-paused { background: rgba(167,139,250,0.15); color: var(--z-violet); }

.drawer-close {
  appearance: none;
  border: none;
  background: transparent;
  color: var(--z-text-secondary);
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 0.45rem;
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: all 0.2s ease;
}
.drawer-close:hover { color: #e2e8f0; background: rgba(255,255,255,0.05); }

.drawer-body {
  padding: 1.25rem;
  overflow-y: auto;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.empty {
  color: var(--z-text-muted);
  font-size: 0.9rem;
}

.detail-block {
  background: rgba(255,255,255,0.025);
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 0.65rem;
  padding: 0.85rem 1rem;
}

.block-label {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  color: var(--z-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  margin-bottom: 0.35rem;
}

.block-value {
  color: #e2e8f0;
  font-size: 0.95rem;
  line-height: 1.5;
}

.text-secondary {
  color: #cbd5e1;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

@media (max-width: 480px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}

.result-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 500;
}
.result-pill.pass { background: rgba(52,211,153,0.12); color: var(--z-success); }
.result-pill.fail { background: rgba(251,113,133,0.12); color: var(--z-danger); }

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.tag {
  display: inline-flex;
  align-items: center;
  padding: 0.3rem 0.55rem;
  border-radius: 0.4rem;
  font-size: 0.75rem;
  background: rgba(34,211,238,0.12);
  color: var(--z-accent-cyan);
  border: 1px solid rgba(34,211,238,0.2);
}

.file-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.file-item {
  font-size: 0.8rem;
  color: #cbd5e1;
  padding: 0.35rem 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}
.file-item:last-child { border-bottom: none; }

/* Transitions */
.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.25s ease;
}
.drawer-enter-active .drawer,
.drawer-leave-active .drawer {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from .drawer,
.drawer-leave-to .drawer {
  transform: translateX(100%);
}
</style>
