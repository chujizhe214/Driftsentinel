import { test, expect } from '@playwright/test'
import { resolve } from 'node:path'
import { readFile } from 'node:fs/promises'

test('完整实验：配置、计算、分布、校准、报告、历史与复现', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '漂移压力测试', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '加载示例' }).click()
  await expect(page.getByRole('switch')).toHaveCount(5)
  await page.getByRole('switch', { name: '极端值注入', exact: true }).click()
  await page.getByRole('checkbox', { name: /增加多字段组合压力场景/ }).check()
  await page.getByRole('button', { name: '运行压力测试', exact: true }).click()
  await expect(page.getByText('实验已完成，结果已保存到本机')).toBeVisible({ timeout: 45000 })
  await expect(page.locator('#result-scenario option')).toHaveCount(17)
  await page.getByRole('button', { name: '结果分析' }).click()
  await expect(page.getByRole('heading', { name: '分层结论' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '混淆矩阵', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'duration', exact: true }).first().click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('img', { name: 'duration基准和场景分布柱状图' })).toBeVisible()
  await page.getByRole('button', { name: '关闭对话框' }).click()
  await page.getByRole('button', { name: '阈值校准', exact: false }).first().click()
  await expect(page.getByRole('heading', { name: '各阈值的实际检测结果' })).toBeVisible()
  await page.getByRole('button', { name: '报告与导出', exact: false }).click()
  await page.getByRole('button', { name: 'JSON', exact: true }).click()
  await expect(page.locator('.code-block')).toContainText('"schema_version"')
  const downloaded = page.waitForEvent('download')
  await page.getByRole('button', { name: '下载 JSON', exact: true }).click()
  expect((await downloaded).suggestedFilename()).toMatch(/\.json$/)
  await page.reload()
  await expect(page.locator('.code-block')).toContainText('model_name')
  await page.getByRole('link', { name: /实验历史/ }).click()
  await expect(
    page.getByRole('button', { name: /Bank Marketing · 稳定性实验/ }).first(),
  ).toBeVisible()
  await page.getByRole('button', { name: '复现实验' }).first().click()
  await expect(page.getByText('实验已完成，结果已保存到本机')).toBeVisible({ timeout: 45000 })
  await expect(page.getByRole('heading', { name: '漂移压力测试', exact: true })).toBeVisible()
  await page.screenshot({ path: 'test-results/workbench-desktop.png', fullPage: true })
  expect(errors).toEqual([])
})

test('标签与模型输入冲突时阻止运行，修正或加载示例后可以完成实验', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '加载示例', exact: true }).click()
  const label = page.locator('#label-select')
  const run = page.getByRole('button', { name: '运行压力测试', exact: true })
  await expect(label).toHaveValue('y')
  await label.selectOption('job')
  await expect(page.getByRole('alert')).toContainText('“job”是内置模型所需的输入特征')
  await expect(run).toBeDisabled()
  await page.reload()
  await expect(label).toHaveValue('job')
  await expect(run).toBeDisabled()
  await page.getByRole('button', { name: '改用示例标签 y', exact: true }).click()
  await expect(label).toHaveValue('y')
  await expect(run).toBeEnabled()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await label.selectOption('job')
  await expect(run).toBeDisabled()
  await page.getByRole('button', { name: '加载示例', exact: true }).click()
  await expect(label).toHaveValue('y')
  await expect(run).toBeEnabled()
  await expect
    .poll(async () => (await (await page.request.get('/api/datasets')).json())[0].label)
    .toBe('y')
  await run.click()
  await expect(page.getByText('实验已完成，结果已保存到本机')).toBeVisible({ timeout: 45000 })
  await expect(page.locator('#result-scenario option')).toHaveCount(13)
})

test('CSV 导入、字段画像、仅数据实验和无标签边界', async ({ page }) => {
  await page.goto('/#/datasets')
  await page.getByRole('button', { name: '导入 CSV', exact: true }).click()
  const csv =
    'value,group,label\n' +
    Array.from({ length: 60 }, (_, i) => `${i},${i % 2 ? 'a' : 'b'},${i % 2}`).join('\n')
  await page
    .locator('input[type=file]')
    .setInputFiles({ name: 'browser-test.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) })
  await expect(page.getByRole('heading', { name: 'browser-test · 数据画像' })).toBeVisible()
  await page.locator('#dataset-label').selectOption('')
  await page.getByRole('button', { name: '保存设置' }).click()
  await page.getByRole('link', { name: '实验工作台', exact: true }).click()
  await expect(page.locator('#model-select option:checked')).toHaveText('仅分析数据漂移')
  await page.getByRole('button', { name: '运行压力测试', exact: true }).click()
  await expect(page.getByText('实验已完成，结果已保存到本机')).toBeVisible({ timeout: 45000 })
  await page.getByRole('button', { name: '结果分析' }).click()
  await expect(page.getByText('03 · 性能变化 无法确认')).toBeVisible()
  await page.getByRole('button', { name: '阈值校准', exact: false }).first().click()
  await expect(page.getByRole('heading', { name: '当前实验无法校准阈值' })).toBeVisible()
})

test('错误 CSV 有清晰提示，规则会校验并持久化', async ({ page }) => {
  await page.goto('/#/datasets')
  await page.getByRole('button', { name: '导入 CSV', exact: true }).click()
  await page
    .locator('input[type=file]')
    .setInputFiles({ name: 'bad.csv', mimeType: 'text/csv', buffer: Buffer.from('x,x\n1,2\n') })
  await expect(page.getByRole('alert')).toContainText('列名不能为空或重复')
  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await page.getByRole('link', { name: '监控规则', exact: true }).click()
  await page.locator('#rule-warning').fill('0.19')
  await page.getByRole('button', { name: '保存规则', exact: true }).click()
  await expect(page.getByText('监控规则已保存')).toBeVisible()
  await page.reload()
  await expect(page.locator('#rule-warning')).toHaveValue('0.19')
})

test('移动端可用，无页面横向溢出或外部资源依赖', async ({ page }) => {
  const external: string[] = []
  page.on('request', (r) => {
    if (!r.url().startsWith('http://127.0.0.1:8010') && !r.url().startsWith('data:'))
      external.push(r.url())
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '漂移压力测试', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '展开菜单' }).click()
  await page.getByRole('link', { name: '模型', exact: true }).click()
  await expect(page.getByRole('heading', { name: '模型', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.screenshot({ path: 'test-results/models-mobile.png', fullPage: true })
  expect(external).toEqual([])
})

test('登记并实际校验一个本地 Python 模型适配器', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '加载示例' }).click()
  await page.getByRole('link', { name: '模型', exact: true }).click()
  await page.getByRole('button', { name: '接入模型', exact: true }).click()
  await page.locator('#adapter-name').fill('Browser Test Adapter')
  await page.locator('#adapter-path').fill(resolve('tests/fixtures/local_adapter.py'))
  await page.locator('#positive-class').fill('yes')
  await page.locator('#negative-class').fill('no')
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: '保存适配器', exact: true }).click()
  const card = page
    .locator('section.panel')
    .filter({ has: page.getByRole('heading', { name: 'Browser Test Adapter', exact: true }) })
  await expect(card).toContainText('待校验')
  await card.getByRole('button', { name: '校验输出', exact: true }).click()
  await expect(page.getByText('模型校验通过：输出形状、类别和概率均有效')).toBeVisible()
  await expect(card).toContainText('predict_proba 可用')
  await expect(card.locator('.tag.ready')).toContainText('可用')
})

test('选择并下载仅类别或支持概率的适配器模板', async ({ page }) => {
  await page.goto('/#/models')
  await page.getByRole('button', { name: '适配器模板', exact: true }).click()
  let dialog = page.getByRole('dialog', { name: '下载适配器模板' })
  await expect(dialog.getByRole('radio', { name: /^仅类别预测/ })).toBeChecked()
  let pending = page.waitForEvent('download')
  await dialog.getByRole('button', { name: '下载模板', exact: true }).click()
  const basic = await pending
  expect(basic.suggestedFilename()).toBe('model_adapter.py')
  const basicCode = await readFile((await basic.path())!, 'utf8')
  expect(basicCode).toContain('def predict(X):')
  expect(basicCode).not.toContain('predict_proba')
  await expect(dialog).not.toBeVisible()

  await page.getByRole('button', { name: '适配器模板', exact: true }).click()
  dialog = page.getByRole('dialog', { name: '下载适配器模板' })
  await dialog.getByRole('radio', { name: /^支持概率预测/ }).check()
  await expect(dialog).toContainText('有有效真实标签时可计算 AUC / ROC')
  await page.screenshot({ path: 'test-results/adapter-template-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(dialog.getByRole('button', { name: '下载模板', exact: true })).toBeVisible()
  await expect
    .poll(async () =>
      page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    )
    .toBe(true)
  await page.screenshot({ path: 'test-results/adapter-template-mobile.png', fullPage: true })
  pending = page.waitForEvent('download')
  await dialog.getByRole('button', { name: '下载模板', exact: true }).click()
  const proba = await pending
  expect(proba.suggestedFilename()).toBe('model_adapter_proba.py')
  const probaCode = await readFile((await proba.path())!, 'utf8')
  expect(probaCode).toContain('def predict(X):')
  expect(probaCode).toContain('def predict_proba(X):')
  expect(probaCode).toContain('return model.predict_proba(X)')
})

test('固定基准对比每日实际 CSV，无模型无标签、字段校验、历史与复现', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto('/')
  await page.getByRole('button', { name: '实际数据对比', exact: true }).click()
  const reference =
    'value,group\n' +
    Array.from({ length: 60 }, (_, i) => `${i},${['a', 'b', 'c'][i % 3]}`).join('\n')
  await page.getByLabel('导入基准 CSV', { exact: true }).setInputFiles({
    name: 'daily-reference.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(reference),
  })
  await expect(page.locator('#dataset-select option:checked')).toHaveText('daily-reference')
  await page.locator('#label-select').selectOption('')
  const referenceId = await page.locator('#dataset-select').inputValue()
  await expect(page.locator('#model-select option:checked')).toHaveText('仅分析数据漂移')
  await expect(page.getByRole('switch')).toHaveCount(0)
  const observed =
    'group,value,extra\n' + Array.from({ length: 90 }, (_, i) => `c,${1000 + i},today`).join('\n')
  await page.getByLabel('导入待检测 CSV', { exact: true }).setInputFiles({
    name: 'observed-today.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(observed),
  })
  await expect(page.locator('#current-dataset-select option:checked')).toContainText(
    'observed-today',
  )
  await expect(page.locator('#dataset-select')).toHaveValue(referenceId)
  await expect(page.locator('#current-label-select option:checked')).toHaveText(
    '无 · 尚未获得真实结果',
  )
  await page.locator('#comparison-name').fill('每日真实数据检测')
  await page.getByRole('button', { name: '运行实际检测', exact: true }).first().click()
  await expect(page.locator('.comparison-identity')).toContainText('待检测：observed-today', {
    timeout: 45000,
  })
  await expect(page.locator('.comparison-identity')).toContainText('60 行')
  await expect(page.locator('.comparison-identity')).toContainText('90 行')
  await expect(page.getByRole('heading', { name: '实际数据字段漂移' })).toBeVisible()
  await expect(page.getByText('待检测数据的额外字段未参与对比：extra')).toBeVisible()
  await page.getByRole('button', { name: '结果分析', exact: false }).first().click()
  await page.getByRole('button', { name: 'value', exact: true }).first().click()
  await expect(page.getByRole('img', { name: 'value基准和待检测分布柱状图' })).toBeVisible()
  await page.getByRole('button', { name: '关闭对话框' }).click()
  await page.getByRole('button', { name: '阈值校准', exact: false }).first().click()
  await expect(page.getByText('单次实际数据对比不自动校准阈值。', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: '报告与导出', exact: false }).click()
  await expect(page.locator('.code-block')).toContainText('observed-today')
  await page.getByRole('link', { name: /实验历史/ }).click()
  const row = page
    .locator('tr')
    .filter({ has: page.getByRole('button', { name: '每日真实数据检测', exact: true }) })
  await expect(row).toContainText('daily-reference')
  await expect(row).toContainText('observed-today')
  await row.getByRole('button', { name: '复现实验', exact: true }).click()
  await expect(page.locator('.comparison-identity')).toContainText('observed-today', {
    timeout: 45000,
  })
  await page.reload()
  await expect(page.locator('#dataset-select')).toHaveValue(referenceId)
  await expect(page.locator('.comparison-identity')).toContainText('observed-today')
  // Invalid current columns never change the fixed reference or enable a run.
  const invalid = reference.replace('value,group', 'wrong,group')
  await page.getByLabel('导入待检测 CSV', { exact: true }).setInputFiles({
    name: 'missing-field.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(invalid),
  })
  await expect(page.getByText('待检测数据缺少基准特征字段：value', { exact: true })).toBeVisible()
  await expect(
    page.getByRole('button', { name: '运行实际检测', exact: true }).first(),
  ).toBeDisabled()
  await page.getByLabel('导入待检测 CSV', { exact: true }).setInputFiles({
    name: 'observed-tomorrow.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(reference),
  })
  await expect(page.locator('#current-dataset-select option:checked')).toContainText(
    'observed-tomorrow',
  )
  await expect(page.locator('#dataset-select')).toHaveValue(referenceId)
  await page.locator('#comparison-name').fill('次日真实数据检测')
  await page.getByRole('button', { name: '运行实际检测', exact: true }).first().click()
  await expect(page.locator('.comparison-identity')).toContainText('observed-tomorrow', {
    timeout: 45000,
  })
  await page.reload()
  await expect(page.locator('.comparison-identity')).toContainText('observed-tomorrow')
  await page.screenshot({ path: 'test-results/real-comparison-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await expect(page.locator('.comparison-identity')).toContainText('observed-tomorrow')
  await expect
    .poll(async () =>
      page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    )
    .toBe(true)
  await page.screenshot({ path: 'test-results/real-comparison-mobile.png', fullPage: true })
  expect(errors).toEqual([])
})
