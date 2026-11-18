import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import Workbench from './pages/Workbench.vue'
import Datasets from './pages/Datasets.vue'
import Models from './pages/Models.vue'
import History from './pages/History.vue'
import Rules from './pages/Rules.vue'
import Settings from './pages/Settings.vue'
import './style.css'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: Workbench, meta: { title: '实验工作台' } },
    { path: '/datasets', component: Datasets, meta: { title: '数据集' } },
    { path: '/models', component: Models, meta: { title: '模型' } },
    { path: '/history', component: History, meta: { title: '实验历史' } },
    { path: '/rules', component: Rules, meta: { title: '监控规则' } },
    { path: '/settings', component: Settings, meta: { title: '设置' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
createApp(App).use(router).mount('#app')
