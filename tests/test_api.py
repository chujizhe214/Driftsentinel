import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend import storage
from backend.app import app


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DATA_DIR',tmp_path)
    with TestClient(app) as client:
        yield client


def run(client,payload):
    response=client.post('/api/experiments',json=payload)
    assert response.status_code==202,response.text
    key=response.json()['id']
    for _ in range(100):
        result=client.get('/api/experiments/'+key).json()
        if result['status'] not in ('running','queued'):
            return result
        time.sleep(.05)
    pytest.fail('Experiment timeout')


def request(**overrides):
    return {'name':'API test','dataset_id':'bank-reference','model_id':'bank-logistic-v1','label':'y','seed':42,
            'samples':300,'sweep':True,'scenarios':[{'id':'missing','type':'missing','field':'duration','strength':50,'enabled':True}],**overrides}


def test_full_experiment_persistence_and_exports(client):
    assert client.get('/api/health').json()['status']=='ok'
    assert len(client.get('/api/datasets').json())==1
    result=run(client,request())
    assert result['status']=='completed',result
    assert result['result']['baseline']['metrics']['f1']>0
    assert len(result['result']['scenarios'])==4
    assert result['result']['calibration']['available']
    json_export=client.get(f'/api/experiments/{result["id"]}/export?format=json')
    assert json_export.status_code==200
    assert 'duration' in json_export.json()['features']
    assert 'model_weights' not in json_export.text
    assert 'monitor_window:' in client.get(f'/api/experiments/{result["id"]}/export?format=yaml').text
    assert '# API test' in client.get(f'/api/experiments/{result["id"]}/export?format=report').text
    assert client.get('/api/experiments').json()[0]['summary']['scenarios']==4
    again=run(client,request())
    assert again['result']['scenarios']==result['result']['scenarios']


def test_no_label_has_no_metrics_or_calibration(client):
    result=run(client,request(label=None,sweep=False))
    assert result['status']=='completed',result
    assert result['result']['baseline']['metrics'] is None
    assert not result['result']['calibration']['available']


def test_combined_scenario_changes_multiple_fields(client):
    scenarios=[{'id':'age','type':'mean_shift','field':'age','strength':40,'enabled':True},
               {'id':'duration','type':'missing','field':'duration','strength':50,'enabled':True}]
    result=run(client,request(sweep=False,combine=True,scenarios=scenarios))
    assert result['status']=='completed',result
    combined=result['result']['scenarios'][-1]
    assert combined['type']=='combined'
    fields={f['name']:f for f in combined['fields']}
    assert fields['age']['psi']>.1
    assert fields['duration']['missing']==pytest.approx(.5)


def test_csv_upload_profile_and_data_only(client):
    content='value,group,label\n'+''.join(f'{i},{"a" if i%2 else "b"},{i%2}\n' for i in range(60))
    response=client.post('/api/datasets',files={'file':('custom.csv',content,'text/csv')})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['profile']['rows']==60
    result=run(client,request(dataset_id=data['id'],model_id=None,label='label',samples=60,sweep=False,
                              scenarios=[{'id':'shift','type':'mean_shift','field':'value','strength':20}]))
    assert result['status']=='completed',result
    assert result['result']['baseline'] is None
    assert client.delete('/api/datasets/'+data['id']).status_code==200
    assert client.get('/api/experiments/'+result['id']).json()['status']=='completed'


def test_validation_errors_do_not_crash_service(client):
    assert client.post('/api/datasets',files={'file':('bad.csv','x,x\n1,2\n','text/csv')}).status_code==422
    assert client.put('/api/rules',json={'warning':.4,'critical':.2}).status_code==422
    assert client.post('/api/experiments',json=request(scenarios=[{'id':'bad','type':'mean_shift','field':'y','strength':20}])).status_code==422
    assert client.delete('/api/datasets/bank-reference').status_code==409


@pytest.mark.parametrize('mode',['stress','compare'])
def test_builtin_input_feature_cannot_be_used_as_label(client,mode):
    payload=request(label='job',mode=mode,sweep=False)
    if mode=='compare':
        import pandas as pd
        frame=pd.read_csv(Path(__file__).resolve().parents[1]/'public/demo/bank_reference.csv').head(60)
        payload.update(current_dataset_id=upload(client,'current.csv',frame),scenarios=[])
    response=client.post('/api/experiments',json=payload)
    assert response.status_code==422,response.text
    assert 'job' in response.json()['detail']
    assert '不能同时作为标签' in response.json()['detail']
    assert client.get('/api/experiments').json()==[]
    # Choosing a label remains valid without a model that requires it as input.
    result=run(client,{**payload,'model_id':None})
    assert result['status']=='completed',result
    assert result['result']['baseline'] is None


def test_local_adapter_output_validation(client,tmp_path):
    path=tmp_path/'adapter.py'
    path.write_text('import numpy as np\ndef predict(X):\n    return np.zeros(len(X), dtype=int)\n')
    payload={'name':'Local adapter','version':'1.0','path':str(path),'consent':True}
    model=client.post('/api/models',json=payload)
    assert model.status_code==200,model.text
    key=model.json()['id']
    validation=client.post(f'/api/models/{key}/validate',json={'dataset_id':'bank-reference'})
    assert validation.status_code==200,validation.text
    assert validation.json()['hasProba'] is False
    path.write_text('import numpy as np\ndef predict(X):\n    return np.zeros((len(X), 3))\n')
    assert client.post(f'/api/models/{key}/validate',json={'dataset_id':'bank-reference'}).status_code==422


@pytest.mark.parametrize('probability',[False,True])
def test_downloaded_adapter_runs_with_matching_model(client,tmp_path,probability):
    import pandas as pd
    from joblib import dump
    from sklearn.linear_model import LogisticRegression
    from sklearn.svm import LinearSVC
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    frame=pd.DataFrame({'value':range(60),'other':[i%3 for i in range(60)],'label':[int(i>=30) for i in range(60)]})
    dataset_id=upload(client,'template-validation.csv',frame)
    estimator=LogisticRegression() if probability else LinearSVC()
    model=make_pipeline(StandardScaler(),estimator).fit(frame[['value','other']],frame['label'])
    assert hasattr(model,'predict_proba') is probability
    dump(model,tmp_path/'model.joblib')
    response=client.get('/api/adapter-template',params={'probability':str(probability).lower()})
    assert response.status_code==200
    filename='model_adapter_proba.py' if probability else 'model_adapter.py'
    assert f'filename="{filename}"' in response.headers['content-disposition']
    path=tmp_path/filename
    path.write_text(response.text,encoding='utf-8')
    registered=client.post('/api/models',json={'name':'Downloaded template','version':'1.0','path':str(path),'consent':True})
    assert registered.status_code==200,registered.text
    model_id=registered.json()['id']
    validated=client.post(f'/api/models/{model_id}/validate',json={'dataset_id':dataset_id})
    assert validated.status_code==200,validated.text
    assert validated.json()['hasProba'] is probability
    result=run(client,request(dataset_id=dataset_id,model_id=model_id,label='label',samples=60,sweep=False,
                              scenarios=[{'id':'shift','type':'mean_shift','field':'value','strength':20}]))
    assert result['status']=='completed',result
    evaluation=result['result']['baseline']
    assert evaluation['metrics']['f1']>.9
    assert (evaluation['probability'] is not None) is probability
    assert (evaluation['metrics']['auc'] is not None) is probability


def test_adapter_template_defaults_and_invalid_probability(client):
    assert 'def predict_proba(X):' in client.get('/api/adapter-template').text
    assert client.get('/api/adapter-template?probability=invalid').status_code==422


def test_rules_persist_and_affect_exports(client):
    rules=client.get('/api/rules').json()
    rules['warning']=.18
    assert client.put('/api/rules',json=rules).status_code==200
    assert client.get('/api/rules').json()['warning']==.18


def test_builtin_model_path_recovers_when_workspace_moves(client):
    import importlib
    module=importlib.import_module('backend.app')
    model=storage.get('models','bank-logistic-v1')
    model['path']='C:/old-machine/demo/model.json'
    storage.put('models',model)
    module.bootstrap()
    updated=storage.get('models','bank-logistic-v1')
    assert Path(updated['path']).is_file()
    assert updated['createdAt']==model['createdAt']


@pytest.mark.parametrize('old_role', [None, 'current'])
def test_builtin_dataset_role_is_restored_and_protected(client, old_role):
    from backend.app import bootstrap

    dataset = storage.get('datasets', 'bank-reference')
    assert dataset['role'] == 'reference'
    dataset['role'] = old_role
    storage.put('datasets', dataset)

    bootstrap()

    assert storage.get('datasets', dataset['id']) == {**dataset, 'role': 'reference'}
    path = '/api/datasets/' + dataset['id']
    assert client.patch(path, json={'role': 'current'}).status_code == 422
    assert client.patch(path, json={'label': None}).json()['role'] == 'reference'


def test_running_experiment_can_be_cancelled(client,monkeypatch):
    import importlib
    module=importlib.import_module('backend.app')
    def slow_run(_frame,_model,_request,progress,cancelled):
        progress(10,'Cancelable test step')
        while not cancelled():
            time.sleep(.01)
        raise InterruptedError('实验已取消')
    monkeypatch.setattr(module,'run_experiment',slow_run)
    response=client.post('/api/experiments',json=request())
    assert response.status_code==202
    key=response.json()['id']
    assert client.post('/api/experiments/'+key+'/cancel').status_code==200
    for _ in range(100):
        item=client.get('/api/experiments/'+key).json()
        if item['status']=='cancelled':
            break
        time.sleep(.01)
    assert item['status']=='cancelled'
    assert item['result'] is None


def test_restart_keeps_results_and_marks_interrupted_work_failed(client):
    completed=run(client,request(sweep=False))
    storage.put('experiments',{'id':'interrupted','status':'running','name':'interrupted'})
    storage.init_db()
    assert storage.get('experiments',completed['id'])['result'] is not None
    assert storage.get('experiments','interrupted')['status']=='failed'


def upload(client, name, frame):
    response=client.post('/api/datasets',files={'file':(name,frame.to_csv(index=False),'text/csv')})
    assert response.status_code==200,response.text
    return response.json()['id']


def test_real_comparison_keeps_reference_uses_all_rows_and_persists(client):
    import pandas as pd
    reference=pd.DataFrame({'value':range(60),'group':['a','b','c']*20})
    current=pd.DataFrame({'group':['c']*90,'value':range(1000,1090),'batch':['today']*90})
    ref_id=upload(client,'normal.csv',reference)
    cur_id=upload(client,'today.csv',current)
    payload=request(mode='compare',dataset_id=ref_id,current_dataset_id=cur_id,model_id=None,label=None,
                    current_label=None,samples=30,scenarios=[],sweep=True,combine=True)
    result=run(client,payload)
    assert result['status']=='completed',result
    data=result['result']
    assert result['datasetName']=='normal'
    assert result['currentDatasetName']=='today'
    assert data['rows']==60 and data['currentRows']==90
    assert data['baseline'] is None and data['scenarios'][0]['evaluation'] is None
    assert len(data['scenarios'])==1 and data['scenarios'][0]['type']=='observed'
    assert data['scenarios'][0]['maxPsi']>1
    assert data['ignoredFields']==['batch'] and len(data['warnings'])==2
    assert not data['calibration']['available']
    assert result['request']['samples'] is None
    assert result['request']['scenarios']==[] and not result['request']['sweep'] and not result['request']['combine']
    config=client.get(f'/api/experiments/{result["id"]}/export?format=json').json()
    assert config['mode']=='compare' and config['task_type']=='data_drift'
    assert config['reference']['dataset_id']==ref_id and config['current']['rows']==90
    report=client.get(f'/api/experiments/{result["id"]}/export?format=report').text
    assert 'today（90 行）' in report and '基准缺失率' in report and 'batch' in report
    assert 'normal（60 行）' in report
    tomorrow=upload(client,'tomorrow.csv',reference)
    stable=run(client,{**payload,'current_dataset_id':tomorrow})
    assert stable['status']=='completed',stable
    assert all(field['psi']==0 for field in stable['result']['scenarios'][0]['fields'])
    assert client.get('/api/experiments/'+result['id']).json()['currentDatasetName']=='today'
    again=run(client,result['request'])
    assert again['result']['scenarios']==data['scenarios']
    assert client.delete('/api/datasets/'+cur_id).status_code==200
    storage.init_db()
    assert client.get('/api/experiments/'+result['id']).json()['result']['currentRows']==90


@pytest.mark.parametrize('problem',['same','absent','missing_field','bad_numeric','bad_label','label_is_feature'])
def test_real_comparison_validates_both_datasets(client,problem):
    import pandas as pd
    reference=pd.DataFrame({'value':range(60),'group':['a','b','c']*20})
    ref_id=upload(client,'ref.csv',reference)
    current=reference.copy()
    if problem=='missing_field':
        current=current.rename(columns={'value':'wrong'})
    if problem=='bad_numeric':
        current['value']=current['value'].astype(str)
        current.loc[0,'value']='not a number'
    cur_id=upload(client,'current.csv',current)
    payload=request(mode='compare',dataset_id=ref_id,current_dataset_id=cur_id,model_id=None,label=None,scenarios=[])
    if problem=='same': payload['current_dataset_id']=ref_id
    if problem=='absent': payload['current_dataset_id']=None
    if problem=='bad_label': payload['current_label']='absent_label'
    if problem=='label_is_feature': payload['current_label']='value'
    response=client.post('/api/experiments',json=payload)
    assert response.status_code==422,response.text
    assert client.get('/api/experiments').json()==[]


def test_real_comparison_model_labels_are_independent_and_not_in_features(client):
    import pandas as pd
    frame=pd.read_csv(Path(__file__).resolve().parents[1]/'public/demo/bank_reference.csv').head(120)
    current=frame.rename(columns={'y':'actual_result'})
    cur_id=upload(client,'observed.csv',current)
    payload=request(mode='compare',current_dataset_id=cur_id,scenarios=[],samples=30)
    no_truth=run(client,payload)
    assert no_truth['status']=='completed',no_truth
    result=no_truth['result']
    assert result['baseline']['metrics'] is not None
    assert result['scenarios'][0]['evaluation']['metrics'] is None
    assert result['scenarios'][0]['f1Drop'] is None
    assert 'actual_result' in result['ignoredFields']
    labelled=run(client,{**payload,'current_label':'actual_result'})
    assert labelled['status']=='completed',labelled
    data=labelled['result']
    assert data['scenarios'][0]['evaluation']['metrics']['f1']>=0
    assert data['scenarios'][0]['f1Drop'] is not None
    assert {f['name'] for f in data['scenarios'][0]['fields']}==set(frame.columns)-{'y'}
    assert data['ignoredFields']==[]
    assert not data['calibration']['available']
    # A missing current label column is valid, and an entirely missing numeric field is detected.
    current=frame.drop(columns='y')
    current['duration']=float('nan')
    cur_id=upload(client,'unlabelled.csv',current)
    unlabelled=run(client,{**payload,'current_dataset_id':cur_id,'model_id':None})
    assert unlabelled['status']=='completed',unlabelled
    duration=next(f for f in unlabelled['result']['scenarios'][0]['fields'] if f['name']=='duration')
    assert duration['missing']==1 and duration['risk']=='critical'
