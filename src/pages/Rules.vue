<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { store, saveRules, notify } from '../store'
import { download, number, percent } from '../api'
import Icon from '../components/Icon.vue'
const draft = reactive({ ...store.rules })
watch(
  () => store.rules,
  (r) => Object.assign(draft, r),
  { deep: true },
)
const busy = ref(false),
  error = ref('')
const dirty = computed(() => JSON.stringify(draft) !== JSON.stringify(store.rules))
const fields = [
  {
    key: 'warning' as const,
    label: 'PSI 预警阈值',
    desc: '字段 PSI 达到此值时标记“关注”。',
    min: 0.01,
    max: 5,
    step: 0.01,
  },
  {
    key: 'critical' as const,
    label: 'PSI 严重阈值',
    desc: '应高于预警阈值，用于标记较大分布变化。',
    min: 0.02,
    max: 10,
    step: 0.01,
  },
  {
    key: 'pvalue' as const,
    label: '统计检验 p 值',
    desc: 'KS 和卡方检验的显著性水平。',
    min: 0.001,
    max: 0.5,
    step: 0.001,
  },
  {
    key: 'missing' as const,
    label: '缺失率告警阈值',
    desc: '字段缺失比例上限，0.10 表示 10%。',
    min: 0,
    max: 1,
    step: 0.01,
  },
  {
    key: 'prediction_change' as const,
    label: '预测正类比例变化',
    desc: '正类比例绝对变化上限，0.15 表示 15pp。',
    min: 0,
    max: 1,
    step: 0.01,
  },
  {
    key: 'impact' as const,
    label: 'F1 下降影响标准',
    desc: 'F1 升降达到此值都提示。下降达到此值才触发告警，并作为阈值校准的依据。',
    min: 0.001,
    max: 1,
    step: 0.01,
  },
]
async function save() {
  busy.value = true
  error.value = ''
  try {
    await saveRules({ ...draft })
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    notify(error.value, true)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <div class="page-header">
    <div>
      <p class="eyebrow">MONITORING CONFIGURATION</p>
      <h1>监控规则</h1>
      <p>保存离线实验的告警规则，生成后续线上监控可用的配置。</p>
    </div>
    <div class="header-actions">
      <button
        class="btn"
        :disabled="!store.current?.result"
        @click="
          store.current && download(`/api/experiments/${store.current.id}/export?format=yaml`)
        "
      >
        <Icon name="download" :size="14" />
        导出 YAML
      </button>
      <button class="btn primary" :disabled="busy || !dirty" @click="save">
        <Icon :name="busy ? 'loader' : 'check'" :class="{ spin: busy }" :size="14" />
        保存规则
      </button>
    </div>
  </div>
  <div class="info-strip blue mb-20">
    <Icon name="info" />
    <span>
      此处配置的是离线压力测试与未来监控规则，第一版不持续接收生产流量。保存后的规则用于新实验及配置导出，历史实验仍保留原有的检测结论。
    </span>
  </div>
  <div v-if="error" class="error-box mb-20" role="alert">{{ error }}</div>
  <div class="grid two">
    <section class="panel">
      <header class="panel-head">
        <h2>检测与告警阈值</h2>
        <span class="tag" :class="dirty ? 'amber' : 'green'">
          {{ dirty ? '有未保存修改' : '已保存' }}
        </span>
      </header>
      <form class="panel-body" @submit.prevent="save">
        <div class="grid two">
          <div v-for="f in fields" :key="f.key" class="form-field">
            <label :for="'rule-' + f.key">{{ f.label }}</label>
            <input
              :id="'rule-' + f.key"
              v-model.number="draft[f.key]"
              type="number"
              :min="f.min"
              :max="f.max"
              :step="f.step"
              required
            />
            <small>{{ f.desc }}</small>
          </div>
        </div>
        <div class="grid two mt-20">
          <div class="form-field">
            <label for="window">监控窗口</label>
            <select id="window" v-model="draft.window">
              <option value="15m">15 分钟</option>
              <option value="1h">1 小时</option>
              <option value="6h">6 小时</option>
              <option value="24h">24 小时</option>
            </select>
          </div>
          <div class="form-field">
            <label for="minimum-samples">最小窗口样本数</label>
            <input
              id="minimum-samples"
              v-model.number="draft.min_samples"
              type="number"
              min="10"
              max="100000"
              required
            />
          </div>
        </div>
        <button class="btn primary full mt-20" type="submit" :disabled="busy || !dirty">
          保存监控规则
        </button>
      </form>
    </section>
    <div class="stack">
      <section class="panel">
        <header class="panel-head">
          <h2>当前生效规则</h2>
          <span class="tag gray">全部字段</span>
        </header>
        <div class="panel-body">
          <div class="kv">
            <span>PSI 预警 / 严重</span>
            <strong class="mono">
              {{ number(store.rules.warning, 2) }} / {{ number(store.rules.critical, 2) }}
            </strong>
          </div>
          <div class="kv">
            <span>KS / 卡方</span>
            <strong class="mono">p &lt; {{ store.rules.pvalue }}</strong>
          </div>
          <div class="kv">
            <span>缺失率上限</span>
            <strong>{{ percent(store.rules.missing) }}</strong>
          </div>
          <div class="kv">
            <span>预测正类比例变化</span>
            <strong>{{ (store.rules.prediction_change * 100).toFixed(1) }}pp</strong>
          </div>
          <div class="kv">
            <span>F1 影响标准</span>
            <strong>{{ (store.rules.impact * 100).toFixed(1) }}pp</strong>
          </div>
          <div class="kv">
            <span>监控窗口 / 最小样本</span>
            <strong>{{ store.rules.window }} / {{ store.rules.min_samples }}</strong>
          </div>
        </div>
      </section>
      <section class="panel">
        <header class="panel-head"><h2>让阈值有实验依据</h2></header>
        <div class="panel-body">
          <p class="small muted">
            固定阈值只是起点。在基准数据上运行多组压力场景后，使用阈值校准比较误报、漏报与召回率，再采用合适的推荐值。
          </p>
          <RouterLink :to="{ path: '/', query: { tab: 'calibration' } }" class="btn subtle mt-16">
            <Icon name="target" :size="14" />
            前往阈值校准
            <Icon name="arrow" :size="13" />
          </RouterLink>
        </div>
      </section>
    </div>
  </div>
</template>
