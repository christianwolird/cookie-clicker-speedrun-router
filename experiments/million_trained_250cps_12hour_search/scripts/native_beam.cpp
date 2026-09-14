#include "native_generator.hpp"
#include "native_guided.hpp"
#include "native_hand_frontier.hpp"
#include <chrono>
#include <atomic>
#include <condition_variable>
#include <fstream>
#include <functional>
#include <future>
#include <iomanip>
#include <iostream>
#include <queue>
#include <string>
#include <thread>
#include <mutex>
using Route=std::vector<Actions>;
struct Node {NativeState state;std::uint32_t parent;Actions incoming;std::uint8_t depth=0,action_count=0;double completion;std::uint64_t upgrade_order=1469598103934665603ULL;};
struct Visit {double age;std::uint32_t id;bool expanded=false;};
std::uint64_t upgrade_hash(std::uint64_t hash,const Actions&a){for(int j=0;j<a.size;++j)if(upgrade_code(a.data[j]))hash=(hash^a.data[j])*1099511628211ULL;return hash;}
constexpr std::uint32_t NONE=UINT32_MAX;
struct Entry {double priority;std::uint32_t id;};
struct Later {bool operator()(const Entry&a,const Entry&b)const {return a.priority>b.priority||(a.priority==b.priority&&a.id>b.id);}};
class WorkerPool {
    std::vector<std::thread> threads;std::queue<std::function<void()>> tasks;
    std::mutex mutex;std::condition_variable ready;bool stopping=false;
public:
    explicit WorkerPool(int count){
        for(int i=0;i<count;++i)threads.emplace_back([this](){
            for(;;){std::function<void()> task;
                {std::unique_lock<std::mutex> lock(mutex);ready.wait(lock,[this](){return stopping||!tasks.empty();});
                    if(stopping&&tasks.empty())return;task=std::move(tasks.front());tasks.pop();}
                task();
            }
        });
    }
    template<class F>std::future<std::vector<Neighbor>> submit(F&&function){
        auto task=std::make_shared<std::packaged_task<std::vector<Neighbor>()>>(std::forward<F>(function));
        auto result=task->get_future();
        {std::lock_guard<std::mutex> lock(mutex);tasks.emplace([task](){(*task)();});}
        ready.notify_one();return result;
    }
    ~WorkerPool(){
        {std::lock_guard<std::mutex> lock(mutex);stopping=true;}ready.notify_all();
        for(auto&thread:threads)thread.join();
    }
};
// Optional fair scheduling across lifetime-cookie ranges. The same exact
// dominance table still governs states; buckets only decide which state runs.
class StageQueue {
    using Heap=std::priority_queue<Entry,std::vector<Entry>,Later>;
    std::array<Heap,10> heaps;std::size_t count=0;
    const std::vector<Node>*nodes;const std::array<std::uint64_t,10>*expanded;bool balanced;
    int selected()const {
        int best=-1;
        for(int i=0;i<10;++i)if(!heaps[i].empty()){
            if(best<0||(balanced&&(*expanded)[i]<(*expanded)[best])||
               ((!balanced||(*expanded)[i]==(*expanded)[best])&&Later{}(heaps[best].top(),heaps[i].top())))best=i;
        }
        return best;
    }
public:
    static int bucket(double baked){constexpr std::array<double,9> bounds{100,1000,10000,50000,100000,250000,500000,750000,900000};return std::upper_bound(bounds.begin(),bounds.end(),baked)-bounds.begin();}
    StageQueue(const std::vector<Node>&n,const std::array<std::uint64_t,10>&e,bool b):nodes(&n),expanded(&e),balanced(b){}
    bool empty()const{return !count;}std::size_t size()const{return count;}
    const Entry&top()const{return heaps[selected()].top();}
    void pop(){heaps[selected()].pop();--count;}
    void push(Entry e){heaps[bucket((*nodes)[e.id].state.baked)].push(e);++count;}
    void assign(std::vector<Entry> entries){
        std::array<std::vector<Entry>,10> groups;
        for(auto e:entries)groups[bucket((*nodes)[e.id].state.baked)].push_back(e);
        count=entries.size();for(int i=0;i<10;++i)heaps[i]=Heap(Later{},std::move(groups[i]));
    }
};
struct Ruler {
    Route route;std::vector<NativeState> states;double final_age;bool canonical_partial;int target_rollout;
    std::uint64_t revision;
    explicit Ruler(const Route&r,bool partial=false,int targets=0):route(r),canonical_partial(partial),target_rollout(targets){static std::atomic<std::uint64_t> next{0};revision=++next;NativeState state{};states.push_back(state);for(auto e:r){NativeState child;if(!evaluate(state,e.data.data(),e.size,child,1e6,-1))throw std::runtime_error("Invalid ruler");states.push_back(child);state=child;}final_age=finish(state);}
    double remaining(const NativeState&s)const {
        if(s.baked>=1e6)return 0;
        auto it=std::upper_bound(states.begin(),states.end(),s.baked,[](double baked,const NativeState&s){return baked<s.baked;});
        int right=it-states.begin(),left=std::max(0,right-1);
        double rb=right<int(states.size())?states[right].baked:1e6,ra=right<int(states.size())?states[right].age:final_age;
        double lb=states[left].baked,la=states[left].age;
        double age=rb==lb?la:la+(s.baked-lb)/(rb-lb)*(ra-la);return std::max(0.0,final_age-age);
    }
    int stage(const NativeState&s)const {
        auto it=std::upper_bound(states.begin(),states.end(),s.baked,[](double baked,const NativeState&s){return baked<s.baked;});
        return std::clamp(int(it-states.begin())-1,0,int(route.size()));
    }
    std::array<int,NB> future_counts(const NativeState&s,double fraction)const {
        double baked=s.baked+fraction*(1e6-s.baked);
        auto it=std::lower_bound(states.begin(),states.end(),baked,[](const NativeState&s,double b){return s.baked<b;});
        if(it==states.end())it=states.end()-1;
        std::array<int,NB> result;for(int j=0;j<NB;++j)result[j]=std::max(0,it->buildings[j]-s.buildings[j]);return result;
    }
    std::vector<Actions> templates(const NativeState&s,int radius,int span)const {
        std::vector<Actions> result;int center=stage(s);
        for(int first=std::max(0,center-radius);first<std::min(int(route.size()),center+radius+1);++first){
            Actions merged;
            for(int end=first;end<std::min(int(route.size()),first+span);++end){
                if(merged.size+route[end].size>MAX_ACTIONS)break;
                for(int j=0;j<route[end].size;++j)merged.data[merged.size++]=route[end].data[j];result.push_back(merged);
            }
        }
        return result;
    }
    Actions next_actions(const NativeState&s,int j,bool targets)const {
        Actions actions;
        if(!targets){
            for(int k=0;k<route[j].size;++k){auto c=route[j].data[k];
                if(upgrade_code(c)&&(s.upgrades&(1u<<item_index(c))))continue;actions.data[actions.size++]=c;
            }
        }else{
            // Aim for the next ruler inventory, retaining any extra buildings
            // already bought by this prefix. This remains a feasible rollout,
            // not a lower bound: every proposed errand is evaluated normally.
            const auto&target=states[j+1];
            for(int b=0;b<NB;++b)for(int q=target.buildings[b]-s.buildings[b];q>0;q-=10){
                if(actions.size==MAX_ACTIONS){actions.size=255;return actions;}
                actions.data[actions.size++]=buy_code(b,std::min(q,10));
            }
            for(int u=0;u<NU;++u)if((target.upgrades&(1u<<u))&&!(s.upgrades&(1u<<u))){
                if(actions.size==MAX_ACTIONS){actions.size=255;return actions;}
                actions.data[actions.size++]=up_code(u);
            }
        }
        return canonicalize(s,actions,canonical_partial);
    }
    double completion(const NativeState&s)const {
        double best=finish(s);int center=stage(s);
        for(int targets=target_rollout==2?1:0;targets<=(target_rollout?1:0);++targets)
        for(int first=std::max(0,center-2);first<=std::min(int(route.size()),center+2);++first){
            NativeState state=s;
            for(int j=first;j<int(route.size());++j){auto actions=next_actions(state,j,targets);
                if(actions.size>MAX_ACTIONS)break;if(!actions.size)continue;NativeState child;
                if(!evaluate(state,actions.data.data(),actions.size,child,1e6,-1))break;
                state=child;best=std::min(best,finish(state));
            }
        }
        return best;
    }
    double cached_suffix(const NativeState&s,int step,int targets,std::size_t limit)const {
        struct Key {StateKey state;int step,targets;bool operator==(const Key&o)const{return state==o.state&&step==o.step&&targets==o.targets;}};
        struct Hash {std::size_t operator()(const Key&k)const{return (StateHash{}(k.state)*1099511628211ULL+k.step)*3+k.targets;}};
        struct Cache {std::uint64_t revision=0;std::unordered_map<Key,double,Hash> values;};
        static thread_local Cache cache;
        if(cache.revision!=revision){cache.values.clear();cache.revision=revision;}
        Key key{state_key(s),step,targets};auto found=cache.values.find(key);
        if(found!=cache.values.end())return s.age+found->second;
        NativeState normalized=s;normalized.age=0;double remaining=finish(normalized);
        if(step<int(route.size())){
            auto actions=next_actions(normalized,step,targets);
            if(actions.size==0)remaining=std::min(remaining,cached_suffix(normalized,step+1,targets,limit));
            else if(actions.size<=MAX_ACTIONS){NativeState child;
                if(evaluate(normalized,actions.data.data(),actions.size,child,1e6,-1))remaining=std::min(remaining,cached_suffix(child,step+1,targets,limit));
            }
        }
        if(cache.values.size()>=limit)cache.values.clear();cache.values.emplace(key,remaining);
        return s.age+remaining;
    }
    double completion_with_suffix_cache(const NativeState&s,std::size_t limit)const {
        if(!limit)return completion(s);double best=finish(s);int center=stage(s);
        for(int targets=target_rollout==2?1:0;targets<=(target_rollout?1:0);++targets)
            for(int first=std::max(0,center-2);first<=std::min(int(route.size()),center+2);++first)
                best=std::min(best,cached_suffix(s,first,targets,limit));
        return best;
    }
    double cached_completion(const NativeState&s,std::size_t limit,std::size_t suffix_limit=0)const {
        if(!limit)return completion_with_suffix_cache(s,suffix_limit);
        // Remaining duration depends on inventory, bank, baked cookies and
        // unlock progress, but not on absolute age. Cache each worker's
        // ranking hints separately and invalidate them with every new ruler.
        struct Cache {std::uint64_t revision=0;std::unordered_map<StateKey,double,StateHash> values;};
        static thread_local Cache cache;
        if(cache.revision!=revision){cache.values.clear();cache.revision=revision;}
        auto key=state_key(s);auto found=cache.values.find(key);
        if(found!=cache.values.end())return s.age+found->second;
        NativeState normalized=s;normalized.age=0;double remaining=completion_with_suffix_cache(normalized,suffix_limit);
        if(cache.values.size()>=limit)cache.values.clear();cache.values.emplace(key,remaining);
        return s.age+remaining;
    }
};
Route read_route(const std::string&path){std::ifstream input(path);int n;if(!(input>>n)||n<0||n>100)throw std::runtime_error("Invalid seed file");Route result;for(int i=0;i<n;++i){int count;if(!(input>>count)||count<1||count>MAX_ACTIONS)throw std::runtime_error("Invalid errand size");Actions a;a.size=count;for(int j=0;j<count;++j)if(!(input>>a.data[j]))throw std::runtime_error("Truncated seed file");result.push_back(a);}return result;}
void print_route(const Route&r){std::cout<<'[';for(int i=0;i<int(r.size());++i){if(i)std::cout<<',';std::cout<<'[';for(int j=0;j<r[i].size;++j){if(j)std::cout<<',';std::cout<<r[i].data[j];}std::cout<<']';}std::cout<<']';}
#ifndef CCSR_NO_BEAM_MAIN
int main(int argc,char**argv){
    std::unordered_map<std::string,std::string> args;for(int i=1;i+1<argc;i+=2)args[argv[i]]=argv[i+1];
    auto number=[&](std::string key,double fallback){auto it=args.find("--"+key);return it==args.end()?fallback:std::stod(it->second);};
    if(!args.count("--seed")){std::cerr<<"--seed FILE required\n";return 2;}
    NativeOptions go;go.width=number("width",160);go.search_width=number("inner",400);go.pops=number("pops",1000);go.max_actions=number("max-actions",12);
    go.horizon=number("horizon",16);go.anchor_all=number("anchor",1);go.upgrade_macros=number("macro",1);
    go.expand_seeds=number("expand-seeds",0);
    go.future_upgrade_mask=number("future-mask",0);go.future_weight=number("future-weight",1);
    go.three_step=number("three-step",0);go.lookahead_branches=number("lookahead-branches",6);
    go.strategy_bins=number("strategy-bins",0);go.canonical_partial=number("canonical-partials",0);
    go.quantity_children=number("quantity-children",0);
    go.queue_diversity=number("queue-diversity",0);go.result_diversity=number("result-diversity",0);go.seed_reserve=number("reserve",0);
    go.upgrade_bonus=number("upgrade-bonus",0);go.expansion_balance=number("balance",0);go.two_step_pool=number("two-step-pool",0);go.two_step_weight=number("two-step-weight",0);
    int workers=number("workers",4);double seconds=number("seconds",600),order=number("order",1.01),prune=number("prune",.94),slack=number("slack",0);
    std::size_t heap_limit=number("heap",500000),node_limit=number("nodes",5000000);bool rollouts=number("rollout",1),dynamic=number("dynamic-ruler",1);
    double rollout_weight=number("rollout-weight",0),hint_slack=number("hint-slack",-1);
    int harvest_limit=number("harvest",0);double harvest_slack=number("harvest-slack",2);
    int harvest_strategy=number("harvest-strategy",0);
    int harvest_order_limit=number("harvest-order-limit",0);
    int guide_width=number("guide-width",0),guide_radius=number("guide-radius",3),guide_span=number("guide-span",2);
    bool stage_balance=number("stage-balance",0),seed_prefixes=number("seed-prefixes",1),compacting=number("compact",0);
    bool persistent_workers=number("persistent-workers",0);std::uint64_t expansion_limit=number("expansions",0);
    int batch_size=number("batch-size",workers);
    bool hand_dominance=number("hand-dominance",0);
    int target_rollout=number("target-rollout",0);
    double future_inventory=number("future-inventory",0);
    bool report_generated=number("report-generated",0);
    bool retain_closed=number("retain-closed",0);
    int start_prefix=number("start-prefix",0);
    bool age_bound=number("age-bound",0);
    int rollout_keep=number("rollout-keep",0),rollout_raw=number("rollout-raw",0);
    int rollout_diverse=number("rollout-diverse",0);
    std::size_t completion_cache=number("completion-cache",0);
    std::size_t suffix_cache=number("suffix-cache",0);
    bool refresh_hints=number("refresh-hints",0);
    bool audit_keys=number("audit-keys",0);
    int inventory_slack=number("inventory-cap",-1);
    bool upgrade_cap=number("upgrade-cap",0);
    std::string stop_path=args.count("--stop-file")?args["--stop-file"]:"";
    std::string shared_ruler=args.count("--shared-ruler")?args["--shared-ruler"]:"";
    if(workers<1||go.width<1||go.search_width<1||go.pops<1||go.max_actions<1||go.max_actions>MAX_ACTIONS)throw std::runtime_error("Invalid limits");
    if(batch_size<1||(!persistent_workers&&batch_size>workers)){
        std::cerr<<"Prefetching requires a positive batch size and the persistent worker pool\n";return 2;
    }
    Route initial_route=read_route(args["--seed"]);Ruler ruler(initial_route,go.canonical_partial,target_rollout);Route best_route=initial_route;double best=ruler.final_age;
    NativeState inventory_cap=ruler.states.back();
    for(int j=0;j<NB;++j)inventory_cap.buildings[j]=inventory_slack<0?NP:std::min(NP,inventory_cap.buildings[j]+inventory_slack);
    if(!upgrade_cap)inventory_cap.upgrades=(1u<<NU)-1;
    bool restricted_inventory=inventory_slack>=0||upgrade_cap;
    if(start_prefix<0||start_prefix>int(initial_route.size()))throw std::runtime_error("Invalid fixed prefix length");
    std::vector<Node> nodes;nodes.reserve(std::min<std::size_t>(node_limit,1000000));
    std::unordered_map<StateKey,Visit,StateHash> visited;visited.reserve(std::min<std::size_t>(node_limit,1000000));
    HandFrontier hand_frontier;std::uint64_t hand_rejected=0,hand_invalidated=0;
    auto invalidate_hand=[&](std::uint32_t id){auto it=visited.find(state_key(nodes[id].state));if(it!=visited.end()&&it->second.id==id){visited.erase(it);++hand_invalidated;}};
    auto priority=[&](const NativeState&s,double hint){double remaining=ruler.remaining(s);return (1-rollout_weight)*(s.age+order*remaining)+rollout_weight*(hint+(order-1)*remaining);};
    std::array<std::uint64_t,10> expanded_by_baked{};
    StageQueue queue(nodes,expanded_by_baked,stage_balance);NativeState initial{};nodes.push_back({initial,NONE,{},0,0,best});visited[state_key(initial)]={initial.age,0};if(!start_prefix)queue.push({priority(initial,best),0});
    std::uint32_t parent=0;
    for(int j=0;j<(seed_prefixes?int(initial_route.size()):start_prefix);++j){auto a=initial_route[j];
        NativeState child;evaluate(nodes[parent].state,a.data.data(),a.size,child,1e6,-1);std::uint32_t id=nodes.size();
        nodes.push_back({child,parent,a,std::uint8_t(std::min(255,nodes[parent].depth+1)),std::uint8_t(std::min(255,nodes[parent].action_count+a.size)),best,upgrade_hash(nodes[parent].upgrade_order,a)});visited[state_key(child)]={child.age,id};
        if(j+1>=start_prefix)queue.push({priority(child,best),id});parent=id;
    }
    if(hand_dominance)for(std::uint32_t id=0;id<nodes.size();++id)hand_frontier.insert(nodes[id].state,id,invalidate_hand);
    auto now=[](){return std::chrono::steady_clock::now();};auto start=now();auto elapsed=[&](){return std::chrono::duration<double>(now()-start).count();};
    std::uint64_t expanded=0,generated=0,stale=0,dropped=0,improvements=0,rollout_checks=0,compactions=0,external_adoptions=0;double next_progress=30,next_stop_check=0,next_shared_check=0;std::string termination="queue_exhausted";
    auto print_buckets=[&](){std::cout<<"[";for(int j=0;j<10;++j){if(j)std::cout<<",";std::cout<<expanded_by_baked[j];}std::cout<<"]";};
    auto reconstruct=[&](std::uint32_t id){Route route;while(nodes[id].parent!=NONE){route.push_back(nodes[id].incoming);id=nodes[id].parent;}std::reverse(route.begin(),route.end());return route;};
    double generated_best=finish(nodes[start_prefix].state);Route generated_route;if(report_generated)generated_route=reconstruct(start_prefix);
    // This archive is only a source of local-search seeds, never a dominance
    // rule: distinct action orders with the same final inventory can matter.
    struct Harvest {double score;std::uint32_t id;Route suffix;};
    using Inventory=std::array<std::uint32_t,NB+3>;
    std::map<Inventory,Harvest> harvested;
    auto harvest=[&](double score,std::uint32_t id,const Route&suffix,const NativeState&state){
        if(harvest_limit<=0||score>best+harvest_slack)return;
        Inventory key{};for(int j=0;j<NB;++j)key[j]=harvest_strategy==1?0:state.buildings[j]/(harvest_strategy>=2?5:1);key[NB]=state.upgrades;
        if(harvest_strategy>=3){
            unsigned actions=nodes[id].action_count;for(const auto&a:suffix)actions+=a.size;
            key[NB]|=std::min<std::size_t>(255,nodes[id].depth+suffix.size())<<16;
            key[NB]|=std::min(255u,actions)<<24;
        }
        if(harvest_strategy){auto hash=nodes[id].upgrade_order;for(const auto&a:suffix)hash=upgrade_hash(hash,a);key[NB+1]=hash;key[NB+2]=hash>>32;}
        auto previous=harvested.find(key);
        if(previous!=harvested.end()&&previous->second.score<=score)return;
        if(previous==harvested.end()&&harvest_strategy&&harvest_order_limit>0){
            int count=0;auto worst=harvested.end();
            for(auto it=harvested.begin();it!=harvested.end();++it)
                if(it->first[NB+1]==key[NB+1]&&it->first[NB+2]==key[NB+2]){
                    ++count;if(worst==harvested.end()||it->second.score>worst->second.score)worst=it;
                }
            if(count>=harvest_order_limit){if(worst->second.score<=score)return;harvested.erase(worst);}
        }
        if(previous==harvested.end()&&int(harvested.size())>=harvest_limit){
            auto worst=std::max_element(harvested.begin(),harvested.end(),[](const auto&a,const auto&b){return a.second.score<b.second.score;});
            if(worst->second.score<=score)return;harvested.erase(worst);
        }
        harvested[key]={score,id,suffix};
    };
    auto live=[&](std::uint32_t id){auto it=visited.find(state_key(nodes[id].state));return it!=visited.end()&&it->second.id==id;};
    auto improve=[&](double score,std::uint32_t id,const Route&suffix){
        if(score>=best-1e-8)return false;best=score;best_route=reconstruct(id);best_route.insert(best_route.end(),suffix.begin(),suffix.end());++improvements;
        std::cout<<"{\"event\":\"improvement\",\"finish\":"<<best<<",\"elapsed\":"<<elapsed()<<",\"expanded\":"<<expanded<<",\"route\":";print_route(best_route);std::cout<<"}\n"<<std::flush;return true;
    };
    auto take_queue=[&](bool reprice){
        std::vector<Entry> entries;entries.reserve(queue.size());
        while(!queue.empty()){auto e=queue.top();queue.pop();if(live(e.id)){
            if(reprice){
                if(refresh_hints)nodes[e.id].completion=std::min(nodes[e.id].completion,ruler.cached_completion(nodes[e.id].state,completion_cache?completion_cache:100000));
                e.priority=priority(nodes[e.id].state,nodes[e.id].completion);
            }
            entries.push_back(e);
        }else ++dropped;}
        auto earlier=[](const Entry&a,const Entry&b){return a.priority<b.priority||(a.priority==b.priority&&a.id<b.id);};
        if(heap_limit&&entries.size()>heap_limit){
            auto original_size=entries.size();
            if(!stage_balance){std::nth_element(entries.begin(),entries.begin()+heap_limit,entries.end(),earlier);entries.resize(heap_limit);}
            else{
                std::sort(entries.begin(),entries.end(),earlier);std::array<std::size_t,10> counts{};
                for(auto e:entries)++counts[StageQueue::bucket(nodes[e.id].state.baked)];
                int nonempty=std::count_if(counts.begin(),counts.end(),[](auto n){return n>0;});
                std::size_t quota=heap_limit/nonempty;counts.fill(0);std::vector<Entry> keep,left;
                for(auto e:entries){int b=StageQueue::bucket(nodes[e.id].state.baked);if(counts[b]<quota){keep.push_back(e);++counts[b];}else left.push_back(e);}
                for(auto e:left){if(keep.size()>=heap_limit)break;keep.push_back(e);}entries=std::move(keep);
            }
            dropped+=original_size-entries.size();
        }
        return entries;
    };
    auto compact_nodes=[&](){
        auto old_size=nodes.size();auto entries=take_queue(false);
        std::vector<unsigned char> retain(nodes.size());
        auto mark=[&](std::uint32_t id){while(id!=NONE&&!retain[id]){retain[id]=1;id=nodes[id].parent;}};
        for(auto e:entries)mark(e.id);for(const auto&kv:harvested)mark(kv.second.id);
        std::vector<std::uint32_t> remap(nodes.size(),NONE);std::vector<Node> survivors;
        survivors.reserve(std::count(retain.begin(),retain.end(),1));
        for(std::uint32_t id=0;id<nodes.size();++id)if(retain[id]){remap[id]=survivors.size();survivors.push_back(nodes[id]);}
        for(auto&n:survivors)if(n.parent!=NONE)n.parent=remap[n.parent];
        for(auto&e:entries)e.id=remap[e.id];for(auto&kv:harvested)kv.second.id=remap[kv.second.id];
        nodes.swap(survivors);
        if(retain_closed){
            // Closed states need only their best age. Their discarded route
            // histories are never dereferenced; a better arrival replaces them.
            for(auto it=visited.begin();it!=visited.end();){auto&visit=it->second;
                if(visit.id!=NONE){auto mapped=remap[visit.id];
                    // A state discarded by the bounded queue may never have
                    // been expanded. Let it be generated again in that case.
                    if(mapped==NONE&&!visit.expanded){it=visited.erase(it);continue;}
                    visit.id=mapped;
                }
                ++it;
            }
        }else{
            // Optional baseline: forget old expanded states and permit repeats.
            decltype(visited) memo;memo.reserve(nodes.size());
            for(std::uint32_t id=0;id<nodes.size();++id){auto key=state_key(nodes[id].state);auto old=memo.find(key);
                if(old==memo.end()||old->second.age>nodes[id].state.age)memo[key]={nodes[id].state.age,id};
            }
            visited.swap(memo);
        }
        if(hand_dominance){hand_frontier.clear();for(std::uint32_t id=0;id<nodes.size();++id)hand_frontier.insert(nodes[id].state,id,invalidate_hand);}
        queue.assign(std::move(entries));++compactions;
        std::cout<<"{\"event\":\"compaction\",\"elapsed\":"<<elapsed()<<",\"before\":"<<old_size<<",\"after\":"<<nodes.size()<<",\"queue\":"<<queue.size()<<"}\n"<<std::flush;
        return nodes.size()<old_size*.95;
    };
    // Declare after the ruler and node storage so workers join before those
    // captured objects are destroyed, including during exception unwinding.
    std::unique_ptr<WorkerPool> pool;if(persistent_workers)pool=std::make_unique<WorkerPool>(workers);
    std::cout<<std::setprecision(15)<<"{\"event\":\"start\",\"ruler\":"<<best<<",\"workers\":"<<workers<<"}\n"<<std::flush;
    while(!queue.empty()){
        if(!shared_ruler.empty()&&elapsed()>=next_shared_check){
            if(std::ifstream(shared_ruler).good())try{
                auto route=read_route(shared_ruler);Ruler external(route,go.canonical_partial,target_rollout);
                if(external.final_age<best-1e-8){
                    best=external.final_age;best_route=std::move(route);++external_adoptions;
                    if(dynamic)ruler=std::move(external);
                    queue.assign(take_queue(dynamic));
                    std::cout<<"{\"event\":\"external_incumbent\",\"finish\":"<<best<<",\"elapsed\":"<<elapsed()<<",\"external_adoptions\":"<<external_adoptions<<",\"route\":";print_route(best_route);std::cout<<"}\n"<<std::flush;
                }
            }catch(const std::runtime_error&error){std::cerr<<"Ignoring unreadable shared ruler: "<<error.what()<<'\n';}
            next_shared_check=elapsed()+5;
        }
        if(!stop_path.empty()&&elapsed()>=next_stop_check){
            if(std::ifstream(stop_path).good()){termination="stop_requested";break;}next_stop_check=elapsed()+1;
        }
        if(elapsed()>=seconds){termination="wall_time_limit";break;}
        if(expansion_limit&&expanded>=expansion_limit){termination="expansion_limit";break;}
        if(nodes.size()>=node_limit&&(!compacting||!compact_nodes())){termination="node_limit";break;}
        std::vector<std::uint32_t> batch;
        // Extra queued tasks keep workers busy when generation costs vary.
        // The ruler and node IDs remain fixed until this entire batch joins.
        std::size_t batch_limit=expansion_limit?std::min<std::uint64_t>(batch_size,expansion_limit-expanded):batch_size;
        while(!queue.empty()&&batch.size()<batch_limit){auto entry=queue.top();queue.pop();if(!live(entry.id)){++stale;continue;}
            const auto&s=nodes[entry.id].state;if(s.age+prune*ruler.remaining(s)>=best+slack&&!(hint_slack>=0&&nodes[entry.id].completion<=best+hint_slack))continue;batch.push_back(entry.id);}
        if(batch.empty())break;
        std::vector<std::future<std::vector<Neighbor>>> futures;
        for(auto id:batch){NativeState s=nodes[id].state;
            auto templates=guide_width?ruler.templates(s,guide_radius,guide_span):std::vector<Actions>{};
            auto options=go;if(future_inventory>0)options.future_counts=ruler.future_counts(s,future_inventory);
            double age_limit=age_bound?best:0;
            auto task=[s,options,guide_width,templates,age_limit,rollout_keep,rollout_raw,rollout_diverse,completion_cache,suffix_cache,restricted_inventory,inventory_cap,&ruler](){
                auto result=generate(s,options,1e6,age_limit,restricted_inventory?&inventory_cap:nullptr);
                if(rollout_keep>0&&int(result.size())>rollout_keep){
                    std::vector<std::pair<double,int>> ranked;ranked.reserve(result.size());
                    for(int j=0;j<int(result.size());++j)ranked.push_back({ruler.cached_completion(result[j].state,completion_cache,suffix_cache),j});
                    std::sort(ranked.begin(),ranked.end());std::vector<unsigned char> selected(result.size());
                    std::vector<Neighbor> keep;keep.reserve(rollout_keep);
                    // Reserve some raw-score choices to explore beyond the
                    // current ruler's continuation strategy.
                    for(int j=0;j<std::min(rollout_keep,rollout_raw);++j){selected[j]=1;keep.push_back(result[j]);}
                    if(rollout_diverse>0){
                        std::unordered_set<std::uint64_t> represented;for(const auto&n:keep)represented.insert(n.strategy);
                        int added=0;
                        for(auto ranked_item:ranked){
                            if(added==rollout_diverse||int(keep.size())==rollout_keep)break;
                            int j=ranked_item.second;
                            if(!selected[j]&&represented.insert(result[j].strategy).second){selected[j]=1;keep.push_back(result[j]);++added;}
                        }
                    }
                    for(auto ranked_item:ranked){if(int(keep.size())==rollout_keep)break;
                        int j=ranked_item.second;if(!selected[j]){selected[j]=1;keep.push_back(result[j]);}
                    }
                    result=std::move(keep);
                }
                if(guide_width){auto guided=guided_generate(s,templates,options,guide_width,[&ruler,completion_cache,suffix_cache](const NativeState&s){return ruler.cached_completion(s,completion_cache,suffix_cache);});
                    for(const auto&n:guided)if(!restricted_inventory||within_inventory(n.state,inventory_cap))result.push_back(n);
                }
                return result;
            };
            if(pool)futures.push_back(pool->submit(std::move(task)));
            else futures.push_back(std::async(std::launch::async,std::move(task)));
        }
        bool changed=false;
        for(int bi=0;bi<int(batch.size());++bi){auto neighbors=futures[bi].get();++expanded;generated+=neighbors.size();
            auto prior=visited.find(state_key(nodes[batch[bi]].state));if(prior!=visited.end()&&prior->second.id==batch[bi])prior->second.expanded=true;
            ++expanded_by_baked[StageQueue::bucket(nodes[batch[bi]].state.baked)];
            for(const auto&n:neighbors){auto key=state_key(n.state);auto previous=visited.find(key);
                if(n.state.age>=best)continue;
                if(previous!=visited.end()&&previous->second.age<=n.state.age)continue;
                if(hand_dominance&&n.state.handmade<1000){
                    auto capped=key;capped.hand=double_bits(1000.0);auto cap=visited.find(capped);
                    if((cap!=visited.end()&&cap->second.age<=n.state.age)||hand_frontier.dominated(n.state)){++hand_rejected;continue;}
                }
                double hint=finish(n.state);
                std::uint32_t id=nodes.size();nodes.push_back({n.state,batch[bi],n.actions,std::uint8_t(std::min(255,nodes[batch[bi]].depth+1)),std::uint8_t(std::min(255,nodes[batch[bi]].action_count+n.actions.size)),hint,upgrade_hash(nodes[batch[bi]].upgrade_order,n.actions)});visited[key]={n.state.age,id};
                if(hand_dominance)hand_frontier.insert(n.state,id,invalidate_hand);
                if(hint<generated_best){generated_best=hint;if(report_generated)generated_route=reconstruct(id);}
                changed|=improve(hint,id,{});
                harvest(hint,id,{},n.state);
                if(rollouts){int stage=ruler.stage(n.state);
                    for(int targets=target_rollout==2?1:0;targets<=(target_rollout?1:0);++targets)
                    for(int begin=std::max(0,stage-2);begin<=std::min(int(ruler.route.size()),stage+2);++begin){
                        NativeState state=n.state;Route suffix;
                        for(int j=begin;j<int(ruler.route.size());++j){auto actions=ruler.next_actions(state,j,targets);
                            if(actions.size>MAX_ACTIONS)break;if(!actions.size)continue;
                            NativeState child;++rollout_checks;
                            if(!evaluate(state,actions.data.data(),actions.size,child,1e6,-1))break;
                            state=child;suffix.push_back(actions);
                            hint=std::min(hint,finish(state));changed|=improve(finish(state),id,suffix);
                            harvest(finish(state),id,suffix,state);
                        }
                    }
                }
                nodes[id].completion=hint;queue.push({priority(n.state,hint),id});
            }
        }
        if(changed&&dynamic)ruler=Ruler(best_route,go.canonical_partial,target_rollout);
        if((changed&&dynamic)||(heap_limit&&queue.size()>heap_limit*1.2)){
            queue.assign(take_queue(changed&&dynamic));
        }
        if(elapsed()>=next_progress){
            std::cout<<"{\"event\":\"progress\",\"finish\":"<<best<<",\"elapsed\":"<<elapsed()<<",\"expanded\":"<<expanded<<",\"generated\":"<<generated<<",\"nodes\":"<<nodes.size()<<",\"queue\":"<<queue.size()<<",\"stale\":"<<stale<<",\"dropped\":"<<dropped<<",\"rollout_checks\":"<<rollout_checks<<",\"expanded_by_baked\":";print_buckets();std::cout<<"}\n"<<std::flush;next_progress=elapsed()+30;
        }
    }
    if(audit_keys){
        // Diagnostic only: the search above continues to use exact keys.
        // Measure whether numeric quantization would actually merge states
        // before deciding whether its loss of exactness is worth considering.
        auto rounded=[](std::uint64_t bits,double quantum){double value;std::memcpy(&value,&bits,8);return double_bits(std::round(value/quantum)*quantum);};
        for(double quantum:{1e-12,1e-9,1e-6}){
            std::unordered_set<StateKey,StateHash> keys;keys.reserve(visited.size());
            for(const auto&entry:visited){auto key=entry.first;key.bank=rounded(key.bank,quantum);key.baked=rounded(key.baked,quantum);key.hand=rounded(key.hand,quantum);keys.insert(key);}
            std::cout<<"{\"event\":\"key_audit\",\"quantum\":"<<quantum<<",\"exact\":"<<visited.size()<<",\"rounded\":"<<keys.size()<<"}\n"<<std::flush;
        }
    }
    for(const auto&item:harvested){const auto&h=item.second;auto route=reconstruct(h.id);route.insert(route.end(),h.suffix.begin(),h.suffix.end());
        std::cout<<"{\"event\":\"candidate\",\"finish\":"<<h.score<<",\"elapsed\":"<<elapsed()<<",\"route\":";print_route(route);std::cout<<"}\n";
    }
    if(report_generated){std::cout<<"{\"event\":\"generated_best\",\"finish\":"<<generated_best<<",\"elapsed\":"<<elapsed()<<",\"route\":";print_route(generated_route);std::cout<<"}\n";}
    std::cout<<"{\"event\":\"complete\",\"finish\":"<<best<<",\"elapsed\":"<<elapsed()<<",\"expanded\":"<<expanded<<",\"generated\":"<<generated<<",\"nodes\":"<<nodes.size()<<",\"improvements\":"<<improvements<<",\"external_adoptions\":"<<external_adoptions<<",\"compactions\":"<<compactions<<",\"hand_rejected\":"<<hand_rejected<<",\"hand_invalidated\":"<<hand_invalidated<<",\"termination\":\""<<termination<<"\",\"expanded_by_baked\":";print_buckets();std::cout<<",\"route\":";print_route(best_route);std::cout<<"}\n"<<std::flush;
}
#endif
