<script setup lang="ts">
import { ref, watch, nextTick, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { GitGraph, Image as ImageIcon, FileCode, Share2 } from 'lucide-vue-next'
import mermaid from 'mermaid'
import * as echarts from 'echarts'

const { t } = useI18n()

const format = ref<'svg' | 'mermaid' | 'echarts'>('svg')
const mermaidContainer = ref<HTMLDivElement | null>(null)
const echartsContainer = ref<HTMLDivElement | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
let echartsInstance: echarts.ECharts | null = null

mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'loose' })

async function fetchGraph() {
  loading.value = true
  error.value = null
  try {
    if (format.value === 'mermaid') {
      const res = await fetch('/workflow/graph?format=mermaid')
      const text = await res.text()
      await nextTick()
      if (mermaidContainer.value) {
        mermaidContainer.value.innerHTML = text
        await mermaid.run({ nodes: [mermaidContainer.value] })
      }
    } else if (format.value === 'echarts') {
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
            formatter: (params: any) => {
              if (params.dataType === 'edge') return `${params.data.source} → ${params.data.target}`
              const d = params.data
              return `<div style="font-weight:600">${d.name}</div>
                      <div>Wave: ${d.wave}</div>
                      <div>Status: ${d.status}</div>
                      ${d.title ? `<div style="margin-top:4px;color:#94a3b8">${d.title}</div>` : ''}`
            }
          },
          legend: {
            data: data.categories.map((c: any) => c.name),
            textStyle: { color: '#e2e8f0' },
            bottom: 0
          },
          series: [
            {
              type: 'graph',
              layout: 'force',
              data: data.nodes,
              links: data.links,
              categories: data.categories,
              roam: true,
              label: { show: true, color: '#e2e8f0', fontSize: 11 },
              force: { repulsion: 320, edgeLength: [80, 150] },
              lineStyle: { color: '#64748b', curveness: 0.2, width: 1.5 },
              emphasis: {
                focus: 'adjacency',
                lineStyle: { width: 3 },
                label: { fontSize: 13, fontWeight: 'bold' }
              },
              itemStyle: {
                borderColor: 'rgba(255,255,255,0.2)',
                borderWidth: 1
              }
            }
          ]
        })
      }
    }
  } catch (e: any) {
    error.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}

watch(format, fetchGraph, { immediate: true })

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
      <div class="format-switch">
        <button
          v-for="f in (['svg', 'mermaid', 'echarts'] as const)"
          :key="f"
          :class="['fmt-btn', { active: format === f }]"
          @click="format = f"
        >
          <ImageIcon v-if="f === 'svg'" :size="13" />
          <FileCode v-else-if="f === 'mermaid'" :size="13" />
          <Share2 v-else :size="13" />
          <span>{{ f.toUpperCase() }}</span>
        </button>
      </div>
    </div>
    <div class="graph-body custom-scrollbar">
      <div v-if="error" class="graph-error">{{ error }}</div>
      <img
        v-if="format === 'svg'"
        :src="'/workflow/graph?format=svg'"
        alt="Workflow Graph"
        class="graph-img"
      />
      <div v-else-if="format === 'mermaid'" ref="mermaidContainer" class="graph-mermaid"></div>
      <div v-else-if="format === 'echarts'" ref="echartsContainer" class="graph-echarts"></div>
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

.format-switch {
  display: inline-flex;
  gap: 0.25rem;
}

.fmt-btn {
  appearance: none;
  border: 1px solid var(--z-border);
  background: rgba(255,255,255,0.04);
  color: var(--z-text-secondary);
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

.fmt-btn:hover { color: #e2e8f0; background: rgba(255,255,255,0.07); }
.fmt-btn.active {
  background: rgba(34,211,238,0.15);
  color: var(--z-accent-cyan);
  border-color: rgba(34,211,238,0.3);
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

.graph-img {
  max-width: 100%;
  height: auto;
  border-radius: 0.6rem;
  border: 1px solid var(--z-border);
}

.graph-mermaid {
  width: 100%;
  min-height: 400px;
}

.graph-mermaid :deep(.node rect) {
  stroke: rgba(255,255,255,0.2);
  stroke-width: 1px;
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
