import { defineStore } from 'pinia'

export type OperatorRole = 'crew' | 'admin'

export const TEAMS = ['排水一班', '排水二班', '排水三班']

type SavedSession = {
  role: OperatorRole
  team: string
}

const STORAGE_KEY = 'pipeline-session'

function loadSession(): SavedSession {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const saved = raw ? (JSON.parse(raw) as Partial<SavedSession>) : null
    if (saved?.role === 'admin') return { role: 'admin', team: '' }
    if (saved?.role === 'crew' && TEAMS.includes(saved.team ?? '')) {
      return { role: 'crew', team: saved.team as string }
    }
  } catch {
    // localStorage 不可用时退回默认演示身份。
  }
  return { role: 'admin', team: '' }
}

export const useSessionStore = defineStore('session', {
  state: () => {
    const saved = loadSession()
    return {
      role: saved.role,
      team: saved.team,
      operator: saved.role === 'admin' ? '值班管理员' : saved.team,
      shiftLabel: '白班 08:00-20:00',
      scope: '城市地下管网巡检养护平台',
    }
  },
  getters: {
    isAdmin: (state) => state.role === 'admin',
    isCrew: (state) => state.role === 'crew',
    canOperate: (state) => state.role === 'crew' && state.team.length > 0,
  },
  actions: {
    setRole(role: OperatorRole) {
      this.role = role
      if (role === 'admin') this.team = ''
      if (role === 'crew' && !TEAMS.includes(this.team)) this.team = TEAMS[0]
      this.persist()
    },
    setTeam(team: string) {
      if (this.role === 'crew' && TEAMS.includes(team)) {
        this.team = team
        this.persist()
      }
    },
    setShift(label: string) {
      this.shiftLabel = label
    },
    persist() {
      this.operator = this.role === 'admin' ? '值班管理员' : this.team
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ role: this.role, team: this.team }))
    },
  },
})
