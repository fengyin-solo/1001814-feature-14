<template>
  <section class="page" data-module="workbench">
    <header class="page-head">
      <div>
        <h2>班组工作台</h2>
        <p class="page-desc">{{ title }}。归属调整和清掏确认都会在这里形成待办。</p>
      </div>
      <button class="btn" type="button" @click="reload">刷新待办</button>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">待处理总数</span>
        <strong class="stat-value">{{ total }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">清掏确认</span>
        <strong class="stat-value">{{ pendingCleaning }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">归属调整</span>
        <strong class="stat-value">{{ ownershipChanges }}</strong>
      </article>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th>归属班组</th>
          <th>待办类型</th>
          <th>事项</th>
          <th>检查井</th>
          <th>状态</th>
          <th>生成时间</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id">
          <td>{{ item.team }}</td>
          <td>{{ typeLabels[item.type] ?? item.type }}</td>
          <td>{{ item.title }}</td>
          <td>#{{ item.entry_id }}</td>
          <td>{{ item.status }}</td>
          <td>{{ item.created_at }}</td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="6" class="empty-state">当前范围暂无待办</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { fetchJson } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Todo = {
  id: number
  entry_id: number
  type: 'cleaning_confirmation' | 'ownership_transfer'
  team: string
  title: string
  status: string
  created_at: string
}

type WorkbenchPayload = {
  items: Todo[]
  total: number
  pending_cleaning: number
  ownership_changes: number
}

const store = useSessionStore()
const items = ref<Todo[]>([])
const total = ref(0)
const pendingCleaning = ref(0)
const ownershipChanges = ref(0)
const typeLabels: Record<string, string> = {
  cleaning_confirmation: '清掏确认',
  ownership_transfer: '归属调整',
}

const title = computed(() => store.isAdmin ? '值班管理员可跨班组核对全部待办' : `当前班组为 ${store.team}，仅显示本班组待办`)

async function reload() {
  const payload = await fetchJson<WorkbenchPayload>('/api/workbench/todos')
  items.value = payload.items ?? []
  total.value = payload.total ?? 0
  pendingCleaning.value = payload.pending_cleaning ?? 0
  ownershipChanges.value = payload.ownership_changes ?? 0
}

watch(() => [store.role, store.team], () => {
  void reload()
})

onMounted(reload)
</script>
