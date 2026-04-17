<script setup lang="ts">
import { ref, watch, nextTick, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { GitGraph, Share2 } from 'lucide-vue-next'
import * as echarts from 'echarts'

const { t } = useI18n()

const echartsContainer = ref<HTMLDivElement | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
let echartsInstance: echarts.ECharts | null = null

async function fetchGraph() {
  loading.value = true
  error.value = null
  try {
    const res = await fetch('/workflow/graph?format=echarts')
    const data = await res.json()
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
            if (params.dataType === 'edge') return `${params.data.source} → ${params.data.target}`
            const d = params.data
            const statusColor = d.status === 'completed' ? '#10b981' : d.status === 'failed' ? '#f43f5e' : d.status === 'running' ? '#06b6d4' : '#94a3b8'
            return `<div style="font-weight:600;margin-bottom:4px">${d.name}</div>
                    <div style="display:flex;align-items:center;gap:6px;margin-bottom:2px">
                      <span style="width:8px;height:8px;border-radius:50%;background:${statusColor};display:inline-block"></span>
                      <span style="text-transform:capitalize">${d.status}</span>
                    </div>
                    <div style="color:#64748b;font-size:12px">Wave ${d.wave}</div>
                    ${d.title ? `<div style="margin-top:6px;color:#94a3b8;font-size:12px;max-width:240px;white-space:normal;line-height:1.4">${d.title}</div>` : ''}`
          }
        },
        // No legend — aligned with v2 clean style
        series: [
          {
            type: 'graph',
            layout: 'force',
            data: data.nodes,
            links: data.links,
            categories: data.categories,
            roam: true,
            label: {
              show: true,
              color: '#e2e8f0',
              fontSize: 11,
              fontFamily: 'JetBrains Mono, monospace',
            },
            force: {
              repulsion: 400,
              edgeLength: [80, 160],
              gravity: 0.1,
            },
            lineStyle: {
              color: 'rgba(100,116,139,0.5)',
              curveness: 0.2,
              width: 1.2,
            },
            emphasis: {
              focus: 'adjacency',
              lineStyle: { width: 2.5, color: 'rgba(6,182,212,0.6)' },
              label: { fontSize: 13, fontWeight: 'bold' }
            },
            itemStyle: {
              borderColor: 'rgba(255,255,255,0.15)',
              borderWidth: 1.5,
              shadowBlur: 8,
              shadowColor: 'rgba(0,0,0,0.3)',
            },
            symbol: 'circle',
          }
        ]
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
      <div class="format-badge">
        <Share2 :size="13" />
        <span>ECHARTS</span>
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
