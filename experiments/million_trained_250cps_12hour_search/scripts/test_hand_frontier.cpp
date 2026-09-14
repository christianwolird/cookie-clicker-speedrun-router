#include "native_hand_frontier.hpp"
#include <cassert>
#include <iostream>
#include <random>

int main(){
    std::mt19937 rng(903);std::uint64_t checks=0,continuations=0;
    for(int trial=0;trial<200;++trial){
        HandFrontier frontier;std::vector<NativeState> oracle;
        for(int j=0;j<200;++j){
            NativeState s{};s.buildings[0]=rng()%3;s.bank=rng()%3;s.baked=1000;
            s.age=(rng()%100)/10.;s.handmade=rng()%1000;
            bool expected=false;
            for(const auto&old:oracle)if(old.buildings[0]==s.buildings[0]&&old.bank==s.bank&&old.age<=s.age&&old.handmade>=s.handmade)expected=true;
            assert(frontier.dominated(s)==expected);++checks;
            if(!expected){frontier.insert(s,oracle.size(),[](auto){});oracle.push_back(s);}
        }
    }
    for(int trial=0;trial<10000;++trial){
        NativeState worse{};worse.buildings[0]=rng()%31;worse.buildings[1]=rng()%21;
        worse.buildings[2]=rng()%11;worse.baked=1000+rng()%30000;worse.bank=rng()%1000;
        worse.handmade=rng()%1000;worse.age=20;
        NativeState better=worse;better.handmade+=rng()%1000;better.age-=double(rng()%100)/10;
        for(auto a:seeds(worse,12)){
            NativeState wc,bc;if(!evaluate(worse,a.data.data(),a.size,wc,1e6,-1))continue;
            assert(evaluate(better,a.data.data(),a.size,bc,1e6,-1));
            assert(bc.age<=wc.age&&bc.handmade>=wc.handmade);
            assert(bc.bank==wc.bank&&bc.baked==wc.baked&&bc.upgrades==wc.upgrades);
            for(int k=0;k<NB;++k)assert(bc.buildings[k]==wc.buildings[k]);++continuations;
        }
    }
    std::cout<<"{\"frontier_checks\":"<<checks<<",\"continuation_checks\":"<<continuations<<"}\n";
}
