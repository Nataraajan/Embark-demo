from dataclasses import asdict
from html import escape
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import importlib
import planning_model
importlib.reload(planning_model)
import funnel_actuals
# Refresh local calculations before rendering the live page.
render_actuals = importlib.reload(funnel_actuals).render_actuals
import ai_chat
render_chat = importlib.reload(ai_chat).render_chat
from planning_model import stage_labels, BASE, CHANNELS, Drivers, PRESETS, forecast, annual, unit_economics, funnel_bridge

st.set_page_config(page_title='Embark | Growth & Financial Planning', page_icon='↗', layout='wide')
NAVY, TEAL, ORANGE, GRAY = '#1c1463', '#594ff0', '#db744e', '#9c96bb'
COLORS = [TEAL, ORANGE, '#4276dd', '#a77adc']
st.markdown('''<style>
.stApp{background:#f7f6fc;color:#1c1463}header[data-testid="stHeader"]{background:transparent;height:0}
.block-container{padding:1.4rem 2.1rem 3rem;max-width:1800px}
[data-testid="stSidebar"]{background:#241970;min-width:240px;max-width:260px}
[data-testid="stSidebar"] *{color:#edeaff}
[data-testid="stSidebar"] [data-baseweb="select"] *{color:#1c1463}
[data-testid="stSidebar"] input{color:#1c1463}
[data-testid="stSidebar"] button p{color:#1c1463!important}
[data-testid="stSidebar"] .pill{color:#5146b8!important}
h1{font-size:2.15rem!important;letter-spacing:-.055em;font-weight:650!important;padding:0!important}
h2{font-size:1.25rem!important;letter-spacing:-.02em}h3{font-size:1.06rem!important}
.eyebrow{font-size:.72rem;letter-spacing:.15em;text-transform:uppercase;color:#676080;font-weight:650;margin-bottom:8px}
.sub{color:#6d6689;font-size:.9rem;margin:8px 0 22px}
.brand{font-size:2rem;letter-spacing:-.06em;color:#fff;margin:0}.brand small{font-size:.65rem;letter-spacing:.2em;display:block;color:#b9b0f1;margin-top:5px}
.sidefoot{font-size:.75rem;line-height:1.8;color:#c8c0e9;margin-top:35px;border-top:1px solid #514887;padding-top:18px}
.pill{border:1px solid #d9d3f1;background:#eeebfc;border-radius:30px;padding:7px 13px;color:#5146b8;font-size:.73rem;display:inline-block}
.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:8px 0 22px}
.card{background:#fff;border:1px solid #e5e0f2;border-radius:14px;padding:20px 22px;min-width:0;overflow:hidden}
.card.hero{background:#35267d;border-color:#35267d;color:#fff}.card.hero .muted{color:#ddd6ff}
.label{font-size:.77rem;font-weight:600;letter-spacing:.02em}.value{font-size:2rem;font-weight:650;letter-spacing:-.045em;margin:10px 0 4px;white-space:nowrap}
.muted{font-size:.72rem;color:#706889;line-height:1.5}.delta{font-size:.76rem;margin-top:10px}.good{color:#594ff0}.bad{color:#be5b40}.hero .good{color:#d8f388}.hero .bad{color:#ffc4a8}
.brief{background:#eeebfc;border-left:4px solid #594ff0;padding:17px 20px;border-radius:0 10px 10px 0;margin:10px 0 18px;font-size:.88rem;line-height:1.6}
.brief strong{color:#403297}.stage{background:#fff;border:1px solid #e1dbef;padding:17px;border-radius:10px;margin:6px 0}.stage b{font-size:1.45rem;display:block;margin:6px 0}
div[data-testid="stVerticalBlockBorderWrapper"]>div{background:white;border-color:#e1dbef!important;border-radius:14px!important}
[data-testid="stMetric"]{padding:14px;border:1px solid #e1dbef;border-radius:10px;background:#fff}
[data-testid="stMetricValue"]{font-size:1.6rem}
[data-testid="stCaptionContainer"]{color:#6b6285}
[data-testid="stCaptionContainer"] p{color:#6b6285!important;opacity:1!important}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p{color:#c8c0e9!important}
[data-testid="stNumberInputContainer"], [data-baseweb="select"]>div{background:#efecf8!important}
[data-testid="stChatMessage"]{background:#f0edfb;border:1px solid #e0d9f5;border-radius:12px}
button[kind="primary"]{background:#594ff0;border-color:#594ff0}
@media(max-width:1100px){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}.value{font-size:1.6rem}.block-container{padding:1rem}}
</style>''', unsafe_allow_html=True)


def money(n):
    if not np.isfinite(n): return '—'
    if n < 0: return '-' + money(-n)
    if abs(n) >= 1e9: return f'${n/1e9:,.2f}B'
    if abs(n) >= 1e6: return f'${n/1e6:,.2f}M'
    if abs(n) >= 1e3: return f'${n/1e3:,.0f}K'
    return f'${n:,.0f}'


def spark(values, color=TEAL):
    a = np.asarray(values, dtype=float)
    y = 34 - 29 * (a - a.min()) / max(float(np.ptp(a)), 1e-9)
    points = ' '.join(f'{i*220/max(1,len(a)-1):.1f},{v:.1f}' for i,v in enumerate(y))
    return f'<svg viewBox="0 0 220 39" width="100%" height="39" style="margin-top:10px" aria-label="Monthly trend"><polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.3"/></svg>'


def card(label, value, foot, delta, trend, hero=False, favorable=True):
    return f'<div class="card {"hero" if hero else ""}"><div class="label">{label}</div><div class="value">{value}</div><div class="muted">{foot}</div>{spark(trend,"#d8f388" if hero else TEAL)}<div class="delta {"good" if favorable else "bad"}">{delta}</div></div>'


def chart(fig, height=310):
    fig.update_layout(height=height, margin=dict(l=12,r=12,t=25,b=15), plot_bgcolor='white', paper_bgcolor='white',
        font=dict(family='Arial',color=NAVY,size=11), legend=dict(orientation='h',y=1.16,x=0),
        hovermode='x unified', xaxis=dict(showgrid=False), yaxis=dict(gridcolor='#eeebf6',zeroline=False))
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})


def reset_inputs():
    for key in list(st.session_state):
        if key.startswith('input_'):
            del st.session_state[key]


with st.sidebar:
    st.markdown('<div class="brand">embark↗<small>GROWTH & FINANCIAL PLANNING</small></div>', unsafe_allow_html=True)
    page = st.radio('Workspace', ['Executive overview','Funnel performance','Funnel & channel ROI','Scenario lab','Forecast & variance','Model & definitions'], label_visibility='collapsed')
    st.divider()
    st.caption('DIRECT ASSUMPTIONS · JUL 2026 ONWARD')
    st.button('Reset to example assumptions', on_click=reset_inputs, use_container_width=True)
    st.markdown('<div class="sidefoot">All operating inputs are illustrative.<br>Management fee: 1.65% starting assumption.<br>CAD · 2026–2030<br>Jan–Jun are fixed simulated actuals.</div>', unsafe_allow_html=True)

st.markdown('<div class="eyebrow">Finance × Marketing × Sales</div>', unsafe_allow_html=True)
st.title({'Funnel performance':'Find the conversion gap. Size the opportunity.', 'Executive overview':'Turn growth drivers into financial decisions.', 'Funnel & channel ROI':'Follow the funnel. Find the economic return.', 'Scenario lab':'Test the next growth decision.', 'Forecast & variance':'Explain the gap. Update the outlook.', 'Model & definitions':'Every metric has a definition.'}[page])
st.markdown('<div class="sub">Channel-specific acquisition → funded accounts → assets → management-fee revenue</div>', unsafe_allow_html=True)

with st.expander('Edit assumptions · actual monthly amounts and conversion rates', expanded=page in ['Scenario lab','Funnel & channel ROI']):
    st.caption('Edit each channel directly. Percentages below are actual conversion rates, not changes from a hidden baseline. Monthly spend is flat unless you edit it.')
    inputs=[]
    for i, row in CHANNELS.iterrows():
        with st.container(border=True):
            st.subheader(row.Channel)
            c=st.columns(4)
            paid=row.Channel in ['Paid search','Paid social']
            partner=row.Channel=='Partnerships'
            labels=stage_labels(row.Channel)
            st.caption(' → '.join((['Impressions'] if paid else [] if partner else ['Organic / referral visits'])+labels))
            spend=c[0].number_input('Monthly spend ($)' if paid else 'Monthly program cost ($)',0.,10000000.,float(row.Spend),1000.,key=f'input_{i}_spend')
            inbound=0.
            if paid:
                cpm=c[1].number_input('Cost per 1,000 impressions ($)',.01,10000.,float(row.CPM),1.,key=f'input_{i}_cpm')
                lead=c[2].number_input('Impression → lead (%)',0.,100.,float(row['Lead rate']*100),.01,format='%.3f',key=f'input_{i}_lead')
            elif partner:
                cpm=np.nan; lead=100.
                inbound=c[1].number_input('Partner introductions / month',0.,1000000.,float(row['Inbound volume']),100.,key=f'input_{i}_inbound')
                c[2].caption('Introductions are entered directly. Program cost affects CAC and profit, not introduction volume automatically.')
            else:
                cpm=np.nan
                st.caption('This combined bucket assumes organic and referral customers arrive through inbound visits. Program cost is independent of visit volume.')
                inbound=c[1].number_input('Organic / referral visits / month',0.,10000000.,float(row['Inbound volume']),1000.,key=f'input_{i}_inbound')
                lead=c[2].number_input('Visit → enquiry (%)',0.,100.,float(row['Lead rate']*100),.1,key=f'input_{i}_visit_rate')
            opp=c[3].number_input('Lead → opportunity (%)' if paid else 'Introduction → application (%)' if partner else 'Enquiry → application (%)',0.,100.,float(row['Opportunity rate']*100),1.,key=f'input_{i}_opp')
            c=st.columns(4)
            close=c[0].number_input('Opportunity → funded (%)' if paid else 'Application → funded (%)',0.,100.,float(row['Close rate']*100),1.,key=f'input_{i}_close')
            initial=c[1].number_input('Initial contribution ($)',0.,100000.,float(row['Initial funding']),100.,key=f'input_{i}_initial')
            monthly=c[2].number_input('Recurring contribution ($ / month)',0.,10000.,float(row['Monthly contribution']),10.,key=f'input_{i}_monthly')
            life=c[3].number_input('Average customer lifetime (years)',1,30,int(row['Lifetime years']),1,key=f'input_{i}_life')
            inputs.append([row.Channel,spend,cpm,lead/100,opp/100,close/100,initial,monthly,float(life),inbound])
    st.subheader('Shared financial assumptions')
    c=st.columns(4)
    fee=c[0].number_input('Annual management fee (%)',0.,5.,1.65,.05,key='input_fee')
    returns=c[1].number_input('Annual investment return (%)',-40.,30.,4.,1.,key='input_return')
    withdrawals=c[2].number_input('Annual partial withdrawals (%)',0.,90.,8.,1.,key='input_withdrawals',help='Partial withdrawals while accounts remain open. Remaining assets also leave when customer lifetime ends.')
    discount=c[3].number_input('Annual LTV discount rate (%)',0.,30.,10.,1.,key='input_discount')
    st.caption('Lifetime is modeled as a fixed planning duration for each new cohort, with full account closure at its end. The same lifetime drives the forecast and LTV. Opening accounts retain their original illustrative 10-year lifetime.')

channels=pd.DataFrame(inputs,columns=CHANNELS.columns)
d=Drivers(fee=fee/100,annual_return=returns/100,annual_redemptions=withdrawals/100)
f,ch=forecast(d,channels=channels); b,bc=forecast(budget=True,channels=CHANNELS); base,_=forecast(channels=CHANNELS)
eco=unit_economics(d,channels=channels,discount=discount/100)

render_chat(d,channels,discount/100,f,eco,page)

y=f.iloc[:12]; by=b.iloc[:12]; fy=f.iloc[6:12]; baseline=base.iloc[6:12]
rev=y.Revenue.sum(); op=y.Revenue_less_marketing.sum(); sales=y.Funded_accounts.sum(); cac=y.Marketing.sum()/sales

if page=='Executive overview':
    st.markdown('<div class="eyebrow">2026 outlook · six months actual + six months forecast</div>', unsafe_allow_html=True)
    cards = card('Management-fee revenue',money(rev),'Full-year outlook · CAD',f'{money(rev-by.Revenue.sum())} vs budget',y.Revenue,True,rev>=by.Revenue.sum())
    cards += card('Revenue less marketing',money(op),'Fee revenue minus channel spend; excludes other business costs',f'{money(op-by.Revenue_less_marketing.sum())} vs budget',y.Revenue_less_marketing,favorable=op>=by.Revenue_less_marketing.sum())
    cards += card('New funded accounts',f'{sales:,.0f}','Full-year acquisitions',f'{sales/by.Funded_accounts.sum()-1:+.1%} vs budget',y.Funded_accounts,favorable=sales>=by.Funded_accounts.sum())
    cards += card('Acquisition cost',money(cac),'Marketing spend / funded accounts',f'{money(cac-by.Marketing.sum()/by.Funded_accounts.sum())} vs budget',y.CAC,favorable=cac<=by.Marketing.sum()/by.Funded_accounts.sum())
    st.markdown('<div class="cards">'+cards+'</div>',unsafe_allow_html=True)
    social=eco[eco.Channel=='Paid social'].iloc[0]; best=eco.sort_values('LTV / CAC',ascending=False).iloc[0]
    st.markdown(f'<div class="brief"><strong>Decision to take into the planning meeting</strong><br>Test a limited budget shift before scaling acquisition. Paid social returns <strong>{social["LTV / CAC"]:.1f}×</strong> modeled revenue LTV / acquisition CAC; {best.Channel.lower()} leads at <strong>{best["LTV / CAC"]:.1f}×</strong>. Validate channel capacity and cohort quality before treating these average economics as marginal returns.</div>',unsafe_allow_html=True)
    left,right=st.columns([1.55,1])
    with left,st.container(border=True):
        st.subheader('Fee revenue: budget to rolling forecast')
        fig=go.Figure()
        fig.add_scatter(x=by.Month,y=by.Revenue,name='Budget',line=dict(color=GRAY,dash='dot'))
        fig.add_scatter(x=y.Month.iloc[:6],y=y.Revenue.iloc[:6],name='Simulated actual',line=dict(color=NAVY,width=3))
        fig.add_scatter(x=y.Month.iloc[5:],y=y.Revenue.iloc[5:],name='Rolling forecast',line=dict(color=TEAL,width=3))
        fig.update_yaxes(tickprefix='$',tickformat='~s');chart(fig)
        st.caption('Customer contributions build assets. Revenue is the management fee earned on the modeled average asset base.')
    with right,st.container(border=True):
        st.subheader('Channel economics')
        fig=go.Figure(go.Bar(x=eco['LTV / CAC'],y=eco.Channel,orientation='h',marker_color=COLORS,text=eco['LTV / CAC'].map(lambda v:f'{v:.1f}×'),textposition='outside'))
        fig.add_vline(x=1,line_dash='dot',line_color=GRAY);fig.update_xaxes(title='Revenue LTV / acquisition CAC');chart(fig)
        st.caption('Revenue LTV excludes business costs and is not a profit measure. LTV follows the editable lifetime for each channel; it is not observed performance.')
    st.info('Use Funnel performance to diagnose simulated actuals by channel and test the value of closing a conversion gap.')

elif page=='Funnel performance':
    render_actuals(d,channels,discount,chart,money)

elif page=='Funnel & channel ROI':
    period=st.radio('Period',['Jul–Dec forecast','Jan–Jun simulated actuals'],horizontal=True)
    mask=ch.Month.dt.month.le(6)&ch.Month.dt.year.eq(2026) if period.startswith('Jan') else ch.Month.dt.month.gt(6)&ch.Month.dt.year.eq(2026)
    c=ch[mask]; totals=c[['Impressions','Leads','Opportunities','Funded accounts']].sum()
    cols=st.columns(4)
    for i,(label,v) in enumerate(totals.items()):
        rate='Paid channels only' if label=='Impressions' else 'Channel-specific entry stages' if label!='Funded accounts' else 'Shared outcome across channels'
        label={'Leads':'Leads / introductions','Opportunities':'Opportunities / applications'}.get(label,label)
        cols[i].markdown(f'<div class="stage"><span class="muted">{label}</span><b>{v:,.0f}</b><span class="muted">{rate}</span></div>',unsafe_allow_html=True)
    st.caption('Paid channels use impressions → leads → qualified opportunities; partnerships use introductions → applications; organic/referral uses visits → enquiries → applications. All end in funded accounts. Non-paid costs do not automatically create volume. Stage totals combine different entry types; they are not a common impression-to-sale funnel.')
    left,right=st.columns([1.15,1])
    g=c.groupby('Channel',sort=False)[['Spend','Leads','Opportunities','Funded accounts']].sum()
    g['Cost / lead']=g.Spend/g.Leads;g['Lead → funded']=g['Funded accounts']/g.Leads;g['CAC']=g.Spend/g['Funded accounts']
    with left,st.container(border=True):
        st.subheader('Where the funnel converts')
        fig=go.Figure()
        for i,(channel,r) in enumerate(g.iterrows()):
            fig.add_scatter(x=['Entry contacts','Next stage','Funded'],y=[100,100*r.Opportunities/r.Leads if r.Leads else 0,100*r['Funded accounts']/r.Leads if r.Leads else 0],mode='lines+markers',name=channel,line=dict(color=COLORS[i],width=3))
        fig.update_yaxes(title='Accounts per 100 entry contacts');chart(fig)
        st.caption('Entry contacts are paid leads, partner introductions or inbound enquiries. The next stage is a qualified opportunity for paid channels and an application for the two non-paid channels.')
    with right,st.container(border=True):
        st.subheader('Acquisition efficiency')
        fig=go.Figure(go.Bar(x=g.index,y=g.CAC,marker_color=COLORS,text=g.CAC.map(lambda v:f'${v:,.0f}'),textposition='outside'))
        fig.update_yaxes(title='Marketing CAC · CAD');chart(fig)
    st.subheader('Channel scorecard')
    st.dataframe(g.style.format({'Spend':'${:,.0f}','Leads':'{:,.0f}','Opportunities':'{:,.0f}','Funded accounts':'{:,.0f}','Cost / lead':'${:,.0f}','Lead → funded':'{:.1%}','CAC':'${:,.0f}'}),use_container_width=True)
    st.subheader('Forward-looking unit economics · current scenario')
    st.dataframe(eco.drop(columns=['10-year LTV']).set_index('Channel').style.format({'Funded accounts':'{:,.0f}','Media CAC':'${:,.0f}','Acquisition CAC':'${:,.0f}','Revenue LTV':'${:,.0f}','Monthly ARPA':'${:,.2f}','Lifetime fee revenue':'${:,.0f}','Lifetime years':'{:.0f}','LTV / CAC':'{:.2f}×','Payback months':'{:.0f}'},na_rep='Not reached'),use_container_width=True)
    st.caption('Monthly ARPA = total cohort fee revenue ÷ lifetime months, per original account. Lifetime fee revenue = ARPA × lifetime months. Revenue LTV discounts management-fee revenue using your chosen rate. Revenue payback compares cumulative fees with channel acquisition spend; blank means not reached within the selected lifetime.')

elif page=='Scenario lab':
    lift=fy.Funded_accounts.sum()-baseline.Funded_accounts.sum(); cost=fy.Marketing.sum()-baseline.Marketing.sum(); gain=fy.Revenue.sum()-baseline.Revenue.sum()
    st.markdown('<div class="eyebrow">July–December decision impact · versus unchanged base forecast</div>',unsafe_allow_html=True)
    cols=st.columns(4)
    for c,label,value in zip(cols,['Additional funded accounts','Incremental fee revenue','Incremental channel spend','Revenue less marketing change'],[f'{lift:+,.0f}',money(gain),money(cost),money(gain-cost)]): c.metric(label,value)
    st.markdown(f'<div class="brief"><strong>Timing matters.</strong> This scenario changes six-month fee revenue by {money(gain)} and revenue less marketing by {money(gain-cost)}. Acquisition spend arrives before the recurring fee stream. Use cohort payback alongside the annual P&L to judge a growth investment.</div>',unsafe_allow_html=True)
    st.subheader('Your monthly funnel · assumptions to outcomes')
    preview=ch[ch.Month.eq(pd.Timestamp('2026-07-01'))].set_index('Channel')
    preview['Entry stage']=[stage_labels(n)[0] for n in preview.index]
    preview['Next stage']=[stage_labels(n)[1] for n in preview.index]
    st.dataframe(preview[['Entry stage','Next stage','Spend','Impressions','Visits','Leads','Opportunities','Funded accounts','CAC']].style.format({n:'{:,.1f}' for n in ['Spend','Impressions','Visits','Leads','Opportunities','Funded accounts','CAC']},na_rep='—'),use_container_width=True)
    st.subheader('Customer economics · linked to your lifetime assumptions')
    st.dataframe(eco[['Channel','Lifetime years','Monthly ARPA','Lifetime fee revenue','Revenue LTV','Acquisition CAC','LTV / CAC','Payback months']].set_index('Channel').style.format('{:,.2f}',na_rep='—'),use_container_width=True)
    st.caption('ARPA is derived, not an extra revenue assumption: assets per account × management fee. Monthly ARPA shown here is the average over the customer lifetime. Lifetime fee revenue = monthly ARPA × 12 × lifetime years. Revenue LTV discounts future management fees; it excludes business costs.')
    fig=go.Figure()
    fig.add_scatter(x=f.Month,y=f.Revenue_less_marketing.cumsum(),name='Current scenario',line=dict(color=TEAL,width=3))
    fig.add_scatter(x=base.Month,y=base.Revenue_less_marketing.cumsum(),name='Base forecast',line=dict(color=GRAY,dash='dot'))
    fig.update_yaxes(title='Cumulative modeled revenue less marketing',tickprefix='$',tickformat='~s');chart(fig)
    st.caption('Linear channel scaling is a planning approximation. A measured pilot should establish marginal CAC, saturation and incrementality before reallocating at scale.')

elif page=='Forecast & variance':
    st.subheader('H1 funnel variance · simulated actuals versus budget')
    ac=ch[ch.Month.lt('2026-07-01')]; bud=bc[bc.Month.lt('2026-07-01')]
    bridge=funnel_bridge(bud,ac); start=bud['Funded accounts'].sum(); end=ac['Funded accounts'].sum()
    fig=go.Figure(go.Waterfall(x=['Budget']+bridge.index.tolist()+['Simulated actual'],y=[start]+bridge.tolist()+[end],measure=['absolute']+['relative']*5+['total'],increasing=dict(marker_color=TEAL),decreasing=dict(marker_color=ORANGE),totals=dict(marker_color=NAVY),text=[f'{v:,.0f}' for v in [start]+bridge.tolist()+[end]],textposition='outside'))
    fig.update_yaxes(title='Funded accounts');chart(fig,330)
    weak=bridge.idxmin()
    st.markdown(f'<div class="brief"><strong>Management commentary</strong><br>H1 funded accounts were {end-start:+,.0f} versus budget ({end/start-1:+.1%}). The largest adverse driver was {weak.lower()} ({bridge.min():+,.0f} accounts). Investigate the social cohort with Marketing and Sales, test a conversion intervention, then carry the measured improvement into the rolling forecast.</div>',unsafe_allow_html=True)
    st.caption('Exact sequential bridge: replace spend → media efficiency → lead capture → qualification → close conversion. Interaction effects depend on this order; attribution is not proof of causation.')
    metrics=['Revenue','Marketing','Revenue_less_marketing']
    var=pd.DataFrame({'H1 budget':b.iloc[:6][metrics].sum(),'H1 simulated actual':f.iloc[:6][metrics].sum()});var['Variance']=var.iloc[:,1]-var.iloc[:,0]
    st.dataframe(var.rename_axis('CAD').style.format('${:,.0f}'),use_container_width=True)
    st.caption('Variance = actual minus budget; a positive cost variance is adverse.')
    st.subheader('Monthly revenue & acquisition plan')
    year=st.selectbox('Schedule year',list(range(2026,2031)))
    sf=f[f.Month.dt.year.eq(year)].copy(); sf['Month']=sf.Month.dt.strftime('%b %Y')
    measures=['Funded_accounts','Active_accounts','Monthly_ARPA','Beginning_AUM','Contributions','Redemptions','Market_return','Ending_AUM','Revenue','Marketing','Revenue_less_marketing']
    table=sf.set_index('Month')[measures].T;table.index=table.index.str.replace('_',' ')
    st.dataframe(table.style.format('{:,.0f}'),use_container_width=True,height=535)
    st.caption('Financial rows in CAD; funded and active accounts are counts. 2026 Jan–Jun are simulated actuals, all subsequent periods are forecast.')


else:
    st.subheader('The financial chain')
    st.markdown('''
1. **Acquisition:** paid channels use spend ÷ CPM × 1,000 → impressions → leads → qualified opportunities → funded accounts. Partnerships use entered introductions → applications → funded accounts. Organic/referral uses entered visits → enquiries → applications → funded accounts. Non-paid program costs feed expenses and CAC independently of volume.
2. **Contributions:** new initial funding + recurring contributions from retained accounts + half a monthly contribution from new accounts.
3. **Assets:** beginning AUM + contributions − withdrawals + market movement − modeled fees = ending AUM.
4. **Revenue:** [beginning AUM + ½ × (contributions − withdrawals + market movement)] × annual management fee ÷ 12.
5. **Revenue less marketing:** fee revenue − channel spend. Other business costs are excluded; this is not operating profit.
''')
    st.info('Management fee starts at your requested 1.65%. Revenue is modeled before any separate rebate or tax adjustments. Customer deposits build assets; they are not corporate revenue.')
    st.subheader('Your active channel assumptions')
    st.dataframe(channels.set_index('Channel').style.format({'Spend':'${:,.0f}','CPM':'${:,.0f}','Lead rate':'{:.2%}','Opportunity rate':'{:.1%}','Close rate':'{:.1%}','Initial funding':'${:,.0f}','Monthly contribution':'${:,.0f}'}),use_container_width=True)
    st.markdown('''
**Opening portfolio:** $750M assets and 30,000 accounts, with $210 monthly contributions. Opening accounts are evenly spread across remaining months of an illustrative 10-year life. These are fixed simulated historical inputs, not company actuals. New cohorts use your channel-specific contribution and lifetime assumptions.

**Lifetime and assets:** new accounts remain for their selected lifetime, then close and withdraw remaining assets. Partial withdrawals and investment returns use your shared controls. No separate attrition rate is layered on top. No hidden budget growth or seasonality is applied.

**ARPA and LTV:** monthly ARPA is average lifetime fee revenue per account per month. Lifetime fee revenue = ARPA × lifetime months. Revenue LTV discounts monthly management fees over the selected lifetime, with no terminal value. Acquisition CAC is channel spend divided by funded accounts. Service, sales and fixed overhead costs are not modeled. Revenue payback indicates fee recovery of acquisition spend, not profitability. The forecast schedule's monthly ARPA is that calendar month's revenue divided by its average active accounts; its older account mix differs from a newly acquired cohort.

**Revenue timing:** same-month funnel conversion and half-month new contributions are explicit simplifications. A production version should estimate lead-to-funding lags, account-level retention, contribution profiles and graduation withdrawals.
''')
    st.subheader('Reporting contract')
    definitions=pd.DataFrame([
        ['Lead','Unique prospect with consent and a captured enquiry','CRM prospect_id; deduplicate by person and reporting window'],
        ['Opportunity','Lead accepted as qualified by Sales','CRM opportunity_id; first accepted timestamp'],
        ['Funded account','New account with first settled contribution','Account_id; first_funded_at; exclude cancellations'],
        ['Channel attribution','One acquisition source per funded account','Persist first-touch source; reconcile unknown and duplicate counts'],
        ['CAC','Attributed marketing cost / new funded accounts','Match spend and acquisition cohort window; track conversion lag'],
        ['AUM','Customer assets under management, not revenue','Custody balances; reconcile beginning + flows + returns − fees'],
        ['Fee revenue','Net earned management fees','Finance ledger; reconcile gross fees, rebates, waivers and net recognition'],
    ],columns=['Metric','Definition','Production control'])
    st.dataframe(definitions,hide_index=True,use_container_width=True)
    st.caption('The prototype starts from aggregated channel-month inputs; it does not claim to implement identity resolution or causal multi-touch attribution.')
    st.markdown('[Business-model reference: Embark Student Plan, June 2025 financial statements, Note 8](https://www.embark.ca/wp-content/uploads/2026/03/Embark-Student-Plan-FS-30Jun2025-English.pdf). Used to confirm the fee structure only; all demo operating assumptions are invented.')

st.divider()
from functools import partial
from excel_export import build_excel
st.download_button(
    'Download Excel model (.xlsx)',
    data=partial(build_excel, type(d)(**asdict(d)), channels.copy(deep=True), discount/100),
    file_name='Embark-revenue-model.xlsx',
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    key='download_excel', on_click='ignore',
    help='Generates your current scenario with auditable formulas, then downloads automatically.',
)
st.caption('Editable assumptions, channel builds and same-sheet Forecast calculations. Allow about 15 seconds for your download to start.')
st.caption('Independent FP&A demonstration · illustrative data throughout · changing assumptions recalculates all forecast pages')
