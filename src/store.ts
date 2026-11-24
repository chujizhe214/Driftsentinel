import { computed, reactive, watch } from 'vue'
import { api, post } from './api'
import type { Dataset, DatasetRole, Model, Rules, Experiment, Scenario, RunRequest } from './types'

const defaults: Rules = {
  warning: 0.2,
  critical: 0.3,
  pvalue: 0.05,
  missing: 0.1,
  prediction_change: 0.15,
  impact: 0.03,
  window: '1h',
  min_samples: 200,
}
function saved() {
  try {
    return JSON.parse(localStorage.getItem('ds-workspace-v1') || '{}')
  } catch {
    return {}
  }
}
const previous = saved()
export const store = reactive({
  ready: false,
  loading: true,
  connectionError: '',
  datasets: [] as Dataset[],
  models: [] as Model[],
  experiments: [] as Experiment[],
  rules: { ...defaults },
  activeDatasetId: previous.activeDatasetId ?? 'bank-reference',
  mode: (previous.mode === 'compare' ? 'compare' : 'stress') as 'stress' | 'compare',
  currentDatasetId: (previous.currentDatasetId || '') as string,
  currentLabel: (previous.currentLabel || null) as string | null,
  activeModelId:
    previous.activeModelId === undefined
      ? 'bank-logistic-v1'
      : (previous.activeModelId as string | null),
  scenarios: (previous.scenarios || []) as Scenario[],
  seed: previous.seed ?? 42,
  samples: previous.samples ?? 1357,
  sweep: previous.sweep ?? true,
  combine: previous.combine ?? false,
  experimentName: previous.experimentName || 'Bank Marketing · 稳定性实验',
  current: null as Experiment | null,
  currentId: previous.currentId || '',
  running: false,
  progress: 0,
  toasts: [] as { id: number; text: string; error: boolean }[],
  health: null as { version: string; storage: string; mode: string } | null,
})
const previousDatasetRoles = computed(() => {
  const roles = new Map<string, DatasetRole>()
  if (store.activeDatasetId) roles.set(store.activeDatasetId, 'reference')
  if (store.currentDatasetId && !roles.has(store.currentDatasetId)) {
    roles.set(store.currentDatasetId, 'current')
  }
  for (const { status, request } of store.experiments) {
    if (status !== 'completed') continue
    if (!roles.has(request.dataset_id)) roles.set(request.dataset_id, 'reference')
    const currentId = request.current_dataset_id
    if (request.mode === 'compare' && currentId && !roles.has(currentId)) {
      roles.set(currentId, 'current')
    }
  }
  return roles
})
export function datasetRole(item: Dataset) {
  if (item.id === 'bank-reference') return 'reference'
  return item.role ?? previousDatasetRoles.value.get(item.id)
}
export const referenceDatasets = computed(() =>
  store.datasets.filter((item) => datasetRole(item) === 'reference'),
)
export const actualDatasets = computed(() =>
  store.datasets.filter((item) => datasetRole(item) === 'current'),
)
export const dataset = computed(() => store.datasets.find((d) => d.id === store.activeDatasetId))
export const currentDataset = computed(() =>
  store.datasets.find((d) => d.id === store.currentDatasetId),
)
export const model = computed(() => store.models.find((m) => m.id === store.activeModelId))
export const modelInputProblem = computed(() => {
  if (!model.value || model.value.kind !== 'builtin') return ''
  const label = dataset.value?.label
  if (label && model.value.features.includes(label))
    return `“${label}”是内置模型所需的输入特征，不能同时作为真实标签。请选择实际结果列，或切换为“仅分析数据漂移”。`
  const missing = model.value.features.filter(
    (name) => !dataset.value?.profile.fields.some((f) => f.name === name),
  )
  return missing.length
    ? `内置模型缺少输入字段：${missing.join('、')}。请选择匹配适配器，或切换为“仅分析数据漂移”。`
    : ''
})
export const compatible = computed(() => !modelInputProblem.value)
let timer: ReturnType<typeof setTimeout> | undefined

export function notify(text: string, error = false) {
  const id = Date.now() + Math.random()
  store.toasts.push({ id, text, error })
  setTimeout(
    () => {
      store.toasts = store.toasts.filter((t) => t.id !== id)
    },
    error ? 8000 : 4000,
  )
}
export const scenarioMeta = {
  mean_shift: {
    name: '数值均值偏移',
    icon: 'trending-up',
    desc: '整体移动数值分布，模拟客群与业务规模变化。',
    unit: '均值偏移',
    min: -80,
    max: 100,
  },
  variance: {
    name: '数值方差变化',
    icon: 'expand',
    desc: '保持均值，改变分布离散程度。',
    unit: '方差增量',
    min: -80,
    max: 200,
  },
  categorical: {
    name: '类别比例变化',
    icon: 'pie-chart',
    desc: '重采样完整样本，调整指定类别所占比例。',
    unit: '目标占比',
    min: 1,
    max: 99,
  },
  missing: {
    name: '缺失值增加',
    icon: 'circle-dashed',
    desc: '将字段缺失率提高到指定水平。',
    unit: '目标缺失率',
    min: 0,
    max: 90,
  },
  outlier: {
    name: '极端值注入',
    icon: 'zap',
    desc: '注入偏离均值 5–10 个标准差的极端值。',
    unit: '注入比例',
    min: 0,
    max: 30,
  },
}
export function resetScenarios() {
  const fields = dataset.value?.profile.fields.filter((f) => f.name !== dataset.value?.label) || []
  const numeric = fields.filter((f) => f.type === 'numeric')
  const categorical = fields.filter((f) => f.type === 'categorical' && f.unique > 1)
  const choose = (name: string, fallback = 0) =>
    numeric.find((f) => f.name === name)?.name || numeric[fallback]?.name || numeric[0]?.name || ''
  const cat = categorical.find((f) => f.name === 'job') || categorical[0]
  store.scenarios = [
    {
      id: 'mean',
      type: 'mean_shift',
      field: choose('duration'),
      strength: 30,
      category: null,
      enabled: numeric.length > 0,
    },
    {
      id: 'variance',
      type: 'variance',
      field: choose('balance', 1),
      strength: 80,
      category: null,
      enabled: numeric.length > 0,
    },
    {
      id: 'category',
      type: 'categorical',
      field: cat?.name || '',
      strength: 60,
      category: cat?.categories?.[0]?.name || null,
      enabled: !!cat,
    },
    {
      id: 'missing',
      type: 'missing',
      field: choose('duration'),
      strength: 25,
      category: null,
      enabled: numeric.length > 0,
    },
    {
      id: 'outlier',
      type: 'outlier',
      field: choose('age'),
      strength: 5,
      category: null,
      enabled: false,
    },
  ]
}
export function selectDataset(id: string) {
  store.activeDatasetId = id
  if (id && id === store.currentDatasetId) selectCurrentDataset('')
  store.samples = dataset.value?.profile.rows || 1000
  resetScenarios()
  if (!compatible.value) store.activeModelId = null
}
export function selectCurrentDataset(id: string) {
  store.currentDatasetId = id
  // New observations have no confirmed ground truth until the user selects it.
  store.currentLabel = null
}
export function setMode(mode: 'stress' | 'compare') {
  store.mode = mode
  if (mode === 'stress' && !store.scenarios.length) resetScenarios()
  store.experimentName =
    mode === 'compare' ? '实际数据漂移检测' : `${dataset.value?.name || '数据'} · 稳定性实验`
}
export async function loadDemo() {
  if (store.running) return
  const demo = store.datasets.find((d) => d.id === 'bank-reference')
  if (!demo) {
    notify('示例数据尚未加载，请稍后重试', true)
    return
  }
  if (demo.label !== 'y') {
    try {
      const updated = await api<Dataset>(`/datasets/${demo.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ label: 'y' }),
      })
      store.datasets = store.datasets.map((d) => (d.id === updated.id ? updated : d))
    } catch (e) {
      notify(e instanceof Error ? e.message : String(e), true)
      return
    }
  }
  store.mode = 'stress'
  store.activeDatasetId = 'bank-reference'
  if (store.currentDatasetId === 'bank-reference') selectCurrentDataset('')
  store.activeModelId = 'bank-logistic-v1'
  store.seed = 42
  store.samples = dataset.value?.profile.rows || 1357
  store.experimentName = 'Bank Marketing · 稳定性实验'
  store.sweep = true
  store.combine = false
  resetScenarios()
  notify('已加载公开数据和示例模型，可以开始实验')
}
export async function initialize() {
  store.loading = true
  store.connectionError = ''
  try {
    const [ds, ms, es, rules, health] = await Promise.all([
      api<Dataset[]>('/datasets'),
      api<Model[]>('/models'),
      api<Experiment[]>('/experiments'),
      api<Rules>('/rules'),
      api<{ version: string; storage: string; mode: string }>('/health'),
    ])
    store.datasets = ds
    store.models = ms
    store.experiments = es
    store.rules = rules
    store.health = health
    if (
      store.activeDatasetId &&
      !referenceDatasets.value.some((d) => d.id === store.activeDatasetId)
    ) {
      selectDataset(referenceDatasets.value[0]?.id || '')
    }
    if (!actualDatasets.value.some((d) => d.id === store.currentDatasetId)) {
      selectCurrentDataset('')
    }
    if (!store.scenarios.length) resetScenarios()
    const active = es.find((e) => e.status === 'running' || e.status === 'queued')
    const current = active?.id || (es.some((e) => e.id === store.currentId) ? store.currentId : '')
    if (current) await openExperiment(current)
    store.ready = true
  } catch (e) {
    store.connectionError = e instanceof Error ? e.message : '连接本地服务失败'
  } finally {
    store.loading = false
  }
}
export async function refreshExperiments() {
  store.experiments = await api<Experiment[]>('/experiments')
}
export async function openExperiment(id: string) {
  clearTimeout(timer)
  store.current = await api<Experiment>(`/experiments/${id}`)
  store.currentId = id
  store.running = ['queued', 'running'].includes(store.current.status)
  store.progress = store.current.progress
  if (store.running) timer = setTimeout(() => poll(id), 650)
}
async function poll(id: string) {
  try {
    const item = await api<Experiment>(`/experiments/${id}`)
    store.current = item
    store.progress = item.progress
    store.running = ['queued', 'running'].includes(item.status)
    if (store.running) timer = setTimeout(() => poll(id), 650)
    else {
      await refreshExperiments()
      notify(
        item.status === 'completed' ? '实验已完成，结果已保存到本机' : item.error || '实验已取消',
        item.status === 'failed',
      )
    }
  } catch (e) {
    store.running = false
    notify(String(e), true)
  }
}
export async function run(overrides?: Partial<RunRequest>) {
  if (store.running) return
  if (!dataset.value) {
    notify('请先选择数据集', true)
    return
  }
  const payload: RunRequest = {
    name: store.experimentName,
    dataset_id: dataset.value.id,
    mode: store.mode,
    current_dataset_id: store.mode === 'compare' ? store.currentDatasetId || null : null,
    current_label: store.mode === 'compare' ? store.currentLabel : null,
    model_id: store.activeModelId,
    label: dataset.value.label,
    seed: store.seed,
    samples: store.mode === 'compare' ? null : store.samples,
    scenarios: store.mode === 'compare' ? [] : store.scenarios,
    sweep: store.mode === 'stress' && store.sweep,
    combine: store.mode === 'stress' && store.combine,
    rules: store.rules,
  }
  if (overrides?.dataset_id) Object.assign(payload, overrides)
  store.progress = 0
  store.running = true
  try {
    const item = await post<Experiment>('/experiments', payload)
    store.current = item
    await openExperiment(item.id)
    await refreshExperiments()
  } catch (e) {
    store.running = false
    notify(e instanceof Error ? e.message : String(e), true)
  }
}
export async function cancel() {
  if (store.current) {
    await post(`/experiments/${store.current.id}/cancel`)
    notify('正在取消，当前计算步骤结束后停止')
  }
}
export async function saveRules(rules: Rules) {
  store.rules = await api<Rules>('/rules', { method: 'PUT', body: JSON.stringify(rules) })
  notify('监控规则已保存')
}
watch(
  () => [
    store.activeDatasetId,
    store.mode,
    store.currentDatasetId,
    store.currentLabel,
    store.activeModelId,
    store.scenarios,
    store.seed,
    store.samples,
    store.sweep,
    store.combine,
    store.experimentName,
    store.currentId,
  ],
  () => {
    localStorage.setItem(
      'ds-workspace-v1',
      JSON.stringify({
        activeDatasetId: store.activeDatasetId,
        mode: store.mode,
        currentDatasetId: store.currentDatasetId,
        currentLabel: store.currentLabel,
        activeModelId: store.activeModelId,
        scenarios: store.scenarios,
        seed: store.seed,
        samples: store.samples,
        sweep: store.sweep,
        combine: store.combine,
        experimentName: store.experimentName,
        currentId: store.currentId,
      }),
    )
  },
  { deep: true },
)
