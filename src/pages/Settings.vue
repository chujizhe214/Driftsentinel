<script setup lang="ts">
import { ref } from 'vue'
import { store, loadDemo, notify } from '../store'
import Icon from '../components/Icon.vue'
const resetting = ref(false)
function reset() {
  loadDemo()
  resetting.value = false
  notify('工作台参数已恢复，已保存的数据与实验仍然保留')
}
</script>
<template>
  <div class="page-header">
    <div>
      <p class="eyebrow">LOCAL WORKSPACE</p>
      <h1>设置</h1>
      <p>查看本地运行环境、数据存储和第一版能力范围。</p>
    </div>
  </div>
  <div class="grid two">
    <section class="panel">
      <header class="panel-head">
        <h2>工作区信息</h2>
        <span class="tag green">运行正常</span>
      </header>
      <div class="panel-body settings-list">
        <div class="settings-row">
          <div>
            <h3>应用版本</h3>
            <p>DriftSentinel · 模型漂移压力测试与监控配置工作台</p>
          </div>
          <span class="tag gray">{{ store.health?.version }}</span>
        </div>
        <div class="settings-row">
          <div>
            <h3>数据存储</h3>
            <p>CSV 基准快照、SQLite 实验与配置</p>
            <p>
              <code>{{ store.health?.storage }}</code>
            </p>
          </div>
          <Icon name="drive" class="muted" />
        </div>
        <div class="settings-row">
          <div>
            <h3>计算环境</h3>
            <p>本地 Python 服务 · Pandas / SciPy / scikit-learn</p>
          </div>
          <span class="tag green">Local</span>
        </div>
        <div class="settings-row">
          <div>
            <h3>接口文档</h3>
            <p>查看业务 API 的数据结构与调用方式</p>
          </div>
          <a href="/docs" target="_blank" class="btn sm" rel="noreferrer">
            API 文档
            <Icon name="external" :size="12" />
          </a>
        </div>
        <div class="settings-row">
          <div>
            <h3>恢复示例参数</h3>
            <p>重置当前数据、模型和场景选择，已保存实验保留。</p>
          </div>
          <button v-if="!resetting" class="btn sm" @click="resetting = true">恢复默认</button>
          <div v-else class="flex">
            <button class="btn sm" @click="resetting = false">取消</button>
            <button class="btn sm primary" @click="reset">确认恢复</button>
          </div>
        </div>
      </div>
    </section>
    <div class="stack">
      <section class="panel">
        <header class="panel-head"><h2>第一版包含的能力</h2></header>
        <div class="panel-body">
          <div
            v-for="text in [
              'CSV 数据导入与画像',
              '内置模型与本地 Python 适配器',
              '五类可复现漂移场景',
              'PSI / KS / 卡方检验',
              '模型性能与预测变化评估',
              '阈值校准与 JSON / YAML 导出',
              '实验历史和本地持久化',
            ]"
            :key="text"
            class="kv"
          >
            <span class="muted">{{ text }}</span>
            <Icon name="check" class="text-primary" :size="14" />
          </div>
        </div>
      </section>
      <div class="info-strip">
        <Icon name="shield" :size="16" />
        <span>
          工作台默认绑定本机地址。样本、模型、预测与统计计算都在本地进行。第一版面向离线压力测试，管理后台、多用户权限与持续生产监控将在后续版本考虑。
        </span>
      </div>
      <p class="small muted">
        公开示例数据：UCI Bank Marketing，CC BY 4.0。来源：Moro、Cortez 与 Rita，DOI
        10.24432/C5K306。
      </p>
    </div>
  </div>
</template>
