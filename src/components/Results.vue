<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ChartConfiguration } from 'chart.js'
import type { Experiment } from '../types'
import { number, percent } from '../api'
import Chart from './Chart.vue'
import Icon from './Icon.vue'
import Modal from './Modal.vue'
const props = defineProps<{ experiment: Experiment; compact?: boolean }>()
const selectedId = ref('')
const selectedField = ref('')
const showField = ref(false)
const result = computed(() => props.experiment.result!)
const comparing = computed(() => props.experiment.request.mode === 'compare')
watch(
  () => props.experiment.id,
  () => {
    const scenarios = props.experiment.result?.scenarios.filter((s) => s.type !== 'control') || []
    selectedId.value =
      [...scenarios].sort((a, b) => (b.f1Drop ?? b.maxPsi) - (a.f1Drop ?? a.maxPsi))[0]?.id || ''
  },
  { immediate: true },
)
const current = computed(
  () => result.value.scenarios.find((s) => s.id === selectedId.value) || result.value.scenarios[0]!,
)
const baseline = computed(() => result.value.baseline)
const metrics = computed(() => current.value.evaluation?.metrics)
const field = computed(
  () => current.value.fields.find((f) => f.name === selectedField.value) || current.value.fields[0],
)
const changed = computed(() => current.value.fields.filter((f) => f.risk !== 'stable').length)
const rule = computed(() => props.experiment.request.rules)
const predictionChanged = computed(() =>
  current.value.evaluation && baseline.value
    ? Math.abs(current.value.evaluation.positiveRate - baseline.value.positiveRate) >=
      rule.value.prediction_change
    : false,
)
const palette = ['#399b7e', '#6b92d3', '#d7ad58']
const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false as const,
  plugins: {
    legend: {
      position: 'top' as const,
      align: 'end' as const,
      labels: {
        usePointStyle: true,
        pointStyle: 'circle',
        boxHeight: 5,
        boxWidth: 5,
        padding: 17,
        color: '#849a8e',
        font: { size: 10 },
      },
    },
  },
  scales: {
    x: { grid: { display: false }, ticks: { color: '#94a79b', font: { size: 9 }, maxRotation: 0 } },
    y: { grid: { color: '#eff3f0' }, ticks: { color: '#94a79b', font: { size: 9 } } },
  },
}
const trend = computed<ChartConfiguration>(() => {
  if (comparing.value)
    return {
      type: 'bar',
      data: {
        labels: current.value.fields.slice(0, 12).map((f) => f.name),
        datasets: [
          {
            label: '字段 PSI',
            data: current.value.fields.slice(0, 12).map((f) => f.psi),
            backgroundColor: '#91b7a7',
            borderRadius: 3,
          },
        ],
      },
      options: chartOptions,
    }
  const group = result.value.scenarios
    .filter((s) => s.type === current.value.type && s.field === current.value.field)
    .sort((a, b) => a.strength - b.strength)
  const scenarios = [result.value.scenarios[0]!, ...group.filter((s) => s.type !== 'control')]
  return {
    type: 'line',
    data: {
      labels: scenarios.map((s) => `${s.strength}%`),
      datasets: [
        ...(baseline.value?.metrics
          ? [
              {
                label: '模型 F1',
                data: scenarios.map((s) => s.evaluation?.metrics?.f1 ?? null),
                borderColor: palette[0],
                backgroundColor: '#399b7e0a',
                fill: true,
                tension: 0.25,
                borderWidth: 2,
                pointRadius: 3,
                yAxisID: 'y',
              },
            ]
          : []),
        {
          label: '最大 PSI',
          data: scenarios.map((s) => s.maxPsi),
          borderColor: palette[1],
          borderDash: [5, 4],
          tension: 0.25,
          borderWidth: 2,
          pointRadius: 3,
          yAxisID: 'y1',
        },
        {
          label: 'PSI 预警阈值',
          data: scenarios.map(() => rule.value.warning),
          borderColor: palette[2],
          borderDash: [3, 4],
          borderWidth: 1,
          pointRadius: 0,
          yAxisID: 'y1',
        },
      ],
    },
    options: {
      ...chartOptions,
      scales: {
        ...chartOptions.scales,
        y: {
          ...chartOptions.scales.y,
          min: 0,
          max: 1,
          title: { display: true, text: 'F1', color: '#91a99a', font: { size: 9 } },
        },
        y1: {
          position: 'right',
          min: 0,
          grid: { drawOnChartArea: false },
          title: { display: true, text: 'PSI', color: '#91a99a', font: { size: 9 } },
          ticks: { color: '#94a79b', font: { size: 9 } },
        },
      },
    },
  }
})
const distChart = computed<ChartConfiguration>(() => ({
  type: 'bar',
  data: {
    labels: field.value?.distribution.labels || [],
    datasets: [
      {
        label: '基准',
        data: field.value?.distribution.reference || [],
        backgroundColor: '#91b7a7',
        borderRadius: 3,
      },
      {
        label: comparing.value ? '待检测数据' : '当前场景',
        data: field.value?.distribution.current || [],
        backgroundColor: '#e4be73',
        borderRadius: 3,
      },
    ],
  },
  options: chartOptions,
}))
const roc = computed<ChartConfiguration>(() => ({
  type: 'line',
  data: {
    datasets: [
      {
        label: `基准 AUC ${number(baseline.value?.metrics?.auc)}`,
        data: baseline.value?.metrics?.roc || [],
        borderColor: palette[0],
        pointRadius: 0,
        borderWidth: 2,
      },
      {
        label: `${comparing.value ? '待检测' : '场景'} AUC ${number(metrics.value?.auc)}`,
        data: metrics.value?.roc || [],
        borderColor: palette[1],
        pointRadius: 0,
        borderWidth: 2,
      },
    ],
  },
  options: {
    ...chartOptions,
    scales: {
      x: {
        type: 'linear',
        min: 0,
        max: 1,
        grid: { color: '#eff3f0' },
        title: { display: true, text: 'False positive rate', font: { size: 9 } },
        ticks: { font: { size: 9 } },
      },
      y: {
        ...chartOptions.scales.y,
        min: 0,
        max: 1,
        title: { display: true, text: 'True positive rate', font: { size: 9 } },
      },
    },
  },
}))
const probabilities = computed<ChartConfiguration>(() => ({
  type: 'bar',
  data: {
    labels: Array.from(
      { length: 10 },
      (_, i) => `${(i / 10).toFixed(1)}–${((i + 1) / 10).toFixed(1)}`,
    ),
    datasets: [
      {
        label: '基准概率分布',
        data: baseline.value?.probability || [],
        backgroundColor: '#91b7a7',
        borderRadius: 3,
      },
      {
        label: comparing.value ? '待检测概率分布' : '场景概率分布',
        data: current.value.evaluation?.probability || [],
        backgroundColor: '#e4be73',
        borderRadius: 3,
      },
    ],
  },
  options: chartOptions,
}))
function inspect(name: string) {
  selectedField.value = name
  showField.value = true
}
</script>
<template>
  <div class="stack">
    <div v-if="comparing" class="info-strip comparison-identity">
      <Icon name="database" :size="16" />
      <span>
        <strong>基准：{{ experiment.datasetName }}</strong>
        （{{ result.rows.toLocaleString() }} 行）
        <br />
        <strong>待检测：{{ experiment.currentDatasetName }}</strong>
        （{{ result.currentRows?.toLocaleString() }} 行）
        <br />
        以下结果表示这份待检测数据相对于固定基准的变化。
      </span>
    </div>
    <div v-for="warning in result.warnings || []" :key="warning" class="info-strip amber">
      {{ warning }}
    </div>
    <div class="flex between wrap">
      <div class="flex">
        <span class="tag completed">
          <Icon name="checks" :size="11" />
          已完成
        </span>
        <span class="small muted">
          {{
            comparing
              ? '实际数据对比 · 全量样本'
              : result.scenarios.length + ' 个场景 · Seed ' + experiment.request.seed
          }}
          · {{ result.duration.toFixed(2) }}s
        </span>
      </div>
      <div v-if="!comparing" class="form-field" style="min-width: 210px; max-width: 330px">
        <label class="screen-reader" for="result-scenario">分析场景</label>
        <select id="result-scenario" v-model="selectedId">
          <option v-for="s in result.scenarios" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </div>
    </div>
    <div class="metrics-row">
      <div class="metric">
        <div class="metric-label">
          <i class="metric-dot"></i>
          {{ comparing && !baseline?.metrics ? '基准样本' : '基准 F1' }}
        </div>
        <div class="metric-number">
          {{
            comparing && !baseline?.metrics
              ? result.rows.toLocaleString()
              : number(baseline?.metrics?.f1)
          }}
        </div>
        <p class="metric-caption">
          {{
            comparing && !baseline?.metrics
              ? '固定参照，使用全部样本'
              : baseline?.metrics
                ? 'Reference dataset'
                : '无有效标签或未接入模型'
          }}
        </p>
      </div>
      <div class="metric">
        <div class="metric-label">
          <i class="metric-dot" style="background: #d8b05c"></i>
          {{ comparing ? (metrics ? '待检测 F1' : '待检测样本') : '场景 F1' }}
        </div>
        <div class="metric-number amber">
          {{ comparing && !metrics ? result.currentRows?.toLocaleString() : number(metrics?.f1) }}
          <span v-if="current.f1Drop !== null">
            {{ current.f1Drop > 0 ? '−' : '+' }}{{ Math.abs(current.f1Drop * 100).toFixed(1) }}pp
          </span>
        </div>
        <p class="metric-caption">
          {{
            current.impacted === null
              ? '无法确认性能影响'
              : current.impacted
                ? '达到性能影响标准'
                : '未达到影响标准'
          }}
        </p>
      </div>
      <div class="metric">
        <div class="metric-label">
          <i class="metric-dot" style="background: #6b92d3"></i>
          最大 PSI
        </div>
        <div class="metric-number blue">{{ number(current.maxPsi, 2) }}</div>
        <p class="metric-caption">
          {{
            current.maxPsi >= rule.critical
              ? '显著漂移'
              : current.maxPsi >= rule.warning
                ? '超过预警阈值'
                : '低于 PSI 预警阈值'
          }}
        </p>
      </div>
      <div class="metric">
        <div class="metric-label">
          <i class="metric-dot" style="background: #d8b05c"></i>
          PSI 预警阈值
        </div>
        <div class="metric-number amber">{{ number(rule.warning, 2) }}</div>
        <p class="metric-caption">{{ changed }} / {{ current.fields.length }} 个字段需关注</p>
      </div>
    </div>
    <section class="panel">
      <header class="panel-head">
        <div>
          <h2>{{ comparing ? '实际数据字段漂移' : '漂移强度与模型表现' }}</h2>
          <p v-if="comparing">
            待检测数据相对于基准的 PSI，展示变化最大的 12 个字段；预警阈值
            {{ number(rule.warning, 2) }}。
          </p>
          <p v-else>
            {{ current.field || '对照组' }} ·
            {{
              experiment.request.sweep
                ? '独立强度梯度实验，左轴为 F1，右轴为 PSI'
                : '单强度实验，与基准对照'
            }}
          </p>
        </div>
        <Icon name="chart" class="muted" />
      </header>
      <div class="panel-body">
        <Chart
          :config="trend"
          :label="comparing ? '实际数据字段 PSI 对比图' : '漂移强度、F1 与 PSI 双轴对比图'"
          :height="compact ? 235 : 280"
        />
      </div>
    </section>
    <section class="panel">
      <header class="panel-head">
        <div>
          <h2>字段漂移排行</h2>
          <p>PSI 与统计检验独立判定；点击字段查看分布。</p>
        </div>
        <span class="tag amber">{{ changed }} 个字段需关注</span>
      </header>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>字段</th>
              <th>PSI</th>
              <th>辅助检验</th>
              <th class="num">p 值</th>
              <th v-if="comparing" class="num">基准缺失率</th>
              <th class="num">{{ comparing ? '待检测缺失率' : '缺失率' }}</th>
              <th>风险</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="f in current.fields.slice(0, compact ? 5 : undefined)"
              :key="f.name"
              class="click-row"
              @click="inspect(f.name)"
            >
              <td>
                <button class="link-button" @click.stop="inspect(f.name)">{{ f.name }}</button>
              </td>
              <td>
                <div class="table-bar">
                  <small class="mono">{{ number(f.psi) }}</small>
                  <span>
                    <i
                      :style="{
                        width: Math.min(100, (f.psi / rule.critical) * 100) + '%',
                        background:
                          f.risk === 'stable'
                            ? '#82baa2'
                            : f.risk === 'critical'
                              ? '#d68b7d'
                              : '#d7b76b',
                      }"
                    ></i>
                  </span>
                </div>
              </td>
              <td>{{ f.method === 'ks' ? 'KS' : 'Chi-square' }}</td>
              <td class="num mono">
                {{ f.pvalue === null ? '—' : f.pvalue < 0.001 ? '< 0.001' : number(f.pvalue) }}
              </td>
              <td v-if="comparing" class="num">{{ percent(f.referenceMissing) }}</td>
              <td class="num">{{ percent(f.missing) }}</td>
              <td>
                <span class="tag" :class="f.risk">
                  {{ { stable: '稳定', warning: '关注', critical: '严重' }[f.risk] }}
                </span>
              </td>
              <td><Icon name="right" :size="12" /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <section v-if="!comparing" class="panel">
      <header class="panel-head">
        <div>
          <h2>场景影响总览</h2>
          <p>比较独立变化的结果，点击场景切换详细分析。</p>
        </div>
        <span class="tag gray">{{ result.scenarios.length }} 个场景</span>
      </header>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>场景</th>
              <th class="num">最大 PSI</th>
              <th class="num">F1</th>
              <th class="num">Recall</th>
              <th class="num">F1 下降</th>
              <th>实际影响</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in compact
                ? [...result.scenarios]
                    .sort((a, b) => (b.f1Drop ?? b.maxPsi) - (a.f1Drop ?? a.maxPsi))
                    .slice(0, 7)
                : result.scenarios"
              :key="s.id"
              :class="{ 'selected-row': s.id === current.id }"
            >
              <td>
                <button class="link-button" @click="selectedId = s.id">{{ s.name }}</button>
              </td>
              <td class="num mono">{{ number(s.maxPsi) }}</td>
              <td class="num mono">{{ number(s.evaluation?.metrics?.f1) }}</td>
              <td class="num mono">{{ number(s.evaluation?.metrics?.recall) }}</td>
              <td class="num" :class="{ 'text-danger': s.impacted }">
                {{ s.f1Drop === null ? '—' : (s.f1Drop * 100).toFixed(1) + 'pp' }}
              </td>
              <td>
                <span
                  class="tag"
                  :class="s.impacted === null ? 'gray' : s.impacted ? 'red' : 'green'"
                >
                  {{ s.impacted === null ? '无法确认' : s.impacted ? '达到标准' : '未达标准' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <template v-if="!compact">
      <div class="grid two">
        <section class="panel">
          <header class="panel-head"><h2>分层结论</h2></header>
          <div class="panel-body">
            <div class="verdict" :class="changed ? '' : 'green'">
              <h4>01 · 数据漂移 {{ changed ? '已检测到' : '未超过当前规则' }}</h4>
              <p>
                {{ changed }} 个字段触发规则；最大 PSI
                {{ number(current.maxPsi) }}。统计检验显著表示分布有变化，不等于模型失效。
              </p>
            </div>
            <div class="verdict" :class="predictionChanged ? '' : 'green'">
              <h4>
                02 · 预测分布
                {{
                  !current.evaluation
                    ? '未评估'
                    : predictionChanged
                      ? '变化超过阈值'
                      : '未超过变化阈值'
                }}
              </h4>
              <p v-if="current.evaluation && baseline">
                预测正类比例 {{ percent(baseline.positiveRate) }} →
                {{ percent(current.evaluation.positiveRate) }}，阈值
                {{ percent(rule.prediction_change) }}。
              </p>
              <p v-else>当前实验仅分析数据分布，未调用模型。</p>
            </div>
            <div
              class="verdict"
              :class="current.impacted === null ? 'blue' : current.impacted ? 'red' : 'green'"
            >
              <h4>
                03 · 性能变化
                {{
                  current.impacted === null
                    ? '无法确认'
                    : current.impacted
                      ? '达到影响标准'
                      : '未达到影响标准'
                }}
              </h4>
              <p v-if="current.f1Drop !== null">
                F1 下降 {{ (current.f1Drop * 100).toFixed(2) }}pp，影响标准为
                {{ (rule.impact * 100).toFixed(1) }}pp。{{
                  comparing
                    ? '这是两批已标注数据的性能差异，不能单独认定由漂移导致。'
                    : '此结论只针对本次保留标签的受控场景。'
                }}
              </p>
              <p v-else>
                {{
                  current.evaluation?.reason ||
                  '需要可用模型和有效真实标签，才能计算 F1、Recall、AUC。'
                }}
              </p>
            </div>
          </div>
        </section>
        <section class="panel">
          <header class="panel-head">
            <h2>模型指标对照</h2>
            <span class="tag gray">{{ comparing ? '基准 → 待检测' : '基准 → 场景' }}</span>
          </header>
          <div class="panel-body">
            <div
              v-for="key in ['accuracy', 'precision', 'recall', 'f1', 'auc'] as const"
              :key="key"
              class="kv"
            >
              <span>
                {{
                  {
                    accuracy: 'Accuracy',
                    precision: 'Precision',
                    recall: 'Recall',
                    f1: 'F1',
                    auc: 'ROC-AUC',
                  }[key]
                }}
              </span>
              <strong class="mono">
                {{ number(baseline?.metrics?.[key]) }}
                <span class="muted">→</span>
                {{ number(metrics?.[key]) }}
              </strong>
            </div>
            <div class="info-strip blue mt-16">
              <Icon name="info" :size="13" />
              <span>
                {{
                  metrics
                    ? '只有带有效真实标签的实验才显示性能指标。未提供概率输出时，AUC 留空。'
                    : '暂无可比较的真实性能指标；页面只呈现可以确认的数据与输出变化。'
                }}
              </span>
            </div>
          </div>
        </section>
        <section class="panel">
          <header class="panel-head"><h2>混淆矩阵</h2></header>
          <div v-if="metrics && baseline?.metrics" class="panel-body grid two">
            <div v-for="(m, index) in [baseline.metrics, metrics]" :key="index">
              <p class="small muted mb-16">
                {{ index === 0 ? '基准数据' : comparing ? '待检测数据' : '场景数据' }}
              </p>
              <div class="confusion-grid">
                <span></span>
                <span>预测负类</span>
                <span>预测正类</span>
                <template v-for="(row, i) in m.confusion" :key="i">
                  <span>实际{{ i ? '正' : '负' }}类</span>
                  <span v-for="(value, j) in row" :key="j" class="cell" :class="{ error: i !== j }">
                    <strong>{{ value }}</strong>
                    <small>{{ i === 0 ? (j === 0 ? 'TN' : 'FP') : j === 0 ? 'FN' : 'TP' }}</small>
                  </span>
                </template>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">
            <Icon name="layers" :size="25" />
            <p>需要模型与有效真实标签</p>
          </div>
        </section>
        <section class="panel">
          <header class="panel-head">
            <h2>ROC 曲线</h2>
            <span class="tag gray">真实标签 + 概率输出</span>
          </header>
          <div v-if="metrics?.roc" class="panel-body">
            <Chart :config="roc" label="基准与场景 ROC 曲线" :height="240" />
          </div>
          <div v-else class="empty-state">
            <Icon name="chart" :size="25" />
            <p>需要有效标签以及 predict_proba 输出</p>
          </div>
        </section>
      </div>
      <section v-if="current.evaluation?.probability" class="panel">
        <header class="panel-head">
          <div>
            <h2>预测概率分布</h2>
            <p>横轴为正类概率，纵轴为样本占比。</p>
          </div>
          <span class="tag blue">predict_proba</span>
        </header>
        <div class="panel-body">
          <Chart :config="probabilities" label="基准与场景预测正类概率分布" :height="250" />
        </div>
      </section>
      <div class="info-strip blue">
        <Icon name="info" :size="14" />
        <span>{{ result.assumption }}</span>
      </div>
    </template>
    <Modal
      v-if="showField && field"
      :title="field.name + ' · 分布对照'"
      wide
      @close="showField = false"
    >
      <div class="grid four mb-20">
        <div class="report-stat">
          <strong>{{ number(field.psi) }}</strong>
          <small>PSI</small>
        </div>
        <div class="report-stat">
          <strong>{{ field.method === 'ks' ? 'KS' : 'χ²' }}</strong>
          <small>{{ number(field.statistic) }}</small>
        </div>
        <div class="report-stat">
          <strong>
            {{ field.pvalue !== null && field.pvalue < 0.001 ? '< 0.001' : number(field.pvalue) }}
          </strong>
          <small>p-value</small>
        </div>
        <div class="report-stat">
          <strong>{{ percent(field.missing) }}</strong>
          <small>{{ comparing ? '待检测缺失率' : '场景缺失率' }}</small>
        </div>
      </div>
      <Chart
        :config="distChart"
        :label="field.name + (comparing ? '基准和待检测分布柱状图' : '基准和场景分布柱状图')"
        :height="300"
      />
      <p class="small muted mt-16">
        纵轴为样本占比；数值字段采用基准数据的分位数分箱，两端包含超出基准范围的样本。
      </p>
    </Modal>
  </div>
</template>
