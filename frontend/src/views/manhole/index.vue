<template>
  <section class="page" data-module="manhole">
    <header class="page-head">
      <div>
        <h2>检查井管理</h2>
        <p class="page-desc">每座检查井按责任班组维护；本班组可登记、确认清掏结果，其他班组只读，值班管理员可跨班组核对和调整归属。</p>
      </div>
      <div class="page-actions">
        <button v-if="store.isCrew && scope === 'mine'" class="btn primary" type="button" @click="openAllScope">跨班组查看</button>
        <button v-if="store.isCrew && scope === 'all'" class="btn" type="button" @click="showMine">只看本班组</button>
        <button class="btn" type="button" @click="openCreate" :disabled="!store.canOperate">登记检查井</button>
        <button class="btn" type="button" @click="exportRows">导出检查井清单</button>
      </div>
    </header>

    <div class="notice-bar" :class="scope === 'all' && store.isCrew ? 'readonly' : 'owned'">
      <template v-if="store.isAdmin">值班管理员：可查看全部班组，并对已登记结果进行跨班组核对或调整归属；不能替班组登记、确认。</template>
      <template v-else-if="scope === 'all'">{{ store.team }} 正在跨班组查看：可见归属班组和最近一次清掏情况，但不能提交其他班组记录。</template>
      <template v-else>{{ store.team }}：仅可维护归属本班组的检查井。</template>
    </div>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>井编号</span>
        <input v-model="keyword" placeholder="按井编号检索" />
      </label>
      <label class="filter-item">
        <span>检查井状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ displayValue(row, column) }}</td>
          <td class="row-actions">
            <template v-if="permissions(row).can_register_cleaning">
              <button class="link" type="button" @click="registerCleaning(row)">登记清掏结果</button>
            </template>
            <template v-if="permissions(row).can_confirm_cleaning">
              <button class="link" type="button" @click="confirmCleaning(row)">确认清掏结果</button>
            </template>
            <template v-if="permissions(row).can_verify_cleaning">
              <button class="link" type="button" @click="verifyCleaning(row)">跨班组核对</button>
            </template>
            <template v-if="permissions(row).can_change_owner">
              <button class="link" type="button" @click="changeOwner(row)">调整归属</button>
            </template>
            <span v-if="!hasAnyPermission(row)" class="readonly-text">只读</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyText }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条检查井记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { readError, request } from '@/api/client'
import { TEAMS, useSessionStore } from '@/stores/session'

type Permissions = {
  can_view: boolean
  can_register_cleaning: boolean
  can_confirm_cleaning: boolean
  can_verify_cleaning: boolean
  can_change_owner: boolean
  can_create_manhole: boolean
}

type Row = Record<string, string | number | null> & {
  权限?: Permissions
}

const ENDPOINT = '/api/manhole'
const columns = ['井编号', '所在道路', '井盖类别', '井室深度', '井室尺寸', '责任班组', '最近清掏日', '最近清掏情况', '清掏确认状态', '历史归属班组', '检查井状态']
const statuses = ['待清掏', '正常使用', '井盖缺失', '已废弃']

const store = useSessionStore()
const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const scope = ref<'mine' | 'all'>(store.isAdmin ? 'all' : 'mine')

const stats = computed(() => [
  { label: store.isAdmin ? '全部检查井' : '本班组检查井', value: total.value },
  { label: '待清掏井室', value: rows.value.filter((row) => row.status === '待清掏').length },
  { label: '待确认清掏', value: rows.value.filter((row) => row['清掏确认状态'] === '待确认').length },
])
const emptyText = computed(() => scope.value === 'all' ? '暂无检查井数据' : '本班组暂无归属检查井，可切换跨班组查看')

watch(() => [store.role, store.team], () => {
  scope.value = store.isAdmin ? 'all' : 'mine'
  void reload()
})

function permissions(row: Row): Permissions {
  return row.权限 ?? {
    can_view: true,
    can_register_cleaning: false,
    can_confirm_cleaning: false,
    can_verify_cleaning: false,
    can_change_owner: false,
    can_create_manhole: false,
  }
}

function hasAnyPermission(row: Row): boolean {
  const p = permissions(row)
  return p.can_register_cleaning || p.can_confirm_cleaning || p.can_verify_cleaning || p.can_change_owner
}

function displayValue(row: Row, column: string): string {
  const value = row[column]
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function openAllScope() {
  scope.value = 'all'
  void reload()
}

function showMine() {
  scope.value = 'mine'
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function submit(values: Record<string, unknown>, fallback: string) {
  const response = await request(ENDPOINT, { method: 'POST', body: JSON.stringify({ values }) })
  if (!response.ok) throw new Error(await readError(response, fallback))
  return response.json()
}

function openCreate() {
  errorMessage.value = ''
  const code = window.prompt('井编号')
  if (!code) return
  const road = window.prompt('所在道路')
  if (!road) return
  const cover = window.prompt('井盖类别')
  if (!cover) return
  const depth = window.prompt('井室深度（可空）') ?? ''
  const size = window.prompt('井室尺寸（可空）') ?? ''
  void submit({
    井编号: code,
    所在道路: road,
    井盖类别: cover,
    井室深度: depth,
    井室尺寸: size,
    责任班组: store.team,
  }, '检查井登记未生效').then(() => reload()).catch((error: unknown) => {
    errorMessage.value = error instanceof Error ? error.message : '检查井登记未生效'
  })
}

async function postAction(row: Row, path: string, values: Record<string, unknown>, fallback: string) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}${path}`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    if (!response.ok) throw new Error(await readError(response, fallback))
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : fallback
  }
}

function registerCleaning(row: Row) {
  const result = window.prompt(`请输入 ${String(row['井编号'])} 本次清掏情况`)
  if (!result) return
  const cleanedOn = window.prompt('清掏日期（YYYY-MM-DD）', new Date().toISOString().slice(0, 10)) ?? new Date().toISOString().slice(0, 10)
  void postAction(row, '/cleanings', { result, cleaned_on: cleanedOn }, '清掏结果登记被拦下')
}

function confirmCleaning(row: Row) {
  void postAction(row, '/cleanings/confirm', {}, '清掏结果确认被拦下')
}

function verifyCleaning(row: Row) {
  void postAction(row, '/cleanings/verify', {}, '跨班组核对未生效')
}

function changeOwner(row: Row) {
  const current = String(row['责任班组'] ?? '')
  const options = TEAMS.filter((team) => team !== current)
  const team = window.prompt(`将 ${String(row['井编号'])} 调整给哪个班组？\n${options.join('、')}`, options[0] ?? '')
  if (!team) return
  void postAction(row, '/ownership', { team }, '归属调整未生效')
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams({
    scope: scope.value,
    ...(keyword.value ? { keyword: keyword.value } : {}),
    ...(statusFilter.value ? { status: statusFilter.value } : {}),
  }).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) throw new Error(await readError(response, '检查井列表读取失败'))
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检查井列表读取失败'
  }
}

onMounted(reload)
</script>
