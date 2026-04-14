<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

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
  <div class="mailbox-panel">
    <div class="panel-head">
      <h2>{{ t('mailbox.title') }}</h2>
      <div class="filters">
        <input
          v-model="filterTo"
          type="text"
          class="filter-input"
          placeholder="To agent..."
          @keydown.enter="fetchMessages"
        />
        <label class="filter-check">
          <input v-model="filterUnread" type="checkbox" @change="fetchMessages" />
          Unread only
        </label>
        <button class="btn-refresh" @click="fetchMessages">{{ t('feedback.success') }}</button>
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
          <button class="btn-action" @click="markRead(msg.id)">{{ t('mailbox.markRead') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mailbox-panel {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 1rem;
  padding: 1rem;
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.panel-head h2 {
  margin: 0;
  font-size: 1rem;
  color: #f8fafc;
}
.filters {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.filter-input {
  appearance: none;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.03);
  color: #e2e8f0;
  font-size: 0.8rem;
  padding: 0.35rem 0.6rem;
  border-radius: 0.4rem;
  min-width: 140px;
}
.filter-input::placeholder { color: #64748b; }
.filter-check {
  color: #94a3b8;
  font-size: 0.8rem;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  cursor: pointer;
}
.btn-refresh {
  appearance: none;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: #e2e8f0;
  font-size: 0.8rem;
  padding: 0.35rem 0.7rem;
  border-radius: 0.4rem;
  cursor: pointer;
}
.empty {
  color: #94a3b8;
  font-size: 0.9rem;
  padding: 1rem 0;
}
.message-list {
  display: grid;
  gap: 0.6rem;
}
.message-card {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 0.75rem;
  padding: 0.9rem;
  transition: box-shadow 0.15s ease;
}
.message-card.unread {
  border-left: 3px solid #22d3ee;
}
.message-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  font-size: 0.8rem;
  color: #94a3b8;
  margin-bottom: 0.5rem;
}
.message-time {
  margin-left: auto;
}
.message-body {
  color: #e2e8f0;
  font-size: 0.9rem;
  line-height: 1.5;
  white-space: pre-wrap;
}
.message-actions {
  margin-top: 0.6rem;
}
.btn-action {
  appearance: none;
  border: 1px solid rgba(34,211,238,0.2);
  background: rgba(34,211,238,0.1);
  color: #22d3ee;
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.3rem 0.6rem;
  border-radius: 0.35rem;
  cursor: pointer;
}
</style>
