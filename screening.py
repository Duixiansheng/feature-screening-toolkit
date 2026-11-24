"""Seven feature selection methods for binary classification training data."""
from dataclasses import dataclass
from itertools import combinations, product
import warnings

import numpy as np
from scipy.optimize import minimize
from scipy.stats import binom, spearmanr
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_selection import mutual_info_classif, mutual_info_regression
from sklearn.linear_model import LogisticRegression
from hsic import kernel_terms as HSIC
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

@dataclass(frozen=True)
class Settings:
    rfe_trees: int = 500
    boruta_trees: int = 500
    boruta_rounds: int = 100
    alpha: float = .05
    jobs: int = 1


def rank(scores):
    return np.argsort(-np.asarray(scores), kind="stable")


def compare(a, b, top=5):
    k = min(top, len(a), len(b))
    ra, rb = np.argsort(a), np.argsort(b)
    sa, sb = set(a[:k]), set(b[:k])
    return {"spearman": float(spearmanr(ra, rb).statistic) if len(a)>1 else 1.,
            "top_k_jaccard": len(sa & sb) / len(sa | sb) if k else None}


def forest(n, seed, cfg, class_weight="balanced", **kwargs):
    return RandomForestClassifier(n_estimators=n, min_samples_leaf=4, max_features="sqrt",
                                  class_weight=class_weight, random_state=seed, n_jobs=cfg.jobs, **kwargs)


def rfe(x, y, seed, cfg):
    active=list(range(x.shape[1]))
    path=[]
    while active:
        model=forest(cfg.rfe_trees,seed,cfg).fit(x[:,active],y)
        imp=model.feature_importances_
        removed=active[int(np.argmin(imp))]
        path.append(dict(features=active.copy(),importance=imp,removed=removed))
        active.remove(removed)
    return {"trees":cfg.rfe_trees,"seed":seed,"path":path,
            "rank":[row["removed"] for row in reversed(path)]}


def boruta(x, y, seed, cfg):
    rng=np.random.default_rng(seed)
    d=x.shape[1]
    status=np.zeros(d,int)
    hits=np.zeros(d,int)
    decision_round=np.zeros(d,int)
    history=[]
    alpha=cfg.alpha/(2*d*cfg.boruta_rounds)
    for it in range(1,cfg.boruta_rounds+1):
        pending=np.flatnonzero(status==0)
        if not len(pending): break
        active=np.flatnonzero(status>=0)
        shadows=np.column_stack([rng.permutation(x[:,j]) for j in active])
        importance=forest(cfg.boruta_trees,seed+it,cfg).fit(
            np.column_stack((x[:,active],shadows)),y).feature_importances_
        cutoff=float(importance[len(active):].max())
        hits[active]+=importance[:len(active)]>cutoff
        for j in pending:
            if binom.sf(hits[j]-1,it,.5)<=alpha: status[j]=1
            elif binom.cdf(hits[j],it,.5)<=alpha: status[j]=-1
            if status[j]: decision_round[j]=it
        history.append({"round":it,"active":active,"shadow_sources":active.copy(),
                        "importance":importance[:len(active)],"shadow_importance":importance[len(active):],
                        "status":status.copy()})
    return {"status":[{1:"Confirmed",0:"Tentative",-1:"Rejected"}[s] for s in status],
            "confirmed":np.flatnonzero(status==1),"tentative":np.flatnonzero(status==0),
            "rejected":np.flatnonzero(status==-1),"decision_round":decision_round,"hits":hits,
            "iterations":len(history),"stop_reason":"resolved" if not np.any(status==0) else "round_limit",
            "per_tail_alpha":alpha,"history":history}


def mrmr(x,y,seed):
    out={}
    for k in (3,5,10):
        rel=mutual_info_classif(x,y,n_neighbors=k,random_state=seed)
        red=np.column_stack([mutual_info_regression(x,x[:,j],n_neighbors=k,random_state=seed)
                             for j in range(x.shape[1])])
        red=(red+red.T)/2
        np.fill_diagonal(red,0)
        order,steps=[],[]
        for _ in rel:
            redundancy=red[order].mean(0) if order else np.zeros_like(rel)
            score=rel-redundancy
            score[order]=-np.inf
            j=int(np.argmax(score))
            order.append(j)
            steps.append([j,float(redundancy[j]),float(score[j])])
        out[k]={"rank":np.array(order),"relevance":rel,"redundancy":red,"steps":steps}
    return parameter_comparison(out)


def parameter_comparison(out):
    return {"settings":out,"pairwise":[{"settings":[a,b],**compare(out[a]["rank"],out[b]["rank"])}
                                      for a,b in combinations(out,2)]}


def relieff(z,y):
    n_available=int(np.bincount(y,minlength=2).min())
    if n_available<2: raise ValueError("ReliefF requires at least two rows in each class")
    near={}
    for label in (0,1):
        ix=np.flatnonzero(y==label)
        model=NearestNeighbors(n_neighbors=min(21,len(ix)),metric="manhattan").fit(z[ix])
        near[label]=ix[model.kneighbors(z,return_distance=False)]
    out={}
    for requested in (5,10,20):
        k=min(requested,n_available-1)
        w=np.zeros(z.shape[1])
        for label in (0,1):
            ix=np.flatnonzero(y==label)
            hit=near[label][ix]
            hit=np.take_along_axis(hit,np.argsort(hit==ix[:,None],axis=1,kind="stable")[:,:k],axis=1)
            miss=near[1-label][ix,:k]
            w+=(abs(z[ix,None,:]-z[miss]).mean(1)-abs(z[ix,None,:]-z[hit]).mean(1)).sum(0)
        out[requested]={"weights":w/len(z),"rank":rank(w),"effective_k":k}
    return parameter_comparison(out)


def hsic_lasso(z,y):
    gram,relevance=HSIC(z,y)
    results={}
    for frac in (.02,.05,.15):
        penalty=frac*max(float(relevance.max()),0.)
        def objective(beta):
            grad=gram@beta-relevance+penalty
            return beta@(grad-.5*gram@beta),grad
        opt=minimize(objective,np.zeros(z.shape[1]),jac=True,bounds=[(0,None)]*z.shape[1],
                     method="L-BFGS-B")
        if not opt.success: raise RuntimeError(opt.message)
        results[frac]={"lambda":penalty,"coefficients":opt.x,"selected":np.flatnonzero(opt.x>1e-8)}
    return {"kernel":"Gaussian sigma=1, normalized Delta, 4096-bin symmetric lookup", "settings":results}


def igr(v,y,min_leaf=2):
    if len(np.unique(y))<2: return {"threshold":None,"gain":0.,"adjusted_gain":0.,"split_info":0.,"ratio":0.}
    order=np.argsort(v,kind="stable")
    v,y=v[order].astype(float),y[order]
    splits=np.flatnonzero(v[:-1]<v[1:])+1
    splits=splits[(splits>=min_leaf)&(splits<=len(v)-min_leaf)]
    if not len(splits): return {"threshold":None,"gain":0.,"adjusted_gain":0.,"split_info":0.,"ratio":0.}
    def entropy(p):
        z=np.clip(p,1e-15,1-1e-15)
        return np.where((p==0)|(p==1),0,-z*np.log2(z)-(1-z)*np.log2(1-z))
    cum=np.cumsum(y,dtype=float)
    left=cum[splits-1]
    f=splits/len(v)
    gains=entropy(cum[-1]/len(v))-f*entropy(left/splits)-(1-f)*entropy((cum[-1]-left)/(len(v)-splits))
    i=int(np.argmax(gains))
    adjusted=max(0.,float(gains[i]-np.log2(len(splits))/len(v)))
    split=int(splits[i])
    e=float(entropy(f[i]))
    return {"threshold":float(v[split-1]+(v[split]-v[split-1])/2) if adjusted>0 else None,
            "gain":float(gains[i]),"adjusted_gain":adjusted,"split_info":e,"ratio":adjusted/e}


def elastic_net(z,y,seed):
    out={}
    for weighting, C, ratio in product(("balanced","unweighted"),(.03,.3,3.),(.25,.75)):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always",ConvergenceWarning)
            model=LogisticRegression(penalty="elasticnet",solver="saga",C=C,l1_ratio=ratio,
                                     class_weight="balanced" if weighting=="balanced" else None,
                                     max_iter=20000,tol=1e-4,random_state=seed).fit(z,y)
        coef=model.coef_[0]
        result={"weighting":weighting,"C":C,"l1_ratio":ratio,"coefficients":coef,
                "intercept":float(model.intercept_[0]),"selected":np.flatnonzero(abs(coef)>1e-8),
                "iterations":int(model.n_iter_[0]),
                "converged":not any(issubclass(w.category,ConvergenceWarning) for w in caught)}
        out[f"{weighting}/{C}/{ratio}"]=result
    return {"primary_weighting":"balanced","settings":out}

METHODS={"RF-RFE","Boruta","mRMR","ReliefF","HSIC-Lasso","IGR","Elastic Net"}


def fit_method(method,x,y,seed,cfg=Settings()):
    x=np.asarray(x)
    y=np.asarray(y,dtype=int)
    if x.ndim!=2 or not x.shape[1] or len(x)!=len(y) or not np.isfinite(x).all():
        raise ValueError("Expected finite numeric training matrix")
    if not np.array_equal(np.unique(y),[0,1]):
        raise ValueError("Training data must contain both binary classes")
    if method not in METHODS: raise ValueError(method)
    if method=="RF-RFE": return rfe(x,y,seed,cfg)
    if method=="Boruta": return boruta(x,y,seed,cfg)
    if method=="mRMR": return mrmr(x,y,seed)
    if method=="IGR":
        scores=[igr(v,y) for v in x.T]
        ordered=rank([s["ratio"] for s in scores])
        return {"scores":scores,"rank":ordered,"positive_gain_rank":[int(i) for i in ordered if scores[i]["ratio"]>0]}
    scale=StandardScaler().fit(x.astype(float))
    z=scale.transform(x.astype(float))
    if method=="ReliefF": result=relieff(z,y)
    elif method=="HSIC-Lasso": result=hsic_lasso(z,y)
    else: result=elastic_net(z,y,seed)
    result["scaler"]={"mean":scale.mean_,"scale":scale.scale_}
    return result


