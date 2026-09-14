"""Cached purchase-only x10 evaluation, checked against the stock shop simulator."""
from math import isfinite
from ccsr.errands.models import ErrandNeighbor
from ccsr.errands.scoring import age_score
from ccsr.game.gamestate import Purchase
from ccsr.errands.generator import _evaluate, price_horizon


class Evaluator:
    def __init__(self,ancestor,target,horizon):
        self.ancestor=ancestor;self.target=target;self.horizon=horizon
        self.names=tuple(ancestor.building_catalog)
        self.index={n:i for i,n in enumerate(self.names)}
        self.enabled=(ancestor.bulk_size==10 and not ancestor.selling_allowed and not ancestor.legacy_errands)
        self.ceiling=min(price_horizon(ancestor,horizon),target-ancestor.lifetime_cookies+ancestor.bank)
        self.prefix=[]
        for name in self.names:
            values=[0]
            while values[-1]<=self.ceiling and len(values)<1002:
                values.append(values[-1]+ancestor.building_price(name,additional_owned=len(values)-1))
            self.prefix.append(values)
        self.automatic=ancestor.automatic_cps();self.hand=ancestor.hand_cps()
        self.rate=self.automatic+self.hand

    def __call__(self,errand):
        a=self.ancestor
        if not self.enabled or errand.sales:
            return _evaluate(a,self.target,errand,self.horizon)
        actions=errand.purchase_order
        if not actions:return None
        price=0
        for i,q in enumerate(errand.building_quantities):
            if q>=len(self.prefix[i]):return None
            price+=self.prefix[i][q]
        if price>self.ceiling:return None
        for u in errand.upgrades:
            if not a.upgrades_allowed or u in a.purchased_upgrades:return None
            price+=a.upgrade_catalog[u].price
        if price>self.ceiling:return None
        needed=max(0,price-a.bank)
        if a.lifetime_cookies+needed>=self.target:return None
        pause=a.errand_delay+len(actions)*a.action_delay
        if self.rate<=0:
            if needed:return None
            duration=pause
        else:duration=max(pause,(needed+self.hand*pause)/self.rate)
        produced=max(needed,self.automatic*pause)
        lifetime=a.lifetime_cookies+produced
        if lifetime>=self.target:return None
        handmade=a.handmade_cookies+self.hand*max(0,duration-pause)
        bank=a.bank+produced
        added=[0]*len(self.names);upgrades=set(a.purchased_upgrades);labels=[]
        for action in actions:
            name,q=action.item,action.quantity
            if action.operation=='buy':
                if not 1<=q<=10:return None
                i=self.index[name];before=added[i];after=before+q
                if after>=len(self.prefix[i]):return None
                cost=self.prefix[i][after]-self.prefix[i][before]
                if cost>bank:return None
                if q<10 and after+1<len(self.prefix[i]) and self.prefix[i][after+1]-self.prefix[i][before]<=bank:return None
                bank-=cost;added[i]=after;labels.append(f'{name} ×{q}')
            elif action.operation=='upgrade':
                u=a.upgrade_catalog[name]
                if name in upgrades or u.price>bank:return None
                if handmade<u.handmade_required or lifetime<u.cookies_required:return None
                if any(a.building_counts[b]+added[self.index[b]]<required for b,required in u.requirements):return None
                bank-=u.price;upgrades.add(name);labels.append(name)
            else:return None
        if tuple(added)!=errand.building_quantities:return None
        if upgrades-a.purchased_upgrades!=errand.upgrades:return None
        child=a.copy();child.age+=duration;child.lifetime_cookies=lifetime
        child.handmade_cookies=handmade;child.bank=bank
        child.building_counts={n:a.building_counts[n]+added[i] for i,n in enumerate(self.names)}
        child.purchased_upgrades=upgrades;child._automatic_cps_cache=None;child._automatic_cps_cache_achievement_count=None
        cps=child.cps()
        purchases=tuple(Purchase(action.operation,action.item,child.age,lifetime,cps,label,
                                 action.quantity,price,bank,len(actions)) for action,label in zip(actions,labels))
        return ErrandNeighbor(errand,child,purchases,age_score(a,child),child.age-a.age)
