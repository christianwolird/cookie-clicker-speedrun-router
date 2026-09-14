// Coverage and constraint checks for an optional, explicitly restricted search.
#define CCSR_NO_BEAM_MAIN
#include "native_beam.cpp"
#include <cassert>
#include <ctime>

int main(int argc,char**argv){
    if(argc!=2)return 2;
    Ruler ruler(read_route(argv[1]),true,1);
    NativeOptions options;options.width=1200;options.search_width=1500;
    options.pops=5000;options.horizon=0;options.anchor_all=4;
    options.upgrade_macros=1;options.canonical_partial=1;
    options.quantity_children=4;options.future_upgrade_mask=32768;
    std::cout<<std::setprecision(12);
    for(double forecast:{0.0,.03,.1})for(int slack:{-1,0,3,8})for(int mask:{0,1}){
        if(slack<0&&mask)continue;
        NativeState cap=ruler.states.back();
        for(int j=0;j<NB;++j)cap.buildings[j]=slack<0?NP:std::min(NP,cap.buildings[j]+slack);
        if(!mask)cap.upgrades=(1u<<NU)-1;
        int matched=0,returned=0;std::vector<int> missing;
        auto started=std::clock();std::clock_t generator_ticks=0;
        for(int i=0;i<int(ruler.route.size());++i){
            auto current=options;
            if(forecast)current.future_counts=ruler.future_counts(ruler.states[i],forecast);
            auto generation_start=std::clock();
            auto neighbors=generate(ruler.states[i],current,1e6,ruler.final_age,&cap);
            generator_ticks+=std::clock()-generation_start;
            if(slack<0){
                auto baseline=generate(ruler.states[i],current,1e6,ruler.final_age);
                assert(baseline.size()==neighbors.size());
                for(int j=0;j<int(neighbors.size());++j){
                    assert(baseline[j].actions==neighbors[j].actions);
                    assert(state_key(baseline[j].state)==state_key(neighbors[j].state));
                    assert(baseline[j].state.age==neighbors[j].state.age);
                    assert(baseline[j].score==neighbors[j].score);
                }
            }
            bool found=false;
            for(const auto&n:neighbors){
                assert(within_inventory(n.state,cap));
                NativeState replay;assert(evaluate(ruler.states[i],n.actions.data.data(),n.actions.size,replay,1e6,-1));
                assert(state_key(replay)==state_key(n.state));assert(replay.age==n.state.age);
                found|=state_key(n.state)==state_key(ruler.states[i+1])&&std::abs(n.state.age-ruler.states[i+1].age)<1e-8;
            }
            matched+=found;returned+=neighbors.size();if(!found)missing.push_back(i+1);
        }
        std::cout<<"{\"forecast\":"<<forecast<<",\"slack\":"<<slack<<",\"upgrade_cap\":"<<mask<<",\"matched\":"<<matched<<",\"total\":"<<ruler.route.size()<<",\"returned\":"<<returned<<",\"generator_cpu_seconds\":"<<double(generator_ticks)/CLOCKS_PER_SEC<<",\"audit_cpu_seconds\":"<<double(std::clock()-started)/CLOCKS_PER_SEC<<",\"missing\":[";
        for(int i=0;i<int(missing.size());++i){if(i)std::cout<<',';std::cout<<missing[i];}
        std::cout<<"]}\n"<<std::flush;
    }
}
