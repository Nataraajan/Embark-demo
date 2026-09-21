import numpy as np
import pandas as pd
import pytest
from pathlib import Path
from planning_model import Drivers, PRESETS, forecast, unit_economics, funnel_bridge, channel_month


@pytest.mark.parametrize('case', list(PRESETS))
def test_financial_reconciliations_and_fixed_actuals(case):
    f,c=forecast(Drivers(**PRESETS[case])); baseline,_=forecast()
    pd.testing.assert_frame_equal(f.iloc[:6],baseline.iloc[:6])
    np.testing.assert_allclose(f.Ending_AUM, f.Beginning_AUM+f.Contributions-f.Redemptions+f.Market_return-f.Revenue)
    np.testing.assert_allclose(f.Active_accounts,f.Beginning_accounts-f.Account_exits+f.Funded_accounts)
    np.testing.assert_allclose(f.Revenue_less_marketing,f.Revenue-f.Marketing)
    np.testing.assert_allclose(f.Beginning_AUM.iloc[1:],f.Ending_AUM.iloc[:-1])
    np.testing.assert_allclose(f.Funded_accounts,c.groupby('Month')['Funded accounts'].sum())
    assert (f.Ending_AUM>0).all()


def test_transfer_preserves_spend_and_changes_revenue():
    a,_=forecast(); b,_=forecast(Drivers(shift=20000))
    np.testing.assert_allclose(a.Marketing,b.Marketing)
    assert b.Funded_accounts.sum()>a.Funded_accounts.sum()
    assert b.Revenue.sum()>a.Revenue.sum()


def test_budget_is_independent_and_funnel_bridge_reconciles():
    b,bc=forecast(budget=True); altered,_=forecast(Drivers(spend_change=.5),budget=True)
    pd.testing.assert_frame_equal(b,altered)
    a,ac=forecast()
    bridge=funnel_bridge(bc.iloc[:24],ac.iloc[:24])
    assert abs(bridge.sum()-(a.iloc[:6].Funded_accounts.sum()-b.iloc[:6].Funded_accounts.sum()))<1e-8


def test_zero_fee_zero_forecast_revenue_and_no_contribution_as_revenue():
    f,_=forecast(Drivers(fee=0))
    assert (f.Revenue.iloc[6:]==0).all()
    assert (f.Contributions.iloc[6:]>0).all()
    e=unit_economics(Drivers(fee=0))
    assert (e['Revenue LTV']==0).all()
    assert e['Payback months'].isna().all()


def test_revenue_only_economics_and_export_schema():
    from dataclasses import asdict
    from planning_model import CHANNELS
    d=Drivers()
    f,_=forecast(d,channels=CHANNELS)
    e=unit_economics(d,channels=CHANNELS,discount=0)
    np.testing.assert_allclose(e['Revenue LTV'],e['Lifetime fee revenue'])
    np.testing.assert_allclose(e['Acquisition CAC'],e['Media CAC'])
    np.testing.assert_allclose(f.Revenue_less_marketing,f.Revenue-f.Marketing)
    assert not {'Service_cost','Sales_cost','Fixed_opex','Opex','Operating_contribution'} & set(f.columns)
    assert not {'service_cost','sales_cost','fixed_opex'} & set(asdict(d))


def test_conversion_and_cashflow_sensitivity():
    a,_=forecast(); higher,_=forecast(Drivers(close_lift=.03)); lower,_=forecast(Drivers(contribution_lift=-.2))
    assert higher.Funded_accounts.sum()>a.Funded_accounts.sum()
    assert higher.Revenue.sum()>a.Revenue.sum()
    assert lower.Revenue.sum()<a.Revenue.sum()


def test_direct_inputs_lifetime_and_arpa():
    from planning_model import CHANNELS
    c=CHANNELS.copy()
    a,ac=forecast(channels=c)
    c.loc[0,'Spend']=240000
    f,ch=forecast(channels=c)
    july=ch[ch.Month.eq('2026-07-01')].iloc[0]
    assert july.Spend==240000
    assert abs(july['Funded accounts']-980)<1e-8
    pd.testing.assert_frame_equal(a.iloc[:6],f.iloc[:6])
    np.testing.assert_allclose(f.Ending_AUM,f.Beginning_AUM+f.Contributions-f.Redemptions+f.Market_return-f.Revenue)
    np.testing.assert_allclose(f.Active_accounts,f.Beginning_accounts-f.Account_exits+f.Funded_accounts)
    e=unit_economics(channels=c)
    np.testing.assert_allclose(e['Lifetime fee revenue'],e['Monthly ARPA']*e['Lifetime years']*12)
    c['Lifetime years']=1
    shorter,_=forecast(channels=c)
    se=unit_economics(channels=c)
    assert shorter.Active_accounts.iloc[-1]<f.Active_accounts.iloc[-1]
    assert shorter.Revenue.iloc[-1]<f.Revenue.iloc[-1]
    assert (se['Revenue LTV']<e['Revenue LTV']).all()
    assert Drivers().fee==.0165


def test_zero_channel_inputs():
    from planning_model import CHANNELS
    c=CHANNELS.copy();c['Spend']=0;c['Inbound volume']=0
    f,ch=forecast(channels=c)
    assert (f.Funded_accounts.iloc[6:]==0).all()
    assert f.CAC.iloc[6:].isna().all()


def test_nonpaid_volume_is_independent_of_cost():
    from planning_model import CHANNELS
    c=CHANNELS.copy()
    base=channel_month(6,channels=c)
    c.loc[2:3,'Spend']*=2
    changed=channel_month(6,channels=c)
    np.testing.assert_allclose(base.loc[2:3,'Funded accounts'],changed.loc[2:3,'Funded accounts'])
    np.testing.assert_allclose(base.loc[2:3,'CAC']*2,changed.loc[2:3,'CAC'])
    assert changed.loc[2:3,'Impressions'].isna().all()
    c.loc[2:3,'Inbound volume']*=2
    more=channel_month(6,channels=c)
    np.testing.assert_allclose(more.loc[2:3,'Funded accounts'],base.loc[2:3,'Funded accounts']*2)
    assert base.loc[2,'Leads']==3000
    assert base.loc[3,'Leads']==2250


def test_app_navigation_and_direct_edit():
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_file(str(Path(__file__).with_name('app.py'))).run(timeout=30)
    assert not app.exception
    assert app.number_input(key='input_fee').value==1.65
    assert len([n for n in app.number_input if n.label=='Cost per 1,000 impressions ($)'])==2
    assert app.number_input(key='input_2_inbound').value==3000
    assert app.number_input(key='input_3_inbound').value==75000
    for page in ['Funnel & channel ROI','Scenario lab','Forecast & variance','Model & definitions']:
        app.sidebar.radio[0].set_value(page).run(timeout=30)
        assert not app.exception,page
    app.sidebar.radio[0].set_value('Scenario lab').run(timeout=30)
    app.number_input(key='input_0_spend').set_value(240000.).run(timeout=30)
    assert not app.exception
    assert float(app.metric[0].value.replace(',',''))>0
    app.number_input(key='input_0_life').set_value(2).run(timeout=30)
    assert not app.exception
    app.sidebar.radio[0].set_value('Executive overview').run(timeout=30)
    assert app.number_input(key='input_0_spend').value==240000
    app.sidebar.button[0].click().run(timeout=30)
    assert app.number_input(key='input_0_spend').value==120000
