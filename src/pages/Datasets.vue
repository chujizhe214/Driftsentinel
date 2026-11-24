<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { Dataset, DatasetRole } from '../types'
import { api, number, percent, date, download } from '../api'
import {
  store,
  dataset,
  datasetRole,
  referenceDatasets,
  actualDatasets,
  selectDataset,
  selectCurrentDataset,
  notify,
} from '../store'
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
  editRole = ref<DatasetRole | ''>(''),
  saving = ref(false)
const roleSelect = ref<HTMLSelectElement>()
const deleteId = ref('')
const importRole = ref<DatasetRole>('reference')
const assigning = ref('')
const filters = [
  { id: 'all', label: '全部数据集', icon: 'layers' },
  { id: 'reference', label: '基准数据集', icon: 'database' },
  { id: 'current', label: '实际数据集', icon: 'clock' },
] as const
const filter = ref<(typeof filters)[number]['id']>('all')
const filterIndex = computed(() => filters.findIndex((item) => item.id === filter.value))
const scopedDatasets = computed(() =>
  filter.value === 'all'
    ? store.datasets
    : filter.value === 'reference'
      ? referenceDatasets.value
      : actualDatasets.value,
)
const query = computed(() => search.value.trim().toLowerCase())
const filtered = computed(() =>
  scopedDatasets.value.filter((item) => item.name.toLowerCase().includes(query.value)),
)
const detail = computed(() => store.datasets.find((d) => d.id === detailId.value))
function openImport() {
  importing.value = true
  importError.value = ''
  importRole.value =
    filter.value === 'all' ? (store.mode === 'compare' ? 'current' : 'reference') : filter.value
}
async function useDataset(item: Dataset) {
  const role = datasetRole(item)
  if (!role) return
  assigning.value = item.id
  try {
    if (item.role !== role) {
      const updated = await api<Dataset>(`/datasets/${item.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ role }),
      })
      store.datasets = store.datasets.map((d) => (d.id === item.id ? updated : d))
    }
    if (role === 'reference') {
      selectDataset(item.id)
      notify('已设为当前基准数据')
    } else {
      store.mode = 'compare'
      selectCurrentDataset(item.id)
      notify('已选为本次待检测数据')
    }
  } catch (e) {
    notify(String(e), true)
  } finally {
    assigning.value = ''
  }
}
watch(detailId, () => {
  const item = detail.value
  editName.value = item?.name || ''
  editLabel.value = item?.label || ''
  editRole.value = item ? (datasetRole(item) ?? '') : ''
})
async function editDatasetRole(id: string) {
  detailId.value = id
  await nextTick()
  roleSelect.value?.focus()
}
async function upload(file?: File) {
  if (!file || uploading.value) return
  uploading.value = true
  importError.value = ''
  const form = new FormData()
  form.append('file', file)
  const role = importRole.value
  try {
    const item = await api<Dataset>(`/datasets?role=${role}`, {
      method: 'POST',
      body: form,
    })
    store.datasets.unshift(item)
    if (role === 'reference') selectDataset(item.id)
    if (filter.value !== 'all') filter.value = role
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
  const original = detail.value
  if (!original || saving.value) return
  const role = editRole.value || undefined
  const roleChanged = role !== undefined && role !== datasetRole(original)
  saving.value = true
  try {
    const item = await api<Dataset>(`/datasets/${original.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ name: editName.value, label: editLabel.value || null, role }),
    })
    store.datasets = store.datasets.map((d) => (d.id === item.id ? item : d))
    if (roleChanged && role === 'reference' && store.currentDatasetId === item.id) {
      selectCurrentDataset('')
    }
    if (dataset.value?.id === item.id) {
      if (roleChanged && role === 'current') selectDataset('')
      else if (original.label !== item.label) selectDataset(item.id)
    }
    if (roleChanged && filter.value !== 'all') filter.value = role
    notify(roleChanged ? '数据集用途已修改' : '数据集设置已保存')
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
    if (store.activeDatasetId === deleteId.value)
      selectDataset(referenceDatasets.value[0]?.id || '')
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
  <div
    class="segmented-control dataset-filters"
    :style="{ '--segment-count': filters.length, '--selected-segment': filterIndex }"
    role="group"
    aria-label="数据集分类"
  >
    <button
      v-for="item in filters"
      :key="item.id"
      type="button"
      :aria-pressed="filter === item.id"
      @click="filter = item.id"
    >
      <Icon :name="item.icon" :size="14" />
      {{ item.label }}
    </button>
  </div>
  <div class="toolbar dataset-toolbar">
    <div class="form-field search-field">
      <div class="input-icon">
        <Icon name="search" :size="14" />
        <input v-model="search" placeholder="搜索数据集…" aria-label="搜索数据集" />
      </div>
    </div>
    <span class="small muted" aria-live="polite">{{ filtered.length }} 个数据集</span>
  </div>
  <div v-if="!filtered.length" class="info-strip mb-16">
    {{ query ? '当前分类下没有匹配的数据集。' : '当前分类暂无数据集。' }}
  </div>
  <div class="grid dataset-grid">
    <article
      v-for="d in filtered"
      :key="d.id"
      class="dataset-card"
      :class="{ active: d.id === store.activeDatasetId && datasetRole(d) === 'reference' }"
      @click="detailId = d.id"
    >
      <div class="flex between">
        <div class="file-tile"><Icon name="database" :size="19" /></div>
        <div class="flex dataset-card-status">
          <span
            v-if="d.id === store.activeDatasetId && datasetRole(d) === 'reference'"
            class="tag green"
          >
            <Icon name="check" :size="10" />
            当前基准
          </span>
          <span
            v-else-if="d.id === store.currentDatasetId && datasetRole(d) === 'current'"
            class="tag blue"
          >
            当前待检测
          </span>
          <span
            v-else-if="d.id === 'bank-reference' && datasetRole(d) === 'reference'"
            class="tag gray"
          >
            公开示例
          </span>
          <span v-else-if="datasetRole(d) === 'reference'" class="tag green">基准数据</span>
          <span v-else-if="datasetRole(d) === 'current'" class="tag blue">实际数据</span>
          <span v-else class="tag gray">未分类</span>
          <button
            v-if="d.id !== 'bank-reference'"
            type="button"
            class="icon-btn"
            :disabled="assigning === d.id"
            title="修改用途"
            :aria-label="'修改用途：' + d.name"
            @click.stop="editDatasetRole(d.id)"
          >
            <Icon name="pencil" :size="14" />
          </button>
          <button
            v-if="d.id !== 'bank-reference'"
            type="button"
            class="icon-btn"
            :disabled="assigning === d.id"
            :title="'删除 ' + d.name"
            :aria-label="'删除 ' + d.name"
            @click.stop="deleteId = d.id"
          >
            <Icon name="trash" :size="14" />
          </button>
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
          v-if="datasetRole(d) === 'reference'"
          class="btn sm"
          :disabled="!!assigning || d.id === store.activeDatasetId"
          @click.stop="useDataset(d)"
        >
          用作基准
        </button>
        <button
          v-else-if="datasetRole(d) === 'current'"
          class="btn sm"
          :disabled="!!assigning || d.id === store.currentDatasetId"
          @click.stop="useDataset(d)"
        >
          用作待检测
        </button>
      </div>
    </article>
    <button class="upload-zone dataset-upload" @click="openImport">
      <Icon name="plus" :size="26" />
      <h3>
        {{
          filter === 'reference'
            ? '添加基准数据'
            : filter === 'current'
              ? '添加实际数据'
              : '添加数据集'
        }}
      </h3>
      <p>CSV · 最多 50,000 行 · 30 MB</p>
    </button>
  </div>
  <section v-if="filtered.some((d) => d.id === 'bank-reference')" class="panel mt-20">
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
      <label for="import-role">数据集用途</label>
      <select id="import-role" v-model="importRole" :disabled="uploading">
        <option value="reference">基准数据</option>
        <option value="current">实际数据</option>
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
  <Modal
    v-if="detail"
    :title="detail.name + ' · 数据画像'"
    wide
    @close="!saving && (detailId = '')"
  >
    <div class="grid four mb-20">
      <div class="report-stat">
        <strong>{{ detail.profile.rows.toLocaleString() }}</strong>
        <small>样本数</small>
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
    <div class="grid three mb-20 dataset-settings">
      <div class="form-field">
        <label for="dataset-role">数据集用途</label>
        <select
          id="dataset-role"
          ref="roleSelect"
          v-model="editRole"
          :disabled="saving || detail.id === 'bank-reference'"
        >
          <option value="" disabled>未分类</option>
          <option value="reference">基准数据</option>
          <option value="current">实际数据</option>
        </select>
      </div>
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

<style scoped>
.dataset-filters {
  margin-bottom: 12px;
}
.dataset-filters > button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  white-space: nowrap;
}
.dataset-grid {
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 275px), 1fr));
  gap: 14px;
}
.dataset-card {
  min-width: 0;
  padding: 15px;
}
.dataset-card-status {
  gap: 5px;
}
.dataset-card h3 {
  margin-top: 11px;
  overflow-wrap: anywhere;
}
.dataset-stats {
  gap: 18px;
  margin-top: 12px;
  padding-top: 10px;
}
.dataset-card .card-actions {
  margin-top: 11px;
  padding-top: 10px;
}
.dataset-upload {
  min-height: 175px;
  padding-block: 20px;
}
@media (max-width: 450px) {
  .dataset-settings {
    grid-template-columns: 1fr;
  }
  .dataset-filters {
    width: 100%;
  }
  .dataset-filters > button {
    gap: 4px;
    padding-inline: 4px;
  }
}
</style>
