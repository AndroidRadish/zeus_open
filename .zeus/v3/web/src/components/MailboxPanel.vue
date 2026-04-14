<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Mail, Eye, Search } from 'lucide-vue-next'

const { t } = useI18n()

interface Message {
  id: number
  ts: string
  from_agent: string | null
  to_agent: string | null
  message: string | null
  read: boolean
}

const messages = ref<Message[]>([])
const filterTo = ref('')
const filterUnread = ref(false)
const loading = ref(false)

async function fetchMessages() {
  loading.value = true
  const params = new URLSearchParams()
  if (filterTo.value.trim()) params.set('to_agent', filterTo.value.trim())
  if (filterUnread.value) params.set('read', 'false')
  params.set('limit', '100')
  try {
    const res = await fetch(`/mailbox?${params.toString()}`)
    messages.value = await res.json()
  } catch (e) {
    console.error('fetch mailbox error', e)
  } finally {
    loading.value = false
  }
}

async function markRead(id: number) {
  try {
    await fetch(`/mailbox/${id}/read`, { method: 'POST' })
    await fetchMessages()
  } catch (e) {
    console.error('mark read error', e)
  }
}

onMounted(fetchMessages)
</script>

<template>
  <div class="mailbox-panel glass-card">
    <div class="panel-head">
      <h2><Mail :size="18" class="head-icon" /> {{ t('mailbox.title') }}</h2>
      <div class="filters">
        <div class="search-box">
          <Search :size="14" class="search-icon" />
          <input
            v-model="filterTo"
            type="text"
            class="filter-input"
            :placeholder="t('mailbox.to') + ' agent...'"
            @keydown.enter="fetchMessages"
          />
        </div>
        <label class="filter-check">
          <input v-model="filterUnread" type="checkbox" @change="fetchMessages" />
          Unread only
        </label>
        <button class="btn-refresh" @click="fetchMessages">Refresh</button>
      </div>
    </div>

    <div v-if="loading" class="empty">Loading…</div>
    <div v-else-if="messages.length === 0" class="empty">{{ t('mailbox.empty') }}</div>

    <div v-else class="message-list">
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="message-card"
        :class="{ unread: !msg.read }"
      >
        <div class="message-meta">
          <span class="message-from">{{ t('mailbox.from') }}: {{ msg.from_agent || '-' }}</span>
          <span class="message-to">{{ t('mailbox.to') }}: {{ msg.to_agent || '-' }}</span>
          <span class="message-time">{{ new Date(msg.ts).toLocaleString() }}</span>
        </div>
        <div class="message-body">{{ msg.message || '-' }}</div>
        <div v-if="!msg.read" class="message-actions">
          <button class="btn-action" @click="markRead(msg.id)">
            <Eye :size="13" /> {{ t('mailbox.markRead') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mailbox-panel {
  padding: 1rem;
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.85rem;
  flex-wrap: wrap;
  gap: 0.5rem;
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
.filters {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
}
.search-box {
  position: relative;
  display: flex;
  align-items: center;
}
.search-icon {
  position: absolute;
  left: 0.55rem;
  color: var(--z-text-muted);
  pointer-events: none;
}
.filter-input {
  appearance: none;
  border: 1px solid var(--z-border);
  background: rgba(255,255,255,0.03);
  color: #e2e8f0;
  font-size: 0.8rem;
  padding: 0.4rem 0.7rem 0.4rem 1.9rem;
  border-radius: 0.5rem;
  min-width: 150px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.filter-input:focus {
  border-color: rgba(34, 211, 238, 0.35);
  box-shadow: 0 0 0 3px rgba(34, 211, 238, 0.08);
}
.filter-input::placeholder { color: var(--z-text-muted); }
.filter-check {
  color: var(--z-text-secondary);
  font-size: 0.8rem;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  cursor: pointer;
}
.btn-refresh {
  appearance: none;
  border: 1px solid var(--z-border);
  background: rgba(255,255,255,0.04);
  color: #e2e8f0;
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.35rem 0.7rem;
  border-radius: 0.4rem;
  cursor: pointer;
  transition: all 0.2s ease;
}
.btn-refresh:hover { background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.14); }
.empty {
  color: var(--z-text-muted);
  font-size: 0.9rem;
  padding: 1rem 0;
}
.message-list {
  display: grid;
  gap: 0.6rem;
}
.message-card {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 0.75rem;
  padding: 0.9rem;
  transition: box-shadow 0.15s ease, background 0.15s ease;
}
.message-card:hover {
  background: rgba(255,255,255,0.045);
}
.message-card.unread {
  border-left: 3px solid var(--z-accent-cyan);
}
.message-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  font-size: 0.8rem;
  color: var(--z-text-secondary);
  margin-bottom: 0.5rem;
}
.message-time {
  margin-left: auto;
}
.message-body {
  color: #e2e8f0;
  font-size: 0.9rem;
  line-height: 1.55;
  white-space: pre-wrap;
}
.message-actions {
  margin-top: 0.6rem;
}
.btn-action {
  appearance: none;
  border: 1px solid rgba(34,211,238,0.2);
  background: rgba(34,211,238,0.1);
  color: var(--z-accent-cyan);
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.35rem 0.65rem;
  border-radius: 0.4rem;
  cursor: pointer;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.btn-action:hover {
  background: rgba(34,211,238,0.16);
  border-color: rgba(34,211,238,0.35);
}
</style>
