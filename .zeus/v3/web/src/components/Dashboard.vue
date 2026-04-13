<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

interface Task {
  id: string
  title?: string
  wave?: number
  status: string
  passes: boolean
}

interface Metrics {
  total_tasks: number
  completed: number
  failed: number
  pending: number
  running: number
  pass_rate: number
}

const tasks = ref<Task[]>([])
const metrics = ref<Metrics | null>(null)
const events = ref<{ time: string; event: string; data: any }[]>([])
const connected = ref(false)

let es: EventSource | null = null
let pollTimer: number | null = null

async function fetchMetrics() {
  try {
    const res = await fetch('/metrics/summary')
    metrics.value = await res.json()
  } catch (e) {
    console.error('fetch metrics error', e)
  }
}

async function fetchTasks() {
  try {
    const res = await fetch('/tasks')
    tasks.value = await res.json()
  } catch (e) {
    console.error('fetch tasks error', e)
  }
}

function connectSSE() {
  es = new EventSource('/events/stream')
  es.onopen = () => { connected.value = true }
  es.onerror = () => { connected.value = false }
  es.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data)
      events.value.unshift({
        time: new Date().toLocaleTimeString(),
        event: msg.event,
        data: msg.data,
      })
      if (events.value.length > 50) events.value.pop()
      if (msg.event && msg.event.startsWith('task.')) {
        fetchTasks()
        fetchMetrics()
      }
    } catch (e) {
      console.error('sse parse error', e)
    }
  }
}

onMounted(() => {
  fetchMetrics()
  fetchTasks()
  connectSSE()
  pollTimer = window.setInterval(() => {
    fetchMetrics()
    fetchTasks()
  }, 5000)
})

onUnmounted(() => {
  es?.close()
  if (pollTimer) clearInterval(pollTimer)
})

function statusClass(status: string) {
  return ['pending', 'running', 'completed', 'failed'].includes(status) ? status : 'pending'
}
</script>

<template>
  <div class="dashboard">
    <header>
      <h1>⚡ ZeusOpen v3 Dashboard</h1>
      <div class="status" :class="{ online: connected, offline: !connected }">
        SSE: {{ connected ? 'connected' : 'disconnected' }}
      </div>
    </header>

    <main>
      <div class="metrics" v-if="metrics">
        <div class="card"><div class="value">{{ metrics.total_tasks }}</div><div class="label">Total</div></div>
        <div class="card"><div class="value">{{ metrics.completed }}</div><div class="label">Completed</div></div>
        <div class="card"><div class="value">{{ metrics.failed }}</div><div class="label">Failed</div></div>
        <div class="card"><div class="value">{{ metrics.pending }}</div><div class="label">Pending</div></div>
        <div class="card"><div class="value">{{ metrics.running }}</div><div class="label">Running</div></div>
        <div class="card"><div class="value">{{ (metrics.pass_rate * 100).toFixed(1) }}%</div><div class="label">Pass Rate</div></div>
      </div>

      <div class="section">
        <h2>Tasks</h2>
        <table>
          <thead>
            <tr><th>ID</th><th>Title</th><th>Wave</th><th>Status</th><th>Pass</th></tr>
          </thead>
          <tbody>
            <tr v-for="t in tasks" :key="t.id">
              <td>{{ t.id }}</td>
              <td>{{ t.title || '' }}</td>
              <td>{{ t.wave ?? '-' }}</td>
              <td><span class="badge" :class="statusClass(t.status)">{{ t.status }}</span></td>
              <td>{{ t.passes ? '✅' : '❌' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="section">
        <h2>Live Events</h2>
        <ul class="events">
          <li v-for="(ev, idx) in events" :key="idx">
            <span class="time">[{{ ev.time }}]</span>
            <strong>{{ ev.event }}</strong>
            <span class="data">{{ JSON.stringify(ev.data) }}</span>
          </li>
        </ul>
      </div>
    </main>
  </div>
</template>

<style scoped>
.dashboard { background: #0f172a; color: #e2e8f0; min-height: 100vh; }
header { background: #1e293b; padding: 1rem 1.5rem; border-bottom: 1px solid #334155; display: flex; align-items: center; justify-content: space-between; }
h1 { margin: 0; font-size: 1.25rem; color: #38bdf8; }
.status { font-size: .875rem; color: #94a3b8; }
.status.online { color: #4ade80; }
.status.offline { color: #f87171; }
main { max-width: 1200px; margin: 0 auto; padding: 1.5rem; }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
.card { background: #1e293b; border: 1px solid #334155; border-radius: .5rem; padding: 1rem; text-align: center; }
.card .value { font-size: 1.5rem; font-weight: 700; }
.card .label { font-size: .75rem; color: #94a3b8; margin-top: .25rem; }
.section { background: #1e293b; border: 1px solid #334155; border-radius: .5rem; padding: 1rem; margin-bottom: 1rem; }
.section h2 { margin: 0 0 .75rem; font-size: 1rem; color: #bae6fd; }
table { width: 100%; border-collapse: collapse; font-size: .875rem; }
th, td { padding: .5rem .75rem; text-align: left; border-bottom: 1px solid #334155; }
th { color: #94a3b8; font-weight: 500; }
.badge { display: inline-block; padding: .15rem .5rem; border-radius: 9999px; font-size: .75rem; font-weight: 600; }
.badge.pending { background: #f59e0b22; color: #f59e0b; }
.badge.running { background: #3b82f622; color: #3b82f6; }
.badge.completed { background: #22c55e22; color: #22c55e; }
.badge.failed { background: #ef444422; color: #ef4444; }
.events { max-height: 240px; overflow-y: auto; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: .75rem; list-style: none; padding: 0; margin: 0; }
.events li { padding: .25rem 0; border-bottom: 1px solid #334155; }
.events .time { color: #94a3b8; margin-right: .5rem; }
.events .data { color: #cbd5e1; margin-left: .5rem; }
</style>
