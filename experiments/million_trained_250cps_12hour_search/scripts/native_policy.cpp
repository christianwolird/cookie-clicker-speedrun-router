// Repeated policy improvement using cheap greedy completions, without a ruler.
#include "native_partition.hpp"
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
void print_route(const Route&r){std::cout<<'[';for(int i=0;i<int(r.size());++i){if(i)std::cout<<',';std::cout<<'[';for(int j=0;j<r[i].size;++j){if(j)std::cout<<',';std::cout<<r[i].data[j];}std::cout<<']';}std::cout<<']';}
struct GreedyPolicy {
    NativeOptions options;std::size_t limit;
    std::unordered_map<StateKey,Solution,StateHash> cache;
    std::uint64_t hits=0,computed=0;
    Solution solve(const NativeState&s){
        auto key=state_key(s);auto found=cache.find(key);
        if(found!=cache.end()){++hits;auto result=found->second;result.score+=s.age;return result;}
        ++computed;NativeState normalized=s;normalized.age=0;Solution result{finish(normalized),{}};
        auto neighbors=generate(normalized,options);
        for(const auto&n:neighbors)if(finish(n.state)<result.score){
            result=solve(n.state);result.route.insert(result.route.begin(),n.actions);break;
        }
        if(limit){if(cache.size()>=limit)cache.clear();cache.emplace(key,result);}
        result.score+=s.age;return result;
    }
};
int main(int argc,char**argv){
    std::unordered_map<std::string,std::string> args;for(int i=1;i+1<argc;i+=2)args[argv[i]]=argv[i+1];
    auto number=[&](std::string key,double fallback){auto it=args.find("--"+key);return it==args.end()?fallback:std::stod(it->second);};
    double seconds=number("seconds",120);int mode=number("mode",2);std::size_t cache_limit=number("cache",100000);
    std::string stop=args.count("--stop-file")?args["--stop-file"]:"";
    NativeOptions options;options.width=number("pool",200);options.search_width=number("inner",800);options.pops=number("pops",2000);
    options.horizon=0;options.anchor_all=4;options.upgrade_macros=1;options.canonical_partial=1;options.quantity_children=4;options.future_upgrade_mask=number("future-mask",32768);
    options.upgrade_bonus=number("upgrade-bonus",0);
    NativeOptions cheap=options;cheap.width=number("rollout-width",16);cheap.search_width=number("rollout-inner",40);cheap.pops=number("rollout-pops",100);
    if(mode<0||mode>2||seconds<=0||options.width<1||options.search_width<1||options.pops<1||cheap.width<1||cheap.search_width<1||cheap.pops<1)return 2;
    // An ensemble supplies feasible complete continuations from several local
    // policies. Bonuses affect ranking only; final route times use the model.
    std::vector<double> bonuses{options.upgrade_bonus};
    if(args.count("--rollout-bonuses")){
        bonuses.clear();std::istringstream values(args["--rollout-bonuses"]);std::string value;
        while(std::getline(values,value,',')){
            std::size_t consumed=0;double bonus=std::stod(value,&consumed);
            if(consumed!=value.size()||!std::isfinite(bonus)||bonus<0)return 2;
            if(std::find(bonuses.begin(),bonuses.end(),bonus)==bonuses.end())bonuses.push_back(bonus);
        }
        if(bonuses.empty()||bonuses.size()>16)return 2;
    }
    std::vector<GreedyPolicy> policies;
    for(double bonus:bonuses)
    for(int variant=mode==1?1:0;variant<=(mode?1:0);++variant){auto policy_options=cheap;policy_options.future_upgrade_mask=variant?32768:0;policy_options.upgrade_bonus=bonus;policies.push_back({policy_options,cache_limit,{}});}
    auto start=std::chrono::steady_clock::now();auto elapsed=[&](){return std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();};
    NativeState state{};Route prefix;Solution best{finish(state),{}};
    for(auto&policy:policies){auto result=policy.solve(state);if(result.score<best.score)best=std::move(result);}
    Route suffix=best.route;std::uint64_t checked=0,improvements=0;double next_progress=30;bool stopped=false;
    auto emit=[&](const char*event){
        NativeState replay{};for(auto a:best.route){NativeState child;if(!evaluate(replay,a.data.data(),a.size,child,1e6,-1))throw std::runtime_error("Invalid policy route");replay=child;}
        double actual=finish(replay);if(std::abs(actual-best.score)>1e-7)throw std::runtime_error("Policy score mismatch");
        std::cout<<"{\"event\":\""<<event<<"\",\"finish\":"<<actual<<",\"elapsed\":"<<elapsed()<<",\"checked\":"<<checked<<",\"prefix\":"<<prefix.size()<<",\"route\":";print_route(best.route);std::cout<<"}\n"<<std::flush;
    };
    std::cout<<std::setprecision(15);emit("initial");
    while(!suffix.empty()&&!stopped){
        auto neighbors=generate(state,options);
        for(const auto&n:neighbors){
            if(elapsed()>=seconds||(!stop.empty()&&std::ifstream(stop).good())){stopped=true;break;}
            ++checked;
            for(auto&policy:policies){auto result=policy.solve(n.state);
                if(result.score<best.score-1e-8){
                    best.score=result.score;suffix=result.route;suffix.insert(suffix.begin(),n.actions);
                    best.route=prefix;best.route.insert(best.route.end(),suffix.begin(),suffix.end());++improvements;emit("improvement");
                }
            }
            if(elapsed()>=next_progress){std::cout<<"{\"event\":\"progress\",\"finish\":"<<best.score<<",\"elapsed\":"<<elapsed()<<",\"checked\":"<<checked<<",\"prefix\":"<<prefix.size()<<"}\n"<<std::flush;next_progress=elapsed()+30;}
        }
        if(suffix.empty()||stopped)break;
        NativeState child;auto next=suffix.front();if(!evaluate(state,next.data.data(),next.size,child,1e6,-1))throw std::runtime_error("Invalid retained continuation");
        prefix.push_back(next);suffix.erase(suffix.begin());state=child;
    }
    std::uint64_t hits=0,computed=0;for(const auto&p:policies){hits+=p.hits;computed+=p.computed;}
    std::cout<<"{\"event\":\"statistics\",\"cache_hits\":"<<hits<<",\"computed\":"<<computed<<",\"improvements\":"<<improvements<<",\"stopped\":"<<stopped<<"}\n";
    emit("complete");
}
