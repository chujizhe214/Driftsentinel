<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { store, openExperiment, refreshExperiments, notify, run } from '../store'
import { api, date, download } from '../api'
import type { Experiment } from '../types'
import Icon from '../components/Icon.vue'
import Modal from '../components/Modal.vue'
const router = useRouter()
const search = ref(''),
  status = ref('all'),
  page = ref(1),
  deleting = ref(''),
  refreshing = ref(false)
const labels: Record<string, string> = {
  completed: '已完成',
  running: '运行中',
  queued: '准备中',
  failed: '失败',
  cancelled: '已取消',
}
const filtered = computed(() =>
  store.experiments.filter(
    (e) =>
      (status.value === 'all' || e.status === status.value) &&
      (e.name + e.datasetName + (e.currentDatasetName || '') + e.modelName)
        .toLowerCase()
        .includes(search.value.toLowerCase()),
  ),
)
const pages = computed(() => Math.max(1, Math.ceil(filtered.value.length / 10)))
const rows = computed(() =>
  filtered.value.slice(
    (Math.min(page.value, pages.value) - 1) * 10,
    Math.min(page.value, pages.value) * 10,
  ),
)
async function open(e: Experiment) {
  try {
    await openExperiment(e.id)
    await router.push({
      path: '/',
      query: { tab: e.status === 'completed' ? 'results' : 'config' },
    })
  } catch (err) {
    notify(String(err), true)
  }
}
async function rerun(e: Experiment) {
  if (store.running) {
    notify('请等待当前实验完成', true)
    return
  }
  const p = e.request
  if (
    !store.datasets.some((d) => d.id === p.dataset_id) ||
    (p.mode === 'compare' && !store.datasets.some((d) => d.id === p.current_dataset_id)) ||
    (p.model_id && !store.models.some((m) => m.id === p.model_id))
  ) {
    notify('此实验的数据集或模型已删除，无法复现', true)
    return
  }
  store.activeDatasetId = p.dataset_id
  store.mode = p.mode || 'stress'
  store.currentDatasetId = p.current_dataset_id || ''
  store.currentLabel = p.current_label || null
  store.activeModelId = p.model_id
  store.scenarios = JSON.parse(JSON.stringify(p.scenarios))
  store.seed = p.seed
  store.samples = p.samples || 1000
  store.sweep = p.sweep
  store.combine = p.combine ?? false
  store.experimentName = e.name + ' · 复现'
  await router.push('/')
  await run({ ...p, name: store.experimentName })
}
async function refresh() {
  refreshing.value = true
  try {
    await refreshExperiments()
  } catch (e) {
    notify(String(e), true)
  } finally {
    refreshing.value = false
  }
}
async function remove() {
  try {
    await api(`/experiments/${deleting.value}`, { method: 'DELETE' })
    if (store.currentId === deleting.value) {
      store.current = null
      store.currentId = ''
    }
    deleting.value = ''
    await refreshExperiments()
    notify('实验记录已删除')
  } catch (e) {
    notify(String(e), true)
  }
}
</script>
<template>
  <div class="page-header">
    <div>
      <p class="eyebrow">EXPERIMENT LOG</p>
      <h1>实验历史</h1>
      <p>保存模拟实验与实际检测的配置和结果，明确记录每次对比的基准与待检测数据。</p>
    </div>
    <RouterLink to="/" class="btn primary">
      <Icon name="plus" :size="14" />
      新建实验
    </RouterLink>
  </div>
  <div class="grid three mb-20">
    <div class="metric">
      <div class="metric-label">全部实验</div>
      <div class="metric-number">{{ store.experiments.length }}</div>
      <p class="metric-caption">本地持久化保存</p>
    </div>
    <div class="metric">
      <div class="metric-label">已完成</div>
      <div class="metric-number blue">
        {{ store.experiments.filter((e) => e.status === 'completed').length }}
      </div>
      <p class="metric-caption">可查看报告与配置</p>
    </div>
    <div class="metric">
      <div class="metric-label">运行中</div>
      <div class="metric-number amber">
        {{ store.experiments.filter((e) => ['running', 'queued'].includes(e.status)).length }}
      </div>
      <p class="metric-caption">所有计算在本机完成</p>
    </div>
  </div>
  <div class="toolbar">
    <div class="form-field search-field">
      <div class="input-icon">
        <Icon name="search" :size="14" />
        <input
          v-model="search"
          aria-label="搜索实验"
          placeholder="搜索名称、数据集或模型…"
          @input="page = 1"
        />
      </div>
    </div>
    <div class="flex">
      <div class="form-field">
        <select v-model="status" aria-label="实验状态" @change="page = 1">
          <option value="all">全部状态</option>
          <option v-for="(label, key) in labels" :key="key" :value="key">{{ label }}</option>
        </select>
      </div>
      <button class="btn" :disabled="refreshing" @click="refresh">
        <Icon name="refresh" :size="13" :class="{ spin: refreshing }" />
        刷新
      </button>
    </div>
  </div>
  <section class="panel">
    <div v-if="rows.length" class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>实验</th>
            <th>基准 / 待检测数据 / 模型</th>
            <th>状态</th>
            <th class="num">场景 / 检测结果</th>
            <th class="num">耗时</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in rows" :key="e.id">
            <td>
              <button class="link-button" @click="open(e)">{{ e.name }}</button>
              <p class="small muted mono">
                {{
                  e.request.mode === 'compare'
                    ? '实际数据对比'
                    : '模拟压力 · Seed ' + e.request.seed
                }}
                · {{ e.id.slice(-6) }}
              </p>
            </td>
            <td>
              <p>基准：{{ e.datasetName }}</p>
              <p v-if="e.currentDatasetName">待检测：{{ e.currentDatasetName }}</p>
              <p class="small muted">{{ e.modelName }}</p>
            </td>
            <td>
              <span class="tag" :class="e.status">{{ labels[e.status] }}</span>
            </td>
            <td class="num">
              {{
                e.summary
                  ? e.request.mode === 'compare'
                    ? (e.summary.driftFields ?? 0) + ' 字段需关注'
                    : e.summary.scenarios + ' 场景 / ' + e.summary.impacted + ' 影响'
                  : '—'
              }}
            </td>
            <td class="num">{{ e.summary ? e.summary.duration.toFixed(2) + 's' : '—' }}</td>
            <td class="small">{{ date(e.createdAt) }}</td>
            <td>
              <div class="flex">
                <button class="icon-btn" title="查看实验" aria-label="查看实验" @click="open(e)">
                  <Icon name="eye" :size="14" />
                </button>
                <button
                  class="icon-btn"
                  :disabled="store.running"
                  title="按原配置复现"
                  aria-label="复现实验"
                  @click="rerun(e)"
                >
                  <Icon name="reset" :size="14" />
                </button>
                <button
                  v-if="e.status === 'completed'"
                  class="icon-btn"
                  title="下载报告"
                  aria-label="下载实验报告"
                  @click="download(`/api/experiments/${e.id}/export?format=report`)"
                >
                  <Icon name="download" :size="14" />
                </button>
                <button
                  class="icon-btn"
                  :disabled="['running', 'queued'].includes(e.status)"
                  title="删除实验"
                  aria-label="删除实验"
                  @click="deleting = e.id"
                >
                  <Icon name="trash" :size="14" />
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="empty-state">
      <div class="empty-symbol"><Icon name="history" :size="24" /></div>
      <h3>{{ search || status !== 'all' ? '没有匹配的实验' : '从第一次实验开始' }}</h3>
      <p>运行后的实验会保存在这里，刷新页面和重启服务后仍可查看。</p>
      <RouterLink to="/" class="btn primary">
        前往工作台
        <Icon name="arrow" :size="13" />
      </RouterLink>
    </div>
    <div v-if="filtered.length" class="pagination">
      <span>共 {{ filtered.length }} 条实验 · 第 {{ Math.min(page, pages) }} / {{ pages }} 页</span>
      <div class="flex">
        <button class="btn sm" :disabled="page <= 1" @click="page--">上一页</button>
        <button class="btn sm" :disabled="page >= pages" @click="page++">下一页</button>
      </div>
    </div>
  </section>
  <Modal v-if="deleting" title="删除实验记录" @close="deleting = ''">
    <p class="muted">删除这次实验的参数和结果？此操作不会影响数据集、模型或已导出的配置。</p>
    <template #footer>
      <button class="btn" @click="deleting = ''">取消</button>
      <button class="btn danger" @click="remove">确认删除</button>
    </template>
  </Modal>
</template>
