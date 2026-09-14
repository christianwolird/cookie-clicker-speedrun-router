#define CCSR_NO_BEAM_MAIN
#include "native_beam.cpp"
#include <ctime>
int main(int argc,char**argv){
    if(argc<3)return 2;Ruler ruler(read_route(argv[1]),true,1),witness(read_route(argv[2]),true,1);
    NativeOptions o;o.width=1200;o.search_width=1500;o.pops=5000;o.max_actions=12;
    o.anchor_all=4;o.upgrade_macros=1;o.future_upgrade_mask=32768;o.canonical_partial=1;o.quantity_children=4;o.horizon=0;
    std::vector<NativeState> samples;
    for(const auto&s:witness.states){auto neighbors=generate(s,o,1e6,ruler.final_age);for(auto&n:neighbors)samples.push_back(n.state);}
    double max_error=0;std::vector<double> uncached;
    auto start=std::clock();
    for(int pass=0;pass<3;++pass)for(auto state:samples){state.age+=pass*7.12345;uncached.push_back(ruler.completion(state));}
    double raw_cpu=double(std::clock()-start)/CLOCKS_PER_SEC;
    for(auto limits:std::vector<std::pair<int,int>>{{100000,0},{0,100000},{100000,100000},{100000,500000}}){
        ruler=Ruler(read_route(argv[1]),true,1);std::size_t query=0;start=std::clock();
        for(int pass=0;pass<3;++pass)for(auto state:samples){state.age+=pass*7.12345;double value=ruler.cached_completion(state,limits.first,limits.second);max_error=std::max(max_error,std::abs(value-uncached[query++]));}
        std::cout<<std::setprecision(15)<<"{\"samples\":"<<samples.size()<<",\"queries\":"<<query<<",\"completion_cache\":"<<limits.first<<",\"suffix_cache\":"<<limits.second<<",\"uncached_cpu\":"<<raw_cpu<<",\"cached_cpu\":"<<double(std::clock()-start)/CLOCKS_PER_SEC<<",\"max_error\":"<<max_error<<"}\n";
    }
    // A new ruler must discard the old completion hints, even at the same
    // object address after assignment.
    ruler=Ruler(witness.route,true,2);
    for(auto state:samples)max_error=std::max(max_error,std::abs(ruler.completion(state)-ruler.cached_completion(state,100000,100000)));
    std::cout<<std::setprecision(15)<<"{\"revision_check_max_error\":"<<max_error<<"}\n";
    return max_error>1e-9;
}
