import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useEventStore = defineStore('event', () => {
  const liveEvents = ref<any[]>([])
  const historyEvents = ref<any[]>([])
  const loading = ref(false)

  async function fetchHistory(limit = 50, offset = 0) {
    loading.value = true
    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_BASE || ''}/events?limit=${limit}&offset=${offset}`
      )
      if (res.ok) {
        historyEvents.value = await res.json()
      }
    } catch {
    } finally {
      loading.value = false
    }
  }

  function pushLive(msg: any) {
    liveEvents.value.unshift(msg)
    if (liveEvents.value.length > 200) liveEvents.value.pop()
  }

  return { liveEvents, historyEvents, loading, fetchHistory, pushLive }
})
