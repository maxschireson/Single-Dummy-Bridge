// Budgeted exact threshold proofs, with an explicitly unproved point estimate.
// On timeout discard the context's interrupted state; no heuristic enters its TT.
#include <algorithm>
#include <cmath>
#include <cstring>
#include <api/solve_board.hpp>
#include <solver_context/solver_context.hpp>
#include <approx_budget.hpp>

namespace {
double rollout(const Deal& d) {
    int nt=0;while(nt<3 && d.currentTrickRank[nt])++nt;
    const int actor=(d.first+nt)%4;double total=0;
    for(int variant=0;variant<2;++variant) {
        bool hand[4][52]{};int left=0;
        for(int h=0;h<4;++h)for(int s=0;s<4;++s)for(int r=2;r<=14;++r)
            if(d.remainCards[h][s]&(1u<<r)){hand[h][13*s+r-2]=true;++left;}
        int tr[4]{},lead=d.first,n=nt,won=0;
        for(int i=0;i<n;++i)tr[i]=13*d.currentTrickSuit[i]+d.currentTrickRank[i]-2;
        auto winner=[&](){int best=0;for(int i=1;i<n;++i){
            auto strength=[&](int c){return (c/13==d.trump?200:c/13==tr[0]/13?100:0)+c%13;};
            if(strength(tr[i])>strength(tr[best]))best=i;
        }return (lead+best)%4;};
        while(left) {
            int seat=(lead+n)%4;bool follow=false;
            if(n)for(int c=0;c<52;++c)if(hand[seat][c] && c/13==tr[0]/13)follow=true;
            int choice=-1,best=-10000,winning=-1,winning_cost=10000,cheap=-1,cheap_cost=10000;
            int current=n?winner():-1;
            for(int c=0;c<52;++c)if(hand[seat][c] && (!follow || c/13==tr[0]/13)) {
                if(!n){int len=0;for(int r=0;r<13;++r)len+=hand[seat][13*(c/13)+r];
                    int val=2*(c%13+(variant?2*len:0))+(c/13!=d.trump);
                    if(val>best){best=val;choice=c;}
                } else {
                    int cost=(c/13==d.trump?100:0)+c%13;
                    if(cost<cheap_cost){cheap_cost=cost;cheap=c;}
                    tr[n]=c;++n;bool wins=winner()==seat;--n;
                    if(wins && cost<winning_cost){winning_cost=cost;winning=c;}
                }
            }
            if(n)choice=(winning>=0 && current%2!=seat%2)?winning:cheap;
            if(choice<0)return 0.;
            hand[seat][choice]=false;--left;tr[n++]=choice;
            if(n==4){lead=winner();won+=lead%2==actor%2;n=0;}
        }
        total+=won;
    }
    return total/2.;
}
}

extern "C" int bridge_dds_approx_value(void* handle,const Deal* deal,
    unsigned long long budget,double guess,double* estimate,int* lower,int* upper,
    unsigned long long* nodes,int* exact)
{
    if (!handle || !deal || !estimate || !lower || !upper || !nodes || !exact || !std::isfinite(guess)) return -1;
    auto& ctx=*static_cast<SolverContext*>(handle);
    int count=0;
    for(int h=0;h<4;++h)for(int s=0;s<4;++s)count+=__builtin_popcount(deal->remainCards[h][s]);
    for(int i=0;i<3;++i)if(deal->currentTrickRank[i])++count;
    if(count<4 || count%4) return -2;
    if(guess<0)guess=rollout(*deal);
    int lo=0,hi=count/4;
    approx_dds::visited=0;approx_dds::limit=budget;approx_dds::enabled=true;
    try {
        ctx.reset_for_solve();
        std::memset(ctx.thread_ptr()->suit,0,sizeof(ctx.thread_ptr()->suit));
        int target=std::clamp(static_cast<int>(std::lround(guess)),1,hi);
        while(lo<hi) {
            FutureTricks f{};
            int status=solve_board(ctx,*deal,target,1,1,&f);
            if(status!=RETURN_NO_FAULT) {approx_dds::enabled=false;ctx.reset_for_solve();std::memset(ctx.thread_ptr()->suit,0,sizeof(ctx.thread_ptr()->suit));return status;}
            if(f.score[0]>=target)lo=target;else hi=target-1;
            target=(lo+hi+1)/2;
        }
    } catch(const approx_dds::Exhausted&) {
        // Only fully completed threshold proofs have updated lo/hi.
    } catch(...) {
        approx_dds::enabled=false;ctx.reset_for_solve();std::memset(ctx.thread_ptr()->suit,0,sizeof(ctx.thread_ptr()->suit));return -3;
    }
    approx_dds::enabled=false;
    *lower=lo;*upper=hi;*nodes=approx_dds::visited;*exact=(lo==hi);
    *estimate=std::clamp(guess,static_cast<double>(lo),static_cast<double>(hi));
    ctx.reset_for_solve();
    std::memset(ctx.thread_ptr()->suit,0,sizeof(ctx.thread_ptr()->suit));
    return 1;
}
