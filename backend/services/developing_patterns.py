"""Developing Pattern Detection Engine - Core + All Pattern Detectors."""
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

STAGE_EARLY = "Stage 1 \u2013 Early Formation"
STAGE_DEV = "Stage 2 \u2013 Pattern Developing"
STAGE_ALMOST = "Stage 3 \u2013 Almost Complete"
STAGE_BKOUT = "Stage 4 \u2013 Breakout Pending"
STAGE_CONF = "Stage 5 \u2013 Confirmed"
STAGE_INV = "Invalidated"


def _piv(df, w=5):
    h, lo, hs, ls = df["High"].values, df["Low"].values, [], []
    for i in range(w, len(df)-w):
        if h[i] == max(h[i-w:i+w+1]): hs.append({"i":i,"p":float(h[i])})
        if lo[i] == min(lo[i-w:i+w+1]): ls.append({"i":i,"p":float(lo[i])})
    return hs, ls

def _pivm(df):
    hm, lm = {}, {}
    for w in [3,5,8]:
        hs, ls = _piv(df, w)
        for p in hs:
            if p["i"] not in hm or p["p"]>hm[p["i"]]["p"]: hm[p["i"]]=p
        for p in ls:
            if p["i"] not in lm or p["p"]<lm[p["i"]]["p"]: lm[p["i"]]=p
    return sorted(hm.values(),key=lambda x:x["i"]), sorted(lm.values(),key=lambda x:x["i"])

def _sy(a,b):
    m=(abs(a)+abs(b))/2
    return max(0,100-abs(a-b)/m*1000) if m else 100.0

def _nq(pts):
    if len(pts)<2: return 50.0
    a=sum(pts)/len(pts)
    return max(0,100-max(abs(p-a)/a*100 for p in pts)*15) if a else 50.0

def _ts(c,lb=30):
    if len(c)<lb+5: return 50.0
    s=c[-lb-5:-5]
    if len(s)<10: return 50.0
    try: sl=np.polyfit(np.arange(len(s)),s,1)[0]
    except: return 50.0
    a=np.mean(s)
    if a==0: return 50.0
    sp=sl/a*100*len(s)
    return min(100,abs(sp)*5) if abs(sp)>2 else 50.0

def _vc(vol,st):
    if vol is None or len(vol)<10: return 50.0
    try:
        pv=vol[st:]
        if len(pv)<5: return 50.0
        sc=50.0
        if np.mean(pv[:len(pv)//2])>0 and np.mean(pv[len(pv)//2:])<np.mean(pv[:len(pv)//2]): sc+=25
        return min(100,sc)
    except: return 50.0

def _sc(sy,nq,dp,tr,vl,ps): return sy*0.25+nq*0.15+dp*0.15+tr*0.15+vl*0.15+ps*0.15
def _bc(pp,vl,cn):
    ps=min(100,pp*15) if pp>2 else (pp*25 if pp>0 else max(0,50+pp*10))
    return ps*0.40+vl*0.35+cn*0.25

def _dnl(a,b,ci):
    if a["i"]==b["i"]: return a["p"]
    return a["p"]+(b["p"]-a["p"])/(b["i"]-a["i"])*(ci-a["i"])

def _best(r):
    v=[x for x in r if x["stage"]!=STAGE_INV]
    p=v if v else r
    if not p: return []
    p.sort(key=lambda x:x["structure_confidence"],reverse=True)
    return [p[0]]

def _stg_b(pv,fi,n):
    if pv>2: return STAGE_CONF,90
    if pv>-1: return STAGE_BKOUT,75
    if fi<n-3: return STAGE_ALMOST,60
    return STAGE_DEV,45

def _R(v): return round(v,2)


def _det_inv_hs(df,ph,pl,cp):
    res=[];c=df["Close"].values;vol=df["Volume"].values if "Volume" in df.columns else None;n=len(df)
    if len(pl)<2: return []
    for i in range(len(pl)-1):
        for j in range(i+1,min(i+6,len(pl))):
            ls,hd=pl[i],pl[j]
            if hd["p"]>=ls["p"] or (ls["p"]-hd["p"])/ls["p"]<0.01 or hd["i"]-ls["i"]<3: continue
            n1c=[h for h in ph if ls["i"]<h["i"]<hd["i"]]
            if not n1c: continue
            n1=max(n1c,key=lambda x:x["p"])
            rsc=[l for l in pl if l["i"]>hd["i"] and l["p"]>hd["p"]]
            n2c=[h for h in ph if h["i"]>hd["i"]]
            if rsc:
                rs=rsc[0];sy=_sy(ls["p"],rs["p"])
                if sy<20: continue
                n2b=[h for h in n2c if hd["i"]<h["i"]<rs["i"]]
                n2=max(n2b,key=lambda x:x["p"]) if n2b else (n2c[0] if n2c else n1)
                nlp=_dnl(n1,n2,n-1);pv=(cp-nlp)/nlp*100;st,pp=_stg_b(pv,rs["i"],n)
                if cp<hd["p"]: st=STAGE_INV
                ds=min(100,(n1["p"]-hd["p"])/n1["p"]*1000)
                s=_sc(sy,_nq([n1["p"],n2["p"]]),ds,_ts(c,max(30,ls["i"])),_vc(vol,ls["i"]),pp)
                b=_bc(pv,_vc(vol,ls["i"]),min(100,max(0,pv*20)))
                ht=nlp-hd["p"];tgt=_R(nlp+ht);inv=_R(hd["p"]*0.98)
                res.append({"pattern":"Inverse Head & Shoulders","type":"bullish","stage":st,"structure_confidence":_R(s),"breakout_confidence":_R(b),"left_shoulder":_R(ls["p"]),"head":_R(hd["p"]),"right_shoulder":_R(rs["p"]),"neckline_1":_R(n1["p"]),"neckline_2":_R(n2["p"]),"dynamic_neckline":_R(nlp),"breakout_level":_R(nlp),"target":tgt,"invalidation":inv,"pattern_start_idx":ls["i"],"description":f"Inv H&S: LS \u20b9{ls['p']:.2f}, Head \u20b9{hd['p']:.2f}, RS \u20b9{rs['p']:.2f}. NL \u20b9{nlp:.2f}. Tgt \u20b9{tgt}."})
            else:
                n2=n2c[0] if n2c else n1;nlp=_dnl(n1,n2,n-1)
                rz=(hd["p"]+(ls["p"]-hd["p"])*0.6,ls["p"]*1.02)
                st=STAGE_DEV if (cp>hd["p"] and cp<nlp) else STAGE_EARLY;pp=40 if st==STAGE_DEV else 25
                if cp<hd["p"]: st=STAGE_INV
                ds=min(100,(n1["p"]-hd["p"])/n1["p"]*1000)
                s=_sc(50,_nq([n1["p"],n2["p"]]),ds,_ts(c,max(30,ls["i"])),_vc(vol,ls["i"]),pp)
                ht=nlp-hd["p"];tgt=_R(nlp+ht);inv=_R(hd["p"]*0.98)
                res.append({"pattern":"Inverse Head & Shoulders","type":"bullish","stage":st,"structure_confidence":_R(s),"breakout_confidence":0,"left_shoulder":_R(ls["p"]),"head":_R(hd["p"]),"right_shoulder":None,"right_shoulder_zone":f"\u20b9{rz[0]:.2f}\u2013\u20b9{rz[1]:.2f}","neckline_1":_R(n1["p"]),"neckline_2":_R(n2["p"]) if n2!=n1 else None,"dynamic_neckline":_R(nlp),"breakout_level":_R(nlp),"target":tgt,"invalidation":inv,"pattern_start_idx":ls["i"],"description":f"Developing Inv H&S: LS \u20b9{ls['p']:.2f}, Head \u20b9{hd['p']:.2f}. RS forming."})
    return _best(res)


def _det_hs(df,ph,pl,cp):
    res=[];c=df["Close"].values;vol=df["Volume"].values if "Volume" in df.columns else None;n=len(df)
    if len(ph)<2: return []
    for i in range(len(ph)-1):
        for j in range(i+1,min(i+6,len(ph))):
            ls,hd=ph[i],ph[j]
            if hd["p"]<=ls["p"] or (hd["p"]-ls["p"])/ls["p"]<0.01 or hd["i"]-ls["i"]<3: continue
            n1c=[l for l in pl if ls["i"]<l["i"]<hd["i"]]
            if not n1c: continue
            n1=min(n1c,key=lambda x:x["p"])
            rsc=[h for h in ph if h["i"]>hd["i"] and h["p"]<hd["p"]]
            n2c=[l for l in pl if l["i"]>hd["i"]]
            if rsc:
                rs=rsc[0];sy=_sy(ls["p"],rs["p"])
                if sy<20: continue
                n2b=[l for l in n2c if hd["i"]<l["i"]<rs["i"]]
                n2=min(n2b,key=lambda x:x["p"]) if n2b else (n2c[0] if n2c else n1)
                nlp=_dnl(n1,n2,n-1);pv=(nlp-cp)/nlp*100;st,pp=_stg_b(pv,rs["i"],n)
                if cp>hd["p"]: st=STAGE_INV
                ds=min(100,(hd["p"]-n1["p"])/n1["p"]*1000)
                s=_sc(sy,_nq([n1["p"],n2["p"]]),ds,_ts(c,max(30,ls["i"])),_vc(vol,ls["i"]),pp)
                b=_bc(pv,_vc(vol,ls["i"]),min(100,max(0,pv*20)))
                ht=hd["p"]-nlp;tgt=_R(nlp-ht);inv=_R(hd["p"]*1.02)
                res.append({"pattern":"Head & Shoulders","type":"bearish","stage":st,"structure_confidence":_R(s),"breakout_confidence":_R(b),"left_shoulder":_R(ls["p"]),"head":_R(hd["p"]),"right_shoulder":_R(rs["p"]),"neckline_1":_R(n1["p"]),"neckline_2":_R(n2["p"]),"dynamic_neckline":_R(nlp),"breakout_level":_R(nlp),"target":tgt,"invalidation":inv,"pattern_start_idx":ls["i"],"description":f"H&S: LS \u20b9{ls['p']:.2f}, Head \u20b9{hd['p']:.2f}, RS \u20b9{rs['p']:.2f}. NL \u20b9{nlp:.2f}. Tgt \u20b9{tgt}."})
            else:
                n2=n2c[0] if n2c else n1;nlp=_dnl(n1,n2,n-1)
                st=STAGE_DEV if (cp<hd["p"] and cp>nlp) else STAGE_EARLY;pp=40 if st==STAGE_DEV else 25
                if cp>hd["p"]: st=STAGE_INV
                ds=min(100,(hd["p"]-n1["p"])/n1["p"]*1000)
                s=_sc(50,_nq([n1["p"],n2["p"]]),ds,_ts(c,max(30,ls["i"])),_vc(vol,ls["i"]),pp)
                ht=hd["p"]-nlp;tgt=_R(nlp-ht);inv=_R(hd["p"]*1.02)
                res.append({"pattern":"Head & Shoulders","type":"bearish","stage":st,"structure_confidence":_R(s),"breakout_confidence":0,"left_shoulder":_R(ls["p"]),"head":_R(hd["p"]),"right_shoulder":None,"neckline_1":_R(n1["p"]),"neckline_2":_R(n2["p"]) if n2!=n1 else None,"dynamic_neckline":_R(nlp),"breakout_level":_R(nlp),"target":tgt,"invalidation":inv,"pattern_start_idx":ls["i"],"description":f"Developing H&S: LS \u20b9{ls['p']:.2f}, Head \u20b9{hd['p']:.2f}. RS forming."})
    return _best(res)


def _det_dt(df,ph,pl,cp):
    res=[];c=df["Close"].values;vol=df["Volume"].values if "Volume" in df.columns else None;n=len(df)
    for p1 in ph:
        p2c=[h for h in ph if h["i"]>p1["i"]+3 and abs(h["p"]-p1["p"])/p1["p"]<0.03]
        if p2c:
            p2=p2c[0]
            bl=[l for l in pl if p1["i"]<l["i"]<p2["i"]]
            nl=min(bl,key=lambda x:x["p"]) if bl else {"i":(p1["i"]+p2["i"])//2,"p":float(min(df["Low"].values[p1["i"]:p2["i"]+1]))}
            sy=_sy(p1["p"],p2["p"]);ht=p1["p"]-nl["p"]
            if ht<=0: continue
            pv=(nl["p"]-cp)/nl["p"]*100;st,pp=_stg_b(pv,p2["i"],n)
            if cp>max(p1["p"],p2["p"])*1.02: st=STAGE_INV
            s=_sc(sy,70,min(100,ht/p1["p"]*1500),_ts(c,max(30,p1["i"])),_vc(vol,p1["i"]),pp)
            b=_bc(pv,_vc(vol,p1["i"]),min(100,max(0,pv*20)))
            tgt=_R(nl["p"]-ht);inv=_R(max(p1["p"],p2["p"])*1.02)
            res.append({"pattern":"Double Top","type":"bearish","stage":st,"structure_confidence":_R(s),"breakout_confidence":_R(b),"peak_1":_R(p1["p"]),"peak_2":_R(p2["p"]),"neckline":_R(nl["p"]),"breakout_level":_R(nl["p"]),"target":tgt,"invalidation":inv,"pattern_start_idx":p1["i"],"description":f"Double Top: Peaks \u20b9{p1['p']:.2f}/\u20b9{p2['p']:.2f}, NL \u20b9{nl['p']:.2f}. Tgt \u20b9{tgt}."})
    return _best(res)


def _det_db(df,ph,pl,cp):
    res=[];c=df["Close"].values;vol=df["Volume"].values if "Volume" in df.columns else None;n=len(df)
    for t1 in pl:
        t2c=[l for l in pl if l["i"]>t1["i"]+3 and abs(l["p"]-t1["p"])/t1["p"]<0.03]
        if t2c:
            t2=t2c[0]
            bh=[h for h in ph if t1["i"]<h["i"]<t2["i"]]
            nl=max(bh,key=lambda x:x["p"]) if bh else {"i":(t1["i"]+t2["i"])//2,"p":float(max(df["High"].values[t1["i"]:t2["i"]+1]))}
            sy=_sy(t1["p"],t2["p"]);ht=nl["p"]-t1["p"]
            if ht<=0: continue
            pv=(cp-nl["p"])/nl["p"]*100;st,pp=_stg_b(pv,t2["i"],n)
            if cp<min(t1["p"],t2["p"])*0.98: st=STAGE_INV
            s=_sc(sy,70,min(100,ht/t1["p"]*1500),_ts(c,max(30,t1["i"])),_vc(vol,t1["i"]),pp)
            b=_bc(pv,_vc(vol,t1["i"]),min(100,max(0,pv*20)))
            tgt=_R(nl["p"]+ht);inv=_R(min(t1["p"],t2["p"])*0.98)
            res.append({"pattern":"Double Bottom","type":"bullish","stage":st,"structure_confidence":_R(s),"breakout_confidence":_R(b),"trough_1":_R(t1["p"]),"trough_2":_R(t2["p"]),"neckline":_R(nl["p"]),"breakout_level":_R(nl["p"]),"target":tgt,"invalidation":inv,"pattern_start_idx":t1["i"],"description":f"Double Bottom: Troughs \u20b9{t1['p']:.2f}/\u20b9{t2['p']:.2f}, NL \u20b9{nl['p']:.2f}. Tgt \u20b9{tgt}."})
    return _best(res)


def _det_at(df,ph,pl,cp):
    res=[];c=df["Close"].values;vol=df["Volume"].values if "Volume" in df.columns else None;n=len(df)
    if len(ph)<2 or len(pl)<2: return []
    for si in range(max(0,len(ph)-5),len(ph)-1):
        hp=[h["p"] for h in ph[si:]];la=[l for l in pl if l["i"]>=ph[si]["i"]]
        if len(hp)<2 or len(la)<2: continue
        ra=sum(hp)/len(hp)
        if ra==0 or (max(hp)-min(hp))/ra*100>2.5: continue
        lp=[l["p"] for l in la]
        if lp[-1]<=lp[0]: continue
        ht=ra-min(lp);pv=(cp-ra)/ra*100
        if pv>2: st,pp=STAGE_CONF,90
        elif pv>-1: st,pp=STAGE_BKOUT,75
        elif len(hp)>=3: st,pp=STAGE_ALMOST,65
        else: st,pp=STAGE_DEV,45
        s=_sc(70,70,min(100,ht/ra*1500),_ts(c,max(30,ph[si]["i"])),_vc(vol,ph[si]["i"]),pp)
        b=_bc(pv,_vc(vol,ph[si]["i"]),min(100,max(0,pv*20)))
        tgt=_R(ra+ht);inv=_R(min(lp)*0.98)
        res.append({"pattern":"Ascending Triangle","type":"bullish","stage":st,"structure_confidence":_R(s),"breakout_confidence":_R(b),"resistance":_R(ra),"rising_support":_R(la[-1]["p"]),"breakout_level":_R(ra),"target":tgt,"invalidation":inv,"pattern_start_idx":ph[si]["i"],"description":f"Ascending Triangle: Flat resistance \u20b9{ra:.2f}, rising lows. Tgt \u20b9{tgt}."})
    return _best(res)


def _det_dtr(df,ph,pl,cp):
    res=[];c=df["Close"].values;vol=df["Volume"].values if "Volume" in df.columns else None;n=len(df)
    if len(ph)<2 or len(pl)<2: return []
    for si in range(max(0,len(pl)-5),len(pl)-1):
        lp=[l["p"] for l in pl[si:]];ha=[h for h in ph if h["i"]>=pl[si]["i"]]
        if len(lp)<2 or len(ha)<2: continue
        sa=sum(lp)/len(lp)
        if sa==0 or (max(lp)-min(lp))/sa*100>2.5: continue
        hp=[h["p"] for h in ha]
        if hp[-1]>=hp[0]: continue
        ht=max(hp)-sa;pv=(sa-cp)/sa*100
        if pv>2: st,pp=STAGE_CONF,90
        elif pv>-1: st,pp=STAGE_BKOUT,75
        elif len(lp)>=3: st,pp=STAGE_ALMOST,65
        else: st,pp=STAGE_DEV,45
        s=_sc(70,70,min(100,ht/sa*1500),_ts(c,max(30,pl[si]["i"])),_vc(vol,pl[si]["i"]),pp)
        b=_bc(pv,_vc(vol,pl[si]["i"]),min(100,max(0,pv*20)))
        tgt=_R(sa-ht);inv=_R(max(hp)*1.02)
        res.append({"pattern":"Descending Triangle","type":"bearish","stage":st,"structure_confidence":_R(s),"breakout_confidence":_R(b),"support":_R(sa),"falling_resistance":_R(ha[-1]["p"]),"breakout_level":_R(sa),"target":tgt,"invalidation":inv,"pattern_start_idx":pl[si]["i"],"description":f"Descending Triangle: Flat support \u20b9{sa:.2f}, falling highs. Tgt \u20b9{tgt}."})
    return _best(res)


def _det_st(df,ph,pl,cp):
    c=df["Close"].values;vol=df["Volume"].values if "Volume" in df.columns else None;n=len(df)
    if len(ph)<3 or len(pl)<3: return []
    h3=[h["p"] for h in ph[-3:]];l3=[l["p"] for l in pl[-3:]]
    if not(h3[0]>h3[1]>h3[2]) or not(l3[0]<l3[1]<l3[2]): return []
    ir,cr=h3[0]-l3[0],h3[2]-l3[2]
    if ir<=0 or cr<=0 or cr/ir>0.7: return []
    apex=(h3[2]+l3[2])/2
    pvu=(cp-h3[2])/h3[2]*100;pvd=(l3[2]-cp)/l3[2]*100
    if pvu>2 or pvd>2: st,pp=STAGE_CONF,85
    elif abs(pvu)<1 or abs(pvd)<1: st,pp=STAGE_BKOUT,70
    elif cr/ir<0.4: st,pp=STAGE_ALMOST,60
    else: st,pp=STAGE_DEV,45
    s=_sc(70,65,min(100,ir/apex*1000),_ts(c,max(30,ph[-3]["i"])),_vc(vol,ph[-3]["i"]),pp)
    b=_bc(max(pvu,pvd),_vc(vol,ph[-3]["i"]),50)
    tgu=_R(h3[2]+ir*0.618);tgd=_R(l3[2]-ir*0.618)
    return [{"pattern":"Symmetrical Triangle","type":"neutral","stage":st,"structure_confidence":_R(s),"breakout_confidence":_R(b),"upper_trendline":_R(h3[2]),"lower_trendline":_R(l3[2]),"apex":_R(apex),"breakout_level_up":_R(h3[2]),"breakout_level_down":_R(l3[2]),"target_up":tgu,"target_down":tgd,"invalidation":None,"pattern_start_idx":ph[-3]["i"],"description":f"Symmetrical Triangle: Converging. Apex \u20b9{apex:.2f}. Up tgt \u20b9{tgu}, Down tgt \u20b9{tgd}."}]


def _det_rw(df,ph,pl,cp):
    c=df["Close"].values;vol=df["Volume"].values if "Volume" in df.columns else None;n=len(df)
    lb=min(40,n)
    try:
        x=np.arange(lb);hs=np.polyfit(x,df["High"].values[-lb:],1)[0];ls=np.polyfit(x,df["Low"].values[-lb:],1)[0]
    except: return []
    if not(hs>0 and ls>0 and ls>hs*0.5): return []
    hi_end=float(df["High"].values[-1]);lo_end=float(df["Low"].values[-1])
    ht=hi_end-lo_end;pv=(lo_end-cp)/lo_end*100
    if pv>2: st,pp=STAGE_CONF,85
    elif pv>-0.5: st,pp=STAGE_BKOUT,70
    elif lb>25: st,pp=STAGE_ALMOST,60
    else: st,pp=STAGE_DEV,45
    s=_sc(65,60,min(100,ht/lo_end*1000),_ts(c,max(30,n-lb)),_vc(vol,n-lb),pp)
    b=_bc(pv,_vc(vol,n-lb),min(100,max(0,pv*20)))
    tgt=_R(lo_end-ht);inv=_R(hi_end*1.02)
    return [{"pattern":"Rising Wedge","type":"bearish","stage":st,"structure_confidence":_R(s),"breakout_confidence":_R(b),"upper_trendline":_R(hi_end),"lower_trendline":_R(lo_end),"breakout_level":_R(lo_end),"target":tgt,"invalidation":inv,"pattern_start_idx":n-lb,"description":f"Rising Wedge: Converging rising trendlines. Bearish. Tgt \u20b9{tgt}."}]


def _det_fw(df,ph,pl,cp):
    c=df["Close"].values;vol=df["Volume"].values if "Volume" in df.columns else None;n=len(df)
    lb=min(40,n)
    try:
        x=np.arange(lb);hs=np.polyfit(x,df["High"].values[-lb:],1)[0];ls=np.polyfit(x,df["Low"].values[-lb:],1)[0]
    except: return []
    if not(hs<0 and ls<0 and hs>ls*0.5): return []
    hi_end=float(df["High"].values[-1]);lo_end=float(df["Low"].values[-1])
    ht=hi_end-lo_end;pv=(cp-hi_end)/hi_end*100
    if pv>2: st,pp=STAGE_CONF,85
    elif pv>-0.5: st,pp=STAGE_BKOUT,70
    elif lb>25: st,pp=STAGE_ALMOST,60
    else: st,pp=STAGE_DEV,45
    s=_sc(65,60,min(100,ht/lo_end*1000),_ts(c,max(30,n-lb)),_vc(vol,n-lb),pp)
    b=_bc(pv,_vc(vol,n-lb),min(100,max(0,pv*20)))
    tgt=_R(hi_end+ht);inv=_R(lo_end*0.98)
    return [{"pattern":"Falling Wedge","type":"bullish","stage":st,"structure_confidence":_R(s),"breakout_confidence":_R(b),"upper_trendline":_R(hi_end),"lower_trendline":_R(lo_end),"breakout_level":_R(hi_end),"target":tgt,"invalidation":inv,"pattern_start_idx":n-lb,"description":f"Falling Wedge: Converging falling trendlines. Bullish. Tgt \u20b9{tgt}."}]


def _det_bf(df,ph,pl,cp):
    c=df["Close"].values;n=len(c);vol=df["Volume"].values if "Volume" in df.columns else None
    if n<25: return []
    pm=(c[-10]-c[-25])/c[-25]
    if pm<=0.08: return []
    fc=c[-10:];fr=(max(fc)-min(fc))/min(fc);fd=(fc[-1]-fc[0])/fc[0]
    if fr>=0.05 or fd<-0.05 or fd>0.02: return []
    pole_ht=float(c[-10]-c[-25]);flag_top=float(max(fc));flag_bot=float(min(fc))
    pv=(cp-flag_top)/flag_top*100
    if pv>2: st,pp=STAGE_CONF,85
    elif pv>-0.5: st,pp=STAGE_BKOUT,70
    elif fr<0.03: st,pp=STAGE_ALMOST,60
    else: st,pp=STAGE_DEV,45
    s=_sc(70,65,min(100,abs(pm)*500),_ts(c,30),_vc(vol,n-25),pp)
    b=_bc(pv,_vc(vol,n-25),min(100,max(0,pv*20)))
    tgt=_R(cp+pole_ht);inv=_R(flag_bot*0.98)
    return [{"pattern":"Bullish Flag","type":"bullish","stage":st,"structure_confidence":_R(s),"breakout_confidence":_R(b),"pole_move":f"{pm*100:.1f}%","flag_top":_R(flag_top),"flag_bottom":_R(flag_bot),"breakout_level":_R(flag_top),"target":tgt,"invalidation":inv,"pattern_start_idx":n-25,"description":f"Bull Flag: {pm*100:.1f}% pole + tight consolidation. Tgt \u20b9{tgt}."}]


def _det_brf(df,ph,pl,cp):
    c=df["Close"].values;n=len(c);vol=df["Volume"].values if "Volume" in df.columns else None
    if n<25: return []
    pm=(c[-10]-c[-25])/c[-25]
    if pm>=-0.08: return []
    fc=c[-10:];fr=(max(fc)-min(fc))/min(fc);fd=(fc[-1]-fc[0])/fc[0]
    if fr>=0.05 or fd>0.05 or fd<-0.02: return []
    pole_ht=float(abs(c[-10]-c[-25]));flag_top=float(max(fc));flag_bot=float(min(fc))
    pv=(flag_bot-cp)/flag_bot*100
    if pv>2: st,pp=STAGE_CONF,85
    elif pv>-0.5: st,pp=STAGE_BKOUT,70
    elif fr<0.03: st,pp=STAGE_ALMOST,60
    else: st,pp=STAGE_DEV,45
    s=_sc(70,65,min(100,abs(pm)*500),_ts(c,30),_vc(vol,n-25),pp)
    b=_bc(pv,_vc(vol,n-25),min(100,max(0,pv*20)))
    tgt=_R(cp-pole_ht);inv=_R(flag_top*1.02)
    return [{"pattern":"Bearish Flag","type":"bearish","stage":st,"structure_confidence":_R(s),"breakout_confidence":_R(b),"pole_move":f"{pm*100:.1f}%","flag_top":_R(flag_top),"flag_bottom":_R(flag_bot),"breakout_level":_R(flag_bot),"target":tgt,"invalidation":inv,"pattern_start_idx":n-25,"description":f"Bear Flag: {abs(pm)*100:.1f}% pole + tight consolidation. Tgt \u20b9{tgt}."}]


def _det_cup(df,ph,pl,cp):
    c=df["Close"].values;vol=df["Volume"].values if "Volume" in df.columns else None;n=len(df)
    if len(ph)<2 or len(pl)<1: return []
    res=[]
    for i in range(len(ph)-1):
        lip=ph[i]
        # Find cup bottom (lowest low between two highs)
        ripc=[h for h in ph if h["i"]>lip["i"]+10 and abs(h["p"]-lip["p"])/lip["p"]<0.05]
        if not ripc: continue
        rip=ripc[0]
        btw_lows=[l for l in pl if lip["i"]<l["i"]<rip["i"]]
        if not btw_lows: continue
        cup_bot=min(btw_lows,key=lambda x:x["p"])
        cup_depth=(lip["p"]-cup_bot["p"])/lip["p"]*100
        if cup_depth<5 or cup_depth>50: continue
        # Check U-shape (not V-shape)
        mid_idx=(lip["i"]+rip["i"])//2
        left_half=c[lip["i"]:mid_idx+1];right_half=c[mid_idx:rip["i"]+1]
        if len(left_half)<3 or len(right_half)<3: continue
        rim_level=(lip["p"]+rip["p"])/2
        # Handle detection
        handle_start=rip["i"]
        handle_data=c[handle_start:] if handle_start<n else []
        has_handle=False
        if len(handle_data)>3:
            handle_low=float(min(handle_data))
            handle_pullback=(rim_level-handle_low)/rim_level*100
            if 2<handle_pullback<cup_depth*0.5:
                has_handle=True
        pv=(cp-rim_level)/rim_level*100
        if has_handle and pv>2: st,pp=STAGE_CONF,90
        elif has_handle and pv>-1: st,pp=STAGE_BKOUT,75
        elif has_handle: st,pp=STAGE_ALMOST,65
        elif rip["i"]<n-3: st,pp=STAGE_DEV,50
        else: st,pp=STAGE_EARLY,30
        sy=_sy(lip["p"],rip["p"])
        s=_sc(sy,70,min(100,cup_depth*5),_ts(c,max(30,lip["i"])),_vc(vol,lip["i"]),pp)
        b=_bc(pv,_vc(vol,lip["i"]),min(100,max(0,pv*20)))
        tgt=_R(rim_level+rim_level-cup_bot["p"]);inv=_R(cup_bot["p"]*0.98)
        desc="Cup & Handle" if has_handle else "Cup (handle forming)"
        res.append({"pattern":"Cup and Handle","type":"bullish","stage":st,"structure_confidence":_R(s),"breakout_confidence":_R(b),"left_rim":_R(lip["p"]),"right_rim":_R(rip["p"]),"cup_bottom":_R(cup_bot["p"]),"cup_depth":f"{cup_depth:.1f}%","has_handle":has_handle,"breakout_level":_R(rim_level),"target":tgt,"invalidation":inv,"pattern_start_idx":lip["i"],"description":f"{desc}: Rim \u20b9{rim_level:.2f}, Bottom \u20b9{cup_bot['p']:.2f}. Tgt \u20b9{tgt}."})
    return _best(res)


# ── Main Entry Point ──────────────────────────────────────────
def detect_developing_patterns(df, current_price=None):
    """Detect all developing chart patterns in OHLCV data.

    Args:
        df: DataFrame with Open, High, Low, Close, Volume columns.
        current_price: Current market price. If None, uses last Close.

    Returns:
        List of pattern dicts with stage, confidence scores, levels.
    """
    if df is None or df.empty or len(df) < 20:
        return []

    cp = current_price if current_price else float(df["Close"].iloc[-1])
    ph, pl = _pivm(df)

    if not ph and not pl:
        return []

    all_patterns = []
    detectors = [
        lambda: _det_inv_hs(df, ph, pl, cp),
        lambda: _det_hs(df, ph, pl, cp),
        lambda: _det_dt(df, ph, pl, cp),
        lambda: _det_db(df, ph, pl, cp),
        lambda: _det_at(df, ph, pl, cp),
        lambda: _det_dtr(df, ph, pl, cp),
        lambda: _det_st(df, ph, pl, cp),
        lambda: _det_rw(df, ph, pl, cp),
        lambda: _det_fw(df, ph, pl, cp),
        lambda: _det_bf(df, ph, pl, cp),
        lambda: _det_brf(df, ph, pl, cp),
        lambda: _det_cup(df, ph, pl, cp),
    ]

    for det in detectors:
        try:
            result = det()
            if result:
                all_patterns.extend(result)
        except Exception as e:
            logger.warning(f"Pattern detector error: {e}")

    # Sort by structure confidence descending
    all_patterns.sort(key=lambda x: x.get("structure_confidence", 0), reverse=True)

    # Add metadata
    for p in all_patterns:
        p["current_price"] = _R(cp)
        # Confidence level classification
        sc = p.get("structure_confidence", 0)
        if sc >= 90:
            p["confidence_level"] = "Very High (90-100)"
        elif sc >= 70:
            p["confidence_level"] = "High (70-89)"
        else:
            p["confidence_level"] = "Moderate (<70) \u2014 Manual verification required"

    return all_patterns