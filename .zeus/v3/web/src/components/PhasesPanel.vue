<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Layers, Target, Plus, Pencil, Trash2, X, Loader2 } from 'lucide-vue-next'

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
const allTasks = ref<{ id: string; title?: string }[]>([])
const selectedPhase = ref<Phase | null>(null)
const selectedMilestone = ref<Milestone | null>(null)
const milestoneTasks = ref<any[]>([])
const loading = ref(false)
const actionLoading = ref(false)

const modalOpen = ref(false)
const modalMode = ref<'create-phase' | 'edit-phase' | 'create-milestone' | 'edit-milestone'>('create-phase')
const modalData = ref<Partial<Phase & Milestone>>({ id: '', title: '', status: 'pending', progress_percent: 0, task_ids: [] })

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

async function fetchTasks() {
  try {
    const res = await fetch('/tasks?limit=1000')
    allTasks.value = await res.json()
  } catch (e) {
    console.error('fetch tasks error', e)
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

function openModal(mode: typeof modalMode.value, item?: Phase | Milestone) {
  modalMode.value = mode
  if (mode === 'edit-phase' && item) {
    modalData.value = { ...item, task_ids: (item as any).task_ids || [] }
  } else if (mode === 'edit-milestone' && item) {
    modalData.value = { ...item, task_ids: (item as Milestone).task_ids || [] }
  } else if (mode === 'create-milestone') {
    modalData.value = { id: '', title: '', status: 'pending', progress_percent: 0, task_ids: [] }
  } else {
    modalData.value = { id: '', title: '', status: 'pending', progress_percent: 0, task_ids: [] }
  }
  modalOpen.value = true
}

function closeModal() {
  modalOpen.value = false
}

async function saveModal() {
  actionLoading.value = true
  try {
    const data = { ...modalData.value }
    if (data.progress_percent !== undefined) {
      data.progress_percent = Number(data.progress_percent)
    }
    if (modalMode.value === 'create-phase' || modalMode.value === 'edit-phase') {
      const url = modalMode.value === 'edit-phase' ? `/phases/${data.id}` : '/phases'
      await fetch(url, {
        method: modalMode.value === 'edit-phase' ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
    } else {
      const url = modalMode.value === 'edit-milestone' ? `/milestones/${data.id}` : '/milestones'
      await fetch(url, {
        method: modalMode.value === 'edit-milestone' ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
    }
    closeModal()
    await fetchPhases()
    if (selectedPhase.value) {
      const updated = phases.value.find(p => p.id === selectedPhase.value!.id)
      if (updated) await openPhase(updated)
    }
  } catch (e) {
    console.error('save modal error', e)
  } finally {
    actionLoading.value = false
  }
}

async function deleteItem(type: 'phase' | 'milestone', id: string) {
  if (!confirm(t('phases.confirmDelete'))) return
  actionLoading.value = true
  try {
    await fetch(`/${type}s/${id}`, { method: 'DELETE' })
    await fetchPhases()
    if (type === 'phase' && selectedPhase.value?.id === id) closeDetail()
    if (type === 'milestone' && selectedMilestone.value?.id === id) {
      selectedMilestone.value = null
      milestoneTasks.value = []
      if (selectedPhase.value) {
        const updated = phases.value.find(p => p.id === selectedPhase.value!.id)
        if (updated) await openPhase(updated)
      }
    }
  } catch (e) {
    console.error('delete error', e)
  } finally {
    actionLoading.value = false
  }
}

function toggleTaskSelection(tid: string) {
  const list = (modalData.value.task_ids || []) as string[]
  const idx = list.indexOf(tid)
  if (idx >= 0) {
    list.splice(idx, 1)
  } else {
    list.push(tid)
  }
  modalData.value.task_ids = [...list]
}

let pollTimer: any = null

onMounted(() => {
  fetchPhases()
  fetchTasks()
  pollTimer = setInterval(() => {
    fetchPhases()
  }, 10000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<template>
  <div class="phases-root">
    <div class="phases-panel glass-card">
      <div class="panel-head">
        <h2><Layers :size="18" class="head-icon" /> {{ t('phases.title') }}</h2>
        <div class="head-actions">
          <button class="btn-action btn-primary" @click="openModal('create-phase')">
            <Plus :size="14" /> {{ t('phases.createPhase') }}
          </button>
          <button class="btn-refresh" @click="fetchPhases">{{ t('actions.refresh') }}</button>
        </div>
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
    </div>

    <!-- Detail overlay -->
    <div v-if="selectedPhase" class="detail-overlay" @click.self="closeDetail">
      <div class="detail-card">
        <div class="detail-head">
          <h3>{{ selectedPhase.title || selectedPhase.id }}</h3>
          <div class="detail-actions">
            <button class="btn-icon" @click.stop="openModal('edit-phase', selectedPhase)">
              <Pencil :size="14" />
            </button>
            <button class="btn-icon btn-danger" @click.stop="deleteItem('phase', selectedPhase.id)">
              <Trash2 :size="14" />
            </button>
            <button class="detail-close" @click="closeDetail" aria-label="Close">×</button>
          </div>
        </div>

        <div class="detail-body custom-scrollbar">
          <div v-if="!selectedMilestone" class="milestone-list">
            <div class="milestone-list-head">
              <span class="section-label">{{ t('phases.milestones') }}</span>
              <button class="btn-action btn-primary" @click="openModal('create-milestone')">
                <Plus :size="14" /> {{ t('phases.createMilestone') }}
              </button>
            </div>
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
            <div class="milestone-detail-head">
              <h4>{{ selectedMilestone.title || selectedMilestone.id }}</h4>
              <div class="detail-actions">
                <button class="btn-icon" @click.stop="openModal('edit-milestone', selectedMilestone)">
                  <Pencil :size="14" />
                </button>
                <button class="btn-icon btn-danger" @click.stop="deleteItem('milestone', selectedMilestone.id)">
                  <Trash2 :size="14" />
                </button>
              </div>
            </div>
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

    <!-- Modal -->
    <Transition name="modal">
      <div v-if="modalOpen" class="modal-overlay" @click.self="closeModal">
        <div class="modal-card">
          <div class="modal-head">
            <h4>
              <span v-if="modalMode === 'create-phase'">{{ t('phases.createPhase') }}</span>
              <span v-else-if="modalMode === 'edit-phase'">{{ t('phases.editPhase') }}</span>
              <span v-else-if="modalMode === 'create-milestone'">{{ t('phases.createMilestone') }}</span>
              <span v-else>{{ t('phases.editMilestone') }}</span>
            </h4>
            <button class="modal-close" @click="closeModal" aria-label="Close"><X :size="16" /></button>
          </div>
          <div class="modal-body">
            <label class="field">
              <span class="field-label">ID</span>
              <input v-model="modalData.id" :disabled="modalMode.startsWith('edit')" class="field-input" placeholder="unique-id" />
            </label>
            <label class="field">
              <span class="field-label">{{ t('phases.name') }}</span>
              <input v-model="modalData.title" class="field-input" />
            </label>
            <label class="field">
              <span class="field-label">{{ t('phases.status') }}</span>
              <select v-model="modalData.status" class="field-input">
                <option value="pending">pending</option>
                <option value="running">running</option>
                <option value="completed">completed</option>
                <option value="failed">failed</option>
              </select>
            </label>
            <label class="field">
              <span class="field-label">{{ t('phases.progress') }} (%)</span>
              <input v-model.number="modalData.progress_percent" type="number" min="0" max="100" class="field-input" />
            </label>

            <div v-if="modalMode === 'create-milestone' || modalMode === 'edit-milestone'" class="field">
              <span class="field-label">{{ t('phases.selectTasks') }}</span>
              <div class="task-checks">
                <label v-for="task in allTasks" :key="task.id" class="task-check">
                  <input
                    type="checkbox"
                    :checked="(modalData.task_ids || []).includes(task.id)"
                    @change="toggleTaskSelection(task.id)"
                  />
                  <span class="mono">{{ task.id }}</span>
                  <span class="task-check-title">{{ task.title || '' }}</span>
                </label>
              </div>
            </div>
          </div>
          <div class="modal-foot">
            <button class="btn-secondary" @click="closeModal">{{ t('actions.close') }}</button>
            <button class="btn-primary" :disabled="actionLoading || !modalData.id" @click="saveModal">
              <Loader2 v-if="actionLoading" class="spinner" :size="14" />
              <span v-else>{{ t('actions.save') }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.phases-root { position: relative; }

.phases-panel { padding: 1rem; }

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

.head-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-action {
  appearance: none;
  border: 1px solid var(--z-border);
  background: rgba(255,255,255,0.04);
  color: #e2e8f0;
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.4rem 0.7rem;
  border-radius: 0.45rem;
  cursor: pointer;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.btn-action:hover { background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.14); }
.btn-primary { color: var(--z-accent-cyan); border-color: rgba(34,211,238,0.18); }
.btn-primary:hover { background: rgba(34,211,238,0.12); border-color: rgba(34,211,238,0.35); }

.btn-refresh {
  appearance: none;
  border: 1px solid var(--z-border);
  background: rgba(255,255,255,0.04);
  color: #e2e8f0;
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.4rem 0.7rem;
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
.detail-actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.btn-icon {
  appearance: none;
  border: 1px solid var(--z-border);
  background: rgba(255,255,255,0.04);
  color: #e2e8f0;
  width: 2rem;
  height: 2rem;
  border-radius: 0.4rem;
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: all 0.2s ease;
}
.btn-icon:hover { background: rgba(255,255,255,0.08); }
.btn-icon.btn-danger { color: var(--z-danger); border-color: rgba(251,113,133,0.2); }
.btn-icon.btn-danger:hover { background: rgba(251,113,133,0.12); }
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
  transition: all 0.2s ease;
}
.detail-close:hover { color: #e2e8f0; background: rgba(255,255,255,0.05); }

.detail-body {
  padding: 1rem 1.25rem;
  overflow: auto;
}
.milestone-list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.6rem;
}
.section-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--z-text-secondary);
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
.milestone-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.35rem;
}
.milestone-detail-head h4 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--z-text-primary);
  font-family: var(--font-display);
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

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0,0,0,0.55);
  backdrop-filter: blur(6px);
  display: grid;
  place-items: center;
  padding: 1rem;
}
.modal-card {
  width: 100%;
  max-width: 480px;
  max-height: 82vh;
  background: rgba(10,12,24,0.98);
  border: 1px solid var(--z-border);
  border-radius: 1rem;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 80px rgba(0,0,0,0.55);
}
.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--z-border);
}
.modal-head h4 {
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
  width: 2rem;
  height: 2rem;
  border-radius: 0.4rem;
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: all 0.2s ease;
}
.modal-close:hover { color: #e2e8f0; background: rgba(255,255,255,0.05); }
.modal-body {
  padding: 1rem 1.25rem;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.field-label {
  font-size: 0.75rem;
  color: var(--z-text-secondary);
  font-weight: 500;
}
.field-input {
  appearance: none;
  border: 1px solid var(--z-border);
  background: rgba(255,255,255,0.04);
  color: #e2e8f0;
  font-size: 0.9rem;
  padding: 0.55rem 0.8rem;
  border-radius: 0.55rem;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.field-input:focus {
  border-color: rgba(34,211,238,0.35);
  box-shadow: 0 0 0 3px rgba(34,211,238,0.08);
  outline: none;
}
.task-checks {
  max-height: 180px;
  overflow-y: auto;
  background: rgba(0,0,0,0.2);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 0.55rem;
  padding: 0.5rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.task-check {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: #e2e8f0;
  cursor: pointer;
}
.task-check-title {
  color: var(--z-text-secondary);
  font-size: 0.8rem;
}
.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 0.85rem 1.25rem;
  border-top: 1px solid var(--z-border);
}
.btn-secondary {
  appearance: none;
  border: 1px solid var(--z-border);
  background: rgba(255,255,255,0.04);
  color: var(--z-text-secondary);
  font-size: 0.85rem;
  font-weight: 500;
  padding: 0.45rem 0.9rem;
  border-radius: 0.55rem;
  cursor: pointer;
  transition: all 0.2s ease;
}
.btn-secondary:hover { background: rgba(255,255,255,0.08); color: #e2e8f0; }
.btn-primary {
  appearance: none;
  border: 1px solid rgba(34,211,238,0.22);
  background: rgba(34,211,238,0.12);
  color: var(--z-accent-cyan);
  font-size: 0.85rem;
  font-weight: 500;
  padding: 0.45rem 0.9rem;
  border-radius: 0.55rem;
  cursor: pointer;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.btn-primary:hover:not(:disabled) { background: rgba(34,211,238,0.2); border-color: rgba(34,211,238,0.35); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.spinner {
  animation: spin 1.2s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
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
.modal-enter-active .modal-card,
.modal-leave-active .modal-card {
  transition: transform 0.25s ease, opacity 0.25s ease;
}
.modal-enter-from .modal-card,
.modal-leave-to .modal-card {
  opacity: 0;
  transform: translateY(12px) scale(0.985);
}
</style>
