<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { api, post, date, download } from '../api'
import { store, dataset, notify } from '../store'
import type { Model } from '../types'
import Icon from '../components/Icon.vue'
import Modal from '../components/Modal.vue'
const adding = ref(false),
  saving = ref(false),
  error = ref(''),
  validating = ref(''),
  deleting = ref('')
const choosingTemplate = ref(false)
const supportsProbability = ref(false)
function downloadTemplate() {
  download(`/api/adapter-template?probability=${supportsProbability.value}`)
  choosingTemplate.value = false
}
const form = reactive({
  name: '',
  version: '1.0.0',
  path: '',
  positive_class: '1',
  negative_class: '0',
  consent: false,
})
const canSave = computed(
  () =>
    form.name.trim() &&
    form.path.trim() &&
    form.version.trim() &&
    form.consent &&
    form.positive_class !== form.negative_class,
)
function openAdd() {
  adding.value = true
  error.value = ''
}
function useModel(id: string) {
  store.activeModelId = id
  notify('已选择模型，请返回工作台运行实验')
}
async function add() {
  saving.value = true
  error.value = ''
  try {
    const item = await post<Model>('/models', form)
    store.models.unshift(item)
    store.activeModelId = item.id
    adding.value = false
    notify('适配器已登记，请用基准数据校验输出')
    form.name = ''
    form.path = ''
    form.consent = false
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    saving.value = false
  }
}
async function validate(model: Model) {
  validating.value = model.id
  try {
    const item = await post<Model>(`/models/${model.id}/validate`, {
      dataset_id: store.activeDatasetId,
    })
    store.models = store.models.map((m) => (m.id === item.id ? item : m))
    notify('模型校验通过：输出形状、类别和概率均有效')
  } catch (e) {
    notify(e instanceof Error ? e.message : String(e), true)
    store.models = await api<Model[]>('/models')
  } finally {
    validating.value = ''
  }
}
async function remove() {
  try {
    await api(`/models/${deleting.value}`, { method: 'DELETE' })
    store.models = store.models.filter((m) => m.id !== deleting.value)
    if (store.activeModelId === deleting.value) store.activeModelId = null
    deleting.value = ''
    notify('模型登记已删除，本地 Python 文件保留')
  } catch (e) {
    notify(String(e), true)
  }
}
</script>
<template>
  <div class="page-header">
    <div>
      <p class="eyebrow">MODEL REGISTRY</p>
      <h1>模型</h1>
      <p>使用内置分类模型，或接入你自己的本地 Python 预测适配器。</p>
    </div>
    <div class="header-actions">
      <button class="btn" @click="choosingTemplate = true">
        <Icon name="download" :size="14" />
        适配器模板
      </button>
      <button class="btn primary" @click="openAdd">
        <Icon name="plus" :size="14" />
        接入模型
      </button>
    </div>
  </div>
  <div class="info-strip mb-20">
    <Icon name="info" />
    <span>
      第一版支持表格二分类。
      <code>predict(X)</code>
      返回一维类别数组；可选
      <code>predict_proba(X)</code>
      返回正类概率或两列概率（第二列为正类）。当前校验数据为
      <strong>{{ dataset?.name }}</strong>
      。
    </span>
  </div>
  <div class="grid two">
    <section v-for="m in store.models" :key="m.id" class="panel">
      <div class="panel-body">
        <div class="flex between">
          <div class="model-header">
            <div class="model-symbol">
              <Icon :name="m.kind === 'builtin' ? 'layers' : 'code'" :size="23" />
            </div>
            <div>
              <h3>{{ m.name }}</h3>
              <p>{{ m.algorithm }} · v{{ m.version }}</p>
            </div>
          </div>
          <span v-if="store.activeModelId === m.id" class="tag green">当前模型</span>
        </div>
        <div class="mt-20">
          <div class="kv">
            <span>模型来源</span>
            <strong>{{ m.kind === 'builtin' ? '内置可复现模型' : '本地 Python 适配器' }}</strong>
          </div>
          <div class="kv">
            <span>正类 / 负类</span>
            <strong class="mono">{{ m.positiveClass }} / {{ m.negativeClass }}</strong>
          </div>
          <div class="kv">
            <span>预测概率</span>
            <span class="tag" :class="m.hasProba ? 'green' : 'gray'">
              {{
                m.hasProba === null
                  ? '待校验'
                  : m.hasProba
                    ? 'predict_proba 可用'
                    : '未提供 · AUC 不可用'
              }}
            </span>
          </div>
          <div class="kv">
            <span>输出校验</span>
            <span class="tag" :class="m.status">
              {{ { ready: '可用', unvalidated: '待校验', error: '校验失败' }[m.status] }}
            </span>
          </div>
          <div v-if="m.trainRows" class="kv">
            <span>训练样本 / 随机种子</span>
            <strong>{{ m.trainRows.toLocaleString() }} / 42</strong>
          </div>
          <div v-if="m.lastValidation" class="kv">
            <span>最近校验</span>
            <strong>{{ date(m.lastValidation.at) }}</strong>
          </div>
        </div>
        <div v-if="m.lastValidation?.error" class="error-box">{{ m.lastValidation.error }}</div>
        <p
          v-if="m.kind === 'adapter'"
          class="small muted mono mt-12"
          style="overflow-wrap: anywhere"
        >
          {{ m.path }}
        </p>
        <div class="card-actions">
          <button class="btn sm" :disabled="!!validating" @click="validate(m)">
            <Icon
              :name="validating === m.id ? 'loader' : 'checks'"
              :class="{ spin: validating === m.id }"
              :size="13"
            />
            {{ validating === m.id ? '校验中…' : '校验输出' }}
          </button>
          <button class="btn sm" :disabled="store.activeModelId === m.id" @click="useModel(m.id)">
            用于实验
          </button>
          <button
            v-if="m.kind === 'adapter'"
            class="icon-btn"
            style="margin-left: auto"
            :aria-label="'删除 ' + m.name"
            @click="deleting = m.id"
          >
            <Icon name="trash" :size="14" />
          </button>
        </div>
      </div>
    </section>
  </div>
  <section class="panel mt-20">
    <header class="panel-head">
      <h2>准备一个模型适配器</h2>
      <span class="tag gray">本地执行</span>
    </header>
    <div class="panel-body grid two">
      <div>
        <ol class="adapter-steps">
          <li>下载模板时选择模型是否支持概率预测，将文件放到你的模型文件旁。</li>
          <li>
            在适配器中加载模型，提供
            <code>predict(X)</code>
            。
          </li>
          <li>
            使用
            <code>Path(__file__).parent</code>
            解析模型路径。
          </li>
          <li>填写 Python 文件绝对路径，并用基准数据校验输出。</li>
        </ol>
        <p class="small muted mt-16">
          内置模型使用在独立训练集上训练的逻辑回归，预处理与权重固定，实验中不重新训练。
        </p>
        <p class="small muted mt-12">
          模板以 joblib / scikit-learn
          为例。其他框架需修改加载和预测代码；有概率接口时选择“支持概率预测”，下载文件会额外包含
          predict_proba(X)。
        </p>
      </div>
      <pre class="code-block">
from pathlib import Path
from joblib import load

model = load(Path(__file__).parent / "model.joblib")

def predict(X):
    return model.predict(X)</pre>
    </div>
  </section>
  <Modal v-if="choosingTemplate" title="下载适配器模板" @close="choosingTemplate = false">
    <fieldset class="template-options">
      <legend>你的模型是否支持概率预测？</legend>
      <label class="template-option" :class="{ selected: !supportsProbability }">
        <input
          v-model="supportsProbability"
          type="radio"
          name="template-probability"
          :value="false"
        />
        <span>
          <strong>仅类别预测</strong>
          <small>
            模型只输出类别，或暂不需要概率。模板只包含 predict(X)，不调用概率接口；AUC / ROC
            和概率分布不可用。
          </small>
          <code>model_adapter.py</code>
        </span>
      </label>
      <label class="template-option" :class="{ selected: supportsProbability }">
        <input
          v-model="supportsProbability"
          type="radio"
          name="template-probability"
          :value="true"
        />
        <span>
          <strong>支持概率预测</strong>
          <small>
            模型可输出概率。模板包含 predict(X) 和
            predict_proba(X)，可分析概率分布；有有效真实标签时可计算 AUC / ROC。
          </small>
          <code>model_adapter_proba.py</code>
        </span>
      </label>
    </fieldset>
    <div class="info-strip mt-16">
      <Icon name="info" :size="14" />
      <span>
        请按模型实际能力选择。模板不能给模型增加概率预测能力，下载后仍需配置模型文件、输入字段和训练时的预处理。
      </span>
    </div>
    <template #footer>
      <button class="btn" @click="choosingTemplate = false">取消</button>
      <button class="btn primary" @click="downloadTemplate">
        <Icon name="download" :size="14" />
        下载模板
      </button>
    </template>
  </Modal>
  <Modal v-if="adding" title="接入本地模型" @close="!saving && (adding = false)">
    <form id="adapter-form" @submit.prevent="add">
      <div class="grid two">
        <div class="form-field">
          <label for="adapter-name">模型名称</label>
          <input
            id="adapter-name"
            v-model="form.name"
            required
            maxlength="80"
            placeholder="例如 CustomerChurn"
          />
        </div>
        <div class="form-field">
          <label for="adapter-version">模型版本</label>
          <input id="adapter-version" v-model="form.version" required maxlength="30" />
        </div>
        <div class="form-field span-all">
          <label for="adapter-path">适配器绝对路径（运行服务的机器）</label>
          <input
            id="adapter-path"
            v-model="form.path"
            required
            placeholder="C:\models\model_adapter.py"
          />
          <small>不会上传模型权重；服务会从此路径加载你的 Python 适配器。</small>
        </div>
        <div class="form-field">
          <label for="positive-class">正类值</label>
          <input
            id="positive-class"
            v-model="form.positive_class"
            required
            placeholder="1 或 yes"
          />
        </div>
        <div class="form-field">
          <label for="negative-class">负类值</label>
          <input id="negative-class" v-model="form.negative_class" required placeholder="0 或 no" />
        </div>
      </div>
      <label class="checkbox-row mt-20">
        <input v-model="form.consent" type="checkbox" />
        <span>我确认这是自己信任的本地 Python 代码，允许工作台在校验和实验时执行它。</span>
      </label>
      <div v-if="error" class="error-box" role="alert">{{ error }}</div>
    </form>
    <template #footer>
      <button class="btn" :disabled="saving" @click="adding = false">取消</button>
      <button class="btn primary" form="adapter-form" type="submit" :disabled="!canSave || saving">
        <Icon :name="saving ? 'loader' : 'plus'" :class="{ spin: saving }" :size="13" />
        保存适配器
      </button>
    </template>
  </Modal>
  <Modal v-if="deleting" title="移除模型登记" @close="deleting = ''">
    <p class="muted">只删除工作台中的模型登记，适配器和模型文件会保留。</p>
    <template #footer>
      <button class="btn" @click="deleting = ''">取消</button>
      <button class="btn danger" @click="remove">确认移除</button>
    </template>
  </Modal>
</template>

<style scoped>
.template-options {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
.template-options legend {
  margin-bottom: 14px;
  font-weight: 600;
}
.template-option {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  margin-top: 12px;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: var(--raised);
  cursor: pointer;
}
.template-option.selected {
  border-color: var(--primary);
  background: var(--primary-soft);
}
.template-option input {
  margin-top: 4px;
  accent-color: var(--primary);
  flex-shrink: 0;
}
.template-option span {
  min-width: 0;
}
.template-option strong,
.template-option small,
.template-option code {
  display: block;
}
.template-option small {
  margin: 7px 0;
  color: var(--muted);
  line-height: 1.7;
}
.template-option code {
  overflow-wrap: anywhere;
  font-size: 11px;
}
</style>
