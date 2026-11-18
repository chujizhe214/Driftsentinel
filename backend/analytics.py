"""Reproducible tabular stress tests, statistical tests and model evaluation."""
import importlib.util
import json
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, ks_2samp
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, roc_curve, confusion_matrix


def clean(value):
    """Convert numpy / pandas values to strictly valid JSON."""
    return json.loads(json.dumps(value, default=lambda x: x.item() if isinstance(x, np.generic) else str(x), allow_nan=False))


def read_csv(content: bytes) -> pd.DataFrame:
    from io import StringIO
    if not content or len(content) > 30 * 1024 * 1024:
        raise ValueError('请选择非空 CSV，文件最大为 30 MB。')
    text = None
    for encoding in ('utf-8-sig', 'gb18030'):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            pass
    if text is None:
        raise ValueError('无法识别编码，请将 CSV 保存为 UTF-8。')
    import csv
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=',;\t')
        records = list(csv.reader(StringIO(text), dialect))
        records = [r for r in records if any(v.strip() for v in r)]
        if len(records) < 2:
            raise ValueError('CSV 需要表头和至少 30 行数据。')
        headers = [s.strip() for s in records[0]]
        if any(not h for h in headers) or len(set(headers)) != len(headers):
            raise ValueError('列名不能为空或重复，请检查 CSV 表头。')
        if len(headers) < 2 or len(headers) > 200:
            raise ValueError('CSV 需要 2–200 列。')
        if any(len(r) != len(headers) for r in records[1:]):
            raise ValueError('CSV 行的列数与表头不一致，请检查引号和分隔符。')
        if not 30 <= len(records)-1 <= 50000:
            raise ValueError('第一版支持 30–50,000 行数据。')
        frame = pd.read_csv(StringIO(text), sep=dialect.delimiter, skip_blank_lines=True)
        frame.columns = headers
        for col in headers:
            if frame[col].dtype == 'object':
                frame[col] = frame[col].map(lambda v: v.strip() if isinstance(v, str) else v).replace('', np.nan)
                numeric = pd.to_numeric(frame[col], errors='coerce')
                if numeric.notna().sum() == frame[col].notna().sum():
                    frame[col] = numeric
            if pd.api.types.is_numeric_dtype(frame[col]):
                frame[col] = frame[col].replace([np.inf, -np.inf], np.nan)
        return frame
    except (csv.Error, pd.errors.ParserError) as exc:
        raise ValueError('CSV 格式有误，请检查分隔符与引号。') from exc


def field_type(series):
    return 'numeric' if pd.api.types.is_numeric_dtype(series) and series.notna().any() else 'categorical'


def profile(frame: pd.DataFrame):
    fields = []
    for name in frame:
        s = frame[name]
        typ = field_type(s)
        item = {'name': name, 'type': typ, 'unique': int(s.nunique()), 'missing': float(s.isna().mean()), 'count': int(s.notna().sum())}
        if typ == 'numeric':
            x = s.dropna().astype(float)
            item.update(mean=float(x.mean()), std=float(x.std(ddof=0)), min=float(x.min()), max=float(x.max()),
                        median=float(x.median()), q25=float(x.quantile(.25)), q75=float(x.quantile(.75)))
        else:
            counts = s.fillna('∅ 缺失').astype(str).value_counts().head(12)
            item['categories'] = [{'name': str(k), 'count': int(v), 'share': float(v/len(s))} for k, v in counts.items()]
        fields.append(item)
    labels = [str(c) for c in frame.columns if frame[c].nunique() == 2 and frame[c].notna().all()]
    return {'rows': len(frame), 'columns': len(frame.columns), 'missing': float(frame.isna().sum().sum()/frame.size),
            'duplicates': int(frame.duplicated().sum()), 'fields': fields, 'labelCandidates': labels,
            'preview': frame.head(8).astype(object).where(frame.head(8).notna(), None).to_dict('records')}


def generate(frame, config, seed):
    rng = np.random.default_rng(seed)
    out = frame.copy(deep=True).reset_index(drop=True)
    field, strength, typ = config['field'], config['strength'], config['type']
    if field not in frame:
        raise ValueError(f'找不到场景字段 {field}')
    s = frame[field]
    if typ in ('mean_shift', 'variance', 'outlier') and field_type(s) != 'numeric':
        raise ValueError(f'{field} 不是数值字段')
    if typ == 'mean_shift':
        # A zero mean still needs an interpretable, effective perturbation.
        scale = abs(float(s.mean())) or float(s.std(ddof=0)) or 1.
        out[field] = s.astype(float).to_numpy() + scale * strength / 100
    elif typ == 'variance':
        mean = float(s.mean())
        out[field] = mean + (s.astype(float).to_numpy()-mean) * np.sqrt(1+strength/100)
    elif typ == 'missing':
        # Strength is the target total missing rate, not an increment.
        needed = max(0, round(len(out)*strength/100)-int(s.isna().sum()))
        available = np.flatnonzero(out[field].notna().to_numpy())
        out.loc[rng.choice(available, min(needed, len(available)), replace=False), field] = np.nan
    elif typ == 'outlier':
        ids = rng.choice(len(out), round(len(out)*strength/100), replace=False)
        out[field] = out[field].astype(float)
        center, spread = float(s.mean()), float(s.std(ddof=0)) or 1.
        out.loc[ids, field] = center + rng.choice([-1, 1], len(ids))*spread*rng.uniform(5, 10, len(ids))
    elif typ == 'categorical':
        if field_type(s) != 'categorical':
            raise ValueError(f'{field} 不是类别字段')
        category = str(config.get('category', ''))
        yes = np.flatnonzero(s.fillna('∅ 缺失').astype(str).to_numpy() == category)
        no = np.flatnonzero(s.fillna('∅ 缺失').astype(str).to_numpy() != category)
        if not len(yes) or not len(no):
            raise ValueError('类别比例场景需要选择一个有样本且不是唯一值的类别。')
        n = round(len(out)*strength/100)
        ids = np.concatenate([rng.choice(yes, n, replace=True), rng.choice(no, len(out)-n, replace=True)])
        rng.shuffle(ids)
        # Resample entire rows so observed feature/label relations stay paired.
        out = frame.iloc[ids].copy().reset_index(drop=True)
    return out


def distribution(reference, current, typ):
    if typ == 'numeric':
        a, b = reference.dropna().astype(float), current.dropna().astype(float)
        if len(a):
            edges = np.unique(np.quantile(a, np.linspace(0, 1, 11)))
            if len(edges) < 2:
                v = float(a.iloc[0]); edges = np.array([v-.5, v+.5])
            labels = [f'{edges[i]:.3g}–{edges[i+1]:.3g}' for i in range(len(edges)-1)]
            edges[0], edges[-1] = -np.inf, np.inf
            ca = np.histogram(a, edges)[0].tolist()
            cb = np.histogram(b, edges)[0].tolist()
        else:
            labels, ca, cb = [], [], []
    else:
        a, b = reference.dropna().astype(str), current.dropna().astype(str)
        categories = pd.concat([a, b]).value_counts().head(12).index.tolist()
        labels = categories + (['其他'] if a.nunique()+b.nunique() > len(categories) else [])
        ca = [int((a == c).sum()) for c in categories]
        cb = [int((b == c).sum()) for c in categories]
        if len(labels) > len(categories):
            ca.append(len(a)-sum(ca)); cb.append(len(b)-sum(cb))
    labels.append('缺失')
    ca.append(int(reference.isna().sum())); cb.append(int(current.isna().sum()))
    pa, pb = np.array(ca, dtype=float)/len(reference), np.array(cb, dtype=float)/len(current)
    # Add epsilon then renormalize: finite PSI even for previously unseen values.
    ea, eb = np.clip(pa, 1e-6, None), np.clip(pb, 1e-6, None)
    ea /= ea.sum(); eb /= eb.sum()
    psi = float(np.sum((eb-ea)*np.log(eb/ea)))
    return {'labels': labels, 'reference': pa.tolist(), 'current': pb.tolist(), 'psi': psi}


def detect(reference, current, label, rules):
    fields = []
    for name in reference:
        if name == label:
            continue
        a, b = reference[name], current[name]
        typ = field_type(a)
        dist = distribution(a, b, typ)
        statistic, pvalue = None, None
        method = 'ks' if typ == 'numeric' else 'chi_square'
        if typ == 'numeric' and a.notna().any() and b.notna().any():
            res = ks_2samp(a.dropna().astype(float), b.dropna().astype(float), method='asymp')
            statistic, pvalue = float(res.statistic), float(res.pvalue)
        elif typ == 'categorical':
            cats = pd.Index(pd.concat([a.fillna('∅').astype(str), b.fillna('∅').astype(str)]).unique())
            counts = np.array([[int((x.fillna('∅').astype(str) == c).sum()) for c in cats] for x in (a,b)])
            if len(cats) > 1:
                statistic, pvalue, _, _ = chi2_contingency(counts, correction=False)
                statistic, pvalue = float(statistic), float(pvalue)
        missing = float(b.isna().mean())
        risk = 'critical' if dist['psi'] >= rules['critical'] else 'warning' if (dist['psi'] >= rules['warning'] or missing > rules['missing'] or pvalue is not None and pvalue < rules['pvalue']) else 'stable'
        fields.append({'name': name, 'type': typ, 'psi': dist['psi'], 'method': method,
                       'statistic': statistic, 'pvalue': pvalue, 'missing': missing,
                       'referenceMissing': float(a.isna().mean()), 'risk': risk, 'distribution': dist})
    return sorted(fields, key=lambda f: f['psi'], reverse=True)


def load_predictor(model):
    if model['kind'] == 'builtin':
        data = json.loads(Path(model['path']).read_text(encoding='utf-8'))
        required = [f['name'] for f in data['numeric']+data['categorical']]
        def predict(frame):
            missing = [c for c in required if c not in frame]
            if missing:
                raise ValueError('内置模型缺少输入字段：' + ', '.join(missing))
            columns = []
            for f in data['numeric']:
                values = pd.to_numeric(frame[f['name']], errors='coerce').fillna(f['median'])
                columns.append((values.to_numpy()-f['mean'])/f['scale'])
            for f in data['categorical']:
                for category in f['categories']:
                    columns.append((frame[f['name']].astype(str) == category).astype(float).to_numpy())
            z = np.column_stack(columns) @ np.array(data['coefficients']) + data['intercept']
            proba = 1 / (1+np.exp(-np.clip(z, -700, 700)))
            classes = np.where(proba >= .5, model['positiveClass'], model['negativeClass'])
            return classes, proba
        return predict
    path = Path(model['path']).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != '.py':
        raise ValueError('模型适配器文件不存在或不是 .py 文件')
    name = f'driftsentinel_adapter_{model["id"]}'
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    if not callable(getattr(module, 'predict', None)):
        raise ValueError('适配器必须提供可调用的 predict(X) 函数')
    def predict(frame):
        classes = np.asarray(module.predict(frame.copy()))
        proba = None
        if callable(getattr(module, 'predict_proba', None)):
            raw = np.asarray(module.predict_proba(frame.copy()), dtype=float)
            if raw.ndim == 2 and raw.shape[1] == 2:
                proba = raw[:, 1]
            elif raw.ndim == 1:
                proba = raw
            else:
                raise ValueError('predict_proba 必须返回 (n,) 或 (n, 2)，第二列为正类概率')
        return classes, proba
    return predict


def class_values(values):
    return pd.Series(values).map(lambda v: str(int(v)) if isinstance(v, (float, np.floating)) and np.isfinite(v) and v.is_integer() else str(v))


def validate_output(classes, proba, n, model):
    if classes.ndim != 1 or len(classes) != n:
        raise ValueError('predict 必须返回长度与样本数一致的一维数组')
    values = class_values(classes)
    allowed = {str(model['positiveClass']), str(model['negativeClass'])}
    if not set(values.unique()).issubset(allowed):
        raise ValueError('预测类别与模型配置的正类/负类不一致')
    if proba is not None:
        if len(proba) != n or not np.isfinite(proba).all() or ((proba < 0) | (proba > 1)).any():
            raise ValueError('预测概率必须是与样本等长的 0–1 有限数值')
    return (values == str(model['positiveClass'])).astype(int).to_numpy(), proba


def evaluate(frame, label, model, predictor):
    if not predictor:
        return None
    classes, proba = predictor(frame.drop(columns=[label], errors='ignore'))
    pred, proba = validate_output(classes, proba, len(frame), model)
    result = {'positiveRate': float(pred.mean()), 'probability': None, 'metrics': None,
              'reason': '未选择有效的二分类真实标签，仅分析预测分布。'}
    if proba is not None:
        counts, _ = np.histogram(proba, bins=np.linspace(0,1,11))
        result['probability'] = (counts/len(proba)).tolist()
    if label and label in frame:
        values = frame[label]
        mapped = class_values(values)
        allowed = {str(model['positiveClass']), str(model['negativeClass'])}
        if values.notna().all() and set(mapped.unique()).issubset(allowed) and len(mapped.unique()) == 2:
            y = (mapped == str(model['positiveClass'])).astype(int).to_numpy()
            metrics = {'accuracy': float(accuracy_score(y,pred)), 'precision': float(precision_score(y,pred,zero_division=0)),
                       'recall': float(recall_score(y,pred,zero_division=0)), 'f1': float(f1_score(y,pred,zero_division=0)),
                       'auc': float(roc_auc_score(y,proba)) if proba is not None else None,
                       'confusion': confusion_matrix(y,pred,labels=[0,1]).tolist(), 'roc': None}
            if proba is not None:
                fpr,tpr,_=roc_curve(y,proba)
                ids=np.unique(np.linspace(0,len(fpr)-1,min(80,len(fpr))).astype(int))
                metrics['roc']=[{'x':float(fpr[i]),'y':float(tpr[i])} for i in ids]
            result.update(metrics=metrics, reason=None)
    return result


def calibration(results, baseline, rules):
    if baseline is None or baseline['metrics'] is None:
        return {'available': False, 'reason': '阈值校准需要有效真实标签和可用模型，以实际 F1 影响为参照。', 'families': {}}
    families = {}
    for family in ('psi', 'pvalue', 'missing'):
        selected = [r for r in results if r['evaluation'] and r['evaluation']['metrics'] and (family == 'psi' or family == 'pvalue' and r['type'] != 'missing' or family == 'missing' and (r['type'] in ('missing','control') or r['type']=='combined' and any(s['type']=='missing' for s in r.get('steps',[]))))]
        if not selected:
            continue
        thresholds = [0.05,.1,.15,.2,.25,.3,.4,.5] if family == 'psi' else [.001,.005,.01,.025,.05,.1] if family == 'pvalue' else [.02,.05,.1,.15,.2,.3]
        rows = []
        for threshold in thresholds:
            tp=fp=fn=tn=0
            for r in selected:
                affected = baseline['metrics']['f1']-r['evaluation']['metrics']['f1'] >= rules['impact']
                detected = r['maxPsi'] >= threshold if family == 'psi' else r['minPvalue'] is not None and r['minPvalue'] < threshold if family == 'pvalue' else r['maxMissing'] >= threshold
                tp += int(detected and affected); fp += int(detected and not affected)
                fn += int(not detected and affected); tn += int(not detected and not affected)
            recall=tp/(tp+fn) if tp+fn else 0
            precision=tp/(tp+fp) if tp+fp else 0
            rows.append({'threshold':threshold,'tp':tp,'fp':fp,'fn':fn,'tn':tn,'recall':recall,'precision':precision,
                         'falseAlarm':fp/(fp+tn) if fp+tn else 0,'missRate':fn/(tp+fn) if tp+fn else 0,
                         'f1':2*precision*recall/(precision+recall) if precision+recall else 0})
        has_impact=any(baseline['metrics']['f1']-r['evaluation']['metrics']['f1'] >= rules['impact'] for r in selected)
        best = max(rows,key=lambda x:(x['f1'],-x['falseAlarm'],-x['threshold'])) if has_impact else None
        families[family]={'rows':rows,'best':best,'count':len(selected),'reason':None if has_impact else '当前场景没有达到性能影响标准，无法给出有依据的推荐阈值。'}
    return {'available':True,'families':families}


def comparison_frames(reference, current, label, current_label):
    """Align real datasets by feature name; never fill absent fields or discard rows."""
    if label and label not in reference:
        raise ValueError('基准数据中不存在所选真实标签列')
    if current_label and current_label not in current:
        raise ValueError('待检测数据中不存在所选真实标签列')
    features = [name for name in reference if name != label]
    if not features:
        raise ValueError('基准数据至少需要一个非标签字段')
    missing = [name for name in features if name not in current or name == current_label]
    if missing:
        raise ValueError('待检测数据缺少基准特征字段：' + '、'.join(missing))
    aligned = current[features].copy()
    for name in features:
        if field_type(reference[name]) == 'numeric':
            converted = pd.to_numeric(aligned[name], errors='coerce')
            if (aligned[name].notna() & converted.isna()).any():
                raise ValueError(f'待检测字段 {name} 应为数值，包含无法转换的内容，请检查 CSV')
            aligned[name] = converted
    ignored = [name for name in current if name not in features and name != current_label and name != label]
    return reference[features].copy(), aligned, ignored


def run_comparison(reference, current, model, request, progress, cancelled):
    started = time.perf_counter()
    ref_features, cur_features, ignored = comparison_frames(reference, current, request['label'], request['current_label'])
    if cancelled():
        raise InterruptedError('检测已取消')
    progress(15, '正在对齐基准与待检测字段，使用两份数据的全部样本')
    predictor = load_predictor(model) if model else None
    ref_eval = ref_features.copy()
    cur_eval = cur_features.copy()
    if request['label']:
        ref_eval[request['label']] = reference[request['label']]
    if request['current_label']:
        cur_eval[request['current_label']] = current[request['current_label']]
    baseline = evaluate(ref_eval, request['label'], model, predictor)
    if cancelled():
        raise InterruptedError('检测已取消')
    progress(40, '正在计算实际数据的字段分布、PSI 与统计检验')
    fields = detect(ref_features, cur_features, None, request['rules'])
    evaluation = evaluate(cur_eval, request['current_label'], model, predictor)
    if cancelled():
        raise InterruptedError('检测已取消')
    delta = baseline['metrics']['f1'] - evaluation['metrics']['f1'] if baseline and baseline['metrics'] and evaluation and evaluation['metrics'] else None
    warnings = []
    if ignored:
        warnings.append('待检测数据的额外字段未参与对比：' + '、'.join(ignored))
    if min(len(reference), len(current)) < request['rules']['min_samples']:
        warnings.append(f'至少一份数据少于规则要求的 {request["rules"]["min_samples"]} 个样本，统计结果请谨慎解读。')
    pvalues = [f['pvalue'] for f in fields if f['pvalue'] is not None]
    scenario = {'id': 'observed', 'type': 'observed', 'name': '实际采集数据', 'field': '全部基准特征', 'strength': 0,
                'fields': fields, 'evaluation': evaluation, 'maxPsi': max(f['psi'] for f in fields),
                'minPvalue': min(pvalues) if pvalues else None, 'maxMissing': max(f['missing'] for f in fields),
                'f1Drop': delta, 'impacted': delta >= request['rules']['impact'] if delta is not None else None}
    progress(95, '实际数据检测完成，正在保存结果')
    return clean({'mode': 'compare', 'baseline': baseline, 'scenarios': [scenario],
                  'calibration': {'available': False, 'families': {}, 'reason': '单次实际数据对比不自动校准阈值。可使用已有监控规则，或在模拟压力测试中校准后应用。'},
                  'duration': round(time.perf_counter()-started, 3), 'rows': len(reference),
                  'currentRows': len(current), 'fields': len(fields), 'ignoredFields': ignored, 'warnings': warnings,
                  'assumption': '固定基准与本次实际采集数据按同名字段对比，使用全部样本，不生成模拟场景。分布变化不等于模型性能下降；有模型和有效真实标签时才计算性能，两批数据的性能差异也不能单独证明由漂移导致。'})


def run_experiment(frame, model, request, progress, cancelled):
    started = time.perf_counter()
    if request['samples']:
        frame=frame.sample(n=request['samples'], replace=request['samples']>len(frame), random_state=request['seed']).reset_index(drop=True)
    predictor=load_predictor(model) if model else None
    baseline=evaluate(frame,request['label'],model,predictor)
    configs=[{'id':'control','type':'control','field':'', 'strength':0,'name':'对照组 · 无变化'}]
    names={'mean_shift':'均值偏移','variance':'方差变化','categorical':'类别比例','missing':'缺失值','outlier':'极端值'}
    for item in request['scenarios']:
        if not item['enabled']:
            continue
        for mult in ([.5,1,1.5] if request['sweep'] else [1]):
            value=item['strength']*mult
            if item['type'] in ('missing','outlier','categorical'):
                value=min(100,value)
            value=max(-90,value)
            configs.append({**item,'strength':value,'id':f'{item["id"]}-{mult}', 'name':f'{item["field"]} · {names[item["type"]]} {value:+g}%'})
    if request.get('combine'):
        steps=[s for s in request['scenarios'] if s['enabled']]
        configs.append({'id':'combined','type':'combined','field':'多个字段','strength':100,
                        'name':f'组合压力 · {len(steps)} 项变换（1×）','steps':steps})
    results=[]
    for index, config in enumerate(configs):
        if cancelled():
            raise InterruptedError('实验已取消')
        if config['type']=='control':
            current=frame.copy()
        elif config['type']=='combined':
            current=frame.copy()
            for step_index, step in enumerate(config['steps']):
                step_seed=int(np.random.SeedSequence([request['seed'],step_index]).generate_state(1)[0])
                current=generate(current,step,step_seed)
        else:
            current=generate(frame, config, request['seed'])
        fields=detect(frame,current,request['label'],request['rules'])
        evaluation=evaluate(current,request['label'],model,predictor)
        pvalues=[f['pvalue'] for f in fields if f['pvalue'] is not None]
        delta=baseline['metrics']['f1']-evaluation['metrics']['f1'] if baseline and baseline['metrics'] and evaluation and evaluation['metrics'] else None
        results.append({**config,'fields':fields,'evaluation':evaluation,'maxPsi':max((f['psi'] for f in fields),default=0),
                        'minPvalue':min(pvalues) if pvalues else None,'maxMissing':max((f['missing'] for f in fields),default=0),
                        'f1Drop':delta,'impacted':delta >= request['rules']['impact'] if delta is not None else None})
        progress(round((index+1)/len(configs)*95),f'正在分析场景 {index+1}/{len(configs)} · {config["name"]}')
    return clean({'baseline':baseline,'scenarios':results,'calibration':calibration(results,baseline,request['rules']),
                  'duration':round(time.perf_counter()-started,3),'rows':len(frame),'fields':len(frame.columns)-(1 if request['label'] else 0),
                  'assumption':'数值、缺失与极端值场景保留原始标签，仅衡量受控输入扰动下的稳健性；不代表真实线上概念漂移。'})
