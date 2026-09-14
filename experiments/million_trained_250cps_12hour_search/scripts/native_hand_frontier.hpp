#pragma once
#include "native_generator.hpp"

// Exact dominance for the restricted trained-250 model: with identical bank,
// baked cookies, inventory and upgrades, an earlier state with at least as
// many handmade cookies can execute every continuation of the later state.
// Handmade cookies only unlock minimum-threshold upgrades in this model.
class HandFrontier {
    struct Point {double age,hand;std::uint32_t id;};
    std::unordered_map<StateKey,std::vector<Point>,StateHash> fronts;
    static StateKey key(const NativeState&s){auto k=state_key(s);k.hand=0;return k;}
public:
    bool dominated(const NativeState&s)const {
        auto it=fronts.find(key(s));if(it==fronts.end())return false;
        for(const auto&p:it->second)if(p.age<=s.age&&p.hand>=s.handmade)return true;
        return false;
    }
    template<class Invalidate>void insert(const NativeState&s,std::uint32_t id,Invalidate invalidate){
        auto k=key(s);auto it=fronts.find(k);
        if(it==fronts.end()){
            if(s.handmade<1000)fronts[k].push_back({s.age,s.handmade,id});
            return;
        }
        auto&points=it->second;
        points.erase(std::remove_if(points.begin(),points.end(),[&](const Point&p){
            if(s.age<=p.age&&s.handmade>=p.hand){invalidate(p.id);return true;}return false;
        }),points.end());
        if(s.handmade<1000)points.push_back({s.age,s.handmade,id});
        if(points.empty())fronts.erase(it);
    }
    void clear(){fronts.clear();}
};
