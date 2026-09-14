#include "native_partition.hpp"
#include <cassert>
#include <fstream>
#include <iomanip>
#include <iostream>

void print_route(const Route&r){
    std::cout<<'[';for(int i=0;i<int(r.size());++i){if(i)std::cout<<',';std::cout<<'[';
        for(int j=0;j<r[i].size;++j){if(j)std::cout<<',';std::cout<<r[i].data[j];}std::cout<<']';}
    std::cout<<']';
}
int main(int argc,char**argv){
    if(argc!=2)return 2;std::ifstream input(argv[1]);int n;input>>n;Route route;
    if(!input||n<1||n>100)return 3;
    for(int i=0;i<n;++i){Actions a;int count;input>>count;if(!input||count<1||count>MAX_ACTIONS)return 3;
        a.size=count;for(int j=0;j<count;++j)input>>a.data[j];route.push_back(a);}
    if(!input)return 3;
    NativeState initial{};std::vector<std::uint16_t> split{buy_code(0,1),up_code(0),buy_code(0,9)};
    auto combined=canonicalize(initial,aggregate_basket(split,0,split.size()),true);
    assert(combined.size==2);NativeState child;
    assert(evaluate(initial,combined.data.data(),combined.size,child,1e6,-1));
    assert(child.buildings[0]==10&&child.upgrades==1);
    std::vector<std::uint16_t> duplicate{up_code(0),up_code(0)};
    assert(aggregate_basket(duplicate,0,duplicate.size()).size==255);
    std::vector<std::uint16_t> too_many(17,buy_code(0,10));
    assert(aggregate_basket(too_many,0,too_many.size()).size==255);
    std::uint64_t checked=0;NativeState state{};
    for(auto errand:route){
        for(double bank:{0.,50.,1000.})for(int mode:{0,4}){
            auto source=state;auto production=rates(source);
            double waited=bank/production.total();source.age+=waited;source.bank+=bank;source.baked+=bank;source.handmade+=waited*production.hand;
            NativeOptions options;options.width=80;options.search_width=160;options.pops=300;
            options.horizon=0;options.anchor_all=4;options.upgrade_macros=1;
            options.canonical_partial=mode!=0;options.quantity_children=mode;
            for(const auto&neighbor:generate(source,options)){
                auto flat=flatten(Route{neighbor.actions});
                auto aggregated=canonicalize(source,aggregate_basket(flat,0,flat.size()),true);
                assert(aggregated.size==neighbor.actions.size);
                NativeState actual;assert(evaluate(source,aggregated.data.data(),aggregated.size,actual,1e6,-1));
                assert(state_key(actual)==state_key(neighbor.state));assert(actual.age==neighbor.state.age);
                assert(actual.handmade==neighbor.state.handmade);++checked;
            }
        }
        NativeState next;assert(evaluate(state,errand.data.data(),errand.size,next,1e6,-1));state=next;
    }
    std::cout<<std::setprecision(15)<<"{\"event\":\"equivalence\",\"checked\":"<<checked<<"}\n";
    auto flat=flatten(route);
    for(int width:{1,4,16})for(int mode:{0,1,2}){
        bool aggregate=mode!=0,expand=mode==2;int max_size=expand?128:aggregate?64:16;
        auto result=partition(flat,width,max_size,expand,false,false,0,aggregate);
        std::cout<<"{\"event\":\"partition\",\"width\":"<<width<<",\"aggregate\":"<<aggregate<<",\"expand\":"<<expand<<",\"finish\":"<<result.score<<",\"route\":";
        print_route(result.route);std::cout<<"}\n"<<std::flush;
    }
}
