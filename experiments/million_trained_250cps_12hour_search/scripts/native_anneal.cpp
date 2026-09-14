#include "native_partition.hpp"
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>
#include <string>
struct FlatHash {std::size_t operator()(const std::vector<std::uint16_t>&a)const{std::size_t h=a.size();for(auto c:a)h=(h^c)*1099511628211ULL;return h;}};
void print_route(const Route&r){std::cout<<'[';for(int i=0;i<int(r.size());++i){if(i)std::cout<<',';std::cout<<'[';for(int j=0;j<r[i].size;++j){if(j)std::cout<<',';std::cout<<r[i].data[j];}std::cout<<']';}std::cout<<']';}
int main(int argc,char**argv){
    if(argc<4){std::cerr<<"seed-file seconds seed [width] [max-size]\n";return 2;}
    std::ifstream input(argv[1]);int n;if(!(input>>n)||n<1||n>100)return 3;Route seed_route;
    for(int i=0;i<n;++i){Actions g;int count;if(!(input>>count)||count<1||count>MAX_ACTIONS)return 3;g.size=count;for(int j=0;j<count;++j)if(!(input>>g.data[j]))return 3;seed_route.push_back(g);}
    std::vector<Route> seed_routes{seed_route};
    while(input>>n){if(n<1||n>100)return 3;Route extra;for(int i=0;i<n;++i){Actions g;int count;if(!(input>>count)||count<1||count>MAX_ACTIONS)return 3;g.size=count;for(int j=0;j<count;++j)if(!(input>>g.data[j]))return 3;extra.push_back(g);}seed_routes.push_back(extra);}
    double seconds=std::stod(argv[2]);std::mt19937_64 rng(std::stoull(argv[3]));int width=argc>4?std::stoi(argv[4]):2,max_size=argc>5?std::stoi(argv[5]):16;
    double tmax=argc>6?std::stod(argv[6]):3,tmin=argc>7?std::stod(argv[7]):.03;
    std::uint64_t cycle=argc>8?std::stoull(argv[8]):1500;
    double errand_bias=argc>9?std::stod(argv[9]):0,action_bias=argc>10?std::stod(argv[10]):0;
    bool expand=argc>11&&std::stoi(argv[11]);
    bool blocks=argc>12&&std::stoi(argv[12]),canonical=argc>13&&std::stoi(argv[13]);
    bool canonical_partial=argc>14&&std::stoi(argv[14]);
    bool lock_upgrades=argc>15&&std::stoi(argv[15]);double restart_best=argc>16?std::stod(argv[16]):.75;
    std::size_t cache_limit=argc>17?std::stoull(argv[17]):0;std::uint64_t trial_limit=argc>18?std::stoull(argv[18]):0;
    std::string stop_path=argc>19?argv[19]:"";
    bool aggregate=argc>20&&std::stoi(argv[20]);
    if(!cycle||width<1||max_size<1||max_size>((expand||aggregate)?256:MAX_ACTIONS)||tmin<=0||tmax<0||seconds<0||restart_best<0||restart_best>1)return 3;
    auto now=[](){return std::chrono::steady_clock::now();};auto start=now();auto elapsed=[&](){return std::chrono::duration<double>(now()-start).count();};
    auto uniform=[&](){return std::generate_canonical<double,53>(rng);};auto index=[&](int n){return int(rng()%n);};
    std::unordered_map<std::vector<std::uint16_t>,Solution,FlatHash> cache;std::uint64_t cache_hits=0,computed=0;
    auto solve=[&](const std::vector<std::uint16_t>&actions){
        if(cache_limit){auto found=cache.find(actions);if(found!=cache.end()){++cache_hits;return found->second;}}
        auto result=partition(actions,width,max_size,expand,canonical,canonical_partial,0,aggregate);++computed;
        if(cache_limit){if(cache.size()>=cache_limit)cache.clear();cache.emplace(actions,result);}return result;
    };
    auto best=solve(flatten(seed_route)),current=best;std::vector<Solution> pool{best};
    auto upgrade_order=[](const std::vector<std::uint16_t>&actions){std::vector<std::uint16_t> result;for(auto c:actions)if(upgrade_code(c))result.push_back(c);return result;};
    auto fixed_order=upgrade_order(flatten(best.route));
    for(const auto&r:seed_routes){auto candidate=solve(flatten(r));if(lock_upgrades&&upgrade_order(flatten(candidate.route))!=fixed_order)continue;pool.push_back(candidate);if(candidate.score<best.score)best=candidate;}
    const std::size_t pool_limit=std::max<std::size_t>(80,pool.size());
    current=best;
    auto energy=[&](const Solution&s){return s.score+errand_bias*s.route.size()+action_bias*flatten(s.route).size();};
    std::uint64_t tried=0,accepted=0,improvements=0;double next_progress=30,next_stop_check=0;
    std::cout<<std::setprecision(15)<<"{\"event\":\"initial\",\"finish\":"<<best.score<<",\"route\":";print_route(best.route);std::cout<<"}\n"<<std::flush;
    while(elapsed()<seconds&&(!trial_limit||tried<trial_limit)){
        if(!stop_path.empty()&&elapsed()>=next_stop_check){if(std::ifstream(stop_path).good())break;next_stop_check=elapsed()+1;}
        if(tried%cycle==0)current=uniform()<restart_best?best:pool[index(pool.size())];
        auto a=flatten(current.route);if(a.empty())a=flatten(best.route);
        int mode=index(blocks?18:12),i=index(a.size());
        if(mode<=2){if(upgrade_code(a[i]))continue;int q=quantity(a[i]);q=uniform()<.6?std::clamp(q+(uniform()<.5?-1:1),1,10):index(10)+1;a[i]=buy_code(item_index(a[i]),q);
            if(uniform()<.2){int j=index(a.size());if(!upgrade_code(a[j]))a[j]=buy_code(item_index(a[j]),index(10)+1);}}
        else if(mode==3){a.erase(a.begin()+i);}
        else if(mode==4||mode==5){auto v=a[i];a.erase(a.begin()+i);int j=uniform()<.75?std::clamp(i+index(7)-3,0,int(a.size())):index(a.size()+1);a.insert(a.begin()+j,v);}
        else if(mode==6){int j=uniform()<.75?std::clamp(i+index(7)-3,0,int(a.size())-1):index(a.size());std::swap(a[i],a[j]);}
        else if(mode<=8){if(a.size()>=60)continue;std::uint16_t v;
            if(uniform()<.8){int q=uniform()<.35?10:index(10)+1;v=buy_code(index(NB),q);}
            else{int u=index(NU);v=up_code(u);if(std::find(a.begin(),a.end(),v)!=a.end())continue;}
            a.insert(a.begin()+index(a.size()+1),v);}
        else if(mode==9){if(upgrade_code(a[i])||quantity(a[i])<=1)continue;
            int b=item_index(a[i]);std::vector<int> matches;for(int j=0;j<int(a.size());++j)if(j!=i&&!upgrade_code(a[j])&&item_index(a[j])==b&&quantity(a[j])<10)matches.push_back(j);
            if(matches.empty())continue;int j=matches[index(matches.size())];
            a[i]=buy_code(b,quantity(a[i])-1);a[j]=buy_code(b,quantity(a[j])+1);}
        else if(mode<=11){
            auto donor=flatten(pool[index(pool.size())].route);int j=std::clamp(int(double(i)/a.size()*donor.size())+index(5)-2,0,int(donor.size()));
            a.resize(i);for(;j<int(donor.size())&&a.size()<60;++j){auto c=donor[j];if(upgrade_code(c)&&std::find(a.begin(),a.end(),c)!=a.end())continue;a.push_back(c);}
        }
        else if(mode==12){
            int end=std::min(int(a.size()),i+2+index(4));std::vector<std::uint16_t> block(a.begin()+i,a.begin()+end);
            a.erase(a.begin()+i,a.begin()+end);int destination=index(a.size()+1);a.insert(a.begin()+destination,block.begin(),block.end());
        }
        else if(mode==13){
            int end=std::min(int(a.size()),i+1+index(4));if(end>=int(a.size()))continue;
            int j=end+index(a.size()-end),last=std::min(int(a.size()),j+1+index(4));std::vector<std::uint16_t> changed;
            changed.insert(changed.end(),a.begin(),a.begin()+i);changed.insert(changed.end(),a.begin()+j,a.begin()+last);
            changed.insert(changed.end(),a.begin()+end,a.begin()+j);changed.insert(changed.end(),a.begin()+i,a.begin()+end);
            changed.insert(changed.end(),a.begin()+last,a.end());a=std::move(changed);
        }
        else if(mode==14){
            if(upgrade_code(a[i]))continue;int b=item_index(a[i]);std::vector<int> matches;
            for(int j=0;j<int(a.size());++j)if(j!=i&&!upgrade_code(a[j])&&item_index(a[j])==b)matches.push_back(j);
            if(matches.empty())continue;int j=matches[index(matches.size())],moved=1+index(quantity(a[i]));std::vector<std::uint16_t> changed;
            for(int k=0;k<int(a.size());++k){
                if(k==i){if(quantity(a[k])>moved)changed.push_back(buy_code(b,quantity(a[k])-moved));}
                else if(k==j){for(int q=quantity(a[k])+moved;q>0;q-=10)changed.push_back(buy_code(b,std::min(q,10)));}
                else changed.push_back(a[k]);
            }
            a=std::move(changed);
        }
        else if(mode==15){int last=std::min(int(a.size()),i+2+index(3));std::reverse(a.begin()+i,a.begin()+last);}
        else if(mode==16){
            auto u=index(NU);if(std::find(a.begin(),a.end(),up_code(u))!=a.end())continue;
            int counts[NB]{};for(int j=0;j<i;++j)if(!upgrade_code(a[j]))counts[item_index(a[j])]+=quantity(a[j]);
            std::vector<std::uint16_t> macro;
            for(int b=0;b<NB;++b)while(counts[b]<UPGRADES[u].req[b]){macro.push_back(buy_code(b,10));counts[b]+=10;}
            macro.push_back(up_code(u));if(a.size()+macro.size()>60)continue;a.insert(a.begin()+i,macro.begin(),macro.end());
        }
        else{
            std::vector<int> upgrades;for(int j=0;j<int(a.size());++j)if(upgrade_code(a[j]))upgrades.push_back(j);
            if(upgrades.size()<2)continue;std::swap(a[upgrades[index(upgrades.size())]],a[upgrades[index(upgrades.size())]]);
        }
        if(a.empty())continue;
        if(lock_upgrades&&upgrade_order(a)!=fixed_order)continue;
        auto candidate=solve(a);++tried;
        if(lock_upgrades&&upgrade_order(flatten(candidate.route))!=fixed_order)continue;
        double phase=double(tried%cycle)/cycle;double temperature=tmin+tmax*std::pow(1-phase,3);
        if(energy(candidate)<energy(current)||uniform()<std::exp((energy(current)-energy(candidate))/temperature)){current=candidate;++accepted;}
        if(candidate.score<best.score-1e-8){
            best=candidate;++improvements;pool.push_back(best);if(pool.size()>pool_limit)pool.erase(pool.begin());
            std::cout<<"{\"event\":\"improvement\",\"finish\":"<<best.score<<",\"elapsed\":"<<elapsed()<<",\"tried\":"<<tried<<",\"route\":";print_route(best.route);std::cout<<"}\n"<<std::flush;
        }else if(candidate.score<best.score+4&&uniform()<.005){pool.push_back(candidate);if(pool.size()>pool_limit)pool.erase(pool.begin());}
        if(elapsed()>=next_progress){std::cout<<"{\"event\":\"progress\",\"finish\":"<<best.score<<",\"current\":"<<current.score<<",\"elapsed\":"<<elapsed()<<",\"tried\":"<<tried<<",\"accepted\":"<<accepted<<"}\n"<<std::flush;next_progress=elapsed()+30;}
    }
    std::cout<<"{\"event\":\"complete\",\"finish\":"<<best.score<<",\"elapsed\":"<<elapsed()<<",\"tried\":"<<tried<<",\"accepted\":"<<accepted<<",\"improvements\":"<<improvements<<",\"cache_hits\":"<<cache_hits<<",\"computed\":"<<computed<<",\"route\":";print_route(best.route);std::cout<<"}\n"<<std::flush;
}
