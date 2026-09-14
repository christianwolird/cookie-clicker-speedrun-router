#define CCSR_NO_BEAM_MAIN
#include "native_beam.cpp"
int main(int argc,char**argv){
    if(argc<2)return 2;Ruler ruler(read_route(argv[1]),true,1);
    NativeOptions options;options.width=5000;options.search_width=3000;options.pops=10000;
    options.horizon=0;options.anchor_all=4;options.upgrade_macros=1;options.future_upgrade_mask=32768;
    options.canonical_partial=1;options.quantity_children=4;options.strategy_bins=2;
    int hits[3]{},group_totals[3]{};int diverse_limits[3]{0,20,40};
    for(int step=0;step<int(ruler.route.size());++step){options.future_counts=ruler.future_counts(ruler.states[step],.1);
        auto ns=generate(ruler.states[step],options,1e6,ruler.final_age);int wanted=-1;
        std::vector<std::pair<double,int>> ranked;
        for(int j=0;j<int(ns.size());++j){ranked.push_back({ruler.cached_completion(ns[j].state,100000),j});if(state_key(ns[j].state)==state_key(ruler.states[step+1]))wanted=j;}
        std::sort(ranked.begin(),ranked.end());std::cout<<"{\"step\":"<<step+1<<",\"pool\":"<<ns.size()<<",\"variants\":[";
        for(int mode=0;mode<3;++mode){std::set<int> chosen;std::set<std::uint64_t> groups;
            for(int j=0;j<std::min(40,int(ns.size()));++j){chosen.insert(j);groups.insert(ns[j].strategy);}
            int added=0;
            for(auto item:ranked){if(added==diverse_limits[mode]||chosen.size()==160)break;
                int j=item.second;if(!chosen.count(j)&&groups.insert(ns[j].strategy).second){chosen.insert(j);++added;}}
            for(auto item:ranked){if(chosen.size()==160)break;chosen.insert(item.second);}
            groups.clear();for(int j:chosen)groups.insert(ns[j].strategy);
            bool found=chosen.count(wanted);hits[mode]+=found;group_totals[mode]+=groups.size();if(mode)std::cout<<',';
            std::cout<<"{\"diverse\":"<<diverse_limits[mode]<<",\"hit\":"<<found<<",\"groups\":"<<groups.size()<<"}";
        }
        std::cout<<"]}\n"<<std::flush;
    }
    std::cout<<"{\"hits\":["<<hits[0]<<','<<hits[1]<<','<<hits[2]<<"],\"group_totals\":["<<group_totals[0]<<','<<group_totals[1]<<','<<group_totals[2]<<"]}\n";
}
