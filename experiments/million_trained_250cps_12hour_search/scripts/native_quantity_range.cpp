// Disjoint, resumable ranges of the fixed-sequence quantity neighborhood.
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
std::uint64_t combinations(int n,int k,int radix=9){
    if(n<k)return 0;std::uint64_t result=1;
    for(int j=1;j<=k;++j)result=result*(n-j+1)/j;
    for(int j=0;j<k;++j)result*=radix;
    return result;
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
    double seconds=std::stod(argv[2]);int order=std::stoi(argv[3]),width=std::stoi(argv[4]);
    std::uint64_t begin=std::stoull(argv[5]),end=std::stoull(argv[6]);
    std::string stop=argc>7?argv[7]:"";
    bool audit=argc>8&&std::stoi(argv[8]);
    bool deletions=argc>9&&std::stoi(argv[9]);
    if(seconds<=0||order<1||order>6||width<1||end<begin)return 3;
    auto start=std::chrono::steady_clock::now();
    auto elapsed=[&](){return std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();};
    auto best=partition(flatten(route),width);auto sequence=flatten(best.route),candidate=sequence;
    std::vector<int> positions;
    for(int i=0;i<int(sequence.size());++i)if(!upgrade_code(sequence[i]))positions.push_back(i);
    // This bound also makes every binomial-count intermediate fit uint64_t.
    if(positions.size()>64)return 3;
    // In deletion mode, visit only combinations containing at least one zero
    // quantity. Positive-only combinations belong to the ordinary scan.
    auto subtree=[&](int available,int left,bool deleted){
        if(!deletions)return combinations(available,left);
        return combinations(available,left,10)-(deleted?0:combinations(available,left,9));
    };
    auto total=subtree(positions.size(),order,false);end=std::min(end,total);
    if(begin>end)return 3;
    std::uint64_t ordinal=0,tried=0,improvements=0,fingerprint=0;bool stopped=false;double next_progress=30;
    std::cout<<std::setprecision(15);
    std::cout<<"{\"event\":\"initial\",\"finish\":"<<best.score<<",\"range_start\":"<<begin<<",\"range_end\":"<<end<<",\"total_combinations\":"<<total<<",\"route\":";
    print_route(best.route);std::cout<<"}\n"<<std::flush;
    std::function<void(int,int,bool)> scan=[&](int first,int left,bool deleted){
        if(stopped||ordinal>=end)return;
        auto count=subtree(int(positions.size())-first,left,deleted);
        if(!count)return;
        if(ordinal+count<=begin){ordinal+=count;return;}
        if(!left){
            if(tried%1000==0&&(elapsed()>=seconds||(!stop.empty()&&std::ifstream(stop).good()))){stopped=true;return;}
            if(audit){
                std::uint64_t hash=1469598103934665603ULL;
                for(auto code:candidate)hash=(hash^code)*1099511628211ULL;
                fingerprint^=hash^(ordinal*0x9e3779b97f4a7c15ULL);
            }
            auto evaluate_candidate=[&](){
                if(!deletions)return partition(candidate,width);
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
        for(int j=first;j+left<=int(positions.size());++j){int at=positions[j],b=item_index(sequence[at]);
            for(int q=deletions?0:1;q<=10&&!stopped&&ordinal<end;++q)if(q!=quantity(sequence[at])){
                candidate[at]=buy_code(b,q);scan(j+1,left-1,deleted||q==0);
            }
            candidate[at]=sequence[at];if(stopped||ordinal>=end)return;
        }
    };
    scan(0,order,false);
    std::cout<<"{\"event\":\"complete\",\"finish\":"<<best.score<<",\"elapsed\":"<<elapsed()<<",\"tried\":"<<tried<<",\"improvements\":"<<improvements<<",\"range_start\":"<<begin<<",\"range_end\":"<<end<<",\"next_index\":"<<ordinal<<",\"total_combinations\":"<<total<<",\"range_finished\":"<<(!stopped&&ordinal==end)<<",\"fingerprint\":"<<fingerprint<<",\"route\":";
    print_route(best.route);std::cout<<"}\n"<<std::flush;
}
