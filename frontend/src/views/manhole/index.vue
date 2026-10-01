<template>
  <section class="page" data-module="manhole">
    <header class="page-head">
      <div>
        <h2>检查井管理</h2>
        <p class="page-desc">检查井由责任班组维护：本班组可登记、安排清掏并确认清掏结果，跨班组仅可查看，值班管理员可跨班组核对与调整归属。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记检查井</button>
        <button class="btn" type="button" @click="exportRows">导出检查井清单</button>
      </div>
    </header>

    <p class="identity-hint">{{ identityHint }}</p>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form v-if="showCreate" class="create-bar" @submit.prevent="submitCreate">
      <label v-for="field in createFields" :key="field" class="filter-item">
        <span>{{ field }}（必填）</span>
        <input v-model="createForm[field]" :placeholder="`填写${field}`" />
      </label>
      <button class="btn primary" type="submit">提交登记</button>
      <button class="btn ghost" type="button" @click="showCreate = false">取消</button>
      <span class="muted">责任班组固定为当前身份所属班组，登记到别的班组会被挡回</span>
    </form>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>最近清掏</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="row in rows" :key="String(row.id)">
          <tr>
            <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
            <td>{{ row['最近清掏'] }}</td>
            <td class="row-actions">
              <button
                v-for="action in rowActions(row)"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
              <span v-if="!rowActions(row).length" class="muted" :title="String(row['只读原因'] ?? '')">仅可查看</span>
              <button class="link" type="button" @click="toggleDetail(row)">
                {{ detailRow && detailRow.id === row.id ? '收起' : '明细' }}
              </button>
            </td>
          </tr>
          <tr v-if="detailRow && detailRow.id === row.id" class="detail-row">
            <td :colspan="columns.length + 2">
              <div class="detail-panel">
                <p>
                  <strong>归属班组：</strong>{{ detailRow['归属班组'] }}
                  <span v-if="detailRow['只读原因']" class="muted">（{{ detailRow['只读原因'] }}）</span>
                </p>
                <p><strong>最近一次清掏：</strong>{{ detailRow['最近清掏'] }}</p>
                <div>
                  <strong>清掏记录（归属调整后仍署名原班组）：</strong>
                  <ul v-if="dredgeRecords.length">
                    <li v-for="(record, index) in dredgeRecords" :key="index">
                      {{ record['日期'] }} · {{ record['班组'] }} · {{ record['结果'] }}
                    </li>
                  </ul>
                  <p v-else class="muted">暂无清掏记录</p>
                </div>
                <div>
                  <strong>归属调整记录：</strong>
                  <ul v-if="reassignRecords.length">
                    <li v-for="(record, index) in reassignRecords" :key="index">
                      {{ record['日期'] }} · {{ record['原班组'] }} → {{ record['新班组'] }} · 操作人：{{ record['操作人'] }}
                    </li>
                  </ul>
                  <p v-else class="muted">未发生过归属调整</p>
                </div>
              </div>
            </td>
          </tr>
        </template>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无检查井数据，可先登记检查井</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条检查井记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { readError, request } from '@/api/client'
import { TEAMS, useSessionStore } from '@/stores/session'

type Row = Record<string, unknown> & { id: number | string }
type DredgeRecord = Record<string, string>

const ENDPOINT = '/api/manhole'
const columns = ["井编号", "所在道路", "井盖类别", "井室深度", "井室尺寸", "上次清掏日", "责任班组", "检查井状态"]
const createFields = ["井编号", "所在道路", "井盖类别"]

const session = useSessionStore()

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const showCreate = ref(false)
const createForm = ref<Record<string, string>>({})
const detailRow = ref<Row | null>(null)
const stats = ref([{ label: '在册检查井', value: 0 }, { label: '待清掏井室', value: 0 }, { label: '井盖缺失', value: 0 }])

const identityHint = computed(() =>
  session.isAdmin
    ? '当前身份：值班管理员 —— 可跨班组核对、调整归属；登记与确认清掏由责任班组完成'
    : `当前身份：${session.team}·班组成员 —— 可登记并维护本班组检查井，其他班组的井仅可查看`,
)

const dredgeRecords = computed<DredgeRecord[]>(() => (detailRow.value?.['清掏记录'] as DredgeRecord[] | undefined) ?? [])
const reassignRecords = computed<DredgeRecord[]>(() => (detailRow.value?.['归属调整记录'] as DredgeRecord[] | undefined) ?? [])

function rowActions(row: Row): string[] {
  return (row['可执行动作'] as string[] | undefined) ?? []
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  showCreate.value = !showCreate.value
}

async function submitCreate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm.value } }),
    })
    if (!response.ok) {
      throw await readError(response, '检查井登记未生效，请稍后重试')
    }
    const result = (await response.json()) as { ok: boolean; message: string }
    if (!result.ok) {
      throw new Error(result.message)
    }
    noticeMessage.value = result.message
    showCreate.value = false
    createForm.value = {}
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检查井登记失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  const values: Record<string, string> = { action }
  if (action === '确认清掏') {
    const result = window.prompt(`填写检查井 ${row['井编号']} 的本次清掏结果`, '清掏完成，井室无淤积')
    if (result === null) return
    values['清掏结果'] = result
  }
  if (action === '跨班组核对') {
    const conclusion = window.prompt(`填写检查井 ${row['井编号']} 的核对结论`, '账实相符')
    if (conclusion === null) return
    values['核对结论'] = conclusion
  }
  if (action === '归属调整') {
    const candidate = TEAMS.find((team) => team !== row['责任班组']) ?? ''
    const team = window.prompt(`检查井 ${row['井编号']} 当前归「${row['责任班组']}」维护，调整到哪个班组？（${TEAMS.join(' / ')}）`, candidate)
    if (team === null) return
    values['新班组'] = team.trim()
  }
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    if (!response.ok) {
      throw await readError(response, '检查井动作未生效，请稍后重试')
    }
    const result = (await response.json()) as { ok: boolean; message: string }
    if (!result.ok) {
      throw new Error(result.message)
    }
    noticeMessage.value = result.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检查井操作失败'
  }
}

async function toggleDetail(row: Row) {
  errorMessage.value = ''
  if (detailRow.value && detailRow.value.id === row.id) {
    detailRow.value = null
    return
  }
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw await readError(response, '检查井明细读取失败')
    }
    detailRow.value = (await response.json()) as Row
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检查井明细读取失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (filters.value['井编号']) params.set('keyword', filters.value['井编号'])
  if (filters.value['所在道路']) params.set('road', filters.value['所在道路'])
  if (filters.value['井盖类别']) params.set('cover', filters.value['井盖类别'])
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw await readError(response, '检查井列表读取失败')
    }
    const payload = (await response.json()) as { items?: Row[]; total?: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    stats.value = [
      { label: '在册检查井', value: total.value },
      { label: '待清掏井室', value: rows.value.filter((row) => row['status'] === '待清掏').length },
      { label: '井盖缺失', value: rows.value.filter((row) => row['status'] === '井盖缺失').length },
    ]
    detailRow.value = null
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检查井列表读取失败'
  }
}

onMounted(reload)
</script>
