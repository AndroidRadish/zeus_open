<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const format = ref<'svg' | 'mermaid' | 'echarts'>('svg')
const mermaidSrc = ref('')
const echartsJson = ref('')
const loading = ref(false)
const error = ref<string | null>(null)

async function fetchGraph() {
  loading.value = true
  error.value = null
  try {
    if (format.value === 'svg') {
      // handled by img src directly
    } else if (format.value === 'mermaid') {
      const res = await fetch('/workflow/graph?format=mermaid')
      mermaidSrc.value = await res.text()
    } else {
      const res = await fetch('/workflow/graph?format=echarts')
      echartsJson.value = JSON.stringify(await res.json(), null, 2)
    }
  } catch (e: any) {
    error.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}

watch(format, fetchGraph, { immediate: true })
</script>

<template>
  <section class="glass panel graph-panel">
    <div class="panel-head">
      <h2>{{ t('graph.title') }}</h2>
      <div class="format-switch">
        <button
          v-for="f in (['svg', 'mermaid', 'echarts'] as const)"
          :key="f"
          :class="['fmt-btn', { active: format === f }]"
          @click="format = f"
        >
          {{ f.toUpperCase() }}
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
      <pre v-else-if="format === 'mermaid'" class="graph-code">{{ mermaidSrc }}</pre>
      <pre v-else-if="format === 'echarts'" class="graph-code">{{ echartsJson }}</pre>
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

.format-switch {
  display: inline-flex;
  gap: 0.25rem;
}

.fmt-btn {
  appearance: none;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: #94a3b8;
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.3rem 0.6rem;
  border-radius: 0.4rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.fmt-btn:hover { color: #e2e8f0; }
.fmt-btn.active {
  background: rgba(34,211,238,0.15);
  color: #22d3ee;
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
  border-radius: 0.5rem;
}

.graph-code {
  width: 100%;
  margin: 0;
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  background: rgba(0,0,0,0.25);
  color: #e2e8f0;
  font-size: 0.8rem;
  line-height: 1.5;
  overflow: auto;
  white-space: pre;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.graph-error {
  padding: 1rem;
  border-radius: 0.5rem;
  background: rgba(251,113,133,0.12);
  color: #fb7185;
  font-size: 0.9rem;
}
</style>
