<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Monitor,
  CircleCheck,
  CircleX,
  Timer,
  Loader2,
} from 'lucide-vue-next'

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
    <div class="glass-card card animate-fade-in-up animate-delay-1">
      <div class="card-top">
        <div>
          <div class="card-label">{{ t('stats.total') }}</div>
          <div class="card-value">{{ metrics.total_tasks }}</div>
        </div>
        <div class="icon-wrap icon-total">
          <Monitor :size="22" />
        </div>
      </div>
      <div class="card-bar"><div class="bar-fill" :style="{ width: '100%' }"></div></div>
    </div>

    <div class="glass-card card animate-fade-in-up animate-delay-2">
      <div class="card-top">
        <div>
          <div class="card-label">{{ t('stats.completed') }}</div>
          <div class="card-value text-emerald">{{ metrics.completed }}</div>
        </div>
        <div class="icon-wrap icon-emerald">
          <CircleCheck :size="22" />
        </div>
      </div>
      <div class="card-bar"><div class="bar-fill bar-emerald" :style="{ width: (metrics.completed / totalTasksForPercent * 100) + '%' }"></div></div>
    </div>

    <div class="glass-card card animate-fade-in-up animate-delay-3">
      <div class="card-top">
        <div>
          <div class="card-label">{{ t('stats.failed') }}</div>
          <div class="card-value text-rose">{{ metrics.failed }}</div>
        </div>
        <div class="icon-wrap icon-rose">
          <CircleX :size="22" />
        </div>
      </div>
      <div class="card-bar"><div class="bar-fill bar-rose" :style="{ width: (metrics.failed / totalTasksForPercent * 100) + '%' }"></div></div>
    </div>

    <div class="glass-card card animate-fade-in-up animate-delay-4">
      <div class="card-top">
        <div>
          <div class="card-label">{{ t('stats.pending') }}</div>
          <div class="card-value text-amber">{{ metrics.pending }}</div>
        </div>
        <div class="icon-wrap icon-amber">
          <Timer :size="22" />
        </div>
      </div>
      <div class="card-bar"><div class="bar-fill bar-amber" :style="{ width: (metrics.pending / totalTasksForPercent * 100) + '%' }"></div></div>
    </div>

    <div class="glass-card card animate-fade-in-up animate-delay-5">
      <div class="card-top">
        <div>
          <div class="card-label">{{ t('stats.running') }}</div>
          <div class="card-value text-cyan">{{ metrics.running }}</div>
        </div>
        <div class="icon-wrap icon-cyan">
          <Loader2 :size="22" class="spin-slow" />
        </div>
      </div>
      <div class="card-bar"><div class="bar-fill bar-cyan" :style="{ width: (metrics.running / totalTasksForPercent * 100) + '%' }"></div></div>
    </div>

    <div class="glass-card card animate-fade-in-up animate-delay-6">
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
  padding: 1.1rem;
}

.card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.card-label {
  font-size: 0.875rem;
  color: var(--z-text-secondary);
  font-weight: 500;
}

.card-value {
  margin-top: 0.35rem;
  font-size: 1.9rem;
  font-weight: 600;
  color: var(--z-text-primary);
  font-family: var(--font-display);
}

.card-value small { font-size: 0.65rem; opacity: 0.8; margin-left: 2px; }

.text-emerald { color: var(--z-success); }
.text-rose { color: var(--z-danger); }
.text-amber { color: var(--z-warning); }
.text-cyan { color: var(--z-accent-cyan); }

.icon-wrap {
  width: 2.75rem;
  height: 2.75rem;
  border-radius: 0.85rem;
  display: grid;
  place-items: center;
}

.icon-total { background: rgba(148,163,184,0.10); color: var(--z-text-secondary); }
.icon-emerald { background: rgba(52,211,153,0.12); color: var(--z-success); }
.icon-rose { background: rgba(251,113,133,0.12); color: var(--z-danger); }
.icon-amber { background: rgba(251,191,36,0.12); color: var(--z-warning); }
.icon-cyan { background: rgba(34,211,238,0.12); color: var(--z-accent-cyan); }

.spin-slow {
  animation: spin 2.2s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

.card-bar {
  margin-top: 0.9rem;
  height: 5px;
  width: 100%;
  background: rgba(255,255,255,0.05);
  border-radius: 999px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: var(--z-text-secondary);
  border-radius: 999px;
  transition: width 0.7s ease;
}

.bar-emerald { background: var(--z-success); }
.bar-rose { background: var(--z-danger); }
.bar-amber { background: var(--z-warning); }
.bar-cyan { background: var(--z-accent-cyan); }
.bar-violet { background: var(--z-violet); }

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
  stroke: var(--z-violet);
  stroke-width: 4;
  stroke-linecap: round;
  transition: stroke-dasharray 0.6s ease;
}
</style>
