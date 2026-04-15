import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useEventStore } from './eventStore'

export const useTaskStore = defineStore('task', () => {
  const tasks = ref<any[]>([])
  const metrics = ref<any>(null)
  const connected = ref(false)
  const health = ref<any>(null)
  let es: EventSource | null = null
  let pollTimer: any = null

  async function fetchTasks() {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE || ''}/tasks`)
      if (res.ok) tasks.value = await res.json()
    } catch {}
  }

  async function fetchMetrics() {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE || ''}/metrics/summary`)
      if (res.ok) metrics.value = await res.json()
    } catch {}
  }

  async function fetchHealth() {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE || ''}/health`)
      if (res.ok) health.value = await res.json()
    } catch {
      health.value = { status: 'error' }
    }
  }

  async function taskAction(action: string, id: string) {
    await fetch(`${import.meta.env.VITE_API_BASE || ''}/tasks/${id}/${action}`, { method: 'POST' })
    await fetchTasks()
  }

  async function switchProject(root: string) {
    const res = await fetch(`${import.meta.env.VITE_API_BASE || ''}/project`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ root }),
    })
    if (res.ok) {
      await fetchTasks()
      await fetchMetrics()
      return true
    }
    return false
  }

  function connectSSE(locale?: string) {
    closeSSE()
    const base = import.meta.env.VITE_API_BASE || window.location.origin
    const url = new URL(`${base}/events/stream`)
    if (locale) url.searchParams.set('lang', locale)
    es = new EventSource(url.toString())
    es.onopen = () => {
      connected.value = true
    }
    es.onerror = () => {
      connected.value = false
    }
    const eventStore = useEventStore()
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        eventStore.pushLive(data)
      } catch {}
    }
  }

  function closeSSE() {
    es?.close()
    es = null
    connected.value = false
  }

  function startPolling() {
    stopPolling()
    pollTimer = setInterval(() => {
      fetchTasks()
      fetchMetrics()
    }, 8000)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    closeSSE()
  }

  return {
    tasks,
    metrics,
    connected,
    health,
    fetchTasks,
    fetchMetrics,
    fetchHealth,
    taskAction,
    switchProject,
    connectSSE,
    closeSSE,
    startPolling,
    stopPolling,
  }
})
