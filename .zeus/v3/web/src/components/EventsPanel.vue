<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  events: { time: string; event: string; data: any }[]
}>()

function isProgress(ev: { event: string; data: any }) {
  return ev.event === 'task.progress' && ev.data?.progress
}

function stepColor(step: string) {
  const map: Record<string, string> = {
    planning: '#a78bfa',
    reading: '#94a3b8',
    writing: '#22d3ee',
    testing: '#fbbf24',
    reviewing: '#f97316',
    completed: '#34d399',
  }
  return map[step] || '#94a3b8'
}

function stepLabel(step: string) {
  return step || 'progress'
}
</script>

<template>
  <section class="glass panel events-panel">
    <div class="panel-head">
      <h2>{{ t('events.title') }}</h2>
    </div>
    <div class="events-body custom-scrollbar">
      <transition-group name="ev" tag="ul" class="events-list">
        <li v-for="(ev, idx) in events" :key="idx" class="event-row" :class="{ 'progress-row': isProgress(ev) }">
          <template v-if="isProgress(ev)">
            <div class="progress-meta">
              <span class="timestamp">{{ ev.time }}</span>
              <span class="progress-source">{{ ev.data.source === 'http' ? 'HTTP' : 'FILE' }}</span>
            </div>
            <div class="progress-content">
              <span class="progress-step" :style="{ backgroundColor: stepColor(ev.data.progress.step) + '22', color: stepColor(ev.data.progress.step), borderColor: stepColor(ev.data.progress.step) + '44' }">
                {{ stepLabel(ev.data.progress.step) }}
              </span>
              <span class="progress-message">{{ ev.data.progress.message }}</span>
            </div>
            <div class="progress-task">Task: {{ ev.data.task_id }}</div>
          </template>
          <template v-else>
            <div class="event-meta">
              <span class="timestamp">{{ ev.time }}</span>
              <span class="event-name">{{ ev.event }}</span>
            </div>
            <div class="event-data">{{ JSON.stringify(ev.data) }}</div>
          </template>
        </li>
      </transition-group>
      <div v-if="events.length === 0" class="empty-events">
        <p>{{ t('events.empty') }}</p>
      </div>
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

.event-row.progress-row {
  background: rgba(255,255,255,0.025);
  border-left: 3px solid rgba(34,211,238,0.35);
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

.progress-meta {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.35rem;
}

.progress-source {
  font-size: 0.65rem;
  padding: 0.15rem 0.4rem;
  border-radius: 0.25rem;
  background: rgba(255,255,255,0.06);
  color: #94a3b8;
}

.progress-content {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
  margin-bottom: 0.25rem;
}

.progress-step {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.55rem;
  border-radius: 0.35rem;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  border: 1px solid;
}

.progress-message {
  color: #e2e8f0;
  font-weight: 500;
}

.progress-task {
  font-size: 0.7rem;
  color: #64748b;
}

.empty-events {
  padding: 2.5rem;
  text-align: center;
  color: #64748b;
  font-size: 0.9rem;
}

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
