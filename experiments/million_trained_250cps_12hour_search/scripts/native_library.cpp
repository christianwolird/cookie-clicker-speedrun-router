#include "native_partition.hpp"
struct NativeNeighbor {NativeState state;std::uint16_t actions[MAX_ACTIONS];std::int32_t action_count;double raw_score,score;};
struct NativeErrand {std::uint16_t actions[MAX_ACTIONS];std::int32_t action_count;};
extern "C" {
int native_evaluate(const NativeState*a,const std::uint16_t*actions,int count,NativeState*out,double target,double horizon){return evaluate(*a,actions,count,*out,target,horizon);}
void native_rates(const NativeState*a,double*out){auto r=rates(*a);out[0]=r.automatic;out[1]=r.hand;}
int native_generate(const NativeState*a,const NativeOptions*options,NativeNeighbor*out,int capacity){
    auto neighbors=generate(*a,*options);int size=std::min<int>(capacity,neighbors.size());
    for(int i=0;i<size;++i){const auto&n=neighbors[i];out[i].state=n.state;std::copy(n.actions.data.begin(),n.actions.data.end(),out[i].actions);out[i].action_count=n.actions.size;out[i].raw_score=n.raw_score;out[i].score=n.score;}return size;
}
int native_options_size(){return sizeof(NativeOptions);}
int native_neighbor_size(){return sizeof(NativeNeighbor);}
int native_canonicalize(const NativeState*a,const std::uint16_t*codes,int count,std::uint16_t*out,int partial){
    if(count<1||count>MAX_ACTIONS)return -1;Actions actions;
    for(int i=0;i<count;++i){auto c=codes[i];int item=item_index(c);
        if(upgrade_code(c)?item>=NU:item>=NB||quantity(c)<1||quantity(c)>10)return -1;
        actions.data[actions.size++]=c;
    }
    auto result=canonicalize(*a,actions,partial);std::copy(result.data.begin(),result.data.begin()+result.size,out);return result.size;
}
int native_partition(const std::uint16_t*actions,int count,int width,int max_size,int expand,NativeErrand*out,int capacity,double*score){
    if(count<1||count>512||width<1||width>32||max_size<1||max_size>256)return -1;
    std::vector<std::uint16_t> sequence(actions,actions+count);auto result=partition(sequence,width,max_size,expand);
    if(int(result.route.size())>capacity)return -2;
    *score=result.score;
    for(int i=0;i<int(result.route.size());++i){std::copy(result.route[i].data.begin(),result.route[i].data.end(),out[i].actions);out[i].action_count=result.route[i].size;}
    return result.route.size();
}
}
