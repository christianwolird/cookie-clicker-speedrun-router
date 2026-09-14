#pragma once
#include "native_generator.hpp"

// Optional incumbent-guided proposals. These are additional hypotheses, not
// claims that a ruler's purchase ordering or quantities are mandatory.
template<class Completion>
std::vector<Neighbor> guided_generate(const NativeState&a,const std::vector<Actions>&templates,
                                     const NativeOptions&o,int width,Completion completion){
    std::unordered_set<Actions,ActionHash> seen;
    std::unordered_map<StateKey,Neighbor,StateHash> distinct;
    auto add=[&](Actions actions){
        if(!actions.size||actions.size>o.max_actions)return;
        actions=canonicalize(a,actions,o.canonical_partial);if(!seen.insert(actions).second)return;
        NativeState state;if(!evaluate(a,actions.data.data(),actions.size,state,1e6,o.horizon))return;
        auto key=state_key(state);auto old=distinct.find(key);
        if(old!=distinct.end()&&old->second.state.age<=state.age)return;
        distinct[key]={state,actions,age_score(a,state),completion(state),strategy(a,state,o.strategy_bins)};
    };
    for(const auto&original:templates){
        Actions base;
        for(int j=0;j<original.size;++j){auto c=original.data[j];
            if(upgrade_code(c)&&(a.upgrades&(1u<<item_index(c))))continue;
            base.data[base.size++]=c;
        }
        add(base);
        for(int j=0;j<base.size;++j){
            if(!upgrade_code(base.data[j]))for(int q=1;q<=10;++q){Actions changed=base;changed.data[j]=buy_code(item_index(base.data[j]),q);add(changed);}
            Actions removed;for(int k=0;k<base.size;++k)if(k!=j)removed.data[removed.size++]=base.data[k];add(removed);
            if(j+1<base.size){Actions swapped=base;std::swap(swapped.data[j],swapped.data[j+1]);add(swapped);}
        }
        // Keeping an upgrade in the same errand can make partial x10 clicks
        // affordable in a different order; include both endpoint positions.
        if(base.size<o.max_actions)for(int u=0;u<NU;++u)if(!(a.upgrades&(1u<<u))){
            Actions appended=base;appended.data[appended.size++]=up_code(u);add(appended);
            Actions prepended;prepended.data[prepended.size++]=up_code(u);
            for(int j=0;j<base.size;++j)prepended.data[prepended.size++]=base.data[j];add(prepended);
        }
    }
    std::vector<Neighbor> result;result.reserve(distinct.size());for(auto&kv:distinct)result.push_back(std::move(kv.second));
    std::sort(result.begin(),result.end(),[](const Neighbor&a,const Neighbor&b){
        if(a.score!=b.score)return a.score<b.score;
        if(a.raw_score!=b.raw_score)return a.raw_score<b.raw_score;
        return a.actions.data<b.actions.data;
    });
    if(int(result.size())>width)result.resize(width);return result;
}
