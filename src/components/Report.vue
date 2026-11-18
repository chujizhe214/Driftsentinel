<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Experiment } from '../types'
import { number, percent, download, date } from '../api'
import { notify, store } from '../store'
import Icon from './Icon.vue'
const props = defineProps<{ experiment: Experiment }>()
const format = ref('yaml')
const code = ref('')
const error = ref('')
const comparing = computed(() => props.experiment.request.mode === 'compare')
const observed = computed(() => props.experiment.result!.scenarios[0]!)
const changed = computed(() => observed.value.fields.filter((f) => f.risk !== 'stable').length)
const affected = computed(() => props.experiment.result!.scenarios.filter((s) => s.impacted))
const driftOnly = computed(() =>
  props.experiment.result!.scenarios.filter(
    (s) => s.maxPsi >= props.experiment.request.rules.warning && s.impacted === false,
  ),
)
const worst = computed(
  () => [...affected.value].sort((a, b) => (b.f1Drop || 0) - (a.f1Drop || 0))[0],
)
watch(
  () => [props.experiment.id, format.value, JSON.stringify(store.rules)],
  async () => {
    try {
      error.value = ''
      const res = await fetch(
        `/api/experiments/${props.experiment.id}/export?format=${format.value}`,
      )
      if (!res.ok) throw new Error('读取配置失败')
      code.value = await res.text()
    } catch (e) {
      error.value = String(e)
    }
  },
  { immediate: true },
)
async function copy() {
  try {
    await navigator.clipboard.writeText(code.value)
    notify('配置已复制')
  } catch {
    notify('无法复制，请使用下载按钮保存配置', true)
  }
}
</script>
<template>
  <div class="stack">
    <section class="panel">
      <header class="panel-head">
        <div>
          <h2>实验报告</h2>
          <p>{{ experiment.name }} · {{ date(experiment.createdAt) }}</p>
        </div>
        <button
          class="btn sm"
          @click="download(`/api/experiments/${experiment.id}/export?format=report`)"
        >
          <Icon name="download" :size="13" />
          下载报告
        </button>
      </header>
      <div class="panel-body">
        <div class="grid four mb-20">
          <div class="report-stat">
            <strong>
              {{
                comparing
                  ? experiment.result!.rows.toLocaleString()
                  : number(experiment.result?.baseline?.metrics?.f1)
              }}
            </strong>
            <small>{{ comparing ? '基准样本' : '基准 F1' }}</small>
          </div>
          <div class="report-stat">
            <strong>
              {{
                comparing
                  ? experiment.result!.currentRows?.toLocaleString()
                  : number(experiment.result?.baseline?.metrics?.auc)
              }}
            </strong>
            <small>{{ comparing ? '待检测样本' : '基准 AUC' }}</small>
          </div>
          <div class="report-stat">
            <strong>
              {{ comparing ? changed : affected.length }} /
              {{ comparing ? experiment.result!.fields : experiment.result!.scenarios.length - 1 }}
            </strong>
            <small>{{ comparing ? '触发漂移规则的字段' : '达到性能影响标准的场景' }}</small>
          </div>
          <div class="report-stat">
            <strong>{{ experiment.result!.duration.toFixed(2) }}s</strong>
            <small>实验计算耗时</small>
          </div>
        </div>
        <div v-if="comparing" class="verdict" :class="changed ? 'red' : 'green'">
          <h4>{{ changed ? '实际数据存在需要关注的分布变化' : '实际数据未超过当前漂移规则' }}</h4>
          <p>
            基准 {{ experiment.datasetName }} → 待检测 {{ experiment.currentDatasetName }}，{{
              changed
            }}
            个字段触发规则，最大 PSI {{ number(observed.maxPsi) }}。该结果不单独证明模型性能下降。
          </p>
        </div>
        <div class="verdict" :class="worst ? 'red' : 'blue'">
          <h4>
            {{
              worst
                ? comparing
                  ? '本次已标注数据的性能差异'
                  : '最需要关注的受控场景'
                : '当前性能结论'
            }}
          </h4>
          <p v-if="worst">
            {{ worst.name }}，F1 下降 {{ percent(worst.f1Drop) }}，最大 PSI
            {{ number(worst.maxPsi) }}。优先关注 {{ worst.field }} 的数据质量与分布变化。
          </p>
          <p v-else-if="comparing && observed.f1Drop !== null">
            待检测 F1 {{ number(observed.evaluation?.metrics?.f1) }}，相对基准变化
            {{ (-observed.f1Drop * 100).toFixed(2) }}pp，未达到设定的 F1 下降标准。
          </p>
          <p v-else>
            {{
              experiment.result?.baseline?.metrics
                ? comparing
                  ? '两份数据需要分别提供有效真实标签，才能确认是否达到设定 F1 下降标准；结果分析中可查看各自的指标。'
                  : '当前场景中没有达到设定 F1 下降标准的结果。可以增加变化强度或扩大场景覆盖后继续实验。'
                : '缺少可用模型或真实标签，无法确认性能变化；请仅将结果用于数据分布分析。'
            }}
          </p>
        </div>
        <div v-if="!comparing && driftOnly.length" class="verdict green">
          <h4>漂移显著不一定意味着性能下降</h4>
          <p>
            {{ driftOnly.length }} 个场景超过 PSI 阈值，但未达到 F1
            影响标准。应结合模型影响校准告警，避免只凭分布变化作性能结论。
          </p>
        </div>
        <p class="small muted mt-16">{{ experiment.result!.assumption }}</p>
      </div>
    </section>
    <div class="grid two">
      <section class="panel">
        <header class="panel-head">
          <h2>监控配置导出</h2>
          <span class="tag green">本地生成</span>
        </header>
        <div class="panel-body">
          <div class="kv">
            <span>模型</span>
            <strong>{{ experiment.modelName }} · {{ experiment.modelVersion || '—' }}</strong>
          </div>
          <div class="kv">
            <span>基准数据</span>
            <strong>{{ experiment.datasetName }}</strong>
          </div>
          <div class="kv">
            <span>{{ comparing ? '待检测数据' : '随机种子' }}</span>
            <strong>
              {{ comparing ? experiment.currentDatasetName : experiment.request.seed }}
            </strong>
          </div>
          <div class="kv">
            <span>监控字段</span>
            <strong>{{ experiment.result!.fields }} 个</strong>
          </div>
          <div class="kv">
            <span>监控窗口</span>
            <strong>{{ store.rules.window }}</strong>
          </div>
          <div class="info-strip mt-16">
            <Icon name="shield" />
            <span>
              配置仅包含模型标识、字段检测方法与规则，不包含原始样本或模型权重。导出采用“监控规则”中当前保存的阈值。
            </span>
          </div>
          <div class="flex mt-16">
            <button
              class="btn primary"
              @click="download(`/api/experiments/${experiment.id}/export?format=${format}`)"
            >
              <Icon name="download" />
              下载 {{ format.toUpperCase() }}
            </button>
            <button class="btn" :disabled="!code" @click="copy">
              <Icon name="copy" />
              复制配置
            </button>
          </div>
          <RouterLink to="/rules" class="link-button mt-16">
            调整监控规则
            <Icon name="arrow" :size="13" />
          </RouterLink>
        </div>
      </section>
      <section class="panel">
        <header class="panel-head">
          <h2>配置预览</h2>
          <div class="pill-row">
            <button
              v-for="f in ['yaml', 'json']"
              :key="f"
              class="pill"
              :class="{ active: format === f }"
              @click="format = f"
            >
              {{ f.toUpperCase() }}
            </button>
          </div>
        </header>
        <div class="panel-body">
          <div v-if="error" class="error-box">{{ error }}</div>
          <pre v-else class="code-block">{{ code || '正在生成配置…' }}</pre>
        </div>
      </section>
    </div>
  </div>
</template>
