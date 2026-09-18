using System;
using System.Collections.Generic;
using System.Linq;

// Port of the reviewed pure Python model/scoring/bounds. No desktop or search calls.
public class ObservedValue {
    public string source;
    public double confidence;
    public long captured_unix_ms;
}
public class CoreState {
    public int[] board;
    public int height=10, width=15, initial_cells=150, skills_mask;
    public int? remaining_ms;
    public int? hud_score;
    public long state_version;
    public string board_hash, policy_version, timing_version;
    public ObservedValue board_observation, time_observation, skill_observation;
    public bool cleared_in_time;
    public int Occupied {get{return board.Count(v=>v!=0);}}
    public void Validate(){
        if(board==null||board.Length==0||height<=0||width<=0||height*width!=board.Length||board.Length>150)throw new ArgumentException("invalid dimensions");
        if(board.Any(v=>v<0||v>9)||initial_cells<Occupied||initial_cells>150||(skills_mask&~7)!=0||skills_mask<0)throw new ArgumentException("invalid board/skills");
        if(remaining_ms.HasValue&&remaining_ms.Value<0)throw new ArgumentException("negative timer");
        if(cleared_in_time&&Occupied!=0)throw new ArgumentException("nonempty clear");
    }
}
public class CoreObjective {
    public string mode="mean_score";
    public decimal? threshold, record;
    public decimal Value(decimal score){
        if(mode=="mean_score")return score;
        if(mode=="beat_threshold"&&threshold.HasValue)return score>threshold.Value?1:0;
        if(mode=="record_gain"&&record.HasValue)return Math.Max(0,score-record.Value);
        throw new ArgumentException("invalid or incomplete objective");
    }
}
public class CoreTiming {
    public int? move_ms, q_ms, w_ms, e_ms, future_plan_ms;
    public bool calibrated;
    public string version="unmeasured";
}
public class CoreAction {
    public string kind="WAIT";
    public int[] rect;
}
public class CoreScore {
    public int cell_points, skill_points;
    public decimal time_points, total;
}
public class RationalValue {
    public long numerator,denominator;
    public RationalValue(long n,long d){long a=n,b=d;while(b!=0){long t=a%b;a=b;b=t;}numerator=n/a;denominator=d/a;}
}
public static class CoreMath {
    public static CoreScore Score(int initial,int remaining,int skills,int remainingMs,bool clear,string rounding){
        if(initial<0||remaining<0||remaining>initial||skills<0||(skills&~7)!=0||remainingMs<0||(clear&&remaining!=0))throw new ArgumentException("invalid terminal");
        if(rounding!="continuous"&&rounding!="floor_seconds")throw new ArgumentException("explicit rounding required");
        int unused=((skills&1)!=0?1:0)+((skills&2)!=0?1:0)+((skills&4)!=0?1:0);
        decimal seconds=rounding=="continuous"?remainingMs/1000m:remainingMs/1000;
        var s=new CoreScore{cell_points=(initial-remaining)*100,skill_points=unused*100,time_points=clear?seconds*10:0};
        s.total=s.cell_points+s.skill_points+s.time_points;return s;
    }
    public static int NumericUpperBound(int[] board,bool qAvailable){
        int[] c=new int[10];foreach(int v in board){if(v<0||v>9)throw new ArgumentException("digit");if(v!=0)c[v]++;}
        int n=c.Sum(),q=qAvailable?Math.Min(5,n):0;
        int a=2*c[1]+2*c[2]+c[3]+2*c[4]+c[5]+c[7]+q;
        int b=(5*c[1]+4*c[2]+c[3]+4*c[4]+2*c[5]+3*c[7]+2*q)/2;
        int upper=Math.Min(n,Math.Min(a,b));
        if(!qAvailable&&board.Sum()%10!=0)upper=Math.Min(upper,Math.Max(0,n-1));
        return upper;
    }
    public static RationalValue[] QResidues(int[] board){
        int[] digits=board.Where(v=>v!=0).ToArray();int k=Math.Min(5,digits.Length);
        long[,] dp=new long[k+1,10];dp[0,0]=1;
        for(int index=0;index<digits.Length;index++)for(int selected=Math.Min(k,index+1);selected>0;selected--)for(int residue=0;residue<10;residue++)
            dp[selected,(residue+digits[index])%10]+=dp[selected-1,residue];
        long denominator=1;for(int i=1;i<=k;i++)denominator=denominator*(digits.Length-i+1)/i;
        var result=new RationalValue[10];for(int r=0;r<10;r++)result[r]=new RationalValue(dp[k,r],denominator);
        return result;
    }
    public static object Analyze(CoreState state,string rounding,CoreObjective objective){
        state.Validate();int upper=NumericUpperBound(state.board,(state.skills_mask&1)!=0);
        var residues=QResidues(state.board);CoreScore current=null,bound=null;
        if(state.remaining_ms.HasValue){
            current=Score(state.initial_cells,state.Occupied,state.skills_mask,state.remaining_ms.Value,state.cleared_in_time,rounding);
            int left=state.Occupied-upper;
            bound=Score(state.initial_cells,left,state.skills_mask,state.remaining_ms.Value+((state.skills_mask&4)!=0?10000:0),left==0,rounding);
        }
        return new {
            score_if_stop=current,
            utility_if_stop=current==null?(decimal?)null:objective.Value(current.total),
            removable_upper_bound=upper,
            clear_not_ruled_out=upper==state.Occupied,
            optimistic_score_bound=bound,
            q_now_residue_probabilities=residues,
            q_now_clear_modulo_necessary_probability=residues[state.board.Sum()%10],
            rounding=rounding,
            note="Numeric and score bounds are optimistic, not reachable predictions. Q-now modulo is necessary only."
        };
    }
}
