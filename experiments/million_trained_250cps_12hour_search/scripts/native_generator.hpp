#pragma once
#include "native_core.hpp"
#include <cstring>
#include <map>
#include <set>
#include <unordered_map>
#include <unordered_set>

struct NativeOptions {
    int width=20,search_width=40,pops=100,max_actions=12;
    int canonical=1,early_stop=0,all_evaluated=1,queue_diversity=0,result_diversity=0,seed_reserve=0,anchor_all=0,two_step_pool=0,upgrade_macros=0,expand_seeds=0,future_upgrade_mask=0,three_step=0,lookahead_branches=6,strategy_bins=0,canonical_partial=0,quantity_children=0;
    double horizon=16,upgrade_bonus=0,expansion_balance=0,two_step_weight=0,future_weight=1;
    std::array<int,NB> future_counts{};
};
struct Neighbor {NativeState state;Actions actions;double raw_score,score;std::uint64_t strategy;};
inline bool within_inventory(const NativeState&s,const NativeState&cap){
    if(s.upgrades&~cap.upgrades)return false;
    for(int j=0;j<NB;++j)if(s.buildings[j]>cap.buildings[j])return false;
    return true;
}
inline std::uint64_t double_bits(double d){std::uint64_t u;std::memcpy(&u,&d,8);return u;}
struct StateKey {
    std::uint64_t inventory,bank,baked,hand;
    bool operator==(const StateKey&o)const{return inventory==o.inventory&&bank==o.bank&&baked==o.baked&&hand==o.hand;}
};
static_assert(NP<128&&NU+7*NB<=64,"Inventory must fit losslessly in the packed key");
inline StateKey state_key(const NativeState&s){StateKey k;k.inventory=s.upgrades;for(int n:s.buildings)k.inventory=(k.inventory<<7)|std::uint64_t(n);k.bank=double_bits(s.bank);k.baked=double_bits(s.baked);k.hand=double_bits(std::min(s.handmade,1000.0));return k;}
struct StateHash {std::size_t operator()(const StateKey&k)const {std::size_t h=k.inventory;h=(h^k.bank)*1099511628211ULL;h=(h^k.baked)*1099511628211ULL;return (h^k.hand)*1099511628211ULL;}};
inline double age_score(const NativeState&a,const NativeState&b){auto ar=rates(a).total(),br=rates(b).total();if(br<=ar)return std::numeric_limits<double>::infinity();return (b.age-a.age)*br/(br-ar);}
inline double future_score(const NativeState&a,const NativeState&b,const NativeOptions&o){
    double raw=age_score(a,b);if(!o.future_weight)return raw;
    bool future_buildings=std::any_of(o.future_counts.begin(),o.future_counts.end(),[](int q){return q>0;});
    if(!o.future_upgrade_mask&&!future_buildings)return raw;
    // Optimistic ranking only: no upgrade is actually added to either state.
    // Keeping the smaller immediate score preserves already-realized value.
    NativeState future_a=a,future_b=b;
    for(int j=0;j<NB;++j){future_a.buildings[j]+=o.future_counts[j];future_b.buildings[j]+=o.future_counts[j];}
    double potential=std::min(raw,age_score(future_a,future_b));
    future_a.upgrades|=o.future_upgrade_mask;future_b.upgrades|=o.future_upgrade_mask;
    potential=std::min(potential,age_score(future_a,future_b));
    return std::isfinite(raw)?(1-o.future_weight)*raw+o.future_weight*potential:potential;
}
inline std::uint64_t strategy(const NativeState&a,const NativeState&b,int bins=0){
    if(!bins){std::uint64_t key=std::uint64_t(b.upgrades&~a.upgrades)<<NB;for(int j=0;j<NB;++j)if(b.buildings[j]>a.buildings[j])key|=1u<<j;return key;}
    std::uint64_t key=std::uint64_t(b.upgrades&~a.upgrades)<<(5*NB);
    for(int j=0;j<NB;++j){int q=b.buildings[j]-a.buildings[j],bucket=0;
        if(bins==1){while(q){++bucket;q>>=1;}}
        else bucket=std::min(31,(q+4)/5);
        key|=std::uint64_t(bucket)<<(5*j);
    }
    return key;
}
inline std::vector<Actions> seeds(const NativeState&a,int max_actions){
    std::vector<Actions> result;result.reserve(NB*10+NU);
    for(int i=0;i<NB;++i)for(int q=1;q<=10;++q){Actions action;action.data[action.size++]=buy_code(i,q);result.push_back(action);}
    for(int i=0;i<NU;++i)if(!(a.upgrades&(1u<<i))){
        Actions action;bool good=true;
        for(int j=0;j<NB;++j)for(int q=a.buildings[j];q<UPGRADES[i].req[j];q+=10){if(action.size>=max_actions){good=false;break;}action.data[action.size++]=buy_code(j,10);}
        if(good&&action.size<max_actions){action.data[action.size++]=up_code(i);result.push_back(action);}
    }
    return result;
}
struct QueueItem {double score;int actions,index;std::uint64_t group;};
struct QueueLess {bool operator()(const QueueItem&a,const QueueItem&b)const {
    if(a.score!=b.score)return a.score<b.score;if(a.actions!=b.actions)return a.actions<b.actions;return a.index<b.index;
}};
inline std::vector<Neighbor> generate(const NativeState&a,const NativeOptions&o,double target=1e6,double max_age=0,const NativeState*inventory_cap=nullptr){
    std::unordered_map<Actions,int,ActionHash> seen;std::vector<Neighbor> evaluated;std::vector<int> popped,seed_ids;
    std::set<QueueItem,QueueLess> queue;std::unordered_map<std::uint64_t,int> group_counts,expanded_groups;
    const auto source_rates=rates(a);const double source_total=source_rates.total();
    bool future_buildings=std::any_of(o.future_counts.begin(),o.future_counts.end(),[](int q){return q>0;});
    bool changed_inventory=std::any_of(o.future_counts.begin(),o.future_counts.end(),[](int q){return q!=0;});
    NativeState future_source=a;for(int j=0;j<NB;++j)future_source.buildings[j]+=o.future_counts[j];
    double future_total=changed_inventory?rates(future_source).total():source_total;
    future_source.upgrades|=o.future_upgrade_mask;
    double masked_total=o.future_upgrade_mask?rates(future_source).total():future_total;
    auto score_after=[&](const NativeState&b,double before){
        double after=rates(b).total();if(after<=before)return std::numeric_limits<double>::infinity();
        return (b.age-a.age)*after/(after-before);
    };
    auto add=[&](Actions actions)->int {
        if(actions.size>o.max_actions||actions.size>MAX_ACTIONS)return -1;
        if(o.canonical)actions=canonicalize(a,actions,o.canonical_partial);
        auto memo=seen.emplace(actions,-1);if(!memo.second)return memo.first->second>=0?-2:memo.first->second;
        NativeState state;if(!evaluate(a,actions.data.data(),actions.size,state,target,o.horizon,&source_rates))return -1;
        if(max_age>0&&state.age>=max_age){memo.first->second=-3;return -3;}
        // Optional restricted search, not dominance: no-selling children can
        // only increase inventory. An excluded basket cannot grow back into
        // the allowed region. Default generation has no inventory constraint.
        if(inventory_cap&&!within_inventory(state,*inventory_cap)){memo.first->second=-3;return -3;}
        double raw=score_after(state,source_total),score=raw;
        if(o.future_weight&&(o.future_upgrade_mask||future_buildings)){
            NativeState forecast=state;for(int j=0;j<NB;++j)forecast.buildings[j]+=o.future_counts[j];
            double potential=changed_inventory?std::min(raw,score_after(forecast,future_total)):raw;
            if(o.future_upgrade_mask){forecast.upgrades|=o.future_upgrade_mask;potential=std::min(potential,score_after(forecast,masked_total));}
            score=std::isfinite(raw)?(1-o.future_weight)*raw+o.future_weight*potential:potential;
        }
        if(state.upgrades!=a.upgrades)score*=1-o.upgrade_bonus;
        int index=evaluated.size();auto group=strategy(a,state,o.strategy_bins);
        memo.first->second=index;
        evaluated.push_back({state,actions,raw,score,group});
        QueueItem next{score,actions.size,index,group};
        // With no group quota, a new worst entry would immediately remove
        // itself. Keep it among evaluated results, but avoid the queue churn.
        if(!o.queue_diversity&&!queue.empty()&&int(queue.size())>=o.search_width&&
           !QueueLess{}(next,*queue.rbegin()))return index;
        queue.insert(next);++group_counts[group];
        if(int(queue.size())>o.search_width){
            auto drop=std::prev(queue.end());
            if(o.queue_diversity){
                for(auto it=queue.rbegin();it!=queue.rend();++it)if(group_counts[it->group]>o.queue_diversity){drop=std::prev(it.base());break;}
            }
            --group_counts[drop->group];queue.erase(drop);
        }
        return index;
    };
    for(auto s:seeds(a,o.max_actions)){int id=add(s);if(id>=0)seed_ids.push_back(id);}
    std::size_t forced=0;
    for(int expansion=0;expansion<o.pops&&(!queue.empty()||(o.expand_seeds&&forced<seed_ids.size()));++expansion){
        int id;
        if(o.expand_seeds&&forced<seed_ids.size()){
            id=seed_ids[forced++];const auto&n=evaluated[id];
            auto at=queue.find({n.score,n.actions.size,id,n.strategy});
            if(at!=queue.end()){--group_counts[at->group];queue.erase(at);}
        }else{
        auto it=queue.begin();
        if(o.expansion_balance){
            double best=std::numeric_limits<double>::infinity();
            for(auto candidate=queue.begin();candidate!=queue.end();++candidate){
                double value=candidate->score*(1+o.expansion_balance*expanded_groups[candidate->group]);
                if(value<best){best=value;it=candidate;}
            }
        }
        id=it->index;--group_counts[it->group];queue.erase(it);
        }
        ++expanded_groups[evaluated[id].strategy];popped.push_back(id);
        // Copy: adding neighbors can reallocate the evaluated vector.
        Neighbor parent=evaluated[id];
        if(o.quantity_children){
            for(int j=0;j<NB;++j){Actions child=parent.actions;int partial=-1;
                for(int k=0;k<child.size;++k)if(!upgrade_code(child.data[k])&&item_index(child.data[k])==j&&quantity(child.data[k])<10){partial=k;break;}
                if(o.quantity_children>=4){
                    int first=partial>=0?quantity(child.data[partial])+1:1;
                    if(partial>=0||child.size<o.max_actions)for(int q=first;q<=10;++q){
                        child=parent.actions;if(partial>=0)child.data[partial]=buy_code(j,q);else child.data[child.size++]=buy_code(j,q);
                        // Skip an infeasible intermediate quantity. -2 means
                        // this valid basket was already evaluated elsewhere.
                        int added=add(child);if(added>=0||added==-2||added==-3)break;
                    }
                }else{
                    if(partial>=0){child.data[partial]=buy_code(j,quantity(child.data[partial])+1);add(child);}
                    else if(child.size<o.max_actions){child.data[child.size++]=buy_code(j,1);add(child);}
                }
                if((o.quantity_children==2||o.quantity_children==5)&&parent.actions.size<o.max_actions){child=parent.actions;child.data[child.size++]=buy_code(j,10);add(child);}
            }
        }
        if(parent.actions.size>=o.max_actions)continue;
        if(o.quantity_children==0||o.quantity_children==3)
            for(int j=0;j<NB;++j){
                int first=1;
                // A second partial click of the same building would already
                // have been affordable at the first click. Only a full batch
                // (which normalization can move before the partial) is possible.
                for(int k=0;k<parent.actions.size;++k){auto c=parent.actions.data[k];
                    if(!upgrade_code(c)&&item_index(c)==j&&quantity(c)<10){first=10;break;}
                }
                for(int q=first;q<=10;++q){Actions child=parent.actions;child.data[child.size++]=buy_code(j,q);add(child);}
            }
        for(int j=0;j<NU;++j)if(!(parent.state.upgrades&(1u<<j))){
            bool ready=true;for(int k=0;k<NB;++k)if(parent.state.buildings[k]<UPGRADES[j].req[k])ready=false;
            if(ready){Actions child=parent.actions;child.data[child.size++]=up_code(j);add(child);}
            else if(o.upgrade_macros){
                Actions child=parent.actions;bool good=true;
                for(int k=0;k<NB;++k)for(int q=parent.state.buildings[k];q<UPGRADES[j].req[k];q+=10){
                    if(child.size>=o.max_actions){good=false;break;}
                    child.data[child.size++]=buy_code(k,10);
                }
                if(good&&child.size<o.max_actions){child.data[child.size++]=up_code(j);add(child);}
            }
        }
    }
    std::vector<int> ids;if(o.all_evaluated){for(int i=0;i<int(evaluated.size());++i)ids.push_back(i);}else ids=popped;
    std::unordered_map<StateKey,int,StateHash> distinct;
    for(int id:ids){auto k=state_key(evaluated[id].state);auto found=distinct.find(k);if(found==distinct.end()||evaluated[id].state.age<evaluated[found->second].state.age)distinct[k]=id;}
    ids.clear();for(auto kv:distinct)ids.push_back(kv.second);
    auto order=[&](int x,int y){const auto&a=evaluated[x];const auto&b=evaluated[y];if(a.score!=b.score)return a.score<b.score;if(a.actions.size!=b.actions.size)return a.actions.size<b.actions.size;return x<y;};
    std::sort(ids.begin(),ids.end(),order);
    if(o.two_step_pool&&o.two_step_weight){
        std::vector<int> pool(ids.begin(),ids.begin()+std::min<int>(ids.size(),o.two_step_pool));
        pool.insert(pool.end(),seed_ids.begin(),seed_ids.end());std::sort(pool.begin(),pool.end());pool.erase(std::unique(pool.begin(),pool.end()),pool.end());
        for(int id:pool){
            auto&n=evaluated[id];double joint=n.raw_score;
            std::vector<std::pair<double,NativeState>> continuation;
            if(o.three_step)continuation.reserve(NB*10+NU);
            for(auto action:seeds(n.state,o.max_actions)){
                NativeState grand;if(evaluate(n.state,action.data.data(),action.size,grand,target,o.horizon)){
                    double value=age_score(a,grand);joint=std::min(joint,value);
                    if(o.three_step)continuation.push_back({value,grand});
                }
            }
            if(o.three_step){
                std::stable_sort(continuation.begin(),continuation.end(),[](const auto&a,const auto&b){return a.first<b.first;});
                for(int j=0;j<int(continuation.size());++j){const auto&grand=continuation[j].second;
                    // Preserve upgrade branches even when their immediate
                    // combined payoff is poor; that is why we look ahead.
                    if(j>=o.lookahead_branches&&grand.upgrades==n.state.upgrades)continue;
                    for(auto action:seeds(grand,o.max_actions)){
                        NativeState great;if(evaluate(grand,action.data.data(),action.size,great,target,o.horizon))joint=std::min(joint,age_score(a,great));
                    }
                }
            }
            n.score=std::isfinite(n.raw_score)?(1-o.two_step_weight)*n.raw_score+o.two_step_weight*joint:joint;
            if(n.state.upgrades!=a.upgrades)n.score*=1-o.upgrade_bonus;
        }
        std::sort(ids.begin(),ids.end(),order);
    }
    std::vector<int> chosen,left;group_counts.clear();
    for(int id:ids){auto group=evaluated[id].strategy;
        if(!o.result_diversity||group_counts[group]<o.result_diversity){chosen.push_back(id);++group_counts[group];}else left.push_back(id);
    }
    if(int(chosen.size())>o.width)chosen.resize(o.width);
    for(int id:left)if(int(chosen.size())<o.width)chosen.push_back(id);
    if(o.seed_reserve||o.anchor_all){
        std::sort(seed_ids.begin(),seed_ids.end(),order);std::vector<int> anchors;std::unordered_set<std::uint64_t> groups;
        for(int id:seed_ids){
            const auto&n=evaluated[id];
            if(o.anchor_all>1&&n.actions.size==1&&!upgrade_code(n.actions.data[0])){
                int b=item_index(n.actions.data[0]),q=quantity(n.actions.data[0]);
                bool keep=q==1||q==10;
                if(o.anchor_all==2)keep|=q==5;
                if(o.anchor_all==3)keep|=q==3||q==6;
                if(o.anchor_all==4){
                    for(int u=0;u<NU;++u)if(!(a.upgrades&(1u<<u)))keep|=a.buildings[b]+q==UPGRADES[u].req[b];
                }
                if(!keep)continue;
            }
            if(o.anchor_all||groups.insert(n.strategy).second)anchors.push_back(id);
        }
        int limit=o.anchor_all?o.width:std::min(o.width,o.seed_reserve);if(int(anchors.size())>limit)anchors.resize(limit);
        std::unordered_set<StateKey,StateHash> keys;for(int id:anchors)keys.insert(state_key(evaluated[id].state));
        for(int id:chosen)if(int(anchors.size())<o.width&&keys.insert(state_key(evaluated[id].state)).second)anchors.push_back(id);
        chosen=anchors;
    }
    std::sort(chosen.begin(),chosen.end(),order);std::vector<Neighbor> result;for(int id:chosen)result.push_back(evaluated[id]);return result;
}
