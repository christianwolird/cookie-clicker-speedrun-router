#pragma once
#include "native_generator.hpp"
#include <optional>
using Route=std::vector<Actions>;
struct Plan {NativeState state{};int parent_position=-1,parent_index=-1;Actions incoming;};
struct Solution {double score;Route route;};
inline Actions compress(const std::vector<std::uint16_t>&a,int begin,int end){
    Actions result;
    for(int i=begin;i<end;){auto code=a[i++];if(upgrade_code(code)){if(result.size==MAX_ACTIONS){result.size=255;return result;}result.data[result.size++]=code;continue;}
        int b=item_index(code),q=quantity(code);while(i<end&&!upgrade_code(a[i])&&item_index(a[i])==b){q+=quantity(a[i]);++i;}
        while(q){if(result.size==MAX_ACTIONS){result.size=255;return result;}int n=std::min(10,q);result.data[result.size++]=buy_code(b,n);q-=n;}
    }
    return result;
}
inline Actions aggregate_basket(const std::vector<std::uint16_t>&a,int begin,int end){
    std::array<int,NB> counts{};std::uint32_t upgrades=0;Actions result;
    for(int i=begin;i<end;++i){auto code=a[i];int item=item_index(code);
        if(upgrade_code(code)){
            if(item>=NU||(upgrades&(1u<<item))){result.size=255;return result;}
            upgrades|=1u<<item;
        }else{
            if(item>=NB||quantity(code)<1||quantity(code)>10){result.size=255;return result;}
            counts[item]+=quantity(code);
        }
    }
    for(int b=0;b<NB;++b)for(int q=counts[b];q>0;q-=10){
        if(result.size==MAX_ACTIONS){result.size=255;return result;}
        result.data[result.size++]=buy_code(b,std::min(q,10));
    }
    for(int i=begin;i<end;++i)if(upgrade_code(a[i])){
        if(result.size==MAX_ACTIONS){result.size=255;return result;}
        result.data[result.size++]=a[i];
    }
    return result;
}
struct BasketPrefixes {
    std::vector<std::array<int,NB>> counts;
    std::vector<int> upgrade_offsets,invalid;
    std::vector<std::uint16_t> upgrades;
    explicit BasketPrefixes(const std::vector<std::uint16_t>&actions){
        counts.reserve(actions.size()+1);upgrade_offsets.reserve(actions.size()+1);
        invalid.reserve(actions.size()+1);upgrades.reserve(actions.size());
        counts.push_back({});upgrade_offsets.push_back(0);invalid.push_back(0);
        for(auto code:actions){
            counts.push_back(counts.back());int bad=invalid.back(),item=item_index(code);
            if(upgrade_code(code)){if(item>=NU)++bad;else upgrades.push_back(code);}
            else if(item>=NB||quantity(code)<1||quantity(code)>10)++bad;
            else counts.back()[item]+=quantity(code);
            upgrade_offsets.push_back(upgrades.size());invalid.push_back(bad);
        }
    }
    Actions basket(int begin,int end)const {
        Actions result;if(invalid[end]!=invalid[begin]){result.size=255;return result;}
        for(int b=0;b<NB;++b)for(int q=counts[end][b]-counts[begin][b];q>0;q-=10){
            if(result.size==MAX_ACTIONS){result.size=255;return result;}
            result.data[result.size++]=buy_code(b,std::min(q,10));
        }
        std::uint32_t seen=0;
        for(int i=upgrade_offsets[begin];i<upgrade_offsets[end];++i){auto code=upgrades[i];auto bit=1u<<item_index(code);
            if(result.size==MAX_ACTIONS||(seen&bit)){result.size=255;return result;}
            seen|=bit;result.data[result.size++]=code;
        }
        return result;
    }
};
inline Solution partition(const std::vector<std::uint16_t>&input,int width=2,int max_size=16,bool expand=false,bool canonical=false,bool canonical_partial=false,double max_age=0,bool aggregate=false){
    std::vector<std::uint16_t> units;
    if(expand)for(auto c:input){if(upgrade_code(c))units.push_back(c);else for(int q=0;q<quantity(c);++q)units.push_back(buy_code(item_index(c),1));}
    const auto&actions=expand?units:input;
    std::optional<BasketPrefixes> prefixes;if(aggregate)prefixes.emplace(actions);
    NativeState initial{};std::vector<std::vector<Plan>> states(actions.size()+1);states[0].push_back({initial,-1,-1,{}});
    // Every label at a sequence position has the same inventory and upgrades.
    // Bank, age and unlock progress can differ, but they do not affect rates
    // in this fixed model without achievements or selling.
    std::vector<Rates> position_rates(actions.size()+1);position_rates[0]=rates(initial);
    double best_score=finish(initial);int best_position=0;
    for(int end=1;end<=int(actions.size());++end){
        std::vector<Plan> candidates;
        for(int count=1;count<=std::min(max_size,end);++count){
            int start=end-count;if(states[start].empty())continue;
            Actions group=aggregate?prefixes->basket(start,end):compress(actions,start,end);if(group.size>MAX_ACTIONS)continue;
            Actions executed=(canonical||aggregate)?canonicalize(states[start][0].state,group,canonical_partial||aggregate):group;
            for(const auto&ancestor:states[start]){
                NativeState child;if(!evaluate(ancestor.state,executed.data.data(),executed.size,child,1e6,-1,&position_rates[start]))continue;
                if(max_age>0&&child.age>=max_age)continue;
                auto key=state_key(child);auto same=std::find_if(candidates.begin(),candidates.end(),[&](const Plan&p){return state_key(p.state)==key;});
                if(same!=candidates.end()&&same->state.age<=child.age)continue;
                Plan plan{child,start,int(&ancestor-states[start].data()),executed};
                if(same==candidates.end())candidates.push_back(std::move(plan));else *same=std::move(plan);
            }
        }
        double total=1;
        if(!candidates.empty()){position_rates[end]=rates(candidates[0].state);total=position_rates[end].total();}
        auto finish_here=[total](const NativeState&s){return s.age+std::max(0.0,1e6-s.baked)/total;};
        std::sort(candidates.begin(),candidates.end(),[&](const Plan&a,const Plan&b){return finish_here(a.state)<finish_here(b.state);});
        if(int(candidates.size())>width)candidates.resize(width);
        if(!candidates.empty()&&finish_here(candidates[0].state)<best_score){best_score=finish_here(candidates[0].state);best_position=end;}
        states[end]=std::move(candidates);
    }
    Route route;int position=best_position,index=0;
    while(position){const auto&plan=states[position][index];route.push_back(plan.incoming);
        position=plan.parent_position;index=plan.parent_index;
    }
    std::reverse(route.begin(),route.end());return {best_score,std::move(route)};
}
inline std::vector<std::uint16_t> flatten(const Route&r){std::vector<std::uint16_t>a;for(const auto&g:r)for(int i=0;i<g.size;++i)a.push_back(g.data[i]);return a;}
