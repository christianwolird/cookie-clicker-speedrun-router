#include "native_generator.hpp"
#include <cassert>
#include <ctime>
#include <fstream>
#include <iostream>
int main(int argc,char**argv){
    if(argc<2)return 2;std::ifstream input(argv[1]);int n;input>>n;
    std::vector<NativeState> states(1);std::vector<Actions> errands;
    for(int j=0;j<n;++j){Actions a;int count;input>>count;a.size=count;for(int k=0;k<count;++k)input>>a.data[k];
        NativeState child;assert(evaluate(states.back(),a.data.data(),a.size,child,1e6,-1));states.push_back(child);errands.push_back(a);
    }
    double best=finish(states.back());NativeOptions o;o.width=1200;o.search_width=1500;o.pops=5000;
    o.max_actions=12;o.canonical_partial=1;o.quantity_children=4;o.anchor_all=4;o.upgrade_macros=1;
    o.future_upgrade_mask=32768;o.horizon=0;
    for(bool bounded:{false,true}){
        std::uint64_t returned=0,ineligible=0,hits=0;auto start=std::clock();
        for(int repeat=0;repeat<3;++repeat)for(int j=0;j<int(errands.size());++j){
            auto ns=generate(states[j],o,1e6,bounded?best:0);returned+=ns.size();
            bool found=false;for(const auto&neighbor:ns){
                ineligible+=neighbor.state.age>=best;if(bounded)assert(neighbor.state.age<best);
                found|=state_key(neighbor.state)==state_key(states[j+1]);
            }
            hits+=found;
        }
        std::cout<<"{\"bounded\":"<<bounded<<",\"cpu\":"<<double(std::clock()-start)/CLOCKS_PER_SEC
                 <<",\"returned\":"<<returned<<",\"ineligible\":"<<ineligible<<",\"witness_hits\":"<<hits<<"}\n"<<std::flush;
    }
}
