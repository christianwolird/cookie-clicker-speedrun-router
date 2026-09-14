// Dense +/-1 quantity neighborhood, changing at least K purchase positions.
#include "native_partition.hpp"
#include <chrono>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <string>

void print_route(const Route&r){
    std::cout<<'[';for(int i=0;i<int(r.size());++i){if(i)std::cout<<',';std::cout<<'[';
        for(int j=0;j<r[i].size;++j){if(j)std::cout<<',';std::cout<<r[i].data[j];}std::cout<<']';}
    std::cout<<']';
}
int main(int argc,char**argv){
    if(argc<7)return 2;
    std::ifstream input(argv[1]);int n;
    if(!(input>>n)||n<1||n>100)return 3;
    Route route;
    for(int i=0;i<n;++i){Actions a;int count;
        if(!(input>>count)||count<1||count>MAX_ACTIONS)return 3;a.size=count;
        for(int j=0;j<count;++j)if(!(input>>a.data[j]))return 3;
        route.push_back(a);
    }
    double seconds=std::stod(argv[2]);int minimum=std::stoi(argv[3]),width=std::stoi(argv[4]);
    std::uint64_t begin=std::stoull(argv[5]),end=std::stoull(argv[6]);
    std::string stop=argc>7?argv[7]:"";
    bool audit=argc>8&&std::stoi(argv[8]);
    if(seconds<=0||minimum<0||minimum>32||width<1||end<begin)return 3;
    auto start=std::chrono::steady_clock::now();
    auto elapsed=[&](){return std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();};
    auto best=partition(flatten(route),width);auto sequence=flatten(best.route),candidate=sequence;
    std::vector<int> positions;
    for(int i=0;i<int(sequence.size());++i)if(!upgrade_code(sequence[i]))positions.push_back(i);
    // At most 3^32 leaves, so all suffix counts fit in uint64_t.
    int size=positions.size();if(size>32)return 3;
    std::vector<std::vector<int>> choices(size);
    for(int i=0;i<size;++i){int q=quantity(sequence[positions[i]]);
        for(int next=std::max(0,q-1);next<=std::min(10,q+1);++next)choices[i].push_back(next);
    }
    std::vector<std::vector<std::uint64_t>> ways(size+1,std::vector<std::uint64_t>(minimum+1));
    ways[size][0]=1;
    for(int i=size-1;i>=0;--i)for(int needed=0;needed<=minimum;++needed)
        for(int q:choices[i])ways[i][needed]+=ways[i+1][std::max(0,needed-int(q!=quantity(sequence[positions[i]])))];
    auto total=ways[0][minimum];end=std::min(end,total);
    if(begin>end)return 3;
    std::uint64_t ordinal=0,tried=0,improvements=0,fingerprint=0;bool stopped=false;double next_progress=30;
    std::cout<<std::setprecision(15);
    std::cout<<"{\"event\":\"initial\",\"finish\":"<<best.score<<",\"range_start\":"<<begin<<",\"range_end\":"<<end<<",\"total_combinations\":"<<total<<",\"route\":";
    print_route(best.route);std::cout<<"}\n"<<std::flush;
    std::function<void(int,int)> scan=[&](int first,int needed){
        if(stopped||ordinal>=end)return;
        auto count=ways[first][needed];
        if(!count)return;
        if(ordinal+count<=begin){ordinal+=count;return;}
        if(first==size){
            if(tried%1000==0&&(elapsed()>=seconds||(!stop.empty()&&std::ifstream(stop).good()))){stopped=true;return;}
            if(audit){
                std::uint64_t hash=1469598103934665603ULL;
                for(auto code:candidate)hash=(hash^code)*1099511628211ULL;
                fingerprint^=hash^(ordinal*0x9e3779b97f4a7c15ULL);
            }
            auto evaluate_candidate=[&](){
                std::vector<std::uint16_t> retained;retained.reserve(candidate.size());
                for(auto code:candidate)if(upgrade_code(code)||quantity(code))retained.push_back(code);
                return partition(retained,width);
            };
            auto result=evaluate_candidate();++tried;++ordinal;
            if(result.score<best.score-1e-8){best=std::move(result);++improvements;
                std::cout<<"{\"event\":\"improvement\",\"finish\":"<<best.score<<",\"elapsed\":"<<elapsed()<<",\"tried\":"<<tried<<",\"next_index\":"<<ordinal<<",\"route\":";
                print_route(best.route);std::cout<<"}\n"<<std::flush;
            }
            if(elapsed()>=next_progress){
                std::cout<<"{\"event\":\"progress\",\"finish\":"<<best.score<<",\"elapsed\":"<<elapsed()<<",\"tried\":"<<tried<<",\"next_index\":"<<ordinal<<"}\n"<<std::flush;
                next_progress=elapsed()+30;
            }
            return;
        }
        int at=positions[first],b=item_index(sequence[at]);
        for(int q:choices[first]){
            if(stopped||ordinal>=end)break;
            candidate[at]=buy_code(b,q);
            scan(first+1,std::max(0,needed-int(q!=quantity(sequence[at]))));
        }
        candidate[at]=sequence[at];
    };
    scan(0,minimum);
    std::cout<<"{\"event\":\"complete\",\"finish\":"<<best.score<<",\"elapsed\":"<<elapsed()<<",\"tried\":"<<tried<<",\"improvements\":"<<improvements<<",\"range_start\":"<<begin<<",\"range_end\":"<<end<<",\"next_index\":"<<ordinal<<",\"total_combinations\":"<<total<<",\"range_finished\":"<<(!stopped&&ordinal==end)<<",\"fingerprint\":"<<fingerprint<<",\"route\":";
    print_route(best.route);std::cout<<"}\n"<<std::flush;
}
