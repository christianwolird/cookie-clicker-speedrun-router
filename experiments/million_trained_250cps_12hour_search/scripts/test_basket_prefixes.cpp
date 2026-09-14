#include "native_partition.hpp"
#include <cassert>
#include <iostream>
#include <random>
int main(){
    std::mt19937 random(8532026);std::uint64_t checked=0;
    for(int trial=0;trial<200;++trial){
        std::vector<std::uint16_t> actions;int length=1+random()%128;
        for(int i=0;i<length;++i){
            if(random()%5==0)actions.push_back(up_code(random()%(NU+2)));
            else actions.push_back(buy_code(random()%(NB+2),random()%12));
        }
        BasketPrefixes prefixes(actions);
        for(int begin=0;begin<length;++begin)for(int end=begin+1;end<=length;++end){
            auto expected=aggregate_basket(actions,begin,end),actual=prefixes.basket(begin,end);
            assert(expected.size==actual.size);
            if(expected.size<=MAX_ACTIONS)assert(expected==actual);
            ++checked;
        }
    }
    std::cout<<"Checked "<<checked<<" basket intervals, including duplicates and invalid items\n";
}
