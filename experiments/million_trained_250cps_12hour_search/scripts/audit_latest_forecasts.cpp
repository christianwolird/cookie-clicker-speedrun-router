#define CCSR_NO_BEAM_MAIN
#include "native_beam.cpp"
#include <ctime>
int main(int argc,char**argv){
    if(argc<2)return 2;Ruler witness(read_route(argv[1]),true,1);
    NativeOptions base;base.search_width=1500;base.pops=5000;base.max_actions=12;
    base.anchor_all=4;base.upgrade_macros=1;base.future_upgrade_mask=32768;
    base.canonical_partial=1;base.quantity_children=4;base.horizon=0;
    for(auto forecast:std::vector<std::pair<double,double>>{{0,0},{.03,0},{.1,0},{.2,0},{.4,0},{0,.1},{.1,.1}})
        for(int width:{160,400,1200}){
            int hits=0;std::vector<int> missing;double cpu=std::clock();
            for(int step=0;step<int(witness.route.size());++step){auto options=base;options.width=width;options.upgrade_bonus=forecast.second;
                if(forecast.first)options.future_counts=witness.future_counts(witness.states[step],forecast.first);
                auto neighbors=generate(witness.states[step],options,1e6,witness.final_age);
                bool found=std::any_of(neighbors.begin(),neighbors.end(),[&](const Neighbor&n){return state_key(n.state)==state_key(witness.states[step+1]);});
                hits+=found;if(!found)missing.push_back(step+1);
            }
            std::cout<<"{\"forecast\":"<<forecast.first<<",\"bonus\":"<<forecast.second<<",\"width\":"<<width<<",\"hits\":"<<hits<<",\"total\":"<<witness.route.size()<<",\"cpu\":"<<(std::clock()-cpu)/CLOCKS_PER_SEC<<",\"missing\":[";
            for(int j=0;j<int(missing.size());++j){if(j)std::cout<<',';std::cout<<missing[j];}std::cout<<"]}\n"<<std::flush;
        }
}
