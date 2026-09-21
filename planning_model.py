"""Illustrative RESP GTM planning model. All operating inputs are synthetic CAD.

Months Jan-Jun 2026 are reproducible simulated actuals. Scenarios affect July
2026 onward only. This is a planning demonstration, not Embark company guidance.
"""
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd


CHANNELS = pd.DataFrame([
    ['Paid search', 120000., 60., .0035, .28, .25, 3000., 225.],
    ['Paid social', 80000., 18., .0009, .18, .17, 1800., 160.],
    ['Partnerships', 45000., 60., .0040, .40, .35, 4000., 250.],
    ['Organic & referral', 30000., 40., .0030, .30, .30, 2800., 210.],
], columns=['Channel', 'Spend', 'CPM', 'Lead rate', 'Opportunity rate', 'Close rate', 'Initial funding', 'Monthly contribution'])
CHANNELS['Lifetime years'] = 10.
CHANNELS['Inbound volume'] = [0., 0., 3000., 75000.]
CHANNELS.loc[CHANNELS.Channel.eq('Partnerships'), ['CPM','Lead rate']] = [np.nan, 1.]
CHANNELS.loc[CHANNELS.Channel.eq('Organic & referral'), ['CPM','Lead rate']] = [np.nan, .03]


def stage_labels(channel):
    if channel == 'Partnerships':
        return ['Partner introductions', 'Applications', 'Funded accounts']
    if channel == 'Organic & referral':
        return ['Inbound enquiries', 'Applications', 'Funded accounts']
    return ['Leads', 'Qualified opportunities', 'Funded accounts']


@dataclass(frozen=True)
class Drivers:
    spend_change: float = 0.
    shift: float = 0.                 # monthly CAD moved social -> search
    close_lift: float = 0.            # percentage-point change expressed as decimal
    lead_lift: float = 0.             # relative lift
    contribution_lift: float = 0.
    annual_growth: float = 0.
    annual_return: float = .04
    fee: float = .0165               # user-selected management fee assumption
    annual_redemptions: float = .08
    annual_attrition: float = .02
    opening_aum: float = 750000000.
    opening_accounts: float = 30000.


BASE = Drivers()
PRESETS = {
    'Base forecast': {},
    'Shift $20k to search': {'shift': 20000.},
    'Fix conversion': {'close_lift': .03},
    'Growth investment': {'spend_change': .20, 'close_lift': .01},
    'Downside': {'lead_lift': -.15, 'annual_return': -.08, 'contribution_lift': -.10},
}


def channel_month(month, d=BASE, actual=False, channels=None):
    """Single-source attributed funded accounts; fractional counts are expectations."""
    f = (CHANNELS if channels is None else channels).copy()
    growth = (1 + d.annual_growth) ** (month / 12)
    season = 1.  # direct spend is the actual monthly amount; no hidden seasonality
    f['Spend'] *= 1 + d.spend_change
    f.loc[f.Channel == 'Paid social', 'Spend'] -= d.shift
    f.loc[f.Channel == 'Paid search', 'Spend'] += d.shift
    if (f.Spend < 0).any():
        raise ValueError('Budget transfer exceeds available channel spend.')
    f['Spend'] *= growth * season
    f['Lead rate'] = np.clip(f['Lead rate'] * (1 + d.lead_lift), 0, 1)
    f['Close rate'] = np.clip(f['Close rate'] + d.close_lift, 0, 1)
    f['Monthly contribution'] *= 1 + d.contribution_lift
    if actual:
        # Deliberate social leakage creates an explainable demo variance.
        f['Spend'] *= [1.03, 1.10, .97, 1.00]
        f['Lead rate'] *= [1.02, .88, 1.00, 1.03]
        f['Close rate'] *= [.98, .85, 1.02, 1.]
    paid=f.Channel.isin(['Paid search','Paid social'])
    partner=f.Channel.eq('Partnerships')
    f['Impressions'] = np.where(paid, f.Spend / f.CPM * 1000, np.nan)
    f['Visits'] = np.where(f.Channel.eq('Organic & referral'),f['Inbound volume'],np.nan)
    f['Leads'] = np.where(paid, f.Impressions*f['Lead rate'],
                          np.where(partner,f['Inbound volume'],f['Inbound volume']*f['Lead rate']))
    f['Opportunities'] = f.Leads * f['Opportunity rate']
    f['Funded accounts'] = f.Opportunities * f['Close rate']
    f['Initial contributions'] = f['Funded accounts'] * f['Initial funding']
    f['CAC'] = f.Spend / f['Funded accounts'].replace(0, np.nan)
    f['Month'] = pd.Timestamp('2026-01-01') + pd.DateOffset(months=month)
    return f


def forecast(d=BASE, budget=False, months=60, channels=None):
    """Assets deduct modeled net fees; market return applies to beginning assets.

    Contributions begin in the funding month (half monthly contribution for new
    accounts). Existing-account monthly contribution is an illustrative $210.
    Whole-book redemptions are independent of account attrition: partial and
    education withdrawals need not close an account. Grants/transfers omitted.
    """
    if channels is not None:
        return direct_forecast(d, channels, budget, months)
    frames, rows = [], []
    aum = BASE.opening_aum  # fixed common start for actuals / budget
    accounts = BASE.opening_accounts
    recurring = accounts * 210.
    for m in range(months):
        actual = not budget and m < 6
        p = BASE if actual or budget else d
        ch = channel_month(m, p, actual)
        frames.append(ch)
        new = ch['Funded accounts'].sum()
        lost = accounts * (1 - (1 - p.annual_attrition) ** (1 / 12))
        retained_recurring = recurring * (1 - lost / accounts) if accounts else 0.
        # Apply an edited contribution amount prospectively to the installed book.
        if m == 6 and not budget:
            retained_recurring *= 1 + d.contribution_lift
        new_recurring = (ch['Funded accounts'] * ch['Monthly contribution']).sum()
        contributions = ch['Initial contributions'].sum() + retained_recurring + .5 * new_recurring
        redemptions = aum * (1 - (1 - p.annual_redemptions) ** (1 / 12))
        market = aum * ((1 + p.annual_return) ** (1 / 12) - 1)
        fee_base = aum + .5 * (contributions - redemptions + market)
        revenue = fee_base * p.fee / 12
        end_aum = aum + contributions - redemptions + market - revenue
        end_accounts = accounts - lost + new
        marketing = ch.Spend.sum()
        rows.append(dict(Month=ch.Month.iloc[0], Period='Budget' if budget else ('Illustrative actual' if actual else 'Forecast'),
            Impressions=ch.Impressions.sum(), Leads=ch.Leads.sum(), Opportunities=ch.Opportunities.sum(),
            Funded_accounts=new, Beginning_accounts=accounts, Account_exits=lost, Active_accounts=end_accounts,
            Beginning_AUM=aum, Contributions=contributions, Redemptions=redemptions, Market_return=market,
            Fee_base=fee_base, Ending_AUM=end_aum, Revenue=revenue, Marketing=marketing,
            Revenue_less_marketing=revenue-marketing, CAC=marketing/new if new else np.nan))
        aum, accounts, recurring = end_aum, end_accounts, retained_recurring + new_recurring
    return pd.DataFrame(rows), pd.concat(frames, ignore_index=True)


def unit_economics(d=BASE, month=6, years=10, discount=.10, channels=None):
    """Discounted lifetime fee revenue per newly funded account.

    Includes modeled fee revenue with account lifetime and asset withdrawals.
    CAC is channel spend per funded account. No service, sales or overhead costs
    are modeled; revenue LTV and revenue payback are not profit measures.
    """
    ch = channel_month(month, d, channels=channels)
    out = []
    for _, r in ch.iterrows():
        balance, active = 0., 1.
        pv = undiscounted = revenue_total = 0.
        cac = r.CAC
        payback = None
        life = int(round(r['Lifetime years'] * 12)) if channels is not None else years * 12
        for m in range(life):
            initial = r['Initial funding'] if m == 0 else 0.
            contribution = initial + active * r['Monthly contribution'] * (.5 if m == 0 else 1)
            withdrawal = balance * (1 - (1 - d.annual_redemptions) ** (1 / 12))
            growth = balance * ((1 + d.annual_return) ** (1 / 12) - 1)
            revenue = (balance + .5 * (contribution - withdrawal + growth)) * d.fee / 12
            margin = revenue
            pv += margin / ((1 + discount) ** ((m + 1) / 12))
            undiscounted += margin
            revenue_total += revenue
            if payback is None and undiscounted >= cac:
                payback = m + 1
            balance += contribution - withdrawal + growth - revenue
            if channels is None:
                active *= (1 - d.annual_attrition) ** (1 / 12)
        out.append({'Channel': r.Channel, 'Funded accounts': r['Funded accounts'],
            'Media CAC': r.CAC, 'Acquisition CAC': cac, '10-year LTV': pv,
            'Lifetime years': life / 12, 'Monthly ARPA': revenue_total / life,
            'Lifetime fee revenue': revenue_total, 'Revenue LTV': pv,
            'LTV / CAC': pv / cac if cac > 0 else np.nan,
            'Payback months': float(payback) if payback else np.nan})
    return pd.DataFrame(out)


def direct_forecast(d, channels, budget=False, months=60):
    """Cohorts stay for the specified lifetime, then withdraw their remaining assets.

    Opening customers are evenly distributed across remaining months of a 10-year
    life. July-onward lifetime edits apply to newly acquired cohorts only.
    No separate attrition assumption is layered on top of cohort lifetime.
    """
    cohorts=[]
    for age in range(120):
        cohorts.append(dict(n=BASE.opening_accounts/120, balance=BASE.opening_aum/120,
                            monthly=210., start=-age-1, life=120))
    rows=[]; frames=[]
    for m in range(months):
        actual=not budget and m<6
        p=BASE if actual or budget else d
        ch=channel_month(m,p,actual,CHANNELS if actual or budget else channels)
        frames.append(ch)
        beginning=sum(c['balance'] for c in cohorts)
        beginning_n=sum(c['n'] for c in cohorts)
        expired=[c for c in cohorts if m-c['start']>=c['life']]
        exits=sum(c['n'] for c in expired)
        redemptions=sum(c['balance'] for c in expired)
        cohorts=[c for c in cohorts if m-c['start']<c['life']]
        for _,r in ch.iterrows():
            cohorts.append(dict(n=r['Funded accounts'],balance=0.,monthly=r['Monthly contribution'],
                initial=r['Initial funding'],start=m,life=int(round(r['Lifetime years']*12))))
        contributions=market=revenue=fee_base=0.
        for c in cohorts:
            new=c['start']==m
            cash=c['n']*(c.get('initial',0.)+.5*c['monthly']) if new else c['n']*c['monthly']
            withdrawal=c['balance']*(1-(1-p.annual_redemptions)**(1/12))
            growth=c['balance']*((1+p.annual_return)**(1/12)-1)
            average=c['balance']+.5*(cash-withdrawal+growth)
            fee=average*p.fee/12
            c['balance']+=cash-withdrawal+growth-fee
            contributions+=cash; redemptions+=withdrawal; market+=growth; revenue+=fee; fee_base+=average
        new=ch['Funded accounts'].sum()
        end_n=sum(c['n'] for c in cohorts)
        average_n=beginning_n-exits+.5*new
        marketing=ch.Spend.sum()
        rows.append(dict(Month=ch.Month.iloc[0],Period='Budget' if budget else 'Illustrative actual' if actual else 'Forecast',
            Impressions=ch.Impressions.sum(),Leads=ch.Leads.sum(),Opportunities=ch.Opportunities.sum(),
            Funded_accounts=new,Beginning_accounts=beginning_n,Account_exits=exits,Active_accounts=end_n,
            Beginning_AUM=beginning,Contributions=contributions,Redemptions=redemptions,Market_return=market,
            Fee_base=fee_base,Ending_AUM=sum(c['balance'] for c in cohorts),Revenue=revenue,Marketing=marketing,
            Revenue_less_marketing=revenue-marketing,CAC=marketing/new if new else np.nan,
            Monthly_ARPA=revenue/average_n if average_n else np.nan))
    return pd.DataFrame(rows),pd.concat(frames,ignore_index=True)


def funnel_bridge(budget_channels, actual_channels):
    """Exact sequential bridge of funded accounts, weighted within each channel.

    Replace spend, then CPM, lead rate, qualification, close rate. Order-dependent
    attribution of interactions, not a causal claim.
    """
    factors = ['Spend', 'CPM', 'Lead rate', 'Opportunity rate', 'Close rate']
    totals = np.zeros(5)
    for (_, b), (_, a) in zip(budget_channels.iterrows(), actual_channels.iterrows()):
        if b.Channel not in ['Paid search','Paid social']:
            # Non-paid volume is supplied independently of program costs.
            totals[2] += (a.Leads-b.Leads)*b['Opportunity rate']*b['Close rate']
            totals[3] += a.Leads*(a['Opportunity rate']-b['Opportunity rate'])*b['Close rate']
            totals[4] += a.Leads*a['Opportunity rate']*(a['Close rate']-b['Close rate'])
            continue
        v = b[factors].astype(float).to_numpy(copy=True)
        calc = lambda x: x[0] / x[1] * 1000 * x[2] * x[3] * x[4]
        for i, name in enumerate(factors):
            before = calc(v)
            v[i] = a[name]
            totals[i] += calc(v) - before
    return pd.Series(totals, index=['Spend', 'Media efficiency', 'Lead capture', 'Qualification', 'Close conversion'])


def annual(f):
    g = f.assign(Year=f.Month.dt.year).groupby('Year')
    a = g[['Funded_accounts', 'Contributions', 'Revenue', 'Marketing', 'Revenue_less_marketing']].sum()
    a['Ending_AUM'] = g.Ending_AUM.last()
    a['CAC'] = a.Marketing / a.Funded_accounts
    return a
