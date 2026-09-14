#include "native_generator.hpp"
#include <iostream>
#include <random>
#include <queue>
int main(){
    std::mt19937 rng(941);std::uint64_t valid_total=0,unit_missing=0,bridge_missing=0;
    int examples=0;
    for(int trial=0;trial<500;++trial){
        NativeState a{};
        // Use actual legal shopping histories, not arbitrary inventories with
        // upgrades whose prerequisites have never been bought.
        for(int step=0;step<int(1+rng()%20);++step){
            std::vector<NativeState> next;
            for(auto action:seeds(a,12)){NativeState child;if(evaluate(a,action.data.data(),action.size,child,1e6,-1))next.push_back(child);}
            if(next.empty())break;a=next[rng()%next.size()];
        }
        if(trial%2){double cookies=std::min(double(rng()%1000),std::max(0.0,999999-a.baked));auto r=rates(a);
            a.age+=cookies/r.total();a.handmade+=r.hand*cookies/r.total();a.baked+=cookies;a.bank+=cookies;
        }
        std::array<bool,1000> valid{};valid[0]=true;
        for(int code=1;code<1000;++code){Actions action;int n=code;
            for(int b=0;b<3;++b){int q=n%10;n/=10;if(q)action.data[action.size++]=buy_code(b,q);}
            action=canonicalize(a,action,true);NativeState s;valid[code]=evaluate(a,action.data.data(),action.size,s,1e6,-1);
            valid_total+=valid[code];
        }
        std::array<std::array<bool,1000>,2> reached{};
        for(int mode=0;mode<2;++mode){std::queue<int> queue;
            for(int place: {1,10,100})for(int q=1;q<10;++q)if(valid[q*place]){reached[mode][q*place]=true;queue.push(q*place);}
            while(!queue.empty()){int code=queue.front();queue.pop();
                for(int place: {1,10,100}){int old=(code/place)%10;
                    for(int q=old+1;q<10;++q){int child=code+(q-old)*place;
                        if(valid[child]){if(!reached[mode][child]){reached[mode][child]=true;queue.push(child);}break;}
                        if(!mode)break;
                    }
                }
            }
        }
        for(int code=1;code<1000;++code)if(valid[code]){
            unit_missing+=!reached[0][code];bridge_missing+=!reached[1][code];
            if(!reached[0][code]&&examples++<5){
                std::cout<<"{\"event\":\"unit_missed\",\"counts\":[";
                for(int b=0;b<NB;++b){if(b)std::cout<<",";std::cout<<a.buildings[b];}
                std::cout<<"],\"bank\":"<<a.bank<<",\"basket_code\":"<<code<<",\"bridge_reaches\":"<<reached[1][code]<<"}\n";
            }
        }
    }
    std::cout<<"{\"valid_baskets\":"<<valid_total<<",\"unit_missing\":"<<unit_missing<<",\"bridge_missing\":"<<bridge_missing<<"}\n";
}
