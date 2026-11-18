<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  store,
  dataset,
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
import { api, number, percent } from '../api'
import type { Dataset, Scenario } from '../types'
import Icon from '../components/Icon.vue'
import HelpTip from '../components/HelpTip.vue'
import Results from '../components/Results.vue'
import Calibration from '../components/Calibration.vue'
import Report from '../components/Report.vue'
const route = useRoute(),
  router = useRouter()
const tab = ref(String(route.query.tab || 'config'))
watch(
  () => route.query.tab,
  (value) => {
    if (value) tab.value = String(value)
  },
)
const tabs = [
  { id: 'config', label: '场景配置', icon: 'sliders' },
  { id: 'results', label: '结果分析', icon: 'chart' },
  { id: 'calibration', label: '阈值校准', icon: 'target' },
  { id: 'report', label: '报告与导出', icon: 'file' },
]
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
const currentChoices = computed(() => store.datasets.filter((d) => d.id !== store.activeDatasetId))
const comparisonProblem = computed(() => {
  if (!currentDataset.value) return '请选择或导入本次采集的待检测数据。'
  if (currentDataset.value.id === dataset.value?.id)
    return '待检测数据不能与基准相同，请选择另一份采集数据。'
  const missing = fields.value.filter(
    (f) =>
      f.name === store.currentLabel ||
      !currentDataset.value!.profile.fields.some((c) => c.name === f.name),
  )
  if (missing.length) return '待检测数据缺少基准特征字段：' + missing.map((f) => f.name).join('、')
  return ''
})
const canRun = computed(
  () =>
    !store.running &&
    !!dataset.value &&
    compatible.value &&
    (comparing.value ? !comparisonProblem.value : selectedCount.value > 0),
)
const baselineInput = ref<HTMLInputElement>()
const currentInput = ref<HTMLInputElement>()
const uploading = ref(false)
const importError = ref('')
async function importDataset(event: Event, role: 'reference' | 'current') {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploading.value = true
  importError.value = ''
  try {
    const form = new FormData()
    form.append('file', file)
    const item = await api<Dataset>('/datasets', { method: 'POST', body: form })
    store.datasets.unshift(item)
    if (role === 'reference') selectDataset(item.id)
    else selectCurrentDataset(item.id)
    notify(role === 'reference' ? '已导入并选择基准数据' : '已导入待检测数据，基准保持不变')
  } catch (e) {
    importError.value = e instanceof Error ? e.message : String(e)
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
  if (!dataset.value) return
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
      <button class="btn" @click="loadDemo">
        <Icon name="reset" :size="14" />
        加载示例
      </button>
      <button class="btn" :disabled="!completed" @click="activate('report')">
        <Icon name="download" :size="14" />
        导出监控配置
      </button>
      <button class="btn primary" :disabled="!canRun || uploading" @click="run()">
        <Icon
          :name="store.running ? 'loader' : 'play'"
          :class="{ spin: store.running }"
          :size="14"
        />
        {{ store.running ? '实验运行中' : comparing ? '运行实际检测' : '运行压力测试' }}
      </button>
    </div>
  </div>
  <section class="panel mode-selector mb-20" aria-label="检测模式">
    <div class="panel-body">
      <div class="pill-row" role="group" aria-label="选择检测模式">
        <button
          class="pill"
          :class="{ active: !comparing }"
          :aria-pressed="!comparing"
          :disabled="store.running"
          @click="setMode('stress')"
        >
          模拟压力测试
        </button>
        <button
          class="pill"
          :class="{ active: comparing }"
          :aria-pressed="comparing"
          :disabled="store.running"
          @click="setMode('compare')"
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
      <div v-if="importError" class="error-box" role="alert">{{ importError }}</div>
    </div>
  </section>
  <div class="summary-bar">
    <div class="summary-cell">
      <span>基准数据集</span>
      <strong>
        <Icon name="database" :size="11" class="summary-icon" />
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
        <span v-if="dataset?.label" style="display: inline; font-size: 9px; margin-left: 4px">
          / binary
        </span>
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
    <button
      v-for="(t, i) in tabs"
      :key="t.id"
      class="work-tab"
      :class="{ active: tab === t.id }"
      @click="activate(t.id)"
    >
      <Icon :name="t.icon" :size="14" />
      {{ comparing && t.id === 'config' ? '检测配置' : t.label }}
      <span class="tab-number">0{{ i + 1 }}</span>
    </button>
  </nav>
  <div v-if="store.running" class="experiment-banner">
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
    <button class="link-button mt-8" :disabled="!canRun || uploading" @click="run()">
      重新运行
      <Icon name="refresh" :size="12" />
    </button>
  </div>
  <template v-if="tab === 'config'">
    <div class="workbench-grid">
      <div class="stack workbench-config">
        <section class="panel">
          <header class="panel-head">
            <h2>
              <span class="panel-step">1</span>
              基准数据
              <HelpTip
                label="基准数据"
                text="用作比较参照的数据。模拟测试在副本上生成变化；实际检测将新数据与它对比。"
              />
            </h2>
            <RouterLink to="/datasets" class="link-button">
              管理
              <Icon name="right" :size="12" />
            </RouterLink>
          </header>
          <div class="panel-body">
            <p v-if="comparing" class="small muted mb-12">
              正常时期的数据，作为固定参照；导入待检测数据不会替换它。
            </p>
            <div class="data-file">
              <div class="file-tile"><Icon name="csv" :size="20" /></div>
              <div style="min-width: 0">
                <strong>{{ dataset?.name }}</strong>
                <small>
                  {{ dataset?.source }} · {{ dataset?.profile.rows.toLocaleString() }} 行
                </small>
              </div>
              <Icon name="success" :size="14" class="file-arrow" />
            </div>
            <div class="form-field mt-12">
              <label for="dataset-select">切换数据集</label>
              <select
                id="dataset-select"
                :value="store.activeDatasetId"
                @change="selectDataset(($event.target as HTMLSelectElement).value)"
              >
                <option v-for="d in store.datasets" :key="d.id" :value="d.id">{{ d.name }}</option>
              </select>
            </div>
            <button
              class="btn sm mt-12"
              :disabled="uploading || store.running"
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
            <div class="form-field mt-12">
              <label for="label-select">真实标签列</label>
              <select
                id="label-select"
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
          </div>
        </section>
        <section v-if="comparing" class="panel">
          <header class="panel-head">
            <h2>
              <span class="panel-step">2</span>
              待检测数据
            </h2>
            <span class="tag blue">本次实际采集</span>
          </header>
          <div class="panel-body">
            <p class="small muted">选择今天或本次采集的数据，与上方固定基准对比。</p>
            <div class="form-field mt-12">
              <label for="current-dataset-select">待检测数据集</label>
              <select
                id="current-dataset-select"
                :value="store.currentDatasetId"
                @change="selectCurrentDataset(($event.target as HTMLSelectElement).value)"
              >
                <option value="">请选择待检测数据</option>
                <option v-for="d in currentChoices" :key="d.id" :value="d.id">
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
          </div>
        </section>
        <section class="panel">
          <header class="panel-head">
            <h2>
              <span class="panel-step">{{ comparing ? 3 : 2 }}</span>
              模型适配器
            </h2>
            <span
              class="tag"
              :class="model?.kind === 'builtin' ? 'amber' : model?.status || 'gray'"
            >
              {{ model?.kind === 'builtin' ? '内置模型' : model ? '本地适配器' : '未接入' }}
            </span>
          </header>
          <div class="panel-body">
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
            <div v-if="!compatible" class="error-box" role="alert">
              <p>{{ modelInputProblem }}</p>
              <button
                v-if="
                  model?.id === 'bank-logistic-v1' &&
                  dataset?.label &&
                  model.features.includes(dataset.label) &&
                  fields.some((f) => f.name === 'y')
                "
                class="link-button mt-8"
                :disabled="store.running"
                @click="setLabel('y')"
              >
                改用示例标签 y
              </button>
            </div>
            <RouterLink to="/models" class="link-button mt-12">
              接入我的模型
              <Icon name="arrow" :size="12" />
            </RouterLink>
          </div>
        </section>
        <section v-if="!comparing" class="panel">
          <header class="panel-head">
            <h2>
              <span class="panel-step">3</span>
              漂移场景
            </h2>
            <span class="tag gray">{{ selectedCount }} / 5 已启用</span>
          </header>
          <div class="panel-body">
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
          </div>
        </section>
        <div class="helper-note">
          <Icon name="info" :size="13" />
          <span>
            性能指标仅在测试样本有有效真实标签时计算。发现数据漂移不等于确认模型性能下降。
          </span>
        </div>
        <button class="btn primary full" :disabled="!canRun || uploading" @click="run()">
          <Icon
            :name="store.running ? 'loader' : 'play'"
            :class="{ spin: store.running }"
            :size="14"
          />
          {{ store.running ? '运行中…' : comparing ? '运行实际检测' : '运行实验' }}
        </button>
      </div>
      <div class="stack">
        <Results v-if="completed" :experiment="completed" compact />
        <template v-else>
          <div class="welcome-card">
            <div class="welcome-overline">
              {{ comparing ? 'REFERENCE → OBSERVED DATA' : 'YOUR MODEL, UNDER PRESSURE.' }}
            </div>
            <h2>
              {{ comparing ? '固定参照，看清每天的数据变化。' : '可靠的模型，从了解变化开始。' }}
            </h2>
            <p>
              {{
                comparing
                  ? '选择正常时期的基准，导入本次实际采集的数据。系统逐字段比较分布，并保存本次检测，供以后回看与复现。'
                  : '用可控、可复现的输入变化，检验你的分类模型。配置已就绪，点击运行即可完成第一次压力测试。'
              }}
            </p>
            <div class="welcome-steps">
              <div class="welcome-step">
                <span>1</span>
                基准数据
                <Icon name="right" :size="11" />
              </div>
              <div class="welcome-step">
                <span>2</span>
                {{ comparing ? '待检测数据' : '变化场景' }}
                <Icon name="right" :size="11" />
              </div>
              <div class="welcome-step">
                <span>3</span>
                {{ comparing ? '分布对比' : '模型影响' }}
                <Icon name="right" :size="11" />
              </div>
              <div class="welcome-step">
                <span>4</span>
                监控规则
              </div>
            </div>
          </div>
          <div class="metrics-row">
            <div class="metric">
              <div class="metric-label">
                <i class="metric-dot"></i>
                基准样本
              </div>
              <div class="metric-number">{{ dataset?.profile.rows.toLocaleString() }}</div>
              <p class="metric-caption">本地数据，准备就绪</p>
            </div>
            <div class="metric">
              <div class="metric-label">
                <i class="metric-dot" style="background: #d8b05c"></i>
                {{ comparing ? '待检测样本' : '场景覆盖' }}
              </div>
              <div class="metric-number amber">
                {{
                  comparing ? currentDataset?.profile.rows.toLocaleString() || '—' : scenarioCount
                }}
              </div>
              <p class="metric-caption">
                {{ comparing ? '使用全部采集数据' : '含强度梯度与对照组' }}
              </p>
            </div>
            <div class="metric">
              <div class="metric-label">
                <i class="metric-dot" style="background: #6b92d3"></i>
                检测方法
              </div>
              <div class="metric-number blue">3</div>
              <p class="metric-caption">PSI · KS · Chi-square</p>
            </div>
            <div class="metric">
              <div class="metric-label">
                <i class="metric-dot" style="background: #d8b05c"></i>
                预警阈值
              </div>
              <div class="metric-number amber">{{ number(store.rules.warning, 2) }}</div>
              <p class="metric-caption">PSI · 实验后可校准</p>
            </div>
          </div>
          <section class="panel">
            <header class="panel-head">
              <div>
                <h2>{{ comparing ? '基准与实际数据分布对比' : '漂移强度与模型表现' }}</h2>
                <p>
                  {{
                    comparing
                      ? '完成检测后，查看字段风险、分布图与缺失率变化。'
                      : '完成实验后，查看基准与场景的真实计算结果。'
                  }}
                </p>
              </div>
              <Icon name="chart" class="muted" />
            </header>
            <div class="empty-state" style="min-height: 300px">
              <div class="empty-symbol"><Icon name="chart" :size="24" /></div>
              <h3>{{ store.running ? '正在计算实验结果' : '等待第一次实验' }}</h3>
              <p>
                {{
                  store.running
                    ? '场景生成、统计检验与模型预测都在本机完成，结果会自动更新。'
                    : '图表将展示输入漂移与模型表现的联系，帮助你区分分布变化和真实性能影响。'
                }}
              </p>
              <button
                v-if="!store.running"
                class="btn primary"
                :disabled="!canRun || uploading"
                @click="run()"
              >
                <Icon name="play" :size="13" />
                {{ comparing ? '开始实际数据检测' : '开始第一次实验' }}
              </button>
            </div>
          </section>
          <section class="panel">
            <header class="panel-head">
              <h2>基准数据速览</h2>
              <RouterLink to="/datasets" class="link-button">
                查看画像
                <Icon name="right" :size="11" />
              </RouterLink>
            </header>
            <div class="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>字段</th>
                    <th>类型</th>
                    <th class="num">唯一值</th>
                    <th class="num">缺失率</th>
                    <th class="num">基准均值 / 主类别</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="f in fields.slice(0, 6)" :key="f.name">
                    <td>
                      <strong>{{ f.name }}</strong>
                    </td>
                    <td>{{ f.type === 'numeric' ? '数值' : '类别' }}</td>
                    <td class="num">{{ f.unique }}</td>
                    <td class="num">{{ percent(f.missing) }}</td>
                    <td class="num">
                      {{ f.type === 'numeric' ? number(f.mean, 2) : f.categories?.[0]?.name }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </template>
        <div v-if="completed" class="flex between">
          <span class="small muted">
            已保存结果：{{ completed.name }} · 基准 {{ completed.datasetName
            }}{{
              completed.currentDatasetName
                ? ' → 待检测 ' + completed.currentDatasetName
                : ' · 模拟压力测试'
            }}
          </span>
          <button class="link-button" @click="activate('results')">
            查看完整分析
            <Icon name="arrow" :size="13" />
          </button>
        </div>
      </div>
    </div>
  </template>
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
</template>
