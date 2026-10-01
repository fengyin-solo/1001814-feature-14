import { defineStore } from 'pinia'

export const TEAMS = ['清掏一班', '清掏二班', '清掏三班']

export type Role = 'crew' | 'admin'

export const useSessionStore = defineStore('session', {
  state: () => ({
    role: 'crew' as Role,
    team: TEAMS[0],
    shiftLabel: '白班 08:00-20:00',
    scope: '城市地下管网巡检养护平台',
  }),
  getters: {
    operator: (state) => (state.role === 'admin' ? '值班管理员' : `${state.team}·班组成员`),
    isAdmin: (state) => state.role === 'admin',
    canOperate: (state) => state.role === 'admin' || state.team.length > 0,
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    setIdentity(role: Role, team: string) {
      this.role = role
      this.team = role === 'admin' ? '' : team
    },
  },
})
