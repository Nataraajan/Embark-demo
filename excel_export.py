"""Portable Streamlit XLSX export: visible cohort formulas with cached results."""
import io
import math
import numpy as np
import xlsxwriter
from xlsxwriter.utility import xl_col_to_name as col
from planning_model import BASE, CHANNELS, channel_month, forecast


def build_excel(d, channels, discount=.1, months=60):
    out=io.BytesIO()
    wb=xlsxwriter.Workbook(out,{'in_memory':True})
    wb.set_calc_mode('auto')
    num='#,##0;(#,##0);"-"'
    formats={}
    def fmt(kind='formula',pct=False):
        key=(kind,pct)
        if key not in formats:
            opts={'font_name':'Arial','font_size':10,'num_format':'0.0%' if pct else num,
                  'font_color':{'input':'#0000FF','link':'#008000','formula':'#000000','output':'#1C1463'}[kind]}
            if kind=='input': opts['bg_color']='#FFF4CE'
            formats[key]=wb.add_format(opts)
        return formats[key]
    title=wb.add_format({'bold':True,'font_size':18,'font_color':'#1C1463','font_name':'Arial'})
    band=wb.add_format({'bold':True,'bg_color':'#1C1463','font_color':'white','font_name':'Arial','num_format':'mmm-yy'})
    note=wb.add_format({'font_color':'#6B6285','font_size':10,'text_wrap':True})
    total=wb.add_format({'bold':True,'bg_color':'#EEEBFC','top':1,'num_format':num,'font_color':'#1C1463'})
    names=['Forecast','Assumptions','Paid search','Paid social','Partnerships','Organic referral','Opening book','Actuals','Checks']
    sheets={n:wb.add_worksheet(n) for n in names}
    dates=[__import__('datetime').datetime(2026+m//12,m%12+1,1) for m in range(months)]
    def setup(s,label):
        s.hide_gridlines(2);s.freeze_panes(6,6);s.set_zoom(85)
        s.set_column('A:A',32);s.set_column('B:F',13);s.set_column(6,months+5,14)
        s.merge_range('A1:L2',label,title)
        s.merge_range('A3:L3','CAD, unrounded calculations. Blue/yellow: inputs; black: formulas; green: links. Synthetic demonstration.',note)
        s.set_row(2,28)
        for m,date in enumerate(dates):
            s.write_datetime(5,m+6,date,band)
            s.write(4,m+6,'Simulated actual' if m<6 else 'Forecast',note)
        s.set_landscape();s.fit_to_pages(1,0);s.repeat_rows(0,5)
        s.set_tab_color('#594FF0')
    for n,s in sheets.items():setup(s,n)
    vals={}
    def put(s,r,c,value,formula=None,pct=False):
        if value is None or (isinstance(value,(float,np.floating)) and not math.isfinite(value)): value=0
        vals[(s.name,r,c)]=value
        if formula:
            s.write_formula(r-1,c-1,'='+formula,fmt('output' if s.name=='Forecast' else 'link' if '!' in formula else 'formula',pct),value)
        else:s.write(r-1,c-1,value,fmt('input',pct))
    a=sheets['Assumptions'];a.merge_range('A4:C4','Forecast controls (July 2026 onward)',band)
    for r,label,value in [(5,'Management fee',d.fee),(6,'Investment return',d.annual_return),(7,'Partial withdrawals',d.annual_redemptions),(8,'LTV discount rate',discount)]:
        a.write(r-1,0,label);put(a,r,4,value,pct=True)
        a.data_validation(r-1,3,r-1,3,{'validate':'decimal','criteria':'between','minimum':-.4 if r==6 else 0,'maximum':.9,'input_title':'Annual rate','input_message':'Enter as a percentage.'})
    fields=['Spend','CPM','Inbound volume','Lead rate','Opportunity rate','Close rate','Initial funding','Monthly contribution','Lifetime years']
    for j,f in enumerate(fields):a.write(10,j+3,f,band)
    for i,(_,row) in enumerate(channels.iterrows()):
        a.write(11+i,0,row.Channel)
        for j,f in enumerate(fields):put(a,12+i,4+j,float(row[f]) if np.isfinite(row[f]) else 0,pct=f.endswith('rate'))
    a.merge_range('A18:L19','Change yellow inputs. Each channel has different entry stages. January–June source inputs remain fixed. Monthly schedules and every cohort recalculate in Excel. Revenue less marketing excludes all other business costs.',note)
    a.merge_range('A21:L22','Opening book is modeled separately: $750M / 30,000 accounts evenly spread across 120 remaining-life cohorts. Existing book is not allocated to acquisition channels. New cohorts retain the contribution and lifetime assumptions from their acquisition month.',note)
    src=sheets['Actuals']
    for r,label,value in [(5,'Historical fee',BASE.fee),(6,'Historical return',BASE.annual_return),(7,'Historical withdrawals',BASE.annual_redemptions),(8,'Opening AUM',BASE.opening_aum),(9,'Opening accounts',BASE.opening_accounts),(10,'Opening monthly contribution',210),(11,'Opening lifetime months',120)]:
        src.write(r-1,0,label);put(src,r,4,value,pct=r<8)
    hist=[channel_month(m,BASE,True,CHANNELS) for m in range(6)]
    for i in range(4):
        for j,f in enumerate(fields):
            r=15+i*11+j;src.write(r-1,0,f'{CHANNELS.iloc[i].Channel}: {f}')
            for m in range(6):put(src,r,m+7,float(hist[m].iloc[i][f]),pct=f.endswith('rate'))
    # Common monthly rates used by all cohort schedules.
    for m in range(months):
        c=m+7;L=col(c-1);source='Actuals' if m<6 else 'Assumptions'
        for r,ar,value in [(27,5,BASE.fee if m<6 else d.fee),(28,6,BASE.annual_return if m<6 else d.annual_return),(29,7,BASE.annual_redemptions if m<6 else d.annual_redemptions)]:
            a.write(r-1,0,{27:'Annual fee',28:'Annual return',29:'Annual withdrawals'}[r]);put(a,r,c,value,f"'{source}'!$D${ar}",True)
    arrays={};cohort_rows={}
    for i,name in enumerate(names[2:7]):
        s=sheets[name];opening=name=='Opening book';agg=np.zeros((9,months));cohort_rows[name]=[]
        if not opening:
            for j,f in enumerate(fields):
                s.write(7+j,0,f)
                for m in range(months):
                    v=float(hist[m].iloc[i][f]) if m<6 else float(channels.iloc[i][f])
                    formula=f"'Actuals'!{col(m+6)}{15+i*11+j}" if m<6 else f"'Assumptions'!${col(j+3)}${12+i}"
                    put(s,8+j,m+7,v,formula,f.endswith('rate'))
            for r,label in [(20,'Impressions / visits'),(21,'Leads / introductions'),(22,'Opportunities / applications'),(23,'Funded accounts'),(24,'Initial contributions'),(25,'Acquisition CAC')]:s.write(r-1,0,label)
            for m in range(months):
                c=m+7;L=col(c-1);v=lambda r:vals[(name,r,c)]
                traffic=v(8)/v(9)*1000 if i<2 and v(9) else v(10) if i==3 else 0
                put(s,20,c,traffic,f'{L}8/{L}9*1000' if i<2 else f'{L}10' if i==3 else '0')
                leads=traffic*v(11) if i!=2 else v(10)
                put(s,21,c,leads,f'{L}20*{L}11' if i!=2 else f'{L}10')
                put(s,22,c,leads*v(12),f'{L}21*{L}12')
                put(s,23,c,v(22)*v(13),f'{L}22*{L}13')
                put(s,24,c,v(23)*v(14),f'{L}23*{L}14')
                put(s,25,c,v(8)/v(23) if v(23) else 0,f'IF({L}23=0,0,{L}8/{L}23)')
        for k in range(120 if opening else months):
            h=45+k*11;s.write(h-1,0,f'Opening cohort {k+1}' if opening else dates[k].strftime('%b-%Y acquisition'),band)
            start=-k-1 if opening else k;birthcol=col(k+6)
            n=BASE.opening_accounts/120 if opening else vals[(name,23,k+7)]
            initial=BASE.opening_aum/120 if opening else vals[(name,14,k+7)]
            monthly=210 if opening else vals[(name,15,k+7)]
            life=120 if opening else vals[(name,16,k+7)]*12
            metadata=[(2,n,"'Actuals'!$D$9/'Actuals'!$D$11" if opening else f'{birthcol}23'),(3,initial,"'Actuals'!$D$8/'Actuals'!$D$11" if opening else f'{birthcol}14'),(4,monthly,"'Actuals'!$D$10" if opening else f'{birthcol}15'),(5,life,"'Actuals'!$D$11" if opening else f'{birthcol}16*12'),(6,start,None)]
            for c,v,f in metadata:put(s,h,c,v,f)
            labels=['Beginning AUM','Active accounts','Contributions','Withdrawals incl. maturity','Market return','Management-fee revenue','Ending AUM','Account exits','Fee base']
            for j,label in enumerate(labels):s.write(h+j,0,label)
            cohort_rows[name].append(h)
            balance=initial if opening else 0
            for m in range(months):
                c=m+7;L=col(c-1);P=col(c-2);active=start<=m<start+life;new=m==start;expired=m==start+life
                fee=BASE.fee if m<6 else d.fee;ret=BASE.annual_return if m<6 else d.annual_return;wd=BASE.annual_redemptions if m<6 else d.annual_redemptions
                cash=n*(initial+.5*monthly) if new else n*monthly if active else 0
                withdrawal=balance if expired else balance*(1-(1-wd)**(1/12)) if active else 0
                growth=balance*((1+ret)**(1/12)-1) if active else 0
                base=balance+.5*(cash-withdrawal+growth) if active else 0;rev=base*fee/12;end=balance+cash-withdrawal+growth-rev
                data=[balance,n if active else 0,cash,withdrawal,growth,rev,end,n if expired else 0,base]
                age=f'{m}-$F${h}';beg=h+1;ac=h+2;ca=h+3;wi=h+4;gr=h+5;re=h+6;en=h+7;ex=h+8;fb=h+9
                formulas=[f'$C${h}' if opening and m==0 else '0' if m==0 else f'{P}{en}',
                    f'IF(AND({age}>=0,{age}<$E${h}),$B${h},0)',
                    f'IF({age}=0,$B${h}*($C${h}+$D${h}/2),{L}{ac}*$D${h})',
                    f'IF({age}=$E${h},{L}{beg},IF({L}{ac}>0,{L}{beg}*(1-(1-Assumptions!{L}29)^(1/12)),0))',
                    f'IF({L}{ac}>0,{L}{beg}*((1+Assumptions!{L}28)^(1/12)-1),0)',
                    f'{L}{fb}*Assumptions!{L}27/12',
                    f'{L}{beg}+{L}{ca}-{L}{wi}+{L}{gr}-{L}{re}',
                    f'IF({age}=$E${h},$B${h},0)',
                    f'IF({L}{ac}>0,{L}{beg}+({L}{ca}-{L}{wi}+{L}{gr})/2,0)']
                for j,(v,f) in enumerate(zip(data,formulas)):put(s,h+1+j,c,v,f);agg[j,m]+=v
                balance=end
        s.write('B42','Accounts',band);s.write('C42','Initial $',band);s.write('D42','Monthly $',band);s.write('E42','Life months',band);s.write('F42','Start index',band)
        for r,j,label in [(28,5,'Revenue'),(29,6,'Ending AUM'),(30,1,'Active accounts'),(31,7,'Account exits'),(32,2,'Contributions'),(33,3,'Withdrawals'),(34,4,'Market return'),(35,8,'Fee base'),(36,0,'Beginning AUM')]:
            s.write(r-1,0,label,total)
            for m in range(months):put(s,r,m+7,agg[j,m],'SUM('+','.join(f'{col(m+6)}{h+1+j}' for h in cohort_rows[name])+')')
        arrays[name]=agg
    f,_=forecast(d,channels=channels,months=months);summary=sheets['Forecast'];checks=sheets['Checks']
    mappings={8:'Impressions',9:'Leads',10:'Opportunities',11:'Funded_accounts',12:'Marketing',14:'Beginning_accounts',15:'Account_exits',16:'Active_accounts',17:'Monthly_ARPA',19:'Beginning_AUM',20:'Contributions',21:'Redemptions',22:'Market_return',23:'Fee_base',24:'Revenue',25:'Ending_AUM',27:'Revenue_less_marketing'}
    sums={8:20,9:21,10:22,11:23,12:8,15:31,16:30,19:36,20:32,21:33,22:34,23:35,24:28,25:29}
    for r,label in mappings.items():summary.write(r-1,0,label.replace('_',' '),total if r in [11,16,24,25,27] else None)
    for m in range(months):
        c=m+7;L=col(c-1);P=col(c-2)
        for r,label in mappings.items():
            if r==8:form=f"'Paid search'!{L}20+'Paid social'!{L}20"
            elif r in sums:
                ns=names[2:6] if r in [9,10,11,12] else names[2:7]
                form='+'.join(f"'{n}'!{L}{sums[r]}" for n in ns)
            elif r==14:form="'Actuals'!$D$9" if m==0 else f'{P}16'
            elif r==17:form=f'IF({L}14-{L}15+{L}11/2=0,0,{L}24/({L}14-{L}15+{L}11/2))'
            elif r==27:form=f'{L}24-{L}12'
            put(summary,r,c,float(f.iloc[m][label]),form)
        checks.write(7,0,'AUM rollforward (zero)');put(checks,8,c,0,f'Forecast!{L}25-(Forecast!{L}19+Forecast!{L}20-Forecast!{L}21+Forecast!{L}22-Forecast!{L}24)')
        checks.write(8,0,'Account rollforward (zero)');put(checks,9,c,0,f'Forecast!{L}16-(Forecast!{L}14+Forecast!{L}11-Forecast!{L}15)')
        checks.write(10,0,'App revenue at export');put(checks,11,c,float(f.iloc[m].Revenue))
        checks.write(11,0,'Revenue vs export snapshot');put(checks,12,c,0,f'Forecast!{L}24-{L}11')
        calculated=sum(arrays[n][5,m] for n in arrays)
        if abs(calculated-f.iloc[m].Revenue)>.01:raise ValueError('Workbook revenue does not reconcile to app.')
    checks.merge_range('A15:L16','Rollforward checks should remain zero. Export snapshot comparisons are expected to change after editing assumptions in Excel. The snapshot is a static audit reference, not an input to the forecast.',note)
    checks.conditional_format(7,6,11,months+5,{'type':'cell','criteria':'not between','minimum':-.01,'maximum':.01,'format':wb.add_format({'bg_color':'#FFE0E0','font_color':'#C00000'})})
    for year in range(5):
        c=year+2;left=col(year*12+6);right=col(min((year+1)*12+5,months+5))
        summary.write(30,c,2026+year,band)
        for rr,source,label in [(32,11,'Annual funded accounts'),(33,12,'Annual channel spend'),(34,24,'Annual fee revenue'),(35,27,'Annual revenue less marketing'),(36,25,'Year-end AUM')]:
            summary.write(rr-1,0,label);put(summary,rr,c+1,float(f.iloc[year*12:(year+1)*12][mappings[source]].iloc[-1] if rr==36 else f.iloc[year*12:(year+1)*12][mappings[source]].sum()),f'{right}{source}' if rr==36 else f'SUM({left}{source}:{right}{source})')
    summary.merge_range('A39:L40','Management fees before rebates. Revenue less marketing is not operating profit. Channel revenue covers acquired cohorts only; the existing portfolio is separately shown in Opening book. Open in Excel with automatic calculation enabled.',note)
    wb.close()
    return out.getvalue()
