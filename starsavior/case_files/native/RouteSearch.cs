using System;
using System.Collections.Generic;
using System.Diagnostics;

class Move {
    public int A,B,C,D,N,H;
    public Move(int a,int b,int c,int d,int n,int h){A=a;B=b;C=c;D=d;N=n;H=h;}
    public string Text(){return A+","+B+","+C+","+D;}
}
class RouteSearch {
    public static string Published;
    public static void Initialize(){Patterns(1,10,new int[10]);}
    public static void ResetState(){previous.Clear();qCache.Clear();}
    static Random rng=new Random();
    static List<Move> previous=new List<Move>();
    static List<int[]> patterns=new List<int[]>();
    const double ClearBonus=7, PairPreference=.10;
    class QEstimate {
        public double Removed, Cleared, UtilitySquared;
        public int Samples;
        public bool Exact;
        public double Value {get{return (Removed+ClearBonus*Cleared)/Samples;}}
        public double Error {
            get {
                if(Exact)return 0;
                if(Samples<2)return 2;
                double variance=Math.Max(0,(UtilitySquared-Samples*Value*Value)/(Samples-1));
                return Math.Sqrt(variance/Samples);
            }
        }
    }
    class Candidate {
        public int[] Final;
        public List<Move> Path;
        public QEstimate Estimate;
        public double Score;
        public double Rank;
    }
    static Dictionary<string,QEstimate> qCache=new Dictionary<string,QEstimate>();
    static string BoardKey(int[] board){
        char[] key=new char[150];for(int i=0;i<150;i++)key[i]=(char)('0'+board[i]);
        return new string(key);
    }
    static List<Move> Moves(int[] board,int maxCells){
        NativeBudget.Check();
        var result=new List<Move>();
        for(int a=0;a<10;a++){NativeBudget.Check();
            int[] sums=new int[15],counts=new int[15],high=new int[15];
            for(int c=a;c<10;c++){
                for(int x=0;x<15;x++) {int v=board[c*15+x];sums[x]+=v;if(v>0)counts[x]++;if(v>=6)high[x]++;}
                for(int b=0;b<15;b++){
                    if(sums[b]==0)continue;
                    int s=0,n=0,h=0,top=0,bottom=0;
                    for(int d=b;d<15;d++){
                        s+=sums[d];n+=counts[d];h+=high[d];top+=board[a*15+d];bottom+=board[c*15+d];
                        if(s>10)break;
                        if(s==10){if(top>0&&bottom>0&&n<=maxCells)result.Add(new Move(a,b,c,d,n,h));break;}
                    }
                }
            }
        }
        return result;
    }
    static bool Apply(int[] board,Move m,int maxCells){
        int sum=0,n=0;for(int r=m.A;r<=m.C;r++)for(int c=m.B;c<=m.D;c++){int v=board[r*15+c];sum+=v;if(v>0)n++;}
        if(sum!=10||n>maxCells)return false;
        for(int r=m.A;r<=m.C;r++)for(int c=m.B;c<=m.D;c++)board[r*15+c]=0;
        return true;
    }
    static int Count(int[] b){int n=0;foreach(int v in b)if(v>0)n++;return n;}
    static bool CanFormTen(int[] board){
        int reachable=1;
        foreach(int v in board)if(v>0){
            reachable=(reachable|(reachable<<v))&2047;
            if((reachable&1024)!=0)return true;
        }
        return false;
    }
    static void Patterns(int digit,int left,int[] p){
        if(digit==10){if(left==0)patterns.Add((int[])p.Clone());return;}
        for(int n=0;n*digit<=left;n++){p[digit]=n;Patterns(digit+1,left-n*digit,p);}p[digit]=0;
    }
    // A lower bound on how many remaining digits can still form tens after rearranging.
    static int Pack(int[] board){
        int[] counts=new int[10];foreach(int v in board)counts[v]++;
        int best=0;
        for(int style=0;style<3;style++){NativeBudget.Check();
            int[] c=(int[])counts.Clone();int total=0;
            while(true){NativeBudget.Check();int[] chosen=null;double bestValue=-1;
                foreach(int[] p in patterns){
                    bool ok=true;int n=0,high=0;
                    for(int d=1;d<=9;d++){if(p[d]>c[d]){ok=false;break;}n+=p[d];if(d>=6)high+=p[d];}
                    if(!ok)continue;
                    double v=style==0 ? n : style==1 ? high*6+n*.2 : n+high*1.5;
                    if(v>bestValue){bestValue=v;chosen=p;}
                }
                if(chosen==null)break;
                for(int d=1;d<=9;d++){c[d]-=chosen[d];total+=chosen[d];}
            }
            best=Math.Max(best,total);
        }
        return best;
    }
    // Q removes five distinct occupied cells uniformly in the model. Continue playing
    // each sampled board; measure cleared cells, rather than just finding a legal move.
    static QEstimate EstimateQ(int[] final,int target,Stopwatch clock,int budget){
        string key=BoardKey(final);QEstimate estimate;
        if(!qCache.TryGetValue(key,out estimate)){
            if(qCache.Count>=4096)qCache.Clear();
            estimate=new QEstimate();qCache[key]=estimate;
            int left=Count(final);
            if(left<=5){estimate.Removed=left;estimate.Cleared=1;estimate.Samples=1;estimate.Exact=true;}
            else if(left==6){estimate.Removed=5;estimate.Samples=1;estimate.Exact=true;}
            else if(left==7){
                var digits=new List<int>();foreach(int v in final)if(v>0)digits.Add(v);
                int pairs=0;for(int i=0;i<7;i++)for(int j=i+1;j<7;j++)if(digits[i]+digits[j]==10)pairs++;
                // Only two cells remain after Q, so geometry cannot block their rectangle.
                double probability=pairs/21.0;
                estimate.Removed=5+2*probability;estimate.Cleared=probability;estimate.Samples=1;estimate.Exact=true;
            }
            else if(!CanFormTen(final)){
                // Deletion cannot create a sum-ten subset when none exists numerically.
                estimate.Removed=5;estimate.Samples=1;estimate.Exact=true;
            }
        }
        if(estimate.Exact)return estimate;
        var occupied=new List<int>();for(int i=0;i<150;i++)if(final[i]>0)occupied.Add(i);
        while(estimate.Samples<target){NativeBudget.Check();
            if(estimate.Samples>0&&clock.ElapsedMilliseconds>=budget)break;
            // Reuse sample seeds across candidates; refinement extends the same samples.
            Random qrng=new Random(unchecked(104729+estimate.Samples*7919));
            int[] after=(int[])final.Clone();int[] ids=occupied.ToArray();
            for(int i=0;i<5;i++){
                int k=qrng.Next(i,ids.Length),tmp=ids[i];ids[i]=ids[k];ids[k]=tmp;
                after[ids[i]]=0;
            }
            int bestLeft=occupied.Count-5;
            for(int style=0;style<3;style++){NativeBudget.Check();
                int[] sim=(int[])after.Clone();
                while(true){NativeBudget.Check();
                    var options=Moves(sim,10);if(options.Count==0)break;
                    Move chosen=null;double score=-1e99;
                    foreach(Move m in options){
                        double bias=style==0?m.N:style==1?m.H*2+m.N*.15:(m.N==2?1:0);
                        double value=bias+qrng.NextDouble()*2.5;
                        if(value>score){score=value;chosen=m;}
                    }
                    Apply(sim,chosen,10);
                }
                bestLeft=Math.Min(bestLeft,Count(sim));
                if(bestLeft==0)break;
            }
            estimate.Removed+=occupied.Count-bestLeft;
            if(bestLeft==0)estimate.Cleared++;
            double utility=occupied.Count-bestLeft+(bestLeft==0?ClearBonus:0);
            estimate.UtilitySquared+=utility*utility;
            estimate.Samples++;
        }
        return estimate;
    }
    static double CandidateScore(Candidate candidate,int initial){
        int left=Count(candidate.Final);
        // Finishing without spending Q also preserves its 100-point unused-skill bonus.
        // A small uncertainty penalty discourages choosing a route from a few lucky samples.
        double future=left==0?ClearBonus+1:candidate.Estimate.Value-.5*candidate.Estimate.Error;
        return initial-left+future+(candidate.Path[0].N==2?PairPreference:0)-candidate.Path.Count*.0001;
    }
    static Candidate MakeCandidate(int[] final,List<Move> path,int initial){
        int left=Count(final);
        double baseScore=initial-left+(left==0?ClearBonus+1:Math.Min(5,left)+(left<=5?ClearBonus:0))-path.Count*.0001;
        // This cheap numeric potential only selects candidates to examine, never the final move.
        double rank=baseScore+(left>7&&CanFormTen(final)?Pack(final)*.12:0);
        return new Candidate{Final=final,Path=path,Score=baseScore,Rank=rank};
    }
    static double Value(int[] final,int initial,bool shuffle,bool q,int pathLength){
        int left=Count(final),removed=initial-left;
        double v=removed;
        if(shuffle)v+=Pack(final)*.85;
        if(left==0 || (q&&left<=5))v+=7;
        return v-pathLength*.0001;
    }
    static List<Move> Rollout(int[] initial,List<Move> seed,int maxCells,int style,out int[] sim){
        sim=(int[])initial.Clone();var path=new List<Move>();
        if(seed.Count>0&&rng.Next(3)>0){
            int prefix=rng.Next(seed.Count);
            for(int i=0;i<prefix;i++){if(!Apply(sim,seed[i],maxCells))break;path.Add(seed[i]);}
        }
        while(true){NativeBudget.Check();
            var options=Moves(sim,maxCells);if(options.Count==0)break;
            Move pick=null;double score=-1e99;
            foreach(Move m in options){
                double bias=style==0?m.N*1.4:style==1?m.H*3+m.N*.1:style==2?m.N*.5:0;
                double value=bias+rng.NextDouble()*3.5;
                if(value>score){score=value;pick=m;}
            }
            Apply(sim,pick,maxCells);path.Add(pick);
        }
        return path;
    }
    public static void Solve(string line){
        string[] parts=line.Split('|');int millis=int.Parse(parts[0]);bool shuffle=parts[1]=="1",q=parts[2]=="1";
        // Preserve complementary small digits until W; allow every valid rectangle afterwards.
        int maxCells=shuffle?2:10;
        string[] nums=parts[3].Split(',');int[] initial=new int[150];for(int i=0;i<150;i++)initial[i]=int.Parse(nums[i]);
        var legal=Moves(initial,maxCells);if(legal.Count==0){Console.WriteLine("NONE");return;}
        Published=legal[0].Text();
        int initialCount=Count(initial);var best=new List<Move>();double bestScore=-1;
        bool qPlanning=!shuffle&&q;
        Stopwatch clock=Stopwatch.StartNew();int trials=0;
        var candidates=new Dictionary<string,Candidate>();
        if(previous.Count>0){
            int[] sim=(int[])initial.Clone();var path=new List<Move>();
            foreach(Move m in previous){if(!Apply(sim,m,maxCells))break;path.Add(m);}
            if(path.Count>0){
                best=path;
                if(qPlanning){
                    var candidate=MakeCandidate(sim,path,initialCount);
                    candidates[BoardKey(sim)]=candidate;bestScore=candidate.Score;
                }else bestScore=Value(sim,initialCount,shuffle,q,path.Count)+(path[0].N==2?PairPreference:0);
            }
        }
        do {
            int[] sim;var path=Rollout(initial,best,maxCells,trials%5,out sim);
            double value;
            if(qPlanning){
                var candidate=MakeCandidate(sim,path,initialCount);value=candidate.Score;
                string key=BoardKey(sim);Candidate old;
                if(!candidates.TryGetValue(key,out old)||candidate.Score>old.Score)candidates[key]=candidate;
                if(candidates.Count>48){
                    string worst=null;double lowest=double.MaxValue;
                    foreach(var entry in candidates)if(entry.Value.Rank<lowest){lowest=entry.Value.Rank;worst=entry.Key;}
                    candidates.Remove(worst);
                }
            }else value=Value(sim,initialCount,shuffle,q,path.Count)+(path[0].N==2?PairPreference:0);
            if(path.Count>0 && value>bestScore){bestScore=value;best=path;Published=best[0].Text();}
            trials++;
        }while(clock.ElapsedMilliseconds<millis*(qPlanning?.80:1.0));
        int qSamples=0;
        if(qPlanning){
            var finalists=new List<Candidate>(candidates.Values);
            finalists.Sort((a,b)=>b.Rank.CompareTo(a.Rank));
            if(finalists.Count>8)finalists=finalists.GetRange(0,8);
            // Always retain the best deterministic route, even if the numeric heuristic ranks it lower.
            int[] baselineFinal=(int[])initial.Clone();foreach(Move m in best)Apply(baselineFinal,m,maxCells);
            string baselineKey=BoardKey(baselineFinal);
            if(!finalists.Exists(c=>BoardKey(c.Final)==baselineKey))finalists.Add(MakeCandidate(baselineFinal,best,initialCount));
            foreach(int target in new[]{12,32,64,128}){
                foreach(Candidate candidate in finalists){
                    candidate.Estimate=EstimateQ(candidate.Final,target,clock,millis);
                    candidate.Score=CandidateScore(candidate,initialCount);
                }
                if(clock.ElapsedMilliseconds>=millis)break;
            }
            bestScore=-1;
            foreach(Candidate candidate in finalists)if(candidate.Score>bestScore){
                bestScore=candidate.Score;best=candidate.Path;Published=best[0].Text();qSamples=candidate.Estimate.Exact?-1:candidate.Estimate.Samples;
            }
            // Exact/cached Q estimates often finish early. Spend the remaining time on routes.
            while(clock.ElapsedMilliseconds<millis){
                int[] sim;var path=Rollout(initial,best,maxCells,trials%5,out sim);
                var candidate=new Candidate{Final=sim,Path=path,Estimate=EstimateQ(sim,128,clock,millis)};
                candidate.Score=CandidateScore(candidate,initialCount);
                if(candidate.Score>bestScore){bestScore=candidate.Score;best=path;Published=best[0].Text();qSamples=candidate.Estimate.Exact?-1:candidate.Estimate.Samples;}
                trials++;
            }
        }
        previous=best.GetRange(1,best.Count-1);
        Console.WriteLine(best[0].Text()+"|"+trials+"|"+bestScore.ToString("F2",System.Globalization.CultureInfo.InvariantCulture)+"|"+best.Count+"|"+qSamples);
    }
    static void Main(){Patterns(1,10,new int[10]);string s;while((s=Console.ReadLine())!=null){try{if(s=="RESET"){previous.Clear();qCache.Clear();Console.WriteLine("OK");}else Solve(s);}catch(Exception ex){Console.WriteLine("ERROR:"+ex.Message);}}}
}
