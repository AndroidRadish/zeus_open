<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

interface Metrics {
  total_tasks: number
  completed: number
  failed: number
  pending: number
  running: number
  pass_rate: number
}

const props = defineProps<{
  metrics: Metrics | null
}>()

const totalTasksForPercent = computed(() => {
  const m = props.metrics
  if (!m || m.total_tasks === 0) return 1
  return m.total_tasks
})

const passRateCircumference = 2 * Math.PI * 18
</script>

<template>
  <section class="stats-grid" v-if="metrics">
    <div class="glass card">
      <div class="card-top">
        <div>
          <div class="card-label">{{ t('stats.total') }}</div>
          <div class="card-value">{{ metrics.total_tasks }}</div>
        </div>
        <div class="icon-wrap icon-total">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect width="20" height="14" x="2" y="3" rx="2"/>
            <line x1="8" x2="16" y1="21" y2="21"/>
            <line x1="12" x2="12" y1="17" y2="21"/>
          </svg>
        </div>
      </div>
      <div class="card-bar"><div class="bar-fill" :style="{ width: '100%' }"></div></div>
    </div>

    <div class="glass card">
      <div class="card-top">
        <div>
          <div class="card-label">{{ t('stats.completed') }}</div>
          <div class="card-value text-emerald">{{ metrics.completed }}</div>
        </div>
        <div class="icon-wrap icon-emerald">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
            <polyline points="22 4 12 14.01 9 11.01"/>
          </svg>
        </div>
      </div>
      <div class="card-bar"><div class="bar-fill bar-emerald" :style="{ width: (metrics.completed / totalTasksForPercent * 100) + '%' }"></div></div>
    </div>

    <div class="glass card">
      <div class="card-top">
        <div>
          <div class="card-label">{{ t('stats.failed') }}</div>
          <div class="card-value text-rose">{{ metrics.failed }}</div>
        </div>
        <div class="icon-wrap icon-rose">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="15" x2="9" y1="9" y2="15"/>
            <line x1="9" x2="15" y1="9" y2="15"/>
          </svg>
        </div>
      </div>
      <div class="card-bar"><div class="bar-fill bar-rose" :style="{ width: (metrics.failed / totalTasksForPercent * 100) + '%' }"></div></div>
    </div>

    <div class="glass card">
      <div class="card-top">
        <div>
          <div class="card-label">{{ t('stats.pending') }}</div>
          <div class="card-value text-amber">{{ metrics.pending }}</div>
        </div>
        <div class="icon-wrap icon-amber">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
        </div>
      </div>
      <div class="card-bar"><div class="bar-fill bar-amber" :style="{ width: (metrics.pending / totalTasksForPercent * 100) + '%' }"></div></div>
    </div>

    <div class="glass card">
      <div class="card-top">
        <div>
          <div class="card-label">{{ t('stats.running') }}</div>
          <div class="card-value text-cyan">{{ metrics.running }}</div>
        </div>
        <div class="icon-wrap icon-cyan">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
          </svg>
        </div>
      </div>
      <div class="card-bar"><div class="bar-fill bar-cyan" :style="{ width: (metrics.running / totalTasksForPercent * 100) + '%' }"></div></div>
    </div>

    <div class="glass card">
      <div class="card-top">
        <div>
          <div class="card-label">{{ t('stats.passRate') }}</div>
          <div class="card-value">{{ (metrics.pass_rate * 100).toFixed(0) }}<small>%</small></div>
        </div>
        <div class="ring">
          <svg viewBox="0 0 40 40">
            <circle cx="20" cy="20" r="18" class="track"></circle>
            <circle cx="20" cy="20" r="18" class="fill"
              :stroke-dasharray="`${passRateCircumference * (metrics.pass_rate || 0)} ${passRateCircumference}`"></circle>
          </svg>
        </div>
      </div>
      <div class="card-bar"><div class="bar-fill bar-violet" :style="{ width: (metrics.pass_rate * 100) + '%' }"></div></div>
    </div>
  </section>
</template>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
  margin-bottom: 1.25rem;
}

@media (min-width: 640px) {
  .stats-grid { grid-template-columns: repeat(3, 1fr); }
}

.card {
  border-radius: 1rem;
  padding: 1.1rem;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.card:hover {
  transform: translateY(-2px);
  background: rgba(255,255,255,0.045);
  border-color: rgba(255,255,255,0.10);
  box-shadow: 0 8px 30px rgba(0,0,0,0.35);
}

.card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.card-label {
  font-size: 0.875rem;
  color: #94a3b8;
  font-weight: 500;
}

.card-value {
  margin-top: 0.35rem;
  font-size: 1.75rem;
  font-weight: 700;
  color: #f8fafc;
}

.card-value small { font-size: 0.65rem; opacity: 0.8; margin-left: 2px; }

.text-emerald { color: #34d399; }
.text-rose { color: #fb7185; }
.text-amber { color: #fbbf24; }
.text-cyan { color: #22d3ee; }

.icon-wrap {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 0.75rem;
  display: grid;
  place-items: center;
}

.icon-wrap svg { width: 1.4rem; height: 1.4rem; }

.icon-total { background: rgba(148,163,184,0.10); color: #94a3b8; }
.icon-emerald { background: rgba(52,211,153,0.10); color: #34d399; }
.icon-rose { background: rgba(251,113,133,0.10); color: #fb7185; }
.icon-amber { background: rgba(251,191,36,0.10); color: #fbbf24; }
.icon-cyan { background: rgba(34,211,238,0.10); color: #22d3ee; }

.card-bar {
  margin-top: 0.9rem;
  height: 4px;
  width: 100%;
  background: rgba(255,255,255,0.05);
  border-radius: 999px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: #94a3b8;
  border-radius: 999px;
  transition: width 0.7s ease;
}

.bar-emerald { background: #34d399; }
.bar-rose { background: #fb7185; }
.bar-amber { background: #fbbf24; }
.bar-cyan { background: #22d3ee; }
.bar-violet { background: #a78bfa; }

.ring {
  position: relative;
  width: 44px;
  height: 44px;
}

.ring svg {
  width: 44px;
  height: 44px;
  transform: rotate(-90deg);
}

.ring .track {
  fill: none;
  stroke: rgba(255,255,255,0.08);
  stroke-width: 4;
}

.ring .fill {
  fill: none;
  stroke: #a78bfa;
  stroke-width: 4;
  stroke-linecap: round;
  transition: stroke-dasharray 0.6s ease;
}
</style>
