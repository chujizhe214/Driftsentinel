import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from backend.analytics import read_csv, generate, distribution, detect, profile, load_predictor, evaluate, validate_output, calibration

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def frame():
    return pd.DataFrame({'value':np.arange(100,dtype=float),'group':['a']*50+['b']*50,'label':['no','yes']*50})


def test_csv_handles_quoted_multiline_and_bom():
    content='\ufeffvalue,group,label\n'+''.join(f'{i},"a,b\ninside",{i%2}\n' for i in range(30))
    result=read_csv(content.encode('utf-8'))
    assert len(result)==30
    assert result.group.iloc[0]=='a,b\ninside'


@pytest.mark.parametrize('text',['a,a\n1,2\n','a,b\n1,2,3\n','just a single column\n1\n','a,b\n'])
def test_csv_rejects_invalid_input(text):
    with pytest.raises(ValueError):
        read_csv(text.encode())


def test_profile_counts_missing_duplicates(frame):
    frame.loc[0,'value']=np.nan
    combined=pd.concat([frame,frame.iloc[[1]]],ignore_index=True)
    result=profile(combined)
    assert result['duplicates']==1
    assert result['fields'][0]['missing']==pytest.approx(1/101)


def test_identical_data_psi_zero_and_new_values_finite(frame):
    assert distribution(frame.value,frame.value,'numeric')['psi']==pytest.approx(0)
    shifted=frame.value+1000
    assert np.isfinite(distribution(frame.value,shifted,'numeric')['psi'])
    assert distribution(frame.value,shifted,'numeric')['psi']>1


@pytest.mark.parametrize('typ,strength',[('mean_shift',20),('variance',80),('missing',30),('outlier',10),('categorical',75)])
def test_scenarios_are_reproducible_and_do_not_mutate(frame,typ,strength):
    field='group' if typ=='categorical' else 'value'
    config={'type':typ,'field':field,'strength':strength,'category':'a'}
    original=frame.copy(deep=True)
    pd.testing.assert_frame_equal(generate(frame,config,42),generate(frame,config,42))
    pd.testing.assert_frame_equal(frame,original)


def test_variance_mean_and_missing_targets(frame):
    changed=generate(frame,{'type':'variance','field':'value','strength':100},42)
    assert changed.value.mean()==pytest.approx(frame.value.mean())
    assert changed.value.var()==pytest.approx(frame.value.var()*2)
    missing=generate(frame,{'type':'missing','field':'value','strength':25},42)
    assert missing.value.isna().mean()==pytest.approx(.25)


def test_categorical_resamples_whole_rows(frame):
    changed=generate(frame,{'type':'categorical','field':'group','strength':80,'category':'a'},42)
    assert (changed.group=='a').mean()==.8
    assert (changed.group.to_numpy()==np.where(changed.value.to_numpy()<50,'a','b')).all()


def test_label_excluded_from_detectors(frame):
    rules={'warning':.2,'critical':.3,'pvalue':.05,'missing':.1}
    result=detect(frame,frame,'label',rules)
    assert {f['name'] for f in result}=={'value','group'}
    assert all(f['psi']==0 and f['risk']=='stable' for f in result)


def test_exported_model_matches_sklearn_and_reference_metrics():
    data=json.loads((ROOT/'public/demo/model.json').read_text())
    model={'id':data['id'],'kind':'builtin','path':str(ROOT/'public/demo/model.json'),'positiveClass':'yes','negativeClass':'no'}
    predictor=load_predictor(model)
    rows=pd.DataFrame([p['row'] for p in data['parityRows']])
    _,proba=predictor(rows)
    np.testing.assert_allclose(proba,[p['probability'] for p in data['parityRows']],atol=1e-12)
    reference=pd.read_csv(ROOT/'public/demo/bank_reference.csv')
    metrics=evaluate(reference,'y',model,predictor)['metrics']
    for key in ('f1','recall','auc'):
        assert metrics[key]==pytest.approx(data['referenceMetrics'][key],abs=1e-12)
    assert evaluate(reference,None,model,predictor)['metrics'] is None


def test_invalid_prediction_shapes_and_probabilities():
    model={'positiveClass':'1','negativeClass':'0'}
    with pytest.raises(ValueError,match='一维'):
        validate_output(np.ones((4,1)),None,4,model)
    with pytest.raises(ValueError,match='概率'):
        validate_output(np.ones(4),np.array([.5,.5,np.nan,.4]),4,model)


def test_calibration_no_labels_cannot_claim_recommendation():
    assert not calibration([],None,{'impact':.03})['available']
