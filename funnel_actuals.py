"""Deterministic synthetic lead cohorts; outcomes observed within 60 days."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from planning_model import CHANNELS, unit_economics, stage_labels

AS_OF = pd.Timestamp('2026-09-21')
WINDOW = 60


@st.cache_data
def simulated_actuals():
    rng=np.random.default_rng(20260921)
    leads=[]; summaries=[]
    for m in range(8):
        month=pd.Timestamp('2026-01-01')+pd.DateOffset(months=m)
        for i,r in CHANNELS.iterrows():
            spend=float(r.Spend*(1+.025*m)*(1.08 if i==1 else 1))
            impressions=int(spend/r.CPM*1000) if i<2 else None
            incoming=r['Inbound volume']*(1+.025*m)
            expected=impressions*r['Lead rate'] if i<2 else incoming if i==2 else incoming*r['Lead rate']
            volume=int(rng.poisson(expected))
            qualify=r['Opportunity rate']*(max(.6,1-.055*m) if i==1 else 1)
            close=r['Close rate']*(max(.55,1-.065*m) if i==1 else .9 if i==0 and m>=4 else 1)
            created=month+pd.to_timedelta(rng.integers(0,month.days_in_month,volume),unit='D')
            qualified=rng.random(volume)<qualify
            funded=qualified & (rng.random(volume)<close)
            qdate=pd.Series(created+pd.to_timedelta(rng.integers(1,15,volume),unit='D'))
            fdate=qdate+pd.to_timedelta(rng.integers(2,42,volume),unit='D')
            qdate.loc[~qualified]=pd.NaT; fdate.loc[~funded]=pd.NaT
            qdate.loc[qdate>AS_OF]=pd.NaT;fdate.loc[fdate>AS_OF]=pd.NaT
            frame=pd.DataFrame({'Lead ID':[f'SIM-{m:02}-{i}-{j:06}' for j in range(volume)],'Channel':r.Channel,
                'Entry stage':stage_labels(r.Channel)[0],'Next stage':stage_labels(r.Channel)[1],'Cohort':month,'Lead date':created,'Qualified date':qdate,'Funded date':fdate})
            leads.append(frame)
            summaries.append({'Cohort':month,'Channel':r.Channel,'Spend':spend,'Impressions':impressions,'Entry stage':stage_labels(r.Channel)[0],'Next stage':stage_labels(r.Channel)[1],
                'Leads':volume,'Opportunities':int(qdate.notna().sum()),'Funded accounts':int(fdate.notna().sum()),
                'Mature':month+pd.offsets.MonthEnd(0)+pd.Timedelta(days=WINDOW)<=AS_OF,
                'Target qualification':r['Opportunity rate'],'Target close':r['Close rate']})
    s=pd.DataFrame(summaries)
    s['Qualification %']=s.Opportunities/s.Leads
    s['Close %']=s['Funded accounts']/s.Opportunities
    s['Lead → funded %']=s['Funded accounts']/s.Leads
    s['CAC']=s.Spend/s['Funded accounts'].replace(0,np.nan)
    return s,pd.concat(leads,ignore_index=True)


def opportunity(row,stage,target):
    if stage=='Opportunity → funded':
        return row.Opportunities*max(0,target-row['Close %'])
    return row.Leads*max(0,target-row['Qualification %'])*row['Close %']


def first_year_fee(row,d):
    balance=total=0.
    for m in range(12):
        cash=(row['Initial funding']+.5*row['Monthly contribution']) if m==0 else row['Monthly contribution']
        withdrawal=balance*(1-(1-d.annual_redemptions)**(1/12))
        growth=balance*((1+d.annual_return)**(1/12)-1)
        fee=(balance+.5*(cash-withdrawal+growth))*d.fee/12
        balance+=cash-withdrawal+growth-fee;total+=fee
    return total


def render_actuals(d,channels,discount,chart,money):
    summary,leads=simulated_actuals()
    st.info('SIMULATED ACTUALS · Generated lead-level records, observed as of 21 Sep 2026. Conversion follows the same acquisition cohort for 60 days. These are separate illustrative diagnostics, not imported company actuals or the financial forecast’s historical ledger.')
    mature=summary[summary.Mature]
    channel=st.selectbox('Channel to diagnose',CHANNELS.Channel.tolist())
    labels=stage_labels(channel)
    transitions=[f'{labels[0]} → {labels[1]}',f'{labels[1]} → funded']
    data=mature[mature.Channel.eq(channel)].sort_values('Cohort')
    st.subheader(f'{channel} · monthly performance')
    st.caption('Comparable, fully observed 60-day lead cohorts only: January–June 2026. July and August are incomplete and excluded from these charts. Hover over a month for exact values.')
    first,last=data.iloc[0],data.iloc[-1]
    st.markdown(f'**January → June:** spend {last.Spend/first.Spend-1:+.1%}; leads {last.Leads/first.Leads-1:+.1%}; next-stage conversion {100*(last["Qualification %"]-first["Qualification %"]):+.1f} pp; funded conversion {100*(last["Close %"]-first["Close %"]):+.1f} pp; CAC {last.CAC/first.CAC-1:+.1%}. These movements identify questions to investigate, not proven causes.')
    from plotly.subplots import make_subplots
    left,right=st.columns(2)
    with left:
        st.markdown(f'**Spend and {labels[0].lower()}**')
        fig=make_subplots(specs=[[{'secondary_y':True}]])
        fig.add_bar(x=data.Cohort,y=data.Spend,name='Spend ($)',marker_color='#c8c1f4',secondary_y=False)
        fig.add_scatter(x=data.Cohort,y=data.Leads,name=labels[0],mode='lines+markers',line_color='#1c1463',secondary_y=True)
        fig.update_yaxes(title_text='Spend ($)',tickprefix='$',tickformat='~s',secondary_y=False)
        fig.update_yaxes(title_text=labels[0],secondary_y=True)
        chart(fig)
    with right:
        st.markdown('**Stage conversion rates**')
        fig=go.Figure()
        for metric,label,color in [('Qualification %',transitions[0],'#594ff0'),('Close %',transitions[1],'#4276dd'),('Lead → funded %',f'{labels[0]} → funded','#db744e')]:
            fig.add_scatter(x=data.Cohort,y=data[metric]*100,name=label,mode='lines+markers',line_color=color)
        fig.update_yaxes(title='Conversion (%)',rangemode='tozero');chart(fig)
    left,right=st.columns(2)
    with left:
        st.markdown('**Funded accounts and acquisition cost**')
        fig=make_subplots(specs=[[{'secondary_y':True}]])
        fig.add_bar(x=data.Cohort,y=data['Funded accounts'],name='Funded accounts',marker_color='#c8c1f4',secondary_y=False)
        fig.add_scatter(x=data.Cohort,y=data.CAC,name='CAC ($)',mode='lines+markers',line_color='#db744e',secondary_y=True)
        fig.update_yaxes(title_text='Funded accounts',secondary_y=False)
        fig.update_yaxes(title_text='CAC ($)',tickprefix='$',secondary_y=True);chart(fig)
    with right:
        st.markdown('**Is the change specific to one channel?**')
        metric=st.selectbox('Compare channels on',['Close %','Qualification %','Lead → funded %','CAC','Funded accounts','Spend','Leads'],format_func=lambda x:{'Close %':transitions[1],'Qualification %':transitions[0],'Lead → funded %':f'{labels[0]} → funded','Leads':'Entry contacts'}.get(x,x))
        fig=go.Figure()
        peers=mature if '%' not in metric else mature[mature.Channel.map(stage_labels).map(lambda x:x==labels)]
        st.caption('Counts, cost and CAC compare all channels. Conversion compares only channels with the same stage definitions.')
        for name,group in peers.groupby('Channel',sort=False):
            group=group.sort_values('Cohort')
            fig.add_scatter(x=group.Cohort,y=group[metric]*(100 if '%' in metric else 1),name=name,mode='lines+markers',line=dict(width=3 if name==channel else 1.5))
        fig.update_yaxes(title='Conversion (%)' if '%' in metric else metric,rangemode='tozero');chart(fig)
    with st.expander('Monthly numbers and incomplete cohorts'):
        monthly=summary[summary.Channel.eq(channel)].copy()
        monthly['Status']=np.where(monthly.Mature,'Mature · comparable','Incomplete · exclude from comparison')
        monthly['Cohort']=monthly.Cohort.dt.strftime('%b %Y')
        st.dataframe(monthly[['Cohort','Status','Spend','Leads','Opportunities','Funded accounts','Qualification %','Close %','CAC']].style.format({'Spend':'${:,.0f}','Qualification %':'{:.1%}','Close %':'{:.1%}','CAC':'${:,.0f}'}),hide_index=True,use_container_width=True)
        st.caption('Incomplete rows show outcomes observed so far, not final 60-day conversion. They are not used for trend conclusions or opportunity estimates.')
    st.divider()
    st.subheader('Inspect a month')
    month=st.selectbox('Lead acquisition cohort',sorted(mature.Cohort.unique(),reverse=True),format_func=lambda x:pd.Timestamp(x).strftime('%B %Y'))
    current=summary[summary.Cohort.eq(month)].copy()
    previous=summary[summary.Cohort.eq(pd.Timestamp(month)-pd.DateOffset(months=1))]
    st.caption('January–June cohorts are fully observed. July and August remain incomplete and are excluded from optimization estimates. Counts are unique leads; funded accounts are credited to the original lead cohort, not the funding month.')
    st.caption('The following headline totals and scorecard cover all channels for the selected month; the funnel below focuses on your selected channel.')
    total=current[['Spend','Leads','Opportunities','Funded accounts']].sum()
    c=st.columns(4)
    for col,label,v in zip(c,['Acquisition / program costs','Entry contacts','Next-stage contacts','Funded accounts'],[money(total.Spend),f'{total.Leads:,.0f}',f'{total.Opportunities:,.0f}',f'{total["Funded accounts"]:,.0f}']):col.metric(label,v)
    st.subheader('Actual channel scorecard')
    table=current.set_index('Channel')[['Entry stage','Next stage','Spend','Leads','Opportunities','Funded accounts','Qualification %','Close %','Lead → funded %','CAC']]
    st.caption('Internal Leads / Opportunities columns mean the entry and next stage listed for each channel. Percentages have different stage definitions and must not be treated as equivalent across channel types.')
    st.dataframe(table.style.format({'Spend':'${:,.0f}','Leads':'{:,.0f}','Opportunities':'{:,.0f}','Funded accounts':'{:,.0f}','Qualification %':'{:.1%}','Close %':'{:.1%}','Lead → funded %':'{:.1%}','CAC':'${:,.0f}'}),use_container_width=True)
    row=current[current.Channel.eq(channel)].iloc[0]
    st.subheader(f'{channel} · where the cohort drops out')
    c=st.columns(2)
    with c[0]:
        fig=go.Figure(go.Funnel(y=labels,x=[row.Leads,row.Opportunities,row['Funded accounts']],textinfo='value+percent previous',marker_color=['#4276dd','#594ff0','#1c1463']))
        chart(fig)
    with c[1]:
        fig=go.Figure()
        fig.add_bar(x=transitions,y=[row['Qualification %']*100,row['Close %']*100],name='Actual',marker_color='#594ff0')
        fig.add_bar(x=transitions,y=[row['Target qualification']*100,row['Target close']*100],name='Example target',marker_color='#c8c1f4')
        fig.update_yaxes(title='Conversion %');chart(fig)
    comparison=[]
    for label,metric,target in [(transitions[0],'Qualification %','Target qualification'),(transitions[1],'Close %','Target close')]:
        prev=previous[previous.Channel.eq(channel)]
        comparison.append({'Stage':label,'Actual':row[metric],'Example target':row[target],
            'Gap to target (pp)':100*(row[metric]-row[target]),'Change vs prior cohort (pp)':100*(row[metric]-prev.iloc[0][metric]) if len(prev) else np.nan})
    st.dataframe(pd.DataFrame(comparison).set_index('Stage').style.format({'Actual':'{:.1%}','Example target':'{:.1%}','Gap to target (pp)':'{:+.1f}','Change vs prior cohort (pp)':'{:+.1f}'},na_rep='No prior cohort'),use_container_width=True)
    st.subheader('Size one improvement opportunity')
    c=st.columns(3)
    chosen=c[0].selectbox('Stage to improve',[transitions[1],transitions[0]],key=f'improve_{channel}')
    stage='Opportunity → funded' if chosen==transitions[1] else 'Lead → opportunity'
    target_key='Target close' if stage=='Opportunity → funded' else 'Target qualification'
    target=c[1].number_input('Achievable conversion target (%)',0.,100.,float(row[target_key]*100),1.,key=f'target_{channel}_{stage}')/100
    cost=c[2].number_input('Pilot cost for this cohort ($)',0.,1000000.,5000.,500.,key='pilot_cost')
    extra=opportunity(row,stage,target)
    assumptions=channels[channels.Channel.eq(channel)].iloc[0]
    economics=unit_economics(d,channels=channels,discount=discount/100).set_index('Channel').loc[channel]
    revenue=extra*first_year_fee(assumptions,d)
    net_value=extra*economics['Revenue LTV']-cost
    c=st.columns(3)
    c[0].metric('Potential additional funded accounts',f'{extra:,.1f}')
    c[1].metric('First 12 months’ additional fee revenue',money(revenue))
    c[2].metric('Lifetime revenue NPV less pilot',money(net_value))
    st.caption(f'Selected final stage: next-stage contacts × positive funding-conversion gap. Selected entry stage: entry contacts × positive next-stage conversion gap × observed funding rate. Only one stage changes at a time. First-year revenue is the 12 months after acquisition, not the calendar-year forecast. Fee {d.fee:.2%}; customer lifetime {assumptions["Lifetime years"]:.0f} years; discount {discount:.1f}%. Economics use the editable channel assumptions above. Revenue NPV deducts only pilot cost; existing channel spend is unchanged. Business costs are excluded, so this is not profit. This estimate is not automatically booked into the forecast.')
    action=('Review follow-up speed, application completion and funding friction with Sales; test a revised follow-up sequence.' if stage=='Opportunity → funded' else 'Review targeting, source quality and qualification rules with Marketing; test a narrower audience or revised enquiry form.')
    st.success(f'Proposed pilot: {action} Measure the selected stage against a comparable control cohort over the same 60-day window. Validate contribution quality and incremental conversion before scaling.')
    with st.expander('Audit the simulated data and cohort maturity'):
        st.dataframe(summary[['Cohort','Channel','Leads','Opportunities','Funded accounts','Mature']],hide_index=True,use_container_width=True)
        sample=leads[leads.Cohort.eq(month)&leads.Channel.eq(channel)]
        st.dataframe(sample.head(100),hide_index=True,use_container_width=True)
        st.caption('Blank dates mean no qualifying/funding event observed by the as-of date. Partnerships and referral impressions are not reported; generated lead counts for these channels are directly simulated. Each lead has one attributed source. This is a diagnostic dataset, not a causal attribution study.')
        st.download_button('Download simulated lead records',leads.to_csv(index=False),'simulated-funnel-leads.csv','text/csv')
        st.download_button('Download cohort scorecard',summary.to_csv(index=False),'simulated-cohort-scorecard.csv','text/csv')
