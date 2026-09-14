#include "native_partition.hpp"
#include <chrono>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <string>
void print_route(const Route&r){std::cout<<'[';for(int i=0;i<int(r.size());++i){if(i)std::cout<<',';std::cout<<'[';for(int j=0;j<r[i].size;++j){if(j)std::cout<<',';std::cout<<r[i].data[j];}std::cout<<']';}std::cout<<']';}
int main(int argc,char**argv){
    if(argc<5)return 2;std::ifstream input(argv[1]);int n;input>>n;if(!input||n<1||n>100)return 3;
    Route route;for(int i=0;i<n;++i){Actions a;int count;input>>count;if(count<1||count>MAX_ACTIONS)return 3;a.size=count;for(int j=0;j<count;++j)input>>a.data[j];route.push_back(a);}if(!input)return 3;
    double seconds=std::stod(argv[2]);int order=std::stoi(argv[3]),width=std::stoi(argv[4]);std::string stop=argc>5?argv[5]:"";
    bool age_bound=argc>6&&std::stoi(argv[6]);
    if(seconds<=0||order<1||order>6||width<1)return 3;
    auto start=std::chrono::steady_clock::now();auto elapsed=[&](){return std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();};
    auto best=partition(flatten(route),width);std::uint64_t tried=0,improvements=0;int passes=0;bool stopped=false;double next_progress=30;
    std::cout<<std::setprecision(15)<<"{\"event\":\"initial\",\"finish\":"<<best.score<<",\"route\":";print_route(best.route);std::cout<<"}\n"<<std::flush;
    do{
        ++passes;double previous=best.score;auto sequence=flatten(best.route),candidate=sequence;std::vector<int> positions;
        for(int i=0;i<int(sequence.size());++i)if(!upgrade_code(sequence[i]))positions.push_back(i);
        std::function<void(int,int)> scan=[&](int first,int left){
            if(stopped)return;
            if(!left){
                if(tried%1000==0&&(elapsed()>=seconds||(!stop.empty()&&std::ifstream(stop).good()))){stopped=true;return;}
                auto result=partition(candidate,width,16,false,false,false,age_bound?best.score:0);++tried;
                if(result.score<best.score-1e-8){best=std::move(result);++improvements;
                    std::cout<<"{\"event\":\"improvement\",\"finish\":"<<best.score<<",\"elapsed\":"<<elapsed()<<",\"tried\":"<<tried<<",\"route\":";print_route(best.route);std::cout<<"}\n"<<std::flush;
                }
                if(elapsed()>=next_progress){std::cout<<"{\"event\":\"progress\",\"finish\":"<<best.score<<",\"elapsed\":"<<elapsed()<<",\"tried\":"<<tried<<",\"passes\":"<<passes<<"}\n"<<std::flush;next_progress=elapsed()+30;}
                return;
            }
            for(int j=first;j+left<=int(positions.size());++j){int at=positions[j],b=item_index(sequence[at]);
                for(int q=1;q<=10&&!stopped;++q)if(q!=quantity(sequence[at])){candidate[at]=buy_code(b,q);scan(j+1,left-1);}
                candidate[at]=sequence[at];if(stopped)return;
            }
        };
        scan(0,order);
        std::cout<<"{\"event\":\"pass\",\"finish\":"<<best.score<<",\"elapsed\":"<<elapsed()<<",\"tried\":"<<tried<<",\"passes\":"<<passes<<",\"finished\":"<<(!stopped)<<"}\n"<<std::flush;
        if(best.score>=previous-1e-8)break;
    }while(!stopped);
    std::cout<<"{\"event\":\"complete\",\"finish\":"<<best.score<<",\"elapsed\":"<<elapsed()<<",\"tried\":"<<tried<<",\"improvements\":"<<improvements<<",\"passes\":"<<passes<<",\"exhausted\":"<<(!stopped)<<",\"route\":";print_route(best.route);std::cout<<"}\n"<<std::flush;
}
