<script setup lang="ts">
import { ref, watch, nextTick, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { GitGraph, Share2, RefreshCw } from 'lucide-vue-next'
import * as echarts from 'echarts'

const { t } = useI18n()

const echartsContainer = ref<HTMLDivElement | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
let echartsInstance: echarts.ECharts | null = null

const STATUS_GLOW: Record<string, { color: string; glow: string; border: string }> = {
  completed: { color: '#10b981', glow: 'rgba(16,185,129,0.55)', border: 'rgba(16,185,129,0.6)' },
  running:   { color: '#06b6d4', glow: 'rgba(6,182,212,0.55)',  border: 'rgba(6,182,212,0.6)' },
  failed:    { color: '#f43f5e', glow: 'rgba(244,63,94,0.55)',  border: 'rgba(244,63,94,0.6)' },
  pending:   { color: '#64748b', glow: 'rgba(100,116,139,0.35)', border: 'rgba(100,116,139,0.5)' },
  paused:    { color: '#a78bfa', glow: 'rgba(167,139,250,0.45)', border: 'rgba(167,139,250,0.55)' },
  cancelled: { color: '#94a3b8', glow: 'rgba(148,163,184,0.30)', border: 'rgba(148,163,184,0.4)' },
}

function getNodeStyle(status: string) {
  const s = STATUS_GLOW[status] || STATUS_GLOW.pending
  return {
    color: s.color,
    borderColor: s.border,
    borderWidth: 2,
    shadowBlur: 14,
    shadowColor: s.glow,
  }
}

async function fetchGraph() {
  loading.value = true
  error.value = null
  try {
    const res = await fetch('/workflow/graph?format=echarts')
    const data = await res.json()

    // Apply glow styles per status
    for (const n of data.nodes) {
      n.itemStyle = getNodeStyle(n.status)
      n.label = { color: '#e2e8f0', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }
    }

    await nextTick()
    if (echartsContainer.value) {
      if (echartsInstance) {
        echartsInstance.dispose()
      }
      echartsInstance = echarts.init(echartsContainer.value, 'dark')

      echartsInstance.setOption({
        backgroundColor: 'transparent',
        tooltip: {
          backgroundColor: 'rgba(10,12,24,0.95)',
          borderColor: 'rgba(255,255,255,0.08)',
          textStyle: { color: '#e2e8f0' },
          formatter: (params: any) => {
            if (params.dataType === 'edge') {
              return `<span style="color:#94a3b8">${params.data.source}</span> <span style="color:#64748b">→</span> <span style="color:#94a3b8">${params.data.target}</span>`
            }
            const d = params.data
            const s = STATUS_GLOW[d.status] || STATUS_GLOW.pending
            return `<div style="font-weight:600;margin-bottom:4px">${d.name}</div>
                    <div style="display:flex;align-items:center;gap:6px;margin-bottom:2px">
                      <span style="width:8px;height:8px;border-radius:50%;background:${s.color};box-shadow:0 0 6px ${s.glow};display:inline-block"></span>
                      <span style="text-transform:capitalize">${d.status}</span>
                    </div>
                    <div style="color:#64748b;font-size:12px">Wave ${d.wave}</div>
                    ${d.title ? `<div style="margin-top:6px;color:#94a3b8;font-size:12px;max-width:240px;white-space:normal;line-height:1.4">${d.title}</div>` : ''}`
          }
        },
        series: [
          {
            type: 'graph',
            layout: 'force',
            data: data.nodes,
            links: data.links,
            categories: data.categories,
            roam: true,
            draggable: true,
            cursor: 'grab',
            label: {
              show: true,
              color: '#e2e8f0',
              fontSize: 11,
              fontFamily: 'JetBrains Mono, monospace',
            },
            force: {
              initLayout: 'circular',
              repulsion: 800,
              edgeLength: [50, 200],
              gravity: 0.12,
              friction: 0.65,
              layoutAnimation: true,
            },
            lineStyle: {
              color: 'rgba(100,116,139,0.35)',
              curveness: 0.2,
              width: 1.2,
            },
            emphasis: {
              focus: 'adjacency',
              lineStyle: { width: 3, color: 'rgba(6,182,212,0.5)' },
              label: { fontSize: 13, fontWeight: 'bold', color: '#fff' },
              itemStyle: {
                shadowBlur: 24,
                borderWidth: 3,
              }
            },
            itemStyle: {
              borderColor: 'rgba(255,255,255,0.2)',
              borderWidth: 1.5,
            },
            symbol: 'circle',
          }
        ]
      })

      // Cursor feedback during drag
      echartsInstance.on('mousedown', () => {
        if (echartsContainer.value) {
          echartsContainer.value.style.cursor = 'grabbing'
        }
      })
      echartsInstance.on('mouseup', () => {
        if (echartsContainer.value) {
          echartsContainer.value.style.cursor = ''
        }
      })
    }
  } catch (e: any) {
    error.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}

watch(() => true, fetchGraph, { immediate: true })

onUnmounted(() => {
  if (echartsInstance) {
    echartsInstance.dispose()
    echartsInstance = null
  }
})
</script>

<template>
  <section class="glass-card panel graph-panel">
    <div class="panel-head">
      <h2><GitGraph :size="18" class="head-icon" /> {{ t('graph.title') }}</h2>
      <div class="head-actions">
        <button class="btn-refresh" :disabled="loading" @click="fetchGraph">
          <RefreshCw :size="14" :class="{ spinner: loading }" />
          {{ t('actions.refresh') }}
        </button>
        <div class="format-badge">
          <Share2 :size="13" />
          <span>ECHARTS</span>
        </div>
      </div>
    </div>
    <div class="graph-body custom-scrollbar">
      <div v-if="error" class="graph-error">{{ error }}</div>
      <div ref="echartsContainer" class="graph-echarts"></div>
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
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.btn-refresh:hover { background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.14); }
.btn-refresh:disabled { opacity: 0.5; cursor: not-allowed; }

.spinner {
  animation: spin 1.2s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

.format-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.35rem 0.65rem;
  border-radius: 0.45rem;
  background: rgba(34,211,238,0.12);
  color: var(--z-accent-cyan);
  border: 1px solid rgba(34,211,238,0.25);
}

.graph-body {
  padding: 1rem;
  min-height: 320px;
  max-height: 640px;
  overflow: auto;
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.graph-echarts {
  width: 100%;
  height: 520px;
}

.graph-error {
  padding: 1rem;
  border-radius: 0.6rem;
  background: rgba(251,113,133,0.12);
  color: var(--z-danger);
  font-size: 0.9rem;
  border: 1px solid rgba(251,113,133,0.2);
}
</style>
