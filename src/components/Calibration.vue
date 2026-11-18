<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ChartConfiguration } from 'chart.js'
import type { Experiment } from '../types'
import { store, saveRules, notify } from '../store'
import { number, percent } from '../api'
import Icon from './Icon.vue'
import Chart from './Chart.vue'
const props = defineProps<{ experiment: Experiment }>()
const family = ref('psi')
const familyLabels: Record<string, string> = {
  psi: 'PSI',
  pvalue: 'KS / 卡方 p 值',
  missing: '缺失率',
}
const cal = computed(() => props.experiment.result!.calibration)
const current = computed(() => cal.value.families[family.value])
const busy = ref(false)
const config = computed<ChartConfiguration>(() => ({
  type: 'line',
  data: {
    labels: current.value?.rows.map((r) => String(r.threshold)) || [],
    datasets: [
      {
        label: '检测召回',
        data: current.value?.rows.map((r) => r.recall) || [],
        borderColor: '#399b7e',
        borderWidth: 2,
        pointRadius: 3,
        tension: 0.2,
      },
      {
        label: '误报率',
        data: current.value?.rows.map((r) => r.falseAlarm) || [],
        borderColor: '#cc8878',
        borderWidth: 2,
        pointRadius: 3,
        tension: 0.2,
      },
      {
        label: '漏报率',
        data: current.value?.rows.map((r) => r.missRate) || [],
        borderColor: '#d8b363',
        borderWidth: 2,
        pointRadius: 3,
        tension: 0.2,
      },
    ],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: {
        position: 'top',
        align: 'end',
        labels: {
          usePointStyle: true,
          boxWidth: 5,
          boxHeight: 5,
          font: { size: 10 },
          color: '#91a597',
        },
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 10 }, color: '#91a597' } },
      y: {
        min: 0,
        max: 1,
        grid: { color: '#eff3f0' },
        ticks: { font: { size: 10 }, color: '#91a597' },
      },
    },
  },
}))
async function apply() {
  const value = current.value?.best?.threshold
  if (value === undefined) return
  busy.value = true
  const rules = { ...store.rules }
  if (family.value === 'psi') {
    rules.warning = value
    if (rules.critical <= value) rules.critical = Math.round((value + 0.1) * 100) / 100
  }
  if (family.value === 'pvalue') rules.pvalue = value
  if (family.value === 'missing') rules.missing = value
  try {
    await saveRules(rules)
  } catch (e) {
    notify(String(e), true)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <section v-if="!cal.available" class="panel">
    <div class="empty-state">
      <div class="empty-symbol"><Icon name="target" :size="23" /></div>
      <h3>当前实验无法校准阈值</h3>
      <p>{{ cal.reason }}</p>
      <RouterLink v-if="experiment.request.mode === 'compare'" to="/rules" class="btn">
        查看监控规则
        <Icon name="arrow" />
      </RouterLink>
      <RouterLink v-else to="/models" class="btn">
        接入模型
        <Icon name="arrow" />
      </RouterLink>
    </div>
  </section>
  <div v-else class="stack">
    <div class="info-strip">
      <Icon name="info" :size="15" />
      <span>
        以 F1 绝对下降 ≥
        <strong>{{ (experiment.request.rules.impact * 100).toFixed(1) }}pp</strong>
        为实际影响标准。不同检测器分别校准，阈值只对本次数据、模型和场景负责。
      </span>
    </div>
    <div class="pill-row">
      <button
        v-for="(label, key) in familyLabels"
        :key="key"
        class="pill"
        :class="{ active: family === key }"
        @click="family = key"
      >
        {{ label }}
      </button>
    </div>
    <div v-if="current" class="grid two">
      <section class="panel">
        <header class="panel-head">
          <div>
            <h2>阈值权衡曲线</h2>
            <p>{{ current.count }} 个场景参与校准 · 纵轴 0–1 表示比例</p>
          </div>
          <Icon name="chart" class="muted" />
        </header>
        <div class="panel-body">
          <Chart :config="config" label="阈值、召回率、误报率与漏报率对比" :height="295" />
        </div>
      </section>
      <section class="panel">
        <header class="panel-head">
          <h2>推荐阈值</h2>
          <span class="tag green">{{ familyLabels[family] }}</span>
        </header>
        <div class="panel-body">
          <template v-if="current.best">
            <div class="recommendation">
              <span>当前实验集上的推荐</span>
              <strong>{{ family === 'pvalue' ? 'p < ' : '≥ ' }}{{ current.best.threshold }}</strong>
              <p>优先取得检测 F1 较高的阈值，再比较误报率。</p>
            </div>
            <div class="grid three mt-16">
              <div>
                <p class="small muted">检测召回</p>
                <strong class="text-primary">{{ percent(current.best.recall) }}</strong>
              </div>
              <div>
                <p class="small muted">误报率</p>
                <strong class="text-amber">{{ percent(current.best.falseAlarm) }}</strong>
              </div>
              <div>
                <p class="small muted">漏报率</p>
                <strong class="text-danger">{{ percent(current.best.missRate) }}</strong>
              </div>
            </div>
            <button class="btn primary full mt-20" :disabled="busy" @click="apply">
              <Icon name="check" />
              采用推荐阈值
            </button>
          </template>
          <div v-else class="info-strip amber">
            <Icon name="warning" />
            <span>{{ current.reason }}</span>
          </div>
        </div>
      </section>
      <section class="panel span-all">
        <header class="panel-head">
          <h2>各阈值的实际检测结果</h2>
          <span class="small muted">正例：模型受影响的压力场景</span>
        </header>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>阈值</th>
                <th class="num">TP</th>
                <th class="num">FP</th>
                <th class="num">FN</th>
                <th class="num">TN</th>
                <th class="num">召回</th>
                <th class="num">精确率</th>
                <th class="num">误报率</th>
                <th class="num">漏报率</th>
                <th>建议</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="r in current.rows"
                :key="r.threshold"
                :class="{ 'selected-row': r.threshold === current.best?.threshold }"
              >
                <td class="mono">
                  {{ family === 'pvalue' ? 'p < ' : '≥ '
                  }}{{ number(r.threshold, family === 'pvalue' ? 3 : 2) }}
                </td>
                <td class="num">{{ r.tp }}</td>
                <td class="num">{{ r.fp }}</td>
                <td class="num">{{ r.fn }}</td>
                <td class="num">{{ r.tn }}</td>
                <td class="num">{{ percent(r.recall, 0) }}</td>
                <td class="num">{{ percent(r.precision, 0) }}</td>
                <td class="num">{{ percent(r.falseAlarm, 0) }}</td>
                <td class="num">{{ percent(r.missRate, 0) }}</td>
                <td>
                  <span v-if="r.threshold === current.best?.threshold" class="tag green">推荐</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
    <div v-else class="info-strip amber">当前实验没有适用于此检测器的场景。</div>
    <div class="info-strip blue">
      <Icon name="info" />
      <span>
        样本量会影响 KS / 卡方检验的敏感度；这里展示每次实验中所有字段的最小 p
        值，未做多重检验校正。当前版本不测量时间窗口的检测延迟。
      </span>
    </div>
  </div>
</template>
