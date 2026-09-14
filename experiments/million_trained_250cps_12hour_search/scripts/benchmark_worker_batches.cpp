// Independent, identical generation tasks isolate worker batching overhead.
#define CCSR_NO_BEAM_MAIN
#include "native_beam.cpp"
#include <ctime>

int main(int argc,char**argv){
    if(argc<2)return 2;
    Ruler ruler(read_route(argv[1]),true,1);
    NativeOptions options;options.width=1200;options.search_width=1500;options.pops=5000;
    options.horizon=0;options.anchor_all=4;options.upgrade_macros=1;
    options.canonical_partial=1;options.quantity_children=4;options.future_upgrade_mask=32768;
    std::vector<NativeState> tasks;
    for(int repeat=0;repeat<3;++repeat)
        for(int i=0;i<int(ruler.states.size())-1;++i)tasks.push_back(ruler.states[(i*7+repeat)% (ruler.states.size()-1)]);
    std::uint64_t expected=0;bool first=true;
    for(int batch_size:{3,6,12,24,1000,3}){
        WorkerPool pool(3);std::atomic<std::uint64_t> working_ns{0};
        auto start=std::chrono::steady_clock::now();auto cpu_start=std::clock();
        std::uint64_t checksum=0,neighbors=0;
        for(int begin=0;begin<int(tasks.size());begin+=batch_size){
            std::vector<std::future<std::vector<Neighbor>>> futures;
            for(int i=begin;i<std::min<int>(tasks.size(),begin+batch_size);++i){auto state=tasks[i];
                futures.push_back(pool.submit([state,options,&working_ns](){
                    auto before=std::chrono::steady_clock::now();auto result=generate(state,options);
                    working_ns+=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-before).count();
                    return result;
                }));
            }
            for(int i=0;i<int(futures.size());++i){auto result=futures[i].get();neighbors+=result.size();
                std::uint64_t hash=begin+i;for(const auto&n:result)hash=(hash^StateHash{}(state_key(n.state)))*1099511628211ULL;
                checksum^=hash;
            }
        }
        double elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        if(!first&&checksum!=expected)return 3;expected=checksum;first=false;
        std::cout<<std::setprecision(15)<<"{\"batch\":"<<batch_size<<",\"workers\":3,\"tasks\":"<<tasks.size()
                 <<",\"neighbors\":"<<neighbors<<",\"checksum\":"<<checksum<<",\"elapsed\":"<<elapsed
                 <<",\"cpu_seconds\":"<<double(std::clock()-cpu_start)/CLOCKS_PER_SEC
                 <<",\"worker_occupancy\":"<<double(working_ns)/1e9/elapsed/3<<"}\n"<<std::flush;
    }
}
