import numpy as np
from funnel_actuals import simulated_actuals, opportunity, AS_OF


def test_cohort_data_reconciles_and_has_no_future_events():
    summary,leads=simulated_actuals()
    assert leads['Lead ID'].is_unique
    for _,r in summary.iterrows():
        cohort=leads[leads.Cohort.eq(r.Cohort)&leads.Channel.eq(r.Channel)]
        assert len(cohort)==r.Leads
        assert cohort['Qualified date'].notna().sum()==r.Opportunities
        assert cohort['Funded date'].notna().sum()==r['Funded accounts']
    funded=leads[leads['Funded date'].notna()]
    assert (funded['Funded date']>=funded['Qualified date']).all()
    assert (funded['Funded date']<=AS_OF).all()
    assert ((funded['Funded date']-funded['Lead date']).dt.days<=60).all()
    assert set(summary[summary.Mature].Cohort.dt.month)==set(range(1,7))
    assert summary[summary.Channel.isin(['Partnerships','Organic & referral'])].Impressions.isna().all()


def test_opportunity_is_single_stage_and_nonnegative():
    s,_=simulated_actuals();r=s.iloc[0]
    assert np.isclose(opportunity(r,'Opportunity → funded',1),r.Opportunities-r['Funded accounts'])
    assert opportunity(r,'Opportunity → funded',0)==0
    assert np.isclose(opportunity(r,'Lead → opportunity',1),(r.Leads-r.Opportunities)*r['Close %'])


def test_performance_page_and_target_edit():
    from streamlit.testing.v1 import AppTest
    from pathlib import Path
    app=AppTest.from_file(str(Path(__file__).with_name('app.py'))).run(timeout=45)
    app.sidebar.radio[0].set_value('Funnel performance').run(timeout=45)
    assert not app.exception
    assert any('Actual channel scorecard'==h.value for h in app.subheader)
    next(s for s in app.selectbox if s.label=='Channel to diagnose').set_value('Paid social').run(timeout=45)
    assert any('Paid social · monthly performance'==h.value for h in app.subheader)
    next(s for s in app.selectbox if s.label=='Compare channels on').set_value('CAC').run(timeout=45)
    assert not app.exception
    assert len(next(s for s in app.selectbox if s.label=='Lead acquisition cohort').options)==6
    target=next(n for n in app.number_input if n.label=='Achievable conversion target (%)')
    target.set_value(50.).run(timeout=45)
    assert not app.exception
    assert float(app.metric[-3].value.replace(',',''))>0
