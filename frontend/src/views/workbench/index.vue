<template>
  <section class="page" data-module="workbench">
    <header class="page-head">
      <div>
        <h2>班组工作台</h2>
        <p class="page-desc">归集本班组待办：检查井归属调整、清掏提醒都会回写到这里，办结后留痕。</p>
      </div>
    </header>

    <p class="identity-hint">{{ identityHint }}</p>

    <form v-if="session.isAdmin" class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>班组</span>
        <select v-model="teamFilter">
          <option value="">全部班组</option>
          <option v-for="team in teams" :key="team" :value="team">{{ team }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th>班组</th>
          <th>类型</th>
          <th>内容</th>
          <th>关联井编号</th>
          <th>时间</th>
          <th>状态</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td>{{ row['班组'] }}</td>
          <td>{{ row['类型'] }}</td>
          <td>{{ row['内容'] }}</td>
          <td>{{ row['关联井编号'] || '—' }}</td>
          <td>{{ row['时间'] }}</td>
          <td>{{ row['status'] }}</td>
          <td class="row-actions">
            <button
              v-if="row['可办结'] && row['status'] === '待办'"
              class="link"
              type="button"
              @click="closeTodo(row)"
            >
              办结
            </button>
            <span v-else class="muted">{{ row['status'] === '待办' ? '仅可查看' : '已办结' }}</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td colspan="7" class="empty-state">暂无待办，检查井归属调整等回写会出现在这里</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条待办</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { readError, request } from '@/api/client'
import { TEAMS, useSessionStore } from '@/stores/session'

type Row = Record<string, unknown> & { id: number | string }

const ENDPOINT = '/api/workbench/todos'

const session = useSessionStore()
const teams = TEAMS

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const teamFilter = ref('')

const identityHint = computed(() =>
  session.isAdmin
    ? '当前身份：值班管理员 —— 可查看全部班组的待办'
    : `当前身份：${session.team}·班组成员 —— 只显示本班组待办，其他班组的待办不可办结`,
)

async function closeTodo(row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '办结' } }),
    })
    if (!response.ok) {
      throw await readError(response, '待办办结未生效，请稍后重试')
    }
    const result = (await response.json()) as { ok: boolean; message: string }
    if (!result.ok) {
      throw new Error(result.message)
    }
    noticeMessage.value = result.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '待办办结失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = teamFilter.value ? `?team=${encodeURIComponent(teamFilter.value)}` : ''
  try {
    const response = await request(`${ENDPOINT}${query}`)
    if (!response.ok) {
      throw await readError(response, '待办列表读取失败')
    }
    const payload = (await response.json()) as { items?: Row[]; total?: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '待办列表读取失败'
  }
}

// 切换身份后待办范围跟着变
watch(() => [session.role, session.team], () => void reload())

onMounted(reload)
</script>
