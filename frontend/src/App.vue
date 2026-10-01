<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">城市地下管网巡检养护平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向城市给排水与燃气管网的管段建档、检查井阀门、巡查巡检、内窥检测、缺陷修复与压力流量监测的一体化养护后台。</span>
        <div class="session-bar">
          <label>
            当前身份
            <select :value="store.role" @change="changeRole(($event.target as HTMLSelectElement).value as 'crew' | 'admin')">
              <option value="crew">班组人员</option>
              <option value="admin">值班管理员</option>
            </select>
          </label>
          <label v-if="store.isCrew">
            责任班组
            <select :value="store.team" @change="store.setTeam(($event.target as HTMLSelectElement).value)">
              <option v-for="team in teams" :key="team" :value="team">{{ team }}</option>
            </select>
          </label>
          <span class="head-user">当前值班：{{ store.operator }} · {{ store.shiftLabel }}</span>
        </div>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { TEAMS, useSessionStore } from '@/stores/session'

const store = useSessionStore()
const teams = TEAMS

const navItems = [{ label: "运营概览", path: "/" }, { label: "班组工作台", path: "/workbench" }, { label: "管段档案", path: "/pipe" }, { label: "检查井", path: "/manhole" }, { label: "阀门井室", path: "/valve" }, { label: "泵站设施", path: "/pumpstation" }, { label: "巡查任务", path: "/patrol" }, { label: "缺陷登记", path: "/defect" }, { label: "内窥检测", path: "/cctv" }, { label: "修复施工", path: "/repair" }, { label: "压力监测", path: "/pressure" }, { label: "流量监测", path: "/flow" }, { label: "泄漏排查", path: "/leak" }, { label: "清淤疏浚", path: "/dredge" }, { label: "养护材料", path: "/material" }, { label: "养护机械", path: "/equip" }, { label: "占道许可", path: "/traffic" }, { label: "公众诉求", path: "/complaint" }, { label: "养护资金", path: "/fund" }, { label: "管网档案", path: "/archive" }]

function changeRole(role: 'crew' | 'admin') {
  store.setRole(role)
}
</script>
