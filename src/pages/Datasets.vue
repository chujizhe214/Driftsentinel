<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Dataset } from '../types'
import { api, number, percent, date, download } from '../api'
import { store, dataset, selectDataset, selectCurrentDataset, notify } from '../store'
import Icon from '../components/Icon.vue'
import Modal from '../components/Modal.vue'
const search = ref(''),
  uploading = ref(false),
  drag = ref(false),
  importError = ref(''),
  importing = ref(false)
const fileInput = ref<HTMLInputElement>()
const detailId = ref(''),
  editName = ref(''),
  editLabel = ref(''),
  saving = ref(false)
const deleteId = ref('')
const importRole = ref<'reference' | 'current'>('reference')
const filtered = computed(() =>
  store.datasets.filter((d) => d.name.toLowerCase().includes(search.value.toLowerCase())),
)
const detail = computed(() => store.datasets.find((d) => d.id === detailId.value))
function openImport() {
  importing.value = true
  importError.value = ''
  importRole.value = store.mode === 'compare' ? 'current' : 'reference'
}
function useDataset(id: string) {
  selectDataset(id)
  notify('已设为当前基准数据')
}
function useCurrentDataset(id: string) {
  store.mode = 'compare'
  selectCurrentDataset(id)
  notify('已设为待检测数据，基准保持不变')
}
watch(detailId, () => {
  editName.value = detail.value?.name || ''
  editLabel.value = detail.value?.label || ''
})
async function upload(file?: File) {
  if (!file) return
  uploading.value = true
  importError.value = ''
  const form = new FormData()
  form.append('file', file)
  try {
    const item = await api<Dataset>('/datasets', { method: 'POST', body: form })
    store.datasets.unshift(item)
    if (importRole.value === 'current') {
      store.mode = 'compare'
      selectCurrentDataset(item.id)
    } else selectDataset(item.id)
    importing.value = false
    detailId.value = item.id
    notify(`已导入 ${item.profile.rows.toLocaleString()} 行数据`)
  } catch (e) {
    importError.value = e instanceof Error ? e.message : String(e)
  } finally {
    uploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}
function drop(event: DragEvent) {
  drag.value = false
  upload(event.dataTransfer?.files[0])
}
async function save() {
  if (!detail.value) return
  saving.value = true
  try {
    const item = await api<Dataset>(`/datasets/${detail.value.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ name: editName.value, label: editLabel.value || null }),
    })
    store.datasets = store.datasets.map((d) => (d.id === item.id ? item : d))
    if (dataset.value?.id === item.id) selectDataset(item.id)
    notify('数据集设置已保存')
    detailId.value = ''
  } catch (e) {
    notify(String(e), true)
  } finally {
    saving.value = false
  }
}
async function remove() {
  try {
    await api(`/datasets/${deleteId.value}`, { method: 'DELETE' })
    store.datasets = store.datasets.filter((d) => d.id !== deleteId.value)
    if (store.activeDatasetId === deleteId.value) selectDataset('bank-reference')
    if (store.currentDatasetId === deleteId.value) selectCurrentDataset('')
    deleteId.value = ''
    notify('数据集已删除，历史实验快照仍可查看')
  } catch (e) {
    notify(String(e), true)
  }
}
</script>
<template>
  <div class="page-header">
    <div>
      <p class="eyebrow">REFERENCE DATA</p>
      <h1>数据集</h1>
      <p>管理固定基准与实际采集数据，查看字段质量，并为每次检测选择数据。</p>
    </div>
    <button class="btn primary" @click="openImport">
      <Icon name="upload" :size="14" />
      导入 CSV
    </button>
  </div>
  <div class="toolbar">
    <div class="form-field search-field">
      <div class="input-icon">
        <Icon name="search" :size="14" />
        <input v-model="search" placeholder="搜索数据集…" aria-label="搜索数据集" />
      </div>
    </div>
    <span class="small muted">{{ store.datasets.length }} 个数据集 · 全部保存在本机</span>
  </div>
  <div class="grid three">
    <article
      v-for="d in filtered"
      :key="d.id"
      class="dataset-card"
      :class="{ active: d.id === store.activeDatasetId }"
      @click="detailId = d.id"
    >
      <div class="flex between">
        <div class="file-tile"><Icon name="database" :size="19" /></div>
        <div class="flex">
          <span v-if="d.id === store.activeDatasetId" class="tag green">
            <Icon name="check" :size="10" />
            当前基准
          </span>
          <span v-else-if="d.id === store.currentDatasetId" class="tag blue">当前待检测</span>
          <span v-else class="tag gray">
            {{ d.source === '本地导入' ? '本地导入' : '公开示例' }}
          </span>
        </div>
      </div>
      <h3>{{ d.name }}</h3>
      <p>{{ d.source }} · {{ date(d.createdAt).split(' ')[0] }}</p>
      <div class="dataset-stats">
        <div>
          <strong>{{ d.profile.rows.toLocaleString() }}</strong>
          <span>样本</span>
        </div>
        <div>
          <strong>{{ d.profile.columns }}</strong>
          <span>字段</span>
        </div>
        <div>
          <strong>{{ percent(d.profile.missing) }}</strong>
          <span>缺失率</span>
        </div>
      </div>
      <div class="card-actions">
        <button class="btn sm" @click.stop="detailId = d.id">
          <Icon name="eye" :size="12" />
          数据画像
        </button>
        <button
          class="btn sm"
          :disabled="d.id === store.activeDatasetId"
          @click.stop="useDataset(d.id)"
        >
          设为基准
        </button>
        <button
          class="btn sm"
          :disabled="d.id === store.activeDatasetId || d.id === store.currentDatasetId"
          @click.stop="useCurrentDataset(d.id)"
        >
          设为待检测
        </button>
        <button
          v-if="d.id !== 'bank-reference'"
          class="icon-btn"
          style="margin-left: auto"
          :aria-label="'删除 ' + d.name"
          @click.stop="deleteId = d.id"
        >
          <Icon name="trash" :size="14" />
        </button>
      </div>
    </article>
    <button class="upload-zone" style="min-height: 240px" @click="openImport">
      <Icon name="plus" :size="26" />
      <h3>添加基准或采集数据</h3>
      <p>CSV · 最多 50,000 行 · 30 MB</p>
    </button>
  </div>
  <div v-if="!filtered.length && search" class="info-strip mt-20">
    没有找到“{{ search }}”相关数据集，请调整搜索条件。
  </div>
  <section class="panel mt-20">
    <header class="panel-head">
      <h2>
        <Icon name="book" :size="14" />
        内置数据来源
      </h2>
      <span class="tag gray">CC BY 4.0</span>
    </header>
    <div class="panel-body">
      <p class="small muted">
        Bank Marketing 是 UCI 公开的银行营销二分类数据集。示例使用 4,521 条样本中的独立 30%
        留出集作为基准，另外 70% 用于训练模型，随机种子为 42。
      </p>
      <a
        class="link-button mt-12"
        href="https://archive.ics.uci.edu/dataset/222/bank+marketing"
        target="_blank"
        rel="noreferrer"
      >
        UCI 数据集与许可证
        <Icon name="external" :size="12" />
      </a>
    </div>
  </section>
  <Modal v-if="importing" title="导入数据" @close="!uploading && (importing = false)">
    <div class="form-field mb-20">
      <label for="import-role">导入后用途</label>
      <select id="import-role" v-model="importRole" :disabled="uploading">
        <option value="reference">设为基准数据</option>
        <option value="current">设为待检测数据（保留当前基准）</option>
      </select>
    </div>
    <input
      ref="fileInput"
      type="file"
      accept=".csv,text/csv"
      class="screen-reader"
      @change="upload(($event.target as HTMLInputElement).files?.[0])"
    />
    <div
      class="upload-zone"
      :class="{ drag }"
      role="button"
      tabindex="0"
      @click="!uploading && fileInput?.click()"
      @keydown.enter="fileInput?.click()"
      @dragover.prevent="drag = true"
      @dragleave.prevent="drag = false"
      @drop.prevent="drop"
    >
      <Icon :name="uploading ? 'loader' : 'upload'" :class="{ spin: uploading }" :size="29" />
      <h3>{{ uploading ? '正在读取与建立数据画像…' : '点击选择，或将 CSV 拖到这里' }}</h3>
      <p>支持 UTF-8 / GB18030 编码，逗号、分号或制表符分隔</p>
    </div>
    <div v-if="importError" class="error-box" role="alert">{{ importError }}</div>
    <div class="info-strip mt-16">
      <Icon name="info" />
      <span>
        需要表头及 30–50,000 行数据，最多 200 列、30
        MB。导入后可选择标签列；没有标签时仍可分析漂移。
      </span>
    </div>
    <template #footer>
      <button class="btn" :disabled="uploading" @click="importing = false">关闭</button>
    </template>
  </Modal>
  <Modal v-if="detail" :title="detail.name + ' · 数据画像'" wide @close="detailId = ''">
    <div class="grid four mb-20">
      <div class="report-stat">
        <strong>{{ detail.profile.rows.toLocaleString() }}</strong>
        <small>基准样本</small>
      </div>
      <div class="report-stat">
        <strong>{{ detail.profile.columns }}</strong>
        <small>字段</small>
      </div>
      <div class="report-stat">
        <strong>{{ percent(detail.profile.missing) }}</strong>
        <small>整体缺失率</small>
      </div>
      <div class="report-stat">
        <strong>{{ detail.profile.duplicates }}</strong>
        <small>重复行</small>
      </div>
    </div>
    <div class="grid two mb-20">
      <div class="form-field">
        <label for="dataset-name">数据集名称</label>
        <input id="dataset-name" v-model="editName" maxlength="100" />
      </div>
      <div class="form-field">
        <label for="dataset-label">真实标签列</label>
        <select id="dataset-label" v-model="editLabel">
          <option value="">不使用标签</option>
          <option v-for="f in detail.profile.fields" :key="f.name" :value="f.name">
            {{ f.name }}{{ detail.profile.labelCandidates.includes(f.name) ? ' · 二分类候选' : '' }}
          </option>
        </select>
      </div>
    </div>
    <h3 class="mb-16">字段统计</h3>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>字段</th>
            <th>类型</th>
            <th class="num">唯一值</th>
            <th class="num">缺失率</th>
            <th class="num">均值 / 主类别</th>
            <th class="num">标准差 / 类别占比</th>
            <th class="num">最小值 / 最大值</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in detail.profile.fields" :key="f.name">
            <td>
              <strong>{{ f.name }}</strong>
              <span v-if="f.name === editLabel" class="tag blue" style="margin-left: 7px">
                标签
              </span>
            </td>
            <td>
              <span class="tag" :class="f.type === 'numeric' ? 'blue' : 'gray'">
                {{ f.type === 'numeric' ? '数值' : '类别' }}
              </span>
            </td>
            <td class="num">{{ f.unique }}</td>
            <td class="num">{{ percent(f.missing) }}</td>
            <td class="num">
              {{ f.type === 'numeric' ? number(f.mean, 2) : f.categories?.[0]?.name }}
            </td>
            <td class="num">
              {{ f.type === 'numeric' ? number(f.std, 2) : percent(f.categories?.[0]?.share) }}
            </td>
            <td class="num">
              {{ f.type === 'numeric' ? number(f.min, 1) + ' / ' + number(f.max, 1) : '—' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <h3 class="mt-20 mb-16">数据预览 · 前 8 行</h3>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th v-for="f in detail.profile.fields" :key="f.name">{{ f.name }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in detail.profile.preview" :key="i">
            <td v-for="f in detail.profile.fields" :key="f.name">{{ row[f.name] ?? '∅' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <template #footer>
      <button class="btn" @click="download(`/api/datasets/${detail.id}/csv`)">
        <Icon name="download" :size="13" />
        下载 CSV
      </button>
      <button class="btn primary" :disabled="saving || !editName.trim()" @click="save">
        <Icon name="check" :size="13" />
        保存设置
      </button>
    </template>
  </Modal>
  <Modal v-if="deleteId" title="删除数据集" @close="deleteId = ''">
    <p class="muted">删除此数据集及本地原始文件？已经完成的实验结果会保留。</p>
    <template #footer>
      <button class="btn" @click="deleteId = ''">取消</button>
      <button class="btn danger" @click="remove">确认删除</button>
    </template>
  </Modal>
</template>
