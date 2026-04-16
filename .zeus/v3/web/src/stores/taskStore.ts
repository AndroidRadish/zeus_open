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
  let reconnectTimer: any = null
  let reconnectDelay = 3000
  const maxReconnectDelay = 30000
  let currentLocale: string | undefined

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
    const res = await fetch(`${import.meta.env.VITE_API_BASE || ''}/control/project/switch`, {
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
    currentLocale = locale
    try {
      const base = (import.meta.env.VITE_API_BASE as string) || (typeof window !== 'undefined' ? window.location.origin : '')
      const urlStr = `${base.replace(/\/$/, '')}/events/stream${locale ? `?lang=${encodeURIComponent(locale)}` : ''}`
      es = new EventSource(urlStr)
      es.onopen = () => {
        connected.value = true
        reconnectDelay = 3000
      }
      es.onerror = () => {
        connected.value = false
        scheduleReconnect()
      }
      const eventStore = useEventStore()
      es.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          eventStore.pushLive(data)
        } catch {}
      }
    } catch (e) {
      console.error('[SSE] failed to connect:', e)
      connected.value = false
      scheduleReconnect()
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) return
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      if (!es) return
      reconnectDelay = Math.min(reconnectDelay * 2, maxReconnectDelay)
      connectSSE(currentLocale)
    }, reconnectDelay)
  }

  function closeSSE() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    es?.close()
    es = null
    connected.value = false
    reconnectDelay = 3000
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
