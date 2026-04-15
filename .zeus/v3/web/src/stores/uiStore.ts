import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUiStore = defineStore('ui', () => {
  const activeTab = ref('overview')
  const logsModal = ref<{ open: boolean; taskId: string; activity: string; loading: boolean }>({
    open: false,
    taskId: '',
    activity: '',
    loading: false,
  })
  const detailDrawer = ref<{ open: boolean; taskId: string | null; task: any | null }>({
    open: false,
    taskId: null,
    task: null,
  })

  function setTab(key: string) {
    activeTab.value = key
  }

  function openLogs(taskId: string) {
    logsModal.value = { open: true, taskId, activity: '', loading: true }
    fetch(`${import.meta.env.VITE_API_BASE || ''}/tasks/${taskId}/logs`)
      .then((r) => r.text())
      .then((text) => {
        logsModal.value.activity = text
      })
      .catch(() => {
        logsModal.value.activity = 'Failed to load logs.'
      })
      .finally(() => {
        logsModal.value.loading = false
      })
  }

  function closeLogs() {
    logsModal.value.open = false
  }

  function openDetail(taskId: string) {
    detailDrawer.value = { open: true, taskId, task: null }
    fetch(`${import.meta.env.VITE_API_BASE || ''}/tasks/${taskId}`)
      .then((r) => r.json())
      .then((data) => {
        detailDrawer.value.task = data
      })
      .catch(() => {
        detailDrawer.value.task = null
      })
  }

  function closeDetail() {
    detailDrawer.value.open = false
  }

  return {
    activeTab,
    logsModal,
    detailDrawer,
    setTab,
    openLogs,
    closeLogs,
    openDetail,
    closeDetail,
  }
})
