<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import Icon from './components/Icon.vue'
import { store, initialize, dataset } from './store'
const route = useRoute()
const mobile = ref(false)
const nav = [
  { path: '/', icon: 'flask', label: '实验工作台' },
  { path: '/history', icon: 'history', label: '实验历史' },
  { path: '/models', icon: 'layers', label: '模型' },
  { path: '/datasets', icon: 'database', label: '数据集' },
  { path: '/rules', icon: 'bell', label: '监控规则' },
]
const activeNavIndex = computed(() => Math.max(nav.findIndex((item) => route.path === item.path), 0))
onMounted(initialize)
</script>
<template>
  <div class="app-layout">
    <aside class="sidebar" :class="{ open: mobile }">
      <RouterLink to="/" class="brand">
        <span class="brand-icon"><Icon name="radar" :size="24" /></span>
        <span>
          <strong>
            DriftSentinel
            <span class="brand-version">v1</span>
          </strong>
          <small>Model quality workbench</small>
        </span>
      </RouterLink>
      <div class="workspace-select">
        <div class="workspace-letter">D</div>
        <div>
          <small>本地工作区</small>
          <strong>我的模型实验室</strong>
        </div>
        <Icon name="chevron" :size="13" />
      </div>
      <p class="nav-caption">工作空间</p>
      <nav
        class="sidebar-nav"
        aria-label="主导航"
        :style="{ '--nav-active-index': activeNavIndex }"
      >
        <span v-if="route.path !== '/settings'" class="nav-glider-track" aria-hidden="true">
          <span class="nav-glider"></span>
        </span>
        <RouterLink
          v-for="item in nav"
          :key="item.path"
          :to="item.path"
          class="nav-link"
          :class="{ active: route.path === item.path }"
          @click="mobile = false"
        >
          <Icon :name="item.icon" />
          <span>{{ item.label }}</span>
          <span v-if="item.path === '/history' && store.experiments.length" class="nav-count">
            {{ store.experiments.length }}
          </span>
        </RouterLink>
      </nav>
      <div class="sidebar-spacer"></div>
      <RouterLink
        to="/settings"
        class="nav-link settings-link"
        :class="{ active: route.path === '/settings' }"
        @click="mobile = false"
      >
        <Icon name="settings" />
        设置
      </RouterLink>
      <div class="local-footer">
        <div>
          <span class="status-dot"></span>
          <strong>本地优先，安心实验</strong>
        </div>
        <small>数据与模型保存在你的设备</small>
        <span class="footer-version">DriftSentinel 1.0.0</span>
      </div>
    </aside>
    <div v-if="mobile" class="sidebar-scrim" @click="mobile = false"></div>
    <main class="main-area">
      <header class="topbar">
        <div class="breadcrumbs">
          <button class="icon-btn mobile-menu" aria-label="展开菜单" @click="mobile = !mobile">
            <Icon name="menu" />
          </button>
          <span>工作空间</span>
          <Icon name="right" :size="12" />
          <strong>{{ route.meta.title }}</strong>
        </div>
        <div class="topbar-right">
          <span class="local-badge">
            <span class="status-dot" :class="{ offline: store.connectionError }"></span>
            {{ store.connectionError ? '服务未连接' : '本地运行' }}
          </span>
          <span class="topbar-divider"></span>
          <span class="avatar">L</span>
        </div>
      </header>
      <div v-if="store.loading && !store.ready" class="app-loading">
        <Icon name="loader" :size="26" class="spin" />
        <strong>正在连接本地工作区</strong>
        <span>加载数据、模型与实验记录…</span>
      </div>
      <div v-else-if="store.connectionError" class="connection-state">
        <Icon name="cable" :size="36" />
        <h1>暂时无法连接本地服务</h1>
        <p>{{ store.connectionError }}</p>
        <p class="muted">
          请启动业务服务后重新连接：
          <code>python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000</code>
        </p>
        <button class="btn primary" @click="initialize">
          <Icon name="refresh" />
          重新连接
        </button>
      </div>
      <div v-else class="page-content">
        <RouterView />
        <footer class="page-footer">
          <span>
            <Icon name="shield" :size="12" />
            数据仅在本地处理
          </span>
          <span>{{ dataset?.source || 'Local workspace' }} · 表格二分类 · V1.0</span>
        </footer>
      </div>
    </main>
    <div class="toast-stack" aria-live="polite">
      <div v-for="t in store.toasts" :key="t.id" class="toast" :class="{ error: t.error }">
        <Icon :name="t.error ? 'warning' : 'success'" />
        <span>{{ t.text }}</span>
        <button
          class="icon-btn"
          aria-label="关闭提示"
          @click="store.toasts = store.toasts.filter((x) => x.id !== t.id)"
        >
          <Icon name="x" :size="13" />
        </button>
      </div>
    </div>
  </div>
</template>
