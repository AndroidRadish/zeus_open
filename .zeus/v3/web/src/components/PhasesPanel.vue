<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Layers, Target } from 'lucide-vue-next'

const { t } = useI18n()

interface Milestone {
  id: string
  title: string
  status: string
  progress_percent: number
  task_ids?: string[]
}

interface Phase {
  id: string
  title: string
  status: string
  progress_percent: number
  milestone_ids?: string[]
  milestones?: Milestone[]
}

const phases = ref<Phase[]>([])
const selectedPhase = ref<Phase | null>(null)
const selectedMilestone = ref<Milestone | null>(null)
const milestoneTasks = ref<any[]>([])
const loading = ref(false)

async function fetchPhases() {
  loading.value = true
  try {
    const res = await fetch('/phases')
    phases.value = await res.json()
  } catch (e) {
    console.error('fetch phases error', e)
  } finally {
    loading.value = false
  }
}

async function openPhase(phase: Phase) {
  selectedPhase.value = phase
  selectedMilestone.value = null
  milestoneTasks.value = []
  try {
    const res = await fetch(`/phases/${phase.id}`)
    const data = await res.json()
    selectedPhase.value = data
  } catch (e) {
    console.error('fetch phase detail error', e)
  }
}

async function openMilestone(ms: Milestone) {
  selectedMilestone.value = ms
  milestoneTasks.value = []
  try {
    const res = await fetch(`/milestones/${ms.id}`)
    const data = await res.json()
    selectedMilestone.value = data
    milestoneTasks.value = data.tasks || []
  } catch (e) {
    console.error('fetch milestone detail error', e)
  }
}

function closeDetail() {
  selectedPhase.value = null
  selectedMilestone.value = null
  milestoneTasks.value = []
}

onMounted(fetchPhases)
</script>

<template>
  <div class="phases-panel glass-card">
    <div class="panel-head">
      <h2><Layers :size="18" class="head-icon" /> {{ t('phases.title') }}</h2>
      <button class="btn-refresh" @click="fetchPhases">Refresh</button>
    </div>

    <div v-if="loading" class="empty">Loading…</div>
    <div v-else-if="phases.length === 0" class="empty">{{ t('phases.empty') }}</div>

    <div v-else class="phase-list">
      <div
        v-for="phase in phases"
        :key="phase.id"
        class="phase-card glass-card"
        @click="openPhase(phase)"
      >
        <div class="phase-header">
          <div class="phase-title">{{ phase.title || phase.id }}</div>
          <div class="phase-badge" :class="phase.status">{{ phase.status }}</div>
        </div>
        <div class="phase-meta">
          <span><Target :size="12" /> {{ (phase.milestone_ids || []).length }} {{ t('phases.milestones') }}</span>
          <span class="phase-progress">{{ phase.progress_percent || 0 }}%</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: `${phase.progress_percent || 0}%` }"></div>
        </div>
      </div>
    </div>

    <!-- Detail overlay -->
    <div v-if="selectedPhase" class="detail-overlay" @click.self="closeDetail">
      <div class="detail-card">
        <div class="detail-head">
          <h3>{{ selectedPhase.title || selectedPhase.id }}</h3>
          <button class="detail-close" @click="closeDetail" aria-label="Close">×</button>
        </div>

        <div class="detail-body custom-scrollbar">
          <div v-if="!selectedMilestone" class="milestone-list">
            <div
              v-for="ms in (selectedPhase.milestones || [])"
              :key="ms.id"
              class="milestone-item"
              @click="openMilestone(ms)"
            >
              <div class="milestone-title">{{ ms.title || ms.id }}</div>
              <div class="milestone-meta">
                <span class="milestone-badge" :class="ms.status">{{ ms.status }}</span>
                <span>{{ ms.progress_percent || 0 }}%</span>
              </div>
            </div>
          </div>

          <div v-else>
            <div class="breadcrumb" @click="selectedMilestone = null; milestoneTasks = []">
              ← {{ selectedPhase.title || selectedPhase.id }}
            </div>
            <h4>{{ selectedMilestone.title || selectedMilestone.id }}</h4>
            <div class="milestone-meta" style="margin-bottom:0.75rem">
              <span class="milestone-badge" :class="selectedMilestone.status">{{ selectedMilestone.status }}</span>
              <span>{{ selectedMilestone.progress_percent || 0 }}%</span>
            </div>
            <div v-if="milestoneTasks.length === 0" class="empty">{{ t('tasks.empty') }}</div>
            <div v-else class="task-list">
              <div v-for="task in milestoneTasks" :key="task.id" class="task-item">
                <div class="task-id">{{ task.id }}</div>
                <div class="task-status" :class="task.status">{{ task.status }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.phases-panel {
  padding: 1rem;
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.85rem;
}
.panel-head h2 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--z-text-primary);
  font-family: var(--font-display);
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}
.head-icon { color: var(--z-accent-cyan); opacity: 0.9; }
.btn-refresh {
  appearance: none;
  border: 1px solid var(--z-border);
  background: rgba(255,255,255,0.04);
  color: #e2e8f0;
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.35rem 0.7rem;
  border-radius: 0.4rem;
  cursor: pointer;
  transition: all 0.2s ease;
}
.btn-refresh:hover { background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.14); }
.empty {
  color: var(--z-text-muted);
  font-size: 0.9rem;
  padding: 1rem 0;
}
.phase-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 0.85rem;
}
.phase-card {
  padding: 1rem;
  cursor: pointer;
}
.phase-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.55rem;
}
.phase-title {
  font-weight: 600;
  color: var(--z-text-primary);
  font-family: var(--font-display);
}
.phase-badge {
  font-size: 0.7rem;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  text-transform: uppercase;
  font-weight: 600;
  background: rgba(255,255,255,0.08);
  color: #e2e8f0;
}
.phase-badge.completed { background: rgba(52,211,153,0.15); color: var(--z-success); }
.phase-badge.running { background: rgba(34,211,238,0.15); color: var(--z-accent-cyan); }
.phase-badge.failed { background: rgba(251,113,133,0.15); color: var(--z-danger); }
.phase-badge.pending { background: rgba(148,163,184,0.15); color: var(--z-text-secondary); }
.phase-meta {
  display: flex;
  justify-content: space-between;
  color: var(--z-text-secondary);
  font-size: 0.8rem;
  margin-bottom: 0.55rem;
}
.progress-bar {
  height: 6px;
  background: rgba(255,255,255,0.08);
  border-radius: 3px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--z-accent-cyan), var(--z-accent-indigo));
  border-radius: 3px;
  transition: width 0.5s ease;
}

/* Detail overlay */
.detail-overlay {
  position: fixed;
  inset: 0;
  z-index: 90;
  background: rgba(0,0,0,0.55);
  backdrop-filter: blur(6px);
  display: grid;
  place-items: center;
  padding: 1rem;
}
.detail-card {
  width: 100%;
  max-width: 640px;
  max-height: 80vh;
  background: rgba(10,12,24,0.98);
  border: 1px solid var(--z-border);
  border-radius: 1rem;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 80px rgba(0,0,0,0.55);
}
.detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--z-border);
}
.detail-head h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--z-text-primary);
  font-family: var(--font-display);
}
.detail-close {
  appearance: none;
  border: none;
  background: transparent;
  color: var(--z-text-secondary);
  font-size: 1.5rem;
  cursor: pointer;
  width: 2rem;
  height: 2rem;
  display: grid;
  place-items: center;
  border-radius: 0.4rem;
  transition: color 0.2s ease, background 0.2s ease;
}
.detail-close:hover { color: #e2e8f0; background: rgba(255,255,255,0.05); }
.detail-body {
  padding: 1rem 1.25rem;
  overflow: auto;
}
.milestone-list {
  display: grid;
  gap: 0.6rem;
}
.milestone-item {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 0.65rem;
  padding: 0.85rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: background 0.15s ease;
}
.milestone-item:hover { background: rgba(255,255,255,0.05); }
.milestone-title {
  font-weight: 500;
  color: var(--z-text-primary);
}
.milestone-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  color: var(--z-text-secondary);
}
.milestone-badge {
  font-size: 0.7rem;
  padding: 0.15rem 0.4rem;
  border-radius: 999px;
  text-transform: uppercase;
  font-weight: 600;
  background: rgba(255,255,255,0.08);
  color: #e2e8f0;
}
.milestone-badge.completed { background: rgba(52,211,153,0.15); color: var(--z-success); }
.milestone-badge.running { background: rgba(34,211,238,0.15); color: var(--z-accent-cyan); }
.milestone-badge.failed { background: rgba(251,113,133,0.15); color: var(--z-danger); }
.milestone-badge.pending { background: rgba(148,163,184,0.15); color: var(--z-text-secondary); }
.breadcrumb {
  color: var(--z-accent-cyan);
  font-size: 0.85rem;
  margin-bottom: 0.75rem;
  cursor: pointer;
  display: inline-flex;
}
.task-list {
  display: grid;
  gap: 0.45rem;
}
.task-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255,255,255,0.02);
  border: 1px solid rgba(255,255,255,0.04);
  border-radius: 0.45rem;
  padding: 0.55rem 0.8rem;
}
.task-id {
  font-size: 0.85rem;
  color: #e2e8f0;
  font-family: var(--font-mono);
}
.task-status {
  font-size: 0.7rem;
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  text-transform: uppercase;
  font-weight: 600;
  background: rgba(255,255,255,0.08);
  color: #e2e8f0;
}
.task-status.completed { background: rgba(52,211,153,0.15); color: var(--z-success); }
.task-status.running { background: rgba(34,211,238,0.15); color: var(--z-accent-cyan); }
.task-status.failed { background: rgba(251,113,133,0.15); color: var(--z-danger); }
.task-status.pending { background: rgba(148,163,184,0.15); color: var(--z-text-secondary); }
</style>
