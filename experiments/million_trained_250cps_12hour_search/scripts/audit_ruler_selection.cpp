#define CCSR_NO_BEAM_MAIN
#include "native_beam.cpp"
int main(int argc,char**argv){
    if(argc<3)return 2;Ruler ruler(read_route(argv[1]),true,1),witness(read_route(argv[2]),true,1);
    NativeOptions o;o.width=1200;o.search_width=1500;o.pops=5000;o.max_actions=12;
    o.anchor_all=4;o.upgrade_macros=1;o.future_upgrade_mask=32768;o.canonical_partial=1;o.quantity_children=4;o.horizon=0;
    int hits[3]{};int limits[3]{80,160,400};
    std::cout<<std::setprecision(15);
    for(int j=0;j<int(witness.route.size());++j){
        auto ns=generate(witness.states[j],o,1e6,ruler.final_age);int wanted=-1;
        std::vector<std::pair<double,int>> ranked;
        for(int k=0;k<int(ns.size());++k){ranked.push_back({ruler.completion(ns[k].state),k});if(state_key(ns[k].state)==state_key(witness.states[j+1]))wanted=k;}
        std::sort(ranked.begin(),ranked.end());int rank=-1;
        for(int k=0;k<int(ranked.size());++k)if(ranked[k].second==wanted)rank=k+1;
        std::cout<<"{\"step\":"<<j+1<<",\"raw_rank\":"<<wanted+1<<",\"completion_rank\":"<<rank<<",\"wanted_hint\":"<<ruler.completion(witness.states[j+1])<<",\"kept\":[";
        for(int mode=0;mode<3;++mode){std::set<int> keep;
            for(int k=0;k<std::min(int(ns.size()),limits[mode]/4);++k)keep.insert(k);
            for(auto item:ranked){if(int(keep.size())>=limits[mode])break;keep.insert(item.second);}
            bool found=keep.count(wanted);hits[mode]+=found;if(mode)std::cout<<",";std::cout<<found;
        }
        std::cout<<"]}\n";
    }
    std::cout<<"{\"hits80\":"<<hits[0]<<",\"hits160\":"<<hits[1]<<",\"hits400\":"<<hits[2]<<"}\n";
}
