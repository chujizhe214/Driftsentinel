<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  store,
  dataset,
  datasetRole,
  referenceDatasets,
  actualDatasets,
  currentDataset,
  model,
  compatible,
  modelInputProblem,
  scenarioMeta,
  loadDemo,
  run,
  cancel,
  selectDataset,
  selectCurrentDataset,
  setMode,
  notify,
} from '../store'
import { api, percent } from '../api'
import type { Dataset, Scenario } from '../types'
import Icon from '../components/Icon.vue'
import HelpTip from '../components/HelpTip.vue'
import Modal from '../components/Modal.vue'
import WorkflowLinks from '../components/WorkflowLinks.vue'
import Results from '../components/Results.vue'
import Calibration from '../components/Calibration.vue'
import Report from '../components/Report.vue'
const route = useRoute(),
  router = useRouter()
const tab = ref(String(route.query.tab || 'config'))
watch(
  () => route.query.tab,
  (value) => {
    tab.value = String(value || 'config')
  },
)
const tabs = [
  { id: 'config', label: '场景配置', icon: 'sliders' },
  { id: 'results', label: '结果分析', icon: 'chart' },
  { id: 'calibration', label: '阈值校准', icon: 'target' },
  { id: 'report', label: '报告与导出', icon: 'file' },
]
const activeTabIndex = computed(() => tabs.findIndex((item) => item.id === tab.value))
const completed = computed(() =>
  store.current?.status === 'completed' && store.current.result ? store.current : null,
)
const fields = computed(
  () => dataset.value?.profile.fields.filter((f) => f.name !== dataset.value?.label) || [],
)
const selectedCount = computed(() => store.scenarios.filter((s) => s.enabled).length)
const scenarioCount = computed(
  () => 1 + selectedCount.value * (store.sweep ? 3 : 1) + (store.combine ? 1 : 0),
)
const comparing = computed(() => store.mode === 'compare')
const comparisonProblem = computed(() => {
  if (!currentDataset.value) return '请选择或导入本次采集的待检测数据。'
  if (currentDataset.value.id === dataset.value?.id)
    return '待检测数据不能与基准相同，请选择另一份采集数据。'
  if (datasetRole(currentDataset.value) !== 'current') return '请从实际数据集中选择待检测数据。'
  const missing = fields.value.filter(
    (f) =>
      f.name === store.currentLabel ||
      !currentDataset.value!.profile.fields.some((c) => c.name === f.name),
  )
  if (missing.length) return '待检测数据缺少基准特征字段：' + missing.map((f) => f.name).join('、')
  return ''
})
const baselineInput = ref<HTMLInputElement>()
const currentInput = ref<HTMLInputElement>()
const uploading = ref(false)
const updatingLabel = ref(false)
const importError = ref('')
const configLabels = {
  baseline: '基准数据',
  observed: '待检测数据',
  model: '模型适配器',
  scenarios: '漂移场景',
}
type ConfigPanel = keyof typeof configLabels
const configPanel = ref<ConfigPanel | null>(null)

const canUseDemoLabel = computed(
  () =>
    model.value?.id === 'bank-logistic-v1' &&
    !!dataset.value?.label &&
    model.value.features.includes(dataset.value.label) &&
    fields.value.some((field) => field.name === 'y'),
)
const runProblem = computed<{ message: string; panel: ConfigPanel } | null>(() => {
  if (!dataset.value || datasetRole(dataset.value) !== 'reference')
    return { message: '请选择基准数据。', panel: 'baseline' }
  if (!compatible.value) return { message: modelInputProblem.value, panel: 'model' }
  if (comparing.value && comparisonProblem.value)
    return { message: comparisonProblem.value, panel: 'observed' }
  if (!comparing.value) {
    if (!selectedCount.value) return { message: '请启用至少一个漂移场景。', panel: 'scenarios' }
    if (!Number.isInteger(store.samples) || store.samples < 30 || store.samples > 50000)
      return { message: '场景样本数须为 30 到 50,000 之间的整数。', panel: 'scenarios' }
    if (!Number.isInteger(store.seed) || store.seed < 0 || store.seed > 4294967295)
      return { message: '随机种子须为 0 到 4,294,967,295 之间的整数。', panel: 'scenarios' }
  }
  if (!store.experimentName.trim())
    return { message: '请输入本次实验的名称。', panel: comparing.value ? 'observed' : 'scenarios' }
  return null
})
const canRun = computed(
  () => !store.running && !uploading.value && !updatingLabel.value && !runProblem.value,
)
const runLabel = computed(() => (comparing.value ? '运行实际检测' : '运行压力测试'))
const modelSummary = computed(() => {
  if (!model.value) return '无需接入模型'
  if (!compatible.value) return '模型与基准配置冲突'
  const status = { ready: '可用', unvalidated: '待校验', error: '校验失败' }[model.value.status]
  return (model.value.kind === 'builtin' ? '内置模型' : '本地适配器') + ' · ' + status
})
const nodes = computed(() => {
  const baseline = {
    id: 'baseline' as const,
    icon: 'database',
    value: dataset.value?.name ?? '选择或导入 CSV',
    detail: dataset.value
      ? dataset.value.profile.rows.toLocaleString() +
        ' 行 · ' +
        (dataset.value.label ? '标签 ' + dataset.value.label : '无真实标签')
      : '',
  }
  const observed = {
    id: 'observed' as const,
    icon: 'csv',
    value: currentDataset.value?.name ?? '选择或导入 CSV',
    detail: currentDataset.value
      ? currentDataset.value.profile.rows.toLocaleString() +
        ' 行 · ' +
        (store.currentLabel ? '标签 ' + store.currentLabel : '无真实标签')
      : '',
  }
  const adapter = {
    id: 'model' as const,
    icon: 'cable',
    value: model.value?.name ?? '仅分析数据漂移',
    detail: modelSummary.value,
  }
  const scenarios = {
    id: 'scenarios' as const,
    icon: 'sliders',
    value: selectedCount.value + ' / ' + store.scenarios.length + ' 项已启用',
    detail: [store.sweep ? '三档强度' : '单档强度', store.combine ? '含组合场景' : '']
      .filter(Boolean)
      .join(' · '),
  }
  return comparing.value ? [baseline, observed, adapter] : [baseline, adapter, scenarios]
})
function openConfig(panel: ConfigPanel) {
  importError.value = ''
  configPanel.value = panel
}
function closeConfig() {
  configPanel.value = null
}
function changeMode(mode: 'stress' | 'compare') {
  if (store.mode !== mode) setMode(mode)
  activate('config')
}
async function importDataset(event: Event, role: 'reference' | 'current') {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploading.value = true
  importError.value = ''
  try {
    const form = new FormData()
    form.append('file', file)
    const item = await api<Dataset>(`/datasets?role=${role}`, { method: 'POST', body: form })
    store.datasets.unshift(item)
    if (role === 'reference') selectDataset(item.id)
    else selectCurrentDataset(item.id)
    notify(role === 'reference' ? '已导入并选择基准数据' : '已导入待检测数据，基准保持不变')
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e)
    if (configPanel.value) importError.value = message
    else notify(message, true)
  } finally {
    uploading.value = false
    input.value = ''
  }
}
function candidates(s: Scenario) {
  return fields.value.filter((f) =>
    s.type === 'categorical'
      ? f.type === 'categorical' && f.unique > 1
      : s.type === 'missing'
        ? true
        : f.type === 'numeric',
  )
}
function categories(s: Scenario) {
  return fields.value.find((f) => f.name === s.field)?.categories || []
}
function changeField(s: Scenario) {
  if (s.type === 'categorical') s.category = categories(s)[0]?.name || null
}
async function setLabel(label: string | null) {
  if (!dataset.value || updatingLabel.value) return
  updatingLabel.value = true
  try {
    const updated = await api<Dataset>(`/datasets/${dataset.value.id}`, {
      method: 'PATCH',
      body: JSON.stringify({
        name: dataset.value.name,
        label,
      }),
    })
    store.datasets = store.datasets.map((d) => (d.id === updated.id ? updated : d))
    store.scenarios.forEach((s) => {
      if (s.field === updated.label) {
        s.enabled = false
        s.field = candidates(s)[0]?.name || ''
      }
    })
  } catch (e) {
    notify(String(e), true)
  } finally {
    updatingLabel.value = false
  }
}
function activate(id: string) {
  tab.value = id
  router.replace({ query: id === 'config' ? {} : { tab: id } })
}
</script>
<template>
  <div class="page-header">
    <div>
      <p class="eyebrow">MODEL STABILITY LAB</p>
      <h1>{{ comparing ? '实际数据漂移检测' : '漂移压力测试' }}</h1>
      <p>
        {{
          comparing
            ? '固定正常时期的基准，检测每天采集的数据相对于基准的分布变化。'
            : '了解输入变化如何影响模型，找到更有依据的监控阈值。'
        }}
      </p>
    </div>
    <div class="header-actions">
      <button class="btn" :disabled="store.running || uploading || updatingLabel" @click="loadDemo">
        <Icon name="reset" :size="14" />
        加载示例
      </button>
      <button class="btn" :disabled="!completed" @click="activate('report')">
        <Icon name="download" :size="14" />
        导出监控配置
      </button>
      <button v-if="tab !== 'config'" class="btn success" :disabled="!canRun" @click="run()">
        <Icon
          :name="store.running ? 'loader' : 'play'"
          :class="{ spin: store.running }"
          :size="14"
        />
        {{ store.running ? '实验运行中' : runLabel }}
      </button>
    </div>
  </div>
  <section class="panel mode-selector mb-20" aria-label="检测模式">
    <div class="panel-body">
      <div
        class="segmented-control"
        :style="{ '--selected-segment': comparing ? 1 : 0 }"
        role="group"
        aria-label="选择检测模式"
      >
        <button
          type="button"
          :aria-pressed="!comparing"
          :disabled="store.running || uploading || updatingLabel"
          @click="changeMode('stress')"
        >
          模拟压力测试
        </button>
        <button
          type="button"
          :aria-pressed="comparing"
          :disabled="store.running || uploading || updatingLabel"
          @click="changeMode('compare')"
        >
          实际数据对比
        </button>
      </div>
      <p class="small muted mt-12">
        {{
          comparing
            ? '基准保持固定，每次只更换待检测数据。使用两份数据的全部样本，无需模型或真实标签也能检测数据漂移。'
            : '从基准数据生成可控变化场景，测试检测器与模型对输入扰动的响应。'
        }}
      </p>
    </div>
  </section>
  <div class="summary-bar">
    <div class="summary-cell">
      <span>基准数据集</span>
      <strong>
        <Icon name="database" :size="13" class="summary-icon" />
        {{ dataset?.name || '未选择' }}
      </strong>
    </div>
    <div class="summary-cell">
      <span>样本数</span>
      <strong>{{ dataset?.profile.rows.toLocaleString() }}</strong>
    </div>
    <div class="summary-cell">
      <span>特征</span>
      <strong>{{ fields.length }} columns</strong>
    </div>
    <div class="summary-cell">
      <span>目标字段</span>
      <strong>
        {{ dataset?.label || '未选择标签' }}
        <small v-if="dataset?.label" class="summary-qualifier">/ binary</small>
      </strong>
    </div>
    <div class="summary-cell">
      <span>模型</span>
      <strong>
        {{ model?.algorithm || '仅数据漂移' }} {{ model?.version ? 'v' + model.version : '' }}
      </strong>
    </div>
  </div>
  <nav class="work-tabs" aria-label="实验流程">
    <div
      class="segmented-control"
      :style="{ '--segment-count': tabs.length, '--selected-segment': activeTabIndex }"
    >
      <button
        v-for="t in tabs"
        :key="t.id"
        type="button"
        class="work-tab"
        :aria-pressed="tab === t.id"
        @click="activate(t.id)"
      >
        <Icon :name="t.icon" :size="14" aria-hidden="true" />
        {{ comparing && t.id === 'config' ? '检测配置' : t.label }}
      </button>
    </div>
  </nav>
  <div v-if="store.running && tab !== 'config'" class="experiment-banner">
    <Icon name="loader" class="spin text-primary" :size="20" />
    <div class="progress-content">
      <div class="flex between">
        <strong>{{ store.current?.name || '准备运行实验' }}</strong>
        <span class="small text-primary">{{ store.progress }}%</span>
      </div>
      <div class="progress-track"><span :style="{ width: store.progress + '%' }"></span></div>
      <p class="progress-message">{{ store.current?.message || '正在提交实验…' }}</p>
    </div>
    <button class="btn sm" @click="cancel">
      <Icon name="pause" :size="12" />
      取消
    </button>
  </div>
  <div v-if="store.current?.status === 'failed'" class="error-box mb-20">
    <strong>实验未能完成</strong>
    <p>{{ store.current.error }}</p>
    <button class="link-button mt-8" :disabled="!canRun" @click="run()">
      重新运行
      <Icon name="refresh" :size="12" />
    </button>
  </div>
  <section
    v-if="tab === 'config'"
    class="config-workflow"
    :aria-label="comparing ? '实际数据对比工作流' : '模拟压力测试工作流'"
  >
    <div class="workflow-diagram">
      <div class="workflow-inputs">
        <button
          v-for="node in nodes"
          :key="node.id"
          type="button"
          class="workflow-node"
          :aria-label="'配置' + configLabels[node.id]"
          aria-haspopup="dialog"
          :disabled="store.running || uploading || updatingLabel"
          @click="openConfig(node.id)"
        >
          <span class="workflow-icon"><Icon :name="node.icon" :size="20" /></span>
          <span class="workflow-node-copy">
            <span class="workflow-node-label">{{ configLabels[node.id] }}</span>
            <strong class="workflow-node-value" :title="node.value">{{ node.value }}</strong>
            <span v-if="node.detail" class="workflow-node-detail" :title="node.detail">
              {{ node.detail }}
            </span>
          </span>
          <Icon name="right" :size="15" class="workflow-node-arrow" />
        </button>
      </div>

      <WorkflowLinks :active="canRun || store.running" />

      <section class="workflow-run" aria-labelledby="workflow-run-title">
        <div class="workflow-run-heading">
          <span class="workflow-icon"><Icon name="play" :size="19" /></span>
          <h2 id="workflow-run-title">运行预览</h2>
        </div>
        <template v-if="store.running">
          <div class="stack workflow-progress" aria-live="polite">
            <div class="flex between">
              <strong>正在运行</strong>
              <span class="mono">{{ store.progress }}%</span>
            </div>
            <div class="progress-track"><span :style="{ width: store.progress + '%' }"></span></div>
            <p class="small muted">{{ store.current?.message || '正在提交实验…' }}</p>
          </div>
          <button class="btn full" @click="cancel">取消运行</button>
        </template>
        <template v-else>
          <dl class="workflow-run-stats">
            <template v-if="comparing">
              <div>
                <dt>基准样本</dt>
                <dd>{{ dataset?.profile.rows.toLocaleString() ?? '—' }}</dd>
              </div>
              <div>
                <dt>待检测样本</dt>
                <dd>{{ currentDataset?.profile.rows.toLocaleString() ?? '—' }}</dd>
              </div>
            </template>
            <template v-else>
              <div>
                <dt>预计场景（含对照）</dt>
                <dd>{{ dataset ? scenarioCount : '—' }}</dd>
              </div>
              <div>
                <dt>每个场景的样本</dt>
                <dd>{{ dataset ? store.samples?.toLocaleString() || '—' : '—' }}</dd>
              </div>
            </template>
          </dl>
          <p
            v-if="runProblem"
            class="workflow-run-issue"
            :role="runProblem.panel === 'model' && !configPanel ? 'alert' : undefined"
          >
            {{ runProblem.message }}
          </p>
          <p v-else class="workflow-run-ready" aria-live="polite">
            <Icon name="success" :size="14" />
            {{ uploading ? '正在导入数据' : updatingLabel ? '正在更新真实标签' : '配置就绪' }}
          </p>
          <button
            v-if="runProblem && canUseDemoLabel"
            class="link-button workflow-run-fix"
            :disabled="updatingLabel"
            @click="setLabel('y')"
          >
            改用示例标签 y
          </button>
          <button
            v-else-if="runProblem"
            class="link-button workflow-run-fix"
            :disabled="uploading || updatingLabel"
            @click="openConfig(runProblem.panel)"
          >
            打开{{ configLabels[runProblem.panel] }}设置
            <Icon name="arrow" :size="12" />
          </button>
          <button class="btn success full workflow-run-button" :disabled="!canRun" @click="run()">
            <Icon name="play" :size="14" />
            {{ runLabel }}
          </button>
          <button
            v-if="completed"
            class="link-button workflow-result-link"
            @click="activate('results')"
          >
            查看已保存结果
            <Icon name="arrow" :size="12" />
          </button>
        </template>
      </section>
    </div>
  </section>
  <template v-else-if="completed">
    <div class="info-strip mb-20">
      <Icon name="clock" :size="13" />
      <span>
        当前查看：
        <strong>{{ completed.name }}</strong>
        · 基准 {{ completed.datasetName
        }}{{
          completed.currentDatasetName
            ? ' → 待检测 ' + completed.currentDatasetName
            : ' · 模拟压力测试'
        }}
        · {{ completed.modelName }}。结果使用本次实验保存的参数。
      </span>
      <RouterLink to="/history" class="link-button" style="margin-left: auto; white-space: nowrap">
        切换实验
      </RouterLink>
    </div>
    <Results v-if="tab === 'results'" :experiment="completed" />
    <Calibration v-else-if="tab === 'calibration'" :experiment="completed" />
    <Report v-else :experiment="completed" />
  </template>
  <section v-else class="panel">
    <div class="empty-state">
      <div class="empty-symbol">
        <Icon
          :name="store.running ? 'loader' : 'flask'"
          :size="24"
          :class="{ spin: store.running }"
        />
      </div>
      <h3>{{ store.running ? '实验正在运行' : '还没有可分析的实验' }}</h3>
      <p>完成一次压力测试后，结果分析、阈值校准和配置导出将在这里呈现。</p>
      <button class="btn primary" @click="activate('config')">
        返回场景配置
        <Icon name="arrow" :size="13" />
      </button>
    </div>
  </section>
  <Modal v-if="configPanel" :title="'配置' + configLabels[configPanel]" @close="closeConfig">
    <template v-if="configPanel === 'baseline'">
      <div class="flex between">
        <div class="field-label field-label-with-help">
          基准数据说明
          <HelpTip
            label="基准数据"
            text="用作比较参照的数据。模拟测试在副本上生成变化；实际检测将新数据与它对比。"
          />
        </div>
        <RouterLink to="/datasets" class="link-button">
          管理数据集
          <Icon name="right" :size="12" />
        </RouterLink>
      </div>
      <p v-if="comparing" class="small muted mt-12 mb-12">正常时期的数据，作为固定参照。</p>
      <div v-if="dataset" class="data-file mt-12">
        <div class="file-tile"><Icon name="csv" :size="20" /></div>
        <div style="min-width: 0">
          <strong>{{ dataset?.name }}</strong>
          <small>{{ dataset?.source }} · {{ dataset?.profile.rows.toLocaleString() }} 行</small>
        </div>
        <Icon name="success" :size="14" class="file-arrow" />
      </div>
      <div class="form-field mt-12">
        <label for="dataset-select">基准数据集</label>
        <select
          id="dataset-select"
          :disabled="uploading || updatingLabel"
          :value="dataset && datasetRole(dataset) === 'reference' ? store.activeDatasetId : ''"
          @change="selectDataset(($event.target as HTMLSelectElement).value)"
        >
          <option value="" disabled>请选择基准数据</option>
          <option v-for="d in referenceDatasets" :key="d.id" :value="d.id">{{ d.name }}</option>
        </select>
      </div>
      <button
        class="btn sm mt-12"
        :disabled="uploading || updatingLabel || store.running"
        @click="baselineInput?.click()"
      >
        <Icon name="upload" :size="13" />
        导入基准 CSV
      </button>
      <input
        ref="baselineInput"
        type="file"
        accept=".csv"
        hidden
        aria-label="导入基准 CSV"
        @change="importDataset($event, 'reference')"
      />
      <div v-if="dataset" class="form-field mt-12">
        <div class="field-label field-label-with-help">
          <label for="label-select">真实标签列</label>
          <HelpTip label="真实标签列" text="选择模型要预测的实际结果列，用于计算模型表现。" />
        </div>
        <select
          id="label-select"
          :disabled="updatingLabel"
          :value="dataset?.label || ''"
          @change="setLabel(($event.target as HTMLSelectElement).value || null)"
        >
          <option value="">不使用标签 · 不计算真实性能</option>
          <option v-for="f in dataset?.profile.fields" :key="f.name" :value="f.name">
            {{ f.name
            }}{{ dataset?.profile.labelCandidates.includes(f.name) ? ' · 二分类候选' : '' }}
          </option>
        </select>
        <small v-if="model?.id === 'bank-logistic-v1'">
          示例模型的真实标签为 y；job 等字段用于模型输入。
        </small>
      </div>
    </template>
    <template v-else-if="configPanel === 'observed'">
      <p class="small muted">从实际数据集中选一批，与基准数据对比。</p>
      <div class="form-field mt-12">
        <label for="current-dataset-select">待检测数据集</label>
        <select
          id="current-dataset-select"
          :disabled="uploading"
          :value="
            currentDataset && datasetRole(currentDataset) === 'current'
              ? store.currentDatasetId
              : ''
          "
          @change="selectCurrentDataset(($event.target as HTMLSelectElement).value)"
        >
          <option value="">请选择待检测数据</option>
          <option v-for="d in actualDatasets" :key="d.id" :value="d.id">
            {{ d.name }} · {{ d.profile.rows.toLocaleString() }} 行
          </option>
        </select>
      </div>
      <button
        class="btn sm mt-12"
        :disabled="uploading || store.running"
        @click="currentInput?.click()"
      >
        <Icon name="upload" :size="13" />
        {{ uploading ? '正在导入…' : '导入待检测 CSV' }}
      </button>
      <input
        ref="currentInput"
        type="file"
        accept=".csv"
        hidden
        aria-label="导入待检测 CSV"
        @change="importDataset($event, 'current')"
      />
      <div v-if="currentDataset" class="form-field mt-12">
        <label for="current-label-select">待检测数据的真实标签列</label>
        <select id="current-label-select" v-model="store.currentLabel">
          <option :value="null">无 · 尚未获得真实结果</option>
          <option v-for="f in currentDataset.profile.fields" :key="f.name" :value="f.name">
            {{ f.name }}
          </option>
        </select>
        <small>只有已获得的实际结果才能作为标签。没有标签仍可检测数据漂移。</small>
      </div>
      <div v-if="comparisonProblem" class="info-strip amber mt-12">
        {{ comparisonProblem }}
      </div>
      <div v-else class="info-strip mt-12">
        {{ dataset?.profile.rows.toLocaleString() }} 行基准 →
        {{ currentDataset?.profile.rows.toLocaleString() }}
        行待检测数据，按基准字段名称对齐；额外字段会在结果中说明。
      </div>
      <div class="form-field mt-12">
        <label for="comparison-name">检测名称</label>
        <input
          id="comparison-name"
          v-model="store.experimentName"
          maxlength="100"
          placeholder="例如 11 月 18 日业务数据检测"
        />
      </div>
    </template>
    <template v-else-if="configPanel === 'model'">
      <div class="form-field">
        <label class="screen-reader" for="model-select">选择模型</label>
        <select id="model-select" v-model="store.activeModelId">
          <option :value="null">仅分析数据漂移</option>
          <option v-for="m in store.models" :key="m.id" :value="m.id">
            {{ m.name }} · v{{ m.version }}
          </option>
        </select>
      </div>
      <div v-if="model" class="mt-12">
        <div class="kv">
          <span>预测接口</span>
          <strong class="mono">predict{{ model.hasProba ? ' · predict_proba' : '' }}</strong>
        </div>
        <div class="kv">
          <span>运行环境</span>
          <strong>本地 Python</strong>
        </div>
        <div class="kv">
          <span>状态</span>
          <span class="tag" :class="model.status">
            {{ { ready: '可用', unvalidated: '待校验', error: '校验失败' }[model.status] }}
          </span>
        </div>
      </div>
      <p v-if="modelInputProblem" class="error-box">{{ modelInputProblem }}</p>
      <RouterLink to="/models" class="link-button mt-12">
        接入我的模型
        <Icon name="arrow" :size="12" />
      </RouterLink>
    </template>
    <template v-else>
      <div
        v-for="s in store.scenarios"
        :key="s.id"
        class="scenario-row"
        :class="{ 'disabled-scenario': !s.enabled }"
      >
        <div class="scenario-heading">
          <Icon :name="scenarioMeta[s.type].icon" :size="14" class="scenario-icon" />
          <strong>{{ scenarioMeta[s.type].name }}</strong>
          <button
            class="switch"
            :class="{ on: s.enabled }"
            role="switch"
            :aria-checked="s.enabled"
            :aria-label="scenarioMeta[s.type].name"
            :disabled="!candidates(s).length"
            @click="s.enabled = !s.enabled"
          >
            <span></span>
          </button>
        </div>
        <div class="scenario-detail">
          <div class="scenario-control-grid">
            <select
              v-model="s.field"
              class="scenario-select"
              :disabled="!s.enabled"
              :aria-label="scenarioMeta[s.type].name + '字段'"
              @change="changeField(s)"
            >
              <option v-for="f in candidates(s)" :key="f.name" :value="f.name">
                {{ f.name }}
              </option>
            </select>
            <output class="range-output">
              {{
                s.type === 'mean_shift' || s.type === 'variance'
                  ? s.strength >= 0
                    ? '+'
                    : ''
                  : ''
              }}{{ s.strength }}%
            </output>
          </div>
          <select
            v-if="s.type === 'categorical'"
            v-model="s.category"
            class="scenario-select mt-8"
            :disabled="!s.enabled"
            aria-label="目标类别"
          >
            <option v-for="c in categories(s)" :key="c.name" :value="c.name">
              {{ c.name }} · 基准 {{ percent(c.share, 0) }}
            </option>
          </select>
          <div class="range-track">
            <input
              v-model.number="s.strength"
              type="range"
              :min="scenarioMeta[s.type].min"
              :max="scenarioMeta[s.type].max"
              :disabled="!s.enabled"
              :aria-label="scenarioMeta[s.type].unit"
            />
          </div>
          <div class="range-limits">
            <span>{{ scenarioMeta[s.type].unit }}</span>
            <span>{{ scenarioMeta[s.type].min }}% — {{ scenarioMeta[s.type].max }}%</span>
          </div>
        </div>
      </div>
      <div class="grid two mt-20" style="gap: 10px">
        <div class="form-field">
          <div class="field-label field-label-with-help">
            <label for="random-seed">随机种子</label>
            <HelpTip
              label="随机种子"
              text="决定随机抽样和扰动的位置，不是行号。数据、配置和种子相同，可复现相同结果。"
            />
          </div>
          <input
            id="random-seed"
            required
            v-model.number="store.seed"
            type="number"
            min="0"
            max="4294967295"
          />
        </div>
        <div class="form-field">
          <div class="field-label field-label-with-help">
            <label for="sample-size">场景样本数</label>
            <HelpTip
              label="场景样本数"
              text="每个场景使用的行数：少于基准行数时随机抽取，等于时用全部，超过时允许重复抽取。"
            />
          </div>
          <input
            id="sample-size"
            required
            v-model.number="store.samples"
            type="number"
            min="30"
            max="50000"
          />
        </div>
      </div>
      <label class="checkbox-row mt-12">
        <input v-model="store.sweep" type="checkbox" />
        <span>
          运行 0.5× / 1× / 1.5× 强度梯度
          <br />
          <span class="muted">含对照组共 {{ scenarioCount }} 个实验场景</span>
        </span>
      </label>
      <label class="checkbox-row mt-12">
        <input v-model="store.combine" type="checkbox" />
        <span>
          增加多字段组合压力场景
          <br />
          <span class="muted">按所选顺序，以 1× 强度叠加全部启用的变换</span>
        </span>
      </label>
      <div class="form-field mt-12">
        <label for="experiment-name">实验名称</label>
        <input
          id="experiment-name"
          v-model="store.experimentName"
          maxlength="100"
          placeholder="给本次实验命名"
        />
      </div>
    </template>
    <div v-if="importError" class="error-box" role="alert">{{ importError }}</div>
    <div v-if="configPanel === 'baseline' && modelInputProblem" class="error-box" role="alert">
      {{ modelInputProblem }}
      <button
        v-if="canUseDemoLabel"
        class="link-button mt-8"
        :disabled="updatingLabel"
        @click="setLabel('y')"
      >
        改用示例标签 y
      </button>
    </div>
    <template #footer>
      <button class="btn primary" @click="closeConfig">完成配置</button>
    </template>
  </Modal>
</template>

<style scoped>
.workflow-diagram {
  display: grid;
  grid-template-columns: minmax(0, 300px) minmax(48px, 1fr) minmax(0, 280px);
  align-items: center;
  max-width: 1120px;
  min-width: 0;
  margin-inline: auto;
  padding: 42px clamp(24px, 5%, 64px);
}
.workflow-inputs {
  display: grid;
  grid-template-rows: repeat(3, 96px);
  gap: 18px;
  min-width: 0;
}
.workflow-node,
.workflow-run {
  background: var(--raised);
  border-radius: 18px;
  color: var(--ink);
  min-width: 0;
}
.workflow-node {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border: none;
  text-align: left;
  transition:
    background-color 160ms ease,
    color 160ms ease;
}
.workflow-node:hover:not(:disabled) {
  background: var(--primary-soft);
}
.workflow-icon {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: var(--primary-soft);
  color: var(--primary);
  flex: none;
}
.workflow-node-copy {
  display: grid;
  min-width: 0;
  gap: 2px;
}
.workflow-node-label,
.workflow-node-detail,
.workflow-node-arrow {
  color: var(--muted);
}
.workflow-node-label,
.workflow-node-detail {
  font-size: 11px;
}
.workflow-node-value {
  font-size: 13px;
  font-weight: 650;
}
.workflow-node-value,
.workflow-node-detail {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workflow-run {
  padding: 20px;
}
.workflow-run-heading {
  display: flex;
  align-items: center;
  gap: 10px;
}
.workflow-run-heading h2 {
  font-size: 15px;
}
.workflow-run-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 18px 0 13px;
}
.workflow-run-stats dt {
  font-size: 11px;
  color: var(--muted);
}
.workflow-run-stats dd {
  margin: 2px 0 0;
  font-size: 23px;
  line-height: 1.25;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.workflow-run-ready,
.workflow-run-issue {
  font-size: 11px;
  overflow-wrap: anywhere;
}
.workflow-run-ready {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
}
.workflow-run-issue {
  color: var(--amber);
}
.workflow-run-button,
.workflow-run-fix,
.workflow-result-link {
  margin-top: 12px;
}
.workflow-result-link {
  display: flex;
  justify-content: center;
  width: 100%;
}
.workflow-progress {
  margin: 16px 0;
  gap: 6px;
}
.workflow-progress .progress-track {
  margin-top: 0;
}
@media (max-width: 1020px) {
  .workflow-diagram {
    padding-inline: 24px;
    grid-template-columns: minmax(0, 270px) minmax(42px, 1fr) minmax(0, 250px);
  }
}
@media (max-width: 700px) {
  .workflow-diagram {
    grid-template-columns: minmax(0, 1fr);
    gap: 12px;
    padding: 14px;
  }
  .workflow-inputs {
    grid-template-rows: repeat(3, auto);
    gap: 8px;
  }
  .workflow-node {
    min-height: 70px;
    padding: 10px 12px;
  }
  .workflow-links {
    display: none;
  }
  .workflow-run {
    padding: 16px;
  }
}
</style>
