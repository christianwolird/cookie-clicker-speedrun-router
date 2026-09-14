#pragma once
#include "native_model_data.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

struct NativeState {
    std::int32_t buildings[NB];std::uint32_t upgrades;
    double age,baked,handmade,bank;
};
struct Rates {double automatic,hand; double total() const{return automatic+hand;}};
inline Rates rates(const NativeState&s) {
    double cursor=1,finger=0,production=1,mouse=0;double mult[NB];std::fill(mult,mult+NB,1.0);
    for(int i=0;i<NU;++i) if(s.upgrades&(1u<<i)) {
        const auto &u=UPGRADES[i];cursor*=u.cursor;finger+=u.finger;production*=u.production;mouse+=u.mouse;
        if(u.building>=0)mult[u.building]*=2;
        if(u.synergy>=0){mult[1]*=2;mult[u.synergy]*=1+s.buildings[1]*.01/(u.synergy-1);}
    }
    int noncursor=0;for(int i=1;i<NB;++i)noncursor+=s.buildings[i];
    double automatic=s.buildings[0]*(BASE_CPS[0]*cursor+finger*noncursor)*mult[0];
    for(int i=1;i<NB;++i)automatic+=s.buildings[i]*BASE_CPS[i]*mult[i];
    automatic*=production;
    return {automatic,250*(cursor+finger*noncursor+mouse*automatic)};
}
inline double finish(const NativeState&s,double target=1e6){return s.age+std::max(0.0,target-s.baked)/rates(s).total();}
inline bool upgrade_code(std::uint16_t code){return code>=256;}
inline int item_index(std::uint16_t code){return code>=256?code-256:code/16;}
inline int quantity(std::uint16_t code){return code>=256?1:code%16;}
inline std::uint16_t buy_code(int i,int q){return static_cast<std::uint16_t>(i*16+q);}
inline std::uint16_t up_code(int i){return static_cast<std::uint16_t>(256+i);}
inline constexpr auto CUMULATIVE_PRICES=[](){
    std::array<std::array<std::uint64_t,NP+1>,NB> result{};
    for(int i=0;i<NB;++i)for(int j=0;j<NP;++j)result[i][j+1]=result[i][j]+PRICES[i][j];
    return result;
}();
inline std::uint64_t building_price(int i,int owned,int q){
    if(i<0||i>=NB||owned<0||q<1||owned+q>NP)return UINT64_MAX/2;
    return CUMULATIVE_PRICES[i][owned+q]-CUMULATIVE_PRICES[i][owned];
}
inline bool evaluate(const NativeState&a,const std::uint16_t *actions,int count,NativeState&child,double target=1e6,double horizon=16,const Rates*cached_rates=nullptr) {
    if(count<1||count>32)return false;
    int owned[NB];std::copy(a.buildings,a.buildings+NB,owned);std::uint64_t cost=0;
    std::uint32_t purchased=a.upgrades;
    for(int k=0;k<count;++k){
        auto code=actions[k];int i=item_index(code);
        if(upgrade_code(code)){
            if(i<0||i>=NU||(purchased&(1u<<i)))return false;
            purchased|=1u<<i;cost+=UPGRADES[i].price;
        }else{
            int q=quantity(code);if(i<0||i>=NB||q<1||q>10)return false;
            auto p=building_price(i,owned[i],q);if(p>=UINT64_MAX/4)return false;
            cost+=p;owned[i]+=q;
        }
        if((horizon>0&&cost>std::max(1000.0,a.baked*horizon))||a.baked+std::max(0.0,double(cost)-a.bank)>=target)return false;
    }
    auto r=cached_rates?*cached_rates:rates(a);double pause=.4+.1*count,needed=std::max(0.0,double(cost)-a.bank);
    double duration=std::max(pause,(needed+r.hand*pause)/r.total());
    double produced=std::max(needed,r.automatic*pause);
    child=a;child.age+=duration;child.baked+=produced;child.handmade+=r.hand*std::max(0.0,duration-pause);child.bank+=produced;
    if(child.baked>=target)return false;
    for(int k=0;k<count;++k){
        auto code=actions[k];int i=item_index(code);
        if(upgrade_code(code)){
            const auto&u=UPGRADES[i];
            if(u.price>child.bank||u.handmade>child.handmade||u.cookies>child.baked)return false;
            for(int j=0;j<NB;++j)if(child.buildings[j]<u.req[j])return false;
            child.bank-=u.price;child.upgrades|=1u<<i;
        }else{
            int q=quantity(code);auto price=building_price(i,child.buildings[i],q);
            if(price>child.bank)return false;
            if(q<10&&building_price(i,child.buildings[i],q+1)<=child.bank)return false;
            child.bank-=price;child.buildings[i]+=q;
        }
    }
    return true;
}
constexpr int MAX_ACTIONS=16;
struct Actions {
    std::array<std::uint16_t,MAX_ACTIONS> data{};std::uint8_t size=0;
    bool operator==(const Actions&o)const{return size==o.size&&data==o.data;}
};
struct ActionHash {std::size_t operator()(const Actions&a)const {std::size_t h=a.size;for(int i=0;i<a.size;++i)h=(h^a.data[i])*1099511628211ULL;return h;}};
inline Actions canonicalize(const NativeState&a,Actions actions,bool sort_partials=false){
    std::vector<std::uint16_t> full,upgrades,partial;int counts[NB];std::copy(a.buildings,a.buildings+NB,counts);
    for(int k=0;k<actions.size;++k){auto c=actions.data[k];if(upgrade_code(c))upgrades.push_back(c);else if(quantity(c)==10){full.push_back(c);counts[item_index(c)]+=10;}else partial.push_back(c);}
    for(auto c:upgrades)for(int j=0;j<NB;++j)if(counts[j]<UPGRADES[item_index(c)].req[j])return actions;
    std::sort(full.begin(),full.end());std::sort(upgrades.begin(),upgrades.end());
    if(sort_partials){
        unsigned used=0;bool distinct=true;
        for(auto c:partial){unsigned bit=1u<<item_index(c);if(used&bit)distinct=false;used|=bit;}
        // For a partial click, remaining bank must be below the next unit's
        // price. Descending price(q+1) is the reverse earliest-deadline order;
        // adjacent exchanges preserve feasibility. See the proof in docs/.
        if(distinct)std::sort(partial.begin(),partial.end(),[&](auto x,auto y){
            auto px=building_price(item_index(x),counts[item_index(x)],quantity(x)+1);
            auto py=building_price(item_index(y),counts[item_index(y)],quantity(y)+1);
            return px!=py?px>py:x<y;
        });
    }
    Actions out;for(auto c:full)out.data[out.size++]=c;for(auto c:upgrades)out.data[out.size++]=c;for(auto c:partial)out.data[out.size++]=c;return out;
}
extern "C" inline int native_model_version(){return 1;}
