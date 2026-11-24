export interface Feature {
  name: string
  type: 'numeric' | 'categorical'
  unique: number
  missing: number
  count: number
  mean?: number
  std?: number
  min?: number
  max?: number
  median?: number
  q25?: number
  q75?: number
  categories?: { name: string; count: number; share: number }[]
}
export type DatasetRole = 'reference' | 'current'
export interface Dataset {
  id: string
  name: string
  source: string
  label: string | null
  role?: DatasetRole | null
  createdAt: string
  profile: {
    rows: number
    columns: number
    missing: number
    duplicates: number
    fields: Feature[]
    labelCandidates: string[]
    preview: Record<string, string | number | null>[]
  }
}
export interface Model {
  id: string
  name: string
  version: string
  kind: 'builtin' | 'adapter'
  algorithm: string
  path: string
  status: 'ready' | 'unvalidated' | 'error'
  positiveClass: string
  negativeClass: string
  features: string[]
  hasProba: boolean | null
  trainRows?: number
  createdAt: string
  lastValidation?: { ok: boolean; at: string; rows?: number; error?: string }
}
export interface Rules {
  warning: number
  critical: number
  pvalue: number
  missing: number
  prediction_change: number
  impact: number
  window: '15m' | '1h' | '6h' | '24h'
  min_samples: number
}
export type ScenarioType = 'mean_shift' | 'variance' | 'categorical' | 'missing' | 'outlier'
export interface Scenario {
  id: string
  type: ScenarioType
  field: string
  strength: number
  category: string | null
  enabled: boolean
}
export interface RunRequest {
  name: string
  dataset_id: string
  mode?: 'stress' | 'compare'
  current_dataset_id?: string | null
  current_label?: string | null
  model_id: string | null
  label: string | null
  seed: number
  samples: number | null
  scenarios: Scenario[]
  sweep: boolean
  combine?: boolean
  rules: Rules
}
export interface Metrics {
  accuracy: number
  precision: number
  recall: number
  f1: number
  auc: number | null
  confusion: number[][]
  roc: { x: number; y: number }[] | null
}
export interface Evaluation {
  positiveRate: number
  probability: number[] | null
  metrics: Metrics | null
  reason: string | null
}
export interface Detection {
  name: string
  type: string
  psi: number
  method: string
  statistic: number | null
  pvalue: number | null
  missing: number
  referenceMissing: number
  risk: 'critical' | 'warning' | 'stable'
  distribution: { labels: string[]; reference: number[]; current: number[]; psi: number }
}
export interface ScenarioResult {
  id: string
  type: ScenarioType | 'control' | 'combined' | 'observed'
  name: string
  field: string
  strength: number
  fields: Detection[]
  evaluation: Evaluation | null
  maxPsi: number
  minPvalue: number | null
  maxMissing: number
  f1Drop: number | null
  impacted: boolean | null
}
export interface CalibrationRow {
  threshold: number
  tp: number
  fp: number
  fn: number
  tn: number
  recall: number
  precision: number
  falseAlarm: number
  missRate: number
  f1: number
}
export interface Family {
  rows: CalibrationRow[]
  best: CalibrationRow | null
  count: number
  reason: string | null
}
export interface Result {
  mode?: 'stress' | 'compare'
  baseline: Evaluation | null
  scenarios: ScenarioResult[]
  calibration: { available: boolean; reason?: string; families: Record<string, Family> }
  duration: number
  rows: number
  currentRows?: number
  warnings?: string[]
  ignoredFields?: string[]
  fields: number
  assumption: string
}
export interface Experiment {
  id: string
  name: string
  datasetName: string
  currentDatasetName?: string
  modelName: string
  modelVersion: string | null
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
  message: string
  createdAt: string
  startedAt?: string
  finishedAt?: string
  request: RunRequest
  result: Result | null
  error: string | null
  summary?: { duration: number; scenarios: number; impacted: number; driftFields?: number } | null
}
