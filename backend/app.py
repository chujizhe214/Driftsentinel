import asyncio
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
import pandas as pd
import yaml
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from . import storage as db
from .analytics import read_csv, profile, load_predictor, evaluate, run_experiment, run_comparison, comparison_frames
from .schemas import RunRequest, AdapterRequest, DatasetRole, DatasetUpdate, Rules

executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='experiment')
cancellations: dict[str, threading.Event] = {}
submission_lock = threading.Lock()
logger = logging.getLogger('driftsentinel')


def require(table, key):
    item = db.get(table, key)
    if not item:
        raise HTTPException(404, '记录不存在或已删除')
    return item


def dataframe(dataset):
    # Stored snapshots use pickle internally, never deserialize user-supplied files.
    return pd.read_pickle(db.DATA_DIR / 'datasets' / f'{dataset["id"]}.pkl')


def add_dataset(frame, name, source, key=None, label=None, role=None):
    key = key or db.uid('data')
    frame.to_pickle(db.DATA_DIR / 'datasets' / f'{key}.pkl')
    info = profile(frame)
    return db.put('datasets', {'id':key, 'name':name, 'source':source, 'label':label, 'role':role,
                              'createdAt':db.now(), 'profile':info})


def bootstrap():
    demo_dir = db.ROOT / 'public' / 'demo'
    if not (demo_dir / 'model.json').exists():
        raise RuntimeError('缺少示例数据，请运行 python scripts/prepare_demo.py')
    info = json.loads((demo_dir / 'model.json').read_text(encoding='utf-8'))
    demo_dataset = db.get('datasets', 'bank-reference')
    if not demo_dataset:
        add_dataset(pd.read_csv(demo_dir / 'bank_reference.csv'), 'Bank Marketing · reference', 'UCI Bank Marketing', 'bank-reference', 'y', 'reference')
    elif demo_dataset.get('role') != 'reference':
        demo_dataset['role'] = 'reference'
        db.put('datasets', demo_dataset)
    existing_model=db.get('models', info['id'])
    if not existing_model:
        db.put('models', {'id':info['id'], 'name':info['name'], 'version':info['version'], 'kind':'builtin',
                         'algorithm':info['algorithm'], 'path':str(demo_dir / 'model.json'), 'status':'ready',
                         'positiveClass':info['positiveClass'], 'negativeClass':info['negativeClass'],
                         'trainRows':info['trainRows'], 'features':[f['name'] for f in info['numeric']+info['categorical']],
                         'hasProba':True,'createdAt':db.now()})
    elif existing_model['path'] != str(demo_dir / 'model.json'):
        # The same workspace may move between a host install and Docker.
        existing_model['path']=str(demo_dir / 'model.json')
        db.put('models', existing_model)


@asynccontextmanager
async def lifespan(_app):
    db.init_db()
    bootstrap()
    yield
    for event in list(cancellations.values()):
        event.set()


app=FastAPI(title='DriftSentinel',version='1.0.0',lifespan=lifespan)


@app.exception_handler(ValueError)
async def value_error(_request: Request, exc: ValueError):
    return JSONResponse(status_code=422,content={'detail':str(exc)})


@app.get('/api/health')
def health():
    return {'status':'ok','version':'1.0.0','mode':'local','storage':str(db.DATA_DIR)}


@app.get('/api/datasets')
def datasets():
    return db.all_items('datasets')


@app.post('/api/datasets')
async def upload_dataset(file: UploadFile=File(...), role: DatasetRole | None=None):
    if not file.filename or not file.filename.lower().endswith('.csv'):
        raise HTTPException(422,'仅支持 .csv 文件')
    content=await file.read(30*1024*1024+1)
    frame=await asyncio.to_thread(read_csv,content)
    candidates=profile(frame)['labelCandidates']
    return await asyncio.to_thread(add_dataset,frame,Path(file.filename).stem,'本地导入',
                                   label=candidates[-1] if candidates else None,role=role)


@app.patch('/api/datasets/{key}')
def update_dataset(key: str, payload: DatasetUpdate):
    item=require('datasets',key)
    if payload.label and payload.label not in [f['name'] for f in item['profile']['fields']]:
        raise HTTPException(422,'标签列不存在')
    changes = payload.model_dump(exclude_unset=True)
    if key == 'bank-reference' and 'role' in changes and payload.role != 'reference':
        raise HTTPException(422, '内置示例固定用作基准数据')
    if payload.name is None:
        changes.pop('name', None)
    item.update(changes)
    return db.put('datasets',item)


@app.delete('/api/datasets/{key}')
def delete_dataset(key: str):
    require('datasets',key)
    if key=='bank-reference':
        raise HTTPException(409,'内置示例数据集保留用于一键演示')
    db.delete('datasets',key)
    (db.DATA_DIR/'datasets'/f'{key}.pkl').unlink(missing_ok=True)
    return {'ok':True}


@app.get('/api/datasets/{key}/csv')
def download_dataset(key: str):
    item=require('datasets',key)
    return Response(dataframe(item).to_csv(index=False),media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition':f'attachment; filename="{key}.csv"'})


@app.get('/api/models')
def models():
    return db.all_items('models')


@app.post('/api/models')
def create_adapter(payload: AdapterRequest):
    if not payload.consent:
        raise HTTPException(422,'请确认此适配器为你信任的本地 Python 文件')
    path=Path(payload.path).expanduser().resolve()
    if not path.is_file() or path.suffix.lower()!='.py':
        raise HTTPException(422,'适配器路径必须指向当前运行机器上的 .py 文件')
    if payload.positive_class == payload.negative_class:
        raise HTTPException(422,'正类与负类不能相同')
    item={'id':db.uid('model'),'name':payload.name,'version':payload.version,'path':str(path),'kind':'adapter',
          'algorithm':'Python adapter','positiveClass':payload.positive_class,'negativeClass':payload.negative_class,
          'status':'unvalidated','hasProba':None,'features':[],'createdAt':db.now()}
    return db.put('models',item)


@app.post('/api/models/{key}/validate')
def validate_adapter(key: str, payload: dict):
    item=require('models',key)
    dataset=require('datasets',str(payload.get('dataset_id','')))
    frame=dataframe(dataset).head(50)
    try:
        predictor=load_predictor(item)
        result=evaluate(frame,dataset['label'],item,predictor)
        item.update(status='ready',hasProba=result['probability'] is not None,lastValidation={'rows':len(frame),'at':db.now(),'ok':True})
        db.put('models',item)
        return item
    except Exception as exc:
        item.update(status='error',lastValidation={'ok':False,'error':str(exc),'at':db.now()})
        db.put('models',item)
        raise HTTPException(422,f'模型输出校验失败：{exc}') from exc


@app.delete('/api/models/{key}')
def delete_model(key: str):
    item=require('models',key)
    if item['kind']=='builtin':
        raise HTTPException(409,'内置示例模型不能删除')
    db.delete('models',key)
    return {'ok':True}


def execute(key, dataset, model, payload, event, current_dataset=None):
    def update(progress, message):
        item=db.get('experiments',key)
        if item:
            item.update(progress=progress,message=message)
            db.put('experiments',item)
    try:
        item=require('experiments',key)
        item.update(status='running',startedAt=db.now())
        db.put('experiments',item)
        if current_dataset:
            result=run_comparison(dataframe(dataset),dataframe(current_dataset),model,payload,update,event.is_set)
        else:
            result=run_experiment(dataframe(dataset),model,payload,update,event.is_set)
        if event.is_set():
            raise InterruptedError('实验已取消')
        item=require('experiments',key)
        item.update(status='completed',progress=100,message='实验已完成',result=result,finishedAt=db.now())
        db.put('experiments',item)
    except Exception as exc:
        item=db.get('experiments',key)
        if item:
            item.update(status='cancelled' if isinstance(exc,InterruptedError) else 'failed',error=str(exc),message=str(exc),finishedAt=db.now())
            db.put('experiments',item)
        if not isinstance(exc,InterruptedError):
            logger.exception('Experiment failed: %s',key)
    finally:
        cancellations.pop(key,None)


@app.post('/api/experiments',status_code=202)
def create_experiment(payload: RunRequest):
    with submission_lock:
        return submit_experiment(payload)


def submit_experiment(payload: RunRequest):
    active=[x for x in db.all_items('experiments') if x['status'] in ('queued','running')]
    if active:
        raise HTTPException(409,'已有实验正在运行，请等待完成或取消后再试')
    dataset=require('datasets',payload.dataset_id)
    current_dataset=require('datasets',payload.current_dataset_id) if payload.mode=='compare' else None
    model=require('models',payload.model_id) if payload.model_id else None
    fields={f['name']:f for f in dataset['profile']['fields']}
    if payload.label and payload.label not in fields:
        raise HTTPException(422,'标签列不存在')
    if model and model['kind']=='builtin':
        if payload.label in model['features']:
            raise HTTPException(422,f'真实标签列“{payload.label}”是内置模型所需的输入特征，不能同时作为标签。请选择实际结果列，或选择仅分析数据漂移。')
        if not set(model['features']).issubset(fields):
            raise HTTPException(422,'所选数据不满足内置模型输入。请接入匹配的适配器，或选择仅分析数据漂移。')
    enabled=[s for s in payload.scenarios if s.enabled]
    if payload.mode=='stress' and not enabled:
        raise HTTPException(422,'请至少启用一个漂移场景')
    if current_dataset:
        comparison_frames(dataframe(dataset),dataframe(current_dataset),payload.label,payload.current_label)
    for s in enabled:
        if s.field not in fields or s.field==payload.label:
            raise HTTPException(422,f'场景字段 {s.field} 不存在或被选为标签')
        if s.type in ('mean_shift','variance','outlier') and fields[s.field]['type']!='numeric':
            raise HTTPException(422,f'{s.field} 必须是数值字段')
        if s.type=='categorical' and fields[s.field]['type']!='categorical':
            raise HTTPException(422,f'{s.field} 必须是类别字段')
    item={'id':db.uid('exp'),'name':payload.name,'datasetName':dataset['name'],'modelName':model['name'] if model else '仅数据漂移',
          'modelVersion':model['version'] if model else None,'status':'queued','progress':0,'message':'准备运行',
          'createdAt':db.now(),'request':payload.model_dump(),'result':None,'error':None}
    if current_dataset:
        item['currentDatasetName']=current_dataset['name']
    db.put('experiments',item)
    event=threading.Event(); cancellations[item['id']]=event
    executor.submit(execute,item['id'],dataset,model,payload.model_dump(),event,current_dataset)
    return item


@app.get('/api/experiments')
def experiments():
    return [{k:v for k,v in item.items() if k!='result'} | {'summary':
            {'duration':item['result']['duration'],'scenarios':len(item['result']['scenarios']),
             'driftFields':sum(f['risk']!='stable' for f in item['result']['scenarios'][0]['fields']),
             'impacted':sum(bool(r['impacted']) for r in item['result']['scenarios'])} if item.get('result') else None}
            for item in db.all_items('experiments')]


@app.get('/api/experiments/{key}')
def experiment(key: str):
    return require('experiments',key)


@app.post('/api/experiments/{key}/cancel')
def cancel(key: str):
    item=require('experiments',key)
    event=cancellations.get(key)
    if event:
        event.set()
    return {'ok':True,'status':item['status']}


@app.delete('/api/experiments/{key}')
def delete_experiment(key: str):
    item=require('experiments',key)
    if item['status'] in ('running','queued'):
        raise HTTPException(409,'请先取消正在运行的实验')
    db.delete('experiments',key)
    return {'ok':True}


def build_config(item, rules):
    result=item['result']
    if not result:
        raise HTTPException(409,'实验尚未完成')
    features={}
    for f in result['scenarios'][0]['fields']:
        features[f['name']]={'method':'psi','warning_threshold':rules['warning'],'critical_threshold':rules['critical'],
                             'secondary_method':f['method'],'pvalue_threshold':rules['pvalue']}
    compare=item['request'].get('mode')=='compare'
    config={'schema_version':'1.0','model_name':item['modelName'],'model_version':item['modelVersion'],
            'task_type':'binary_classification' if item['request']['model_id'] else 'data_drift',
            'mode':'compare' if compare else 'stress','experiment_id':item['id'],'generated_at':db.now(),
            'reference':{'dataset':item['datasetName'],'dataset_id':item['request']['dataset_id'],'rows':result['rows'],'label_column':item['request']['label']},
            'features':features,'global_rules':{'missing_rate_alert':rules['missing'],'prediction_rate_change':rules['prediction_change'],'f1_drop':rules['impact']},
            'monitor_window':rules['window'],'minimum_samples':rules['min_samples'],
            'calibration_scope':'实际对比使用已有规则，不根据单次结果自动推荐阈值。' if compare else '仅适用于当前基准数据、模型与受控压力场景，更换后需重新校准。'}
    if compare:
        config['current']={'dataset':item['currentDatasetName'],'dataset_id':item['request']['current_dataset_id'],
                           'rows':result['currentRows'],'label_column':item['request'].get('current_label')}
    else:
        config['reference']['seed']=item['request']['seed']
    return config


@app.get('/api/experiments/{key}/export')
def export(key: str, format: str='yaml'):
    item=require('experiments',key)
    if format=='report':
        result=item.get('result')
        if not result:
            raise HTTPException(409,'实验尚未完成')
        compare=item['request'].get('mode')=='compare'
        lines=[f'# {item["name"]}',f'\n- 模式：{"实际数据对比" if compare else "模拟压力测试"}',
               f'- 基准数据：{item["datasetName"]}（{result["rows"]} 行）',
               f'- 模型：{item["modelName"]} {item["modelVersion"] or ""}']
        if compare:
            lines.append(f'- 待检测数据：{item["currentDatasetName"]}（{result["currentRows"]} 行）')
        else:
            lines.extend([f'- 随机种子：{item["request"]["seed"]}',f'- 场景：{len(result["scenarios"])}'])
        lines.extend([f'\n{result["assumption"]}', '\n| 对比项 | 最大 PSI | F1 | F1 下降 |','|---|---:|---:|---:|'])
        for r in result['scenarios']:
            metrics=r['evaluation']['metrics'] if r['evaluation'] else None
            lines.append(f'| {r["name"]} | {r["maxPsi"]:.4f} | {metrics["f1"] if metrics else "无标签/模型"} | {r["f1Drop"] if r["f1Drop"] is not None else "—"} |')
        if compare:
            def cell(value):
                return str(value).replace('|','\\|').replace('\n',' ')
            lines.extend(['\n| 字段 | PSI | p 值 | 基准缺失率 | 待检测缺失率 | 风险 |','|---|---:|---:|---:|---:|---|'])
            for field in result['scenarios'][0]['fields']:
                pvalue=f'{field["pvalue"]:.6g}' if field['pvalue'] is not None else '—'
                lines.append(f'| {cell(field["name"])} | {field["psi"]:.4f} | {pvalue} | {field["referenceMissing"]:.1%} | {field["missing"]:.1%} | { {"stable":"稳定","warning":"关注","critical":"严重"}[field["risk"]] } |')
            lines.extend(f'\n- {warning}' for warning in result.get('warnings',[]))
        content='\n'.join(lines); ext='md'; media='text/markdown'
    else:
        rules=(db.get('settings','rules') or {}).get('value',item['request']['rules'])
        config=build_config(item,rules)
        if format not in ('yaml','json'):
            raise HTTPException(422,'导出格式必须为 yaml、json 或 report')
        content=yaml.safe_dump(config,allow_unicode=True,sort_keys=False) if format=='yaml' else json.dumps(config,ensure_ascii=False,indent=2)
        ext=format; media='text/yaml' if format=='yaml' else 'application/json'
    return Response(content,media_type=media,headers={'Content-Disposition':f'attachment; filename="{key}.{ext}"'})


@app.get('/api/rules')
def get_rules():
    return (db.get('settings','rules') or {}).get('value',Rules().model_dump())


@app.put('/api/rules')
def save_rules(payload: Rules):
    db.put('settings',{'id':'rules','value':payload.model_dump()})
    return payload


@app.get('/api/adapter-template')
def adapter_template(probability: bool=True):
    code='''"""DriftSentinel 本地表格二分类适配器（joblib / scikit-learn 示例）。"""
from pathlib import Path
from joblib import load

# 修改模型文件名；建议加载包含训练时预处理的完整 Pipeline。
# 模型文件与本适配器放在同一文件夹，路径同时适用于 Docker 和本地运行。
model = load(Path(__file__).parent / "model.joblib")

def predict(X):
    # X 是平台传入的 pandas DataFrame，不包含已选择的真实标签列。
    # 字段、类型、顺序和预处理须与训练时一致；返回长度为 len(X) 的类别数组。
    return model.predict(X)
'''
    if probability:
        code+='''
def predict_proba(X):
    # 模型必须支持 predict_proba；无此接口请选择“仅类别预测”模板。
    # 两列概率的第二列必须对应平台登记的正类，请检查 model.classes_ 顺序。
    # 也可改为返回一维正类概率，范围为 0–1，长度为 len(X)。
    return model.predict_proba(X)
'''
    filename='model_adapter_proba.py' if probability else 'model_adapter.py'
    return Response(code,media_type='text/plain; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="{filename}"'})


dist=db.ROOT/'dist'
if (dist/'assets').exists():
    app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')


@app.get('/')
def index():
    if (dist/'index.html').exists():
        return FileResponse(dist/'index.html', headers={'Cache-Control':'no-store'})
    return {'message':'前端尚未构建。运行 npm run build，或在开发模式访问 http://127.0.0.1:5173','docs':'/docs'}
