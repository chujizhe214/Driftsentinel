from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Scenario(BaseModel):
    id: str
    type: Literal['mean_shift', 'variance', 'categorical', 'missing', 'outlier']
    field: str = Field(min_length=1)
    strength: float = Field(ge=-90, le=500)
    category: str | None = None
    enabled: bool = True

    @model_validator(mode='after')
    def validate_strength(self):
        if self.type in ('missing', 'outlier', 'categorical') and not 0 <= self.strength <= 100:
            raise ValueError('缺失率、注入比例或类别比例必须位于 0–100%')
        return self


class Rules(BaseModel):
    warning: float = Field(default=.2, gt=0, le=5)
    critical: float = Field(default=.3, gt=0, le=10)
    pvalue: float = Field(default=.05, gt=0, le=.5)
    missing: float = Field(default=.1, ge=0, le=1)
    prediction_change: float = Field(default=.15, ge=0, le=1)
    impact: float = Field(default=.03, gt=0, le=1)
    window: Literal['15m', '1h', '6h', '24h'] = '1h'
    min_samples: int = Field(default=200, ge=10, le=100000)

    @model_validator(mode='after')
    def validate_order(self):
        if self.critical <= self.warning:
            raise ValueError('严重阈值必须大于预警阈值')
        return self


class RunRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    dataset_id: str
    mode: Literal['stress', 'compare'] = 'stress'
    current_dataset_id: str | None = None
    current_label: str | None = None
    model_id: str | None = None
    label: str | None = None
    seed: int = Field(default=42, ge=0, le=2**32-1)
    samples: int | None = Field(default=None, ge=30, le=50000)
    scenarios: list[Scenario] = Field(default_factory=list, max_length=20)
    sweep: bool = True
    combine: bool = False
    rules: Rules = Field(default_factory=Rules)

    @model_validator(mode='after')
    def validate_mode(self):
        if self.mode == 'compare':
            if not self.current_dataset_id:
                raise ValueError('请选择待检测数据集')
            if self.current_dataset_id == self.dataset_id:
                raise ValueError('待检测数据集不能与基准数据集相同')
            # Real comparisons always use both complete datasets, without simulation.
            self.samples = None
            self.scenarios = []
            self.sweep = False
            self.combine = False
        else:
            if not self.scenarios:
                raise ValueError('请至少配置一个漂移场景')
            self.current_dataset_id = None
            self.current_label = None
        return self


class AdapterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    version: str = Field(min_length=1, max_length=30)
    path: str = Field(min_length=1, max_length=1000)
    positive_class: str = '1'
    negative_class: str = '0'
    consent: bool = False


class DatasetUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    label: str | None = None
