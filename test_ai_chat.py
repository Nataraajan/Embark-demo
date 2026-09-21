import copy
import pandas as pd
import pytest
from planning_model import Drivers,CHANNELS,forecast,unit_economics
from ai_chat import compare_scenario,answer,snapshot


def test_scenario_uses_engine_and_does_not_mutate():
    c=CHANNELS.copy();original=c.copy()
    result=compare_scenario(Drivers(),c,.1,[{'channel':'Paid search','field':'Spend','value':240000}],{})
    assert result['periods']['H2 2026']['Funded_accounts']['change']==pytest.approx(2940)
    pd.testing.assert_frame_equal(c,original)
    assert result['status'].startswith('Preview only')


@pytest.mark.parametrize('change',[
    {'channel':'Partnerships','field':'CPM','value':3},
    {'channel':'Paid search','field':'Spend','value':-1},
    {'channel':'Paid social','field':'Close rate','value':25},
    {'channel':'Paid search','field':'Spend','value':float('nan')},
    {'channel':'Organic & referral','field':'__code__','value':1},
])
def test_invalid_changes_are_rejected(change):
    with pytest.raises(ValueError):compare_scenario(Drivers(),CHANNELS,.1,[change],{})


def test_tool_roundtrip_and_snapshot_is_current():
    calls=[]
    def fake(payload,key):
        calls.append(copy.deepcopy(payload))
        if len(calls)==1:return {'content':[{'type':'tool_use','id':'test1','name':'compare_scenario','input':{'channel_changes':[{'channel':'Paid search','field':'Spend','value':150000}],'financial_changes':{}}}]}
        assert 'tool_result'==payload['messages'][-1]['content'][0]['type']
        return {'content':[{'type':'text','text':'This is a calculated preview.'}]}
    d=Drivers();f,_=forecast(d,channels=CHANNELS);e=unit_economics(d,channels=CHANNELS)
    text,previews=answer('What if search is $150k?',[],snapshot(d,CHANNELS,.1,f,e,'Scenario lab'),d,CHANNELS,.1,'test-key','mock',fake)
    assert len(previews)==1 and 'preview' in text
    assert 'CURRENT_SNAPSHOT' in calls[0]['system']
    assert 'test-key' not in str(calls)


def test_chat_visible_without_network_call():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_file(str(Path(__file__).with_name('app.py'))).run(timeout=45)
    assert not app.exception
    assert len(app.chat_input)==0
    app.button(key='ai_toggle').click().run()
    assert not app.exception
    assert len(app.chat_input)==1
    assert len(app.text_input)==0
    app.button(key='ai_toggle').click().run()
    assert len(app.chat_input)==0
