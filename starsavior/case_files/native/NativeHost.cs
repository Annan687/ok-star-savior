using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Threading;
using System.Web.Script.Serialization;

public class NativeRequest {
    public int protocol=2;
    public string type,request_id;
    public long deadline_unix_ms;
    public int budget_ms=420;
    public CoreState state;
    public string rounding="floor_seconds";
    public CoreObjective objective=new CoreObjective();
    public CoreTiming timing;
}
public class SearchInterrupted:Exception {public string reason;public SearchInterrupted(string reason){this.reason=reason;}}
public static class NativeBudget {
    public static Stopwatch clock;
    public static int milliseconds;
    public static volatile bool cancelled;
    public static void Check(){
        if(cancelled)throw new SearchInterrupted("cancelled");
        if(clock!=null&&clock.ElapsedMilliseconds>=milliseconds)throw new SearchInterrupted("deadline");
    }
}
public class NativeHost {
    static TextWriter output=Console.Out;
    static object outputLock=new object(),jobLock=new object();
    static string activeId;
    static Thread worker;
    static JavaScriptSerializer serializer=new JavaScriptSerializer{MaxJsonLength=1000000};
    static long UtcMs(){return (DateTime.UtcNow.Ticks-621355968000000000L)/10000;}
    static void Emit(object value){lock(outputLock){output.WriteLine(new JavaScriptSerializer().Serialize(value));output.Flush();}}
    static CoreAction ParseAction(string line){
        if(String.IsNullOrEmpty(line)||line.StartsWith("NONE"))return new CoreAction();
        string[] p=line.Split('|')[0].Split(',');if(p.Length!=4)return new CoreAction();
        return new CoreAction{kind="MOVE",rect=Array.ConvertAll(p,int.Parse)};
    }
    static bool Legal(CoreState s,CoreAction action){
        if(action.kind=="WAIT")return true;
        int[] p=action.rect;if(p==null||p.Length!=4||p[0]<0||p[1]<0||p[2]>=s.height||p[3]>=s.width||p[0]>p[2]||p[1]>p[3])return false;
        int sum=0;for(int r=p[0];r<=p[2];r++)for(int c=p[1];c<=p[3];c++)sum+=s.board[r*s.width+c];return sum==10;
    }
    static void Run(NativeRequest request){
        var watch=Stopwatch.StartNew();string status="ok",line=null,error=null;
        object analysis=null;CoreAction action=new CoreAction();
        try {
            request.state.Validate();
            if(request.state.board_hash==null||request.state.state_version<0)throw new ArgumentException("state identity missing");
            analysis=CoreMath.Analyze(request.state,request.rounding,request.objective);
            if(request.type=="choose"){
                if(request.state.height!=10||request.state.width!=15)throw new ArgumentException("full-board planner expects 10x15");
                int left=(int)Math.Min(request.budget_ms,Math.Max(0,request.deadline_unix_ms-UtcMs()));
                NativeBudget.clock=watch;NativeBudget.milliseconds=Math.Min(request.budget_ms,(int)watch.ElapsedMilliseconds+left);
                NativeBudget.Check();
                var captured=new StringWriter(CultureInfo.InvariantCulture);
                Console.SetOut(captured);
                RouteSearch.Published=null;
                try {
                    // Leave a small reserve for completing a rollout, serializing and IPC.
                    int softBudget=Math.Max(1,left-30);
                    string text=softBudget+"|"+(((request.state.skills_mask&2)!=0)?"1":"0")+"|"+(((request.state.skills_mask&1)!=0)?"1":"0")+"|"+string.Join(",",request.state.board);
                    RouteSearch.Solve(text);line=captured.ToString().Trim();
                }catch(SearchInterrupted stop){status=stop.reason;line=RouteSearch.Published;RouteSearch.ResetState();}
                finally {Console.SetOut(output);}
                action=ParseAction(line);
                if(!Legal(request.state,action))throw new InvalidOperationException("planner emitted invalid rectangle");
            }
        }catch(SearchInterrupted stop){status=stop.reason;}
        catch(Exception ex){status="error";error=ex.Message;}
        finally {
            NativeBudget.clock=null;
            lock(jobLock){
                Emit(new {protocol=2,request_id=request.request_id,state_version=request.state==null?0:request.state.state_version,board_hash=request.state==null?null:request.state.board_hash,status=status,error=error,action=action,analysis=analysis,elapsed_ms=watch.Elapsed.TotalMilliseconds,search_finished=status=="ok",optimal=false,policy="v1.2-route-with-deadline",legacy_diagnostics=line});
                activeId=null;
            }
        }
    }
    public static void Main(){
        Thread.CurrentThread.CurrentCulture=CultureInfo.InvariantCulture;
        RouteSearch.Initialize();string line;
        while((line=Console.ReadLine())!=null){
            NativeRequest r;
            try {r=serializer.Deserialize<NativeRequest>(line);if(r==null||r.protocol!=2||String.IsNullOrEmpty(r.request_id))throw new ArgumentException("invalid protocol/request id");}
            catch(Exception ex){Emit(new {protocol=2,status="error",error=ex.Message});continue;}
            lock(jobLock){
                if(r.type=="cancel"){
                    if(activeId==r.request_id)NativeBudget.cancelled=true;
                    continue;
                }
                if(activeId!=null){Emit(new {protocol=2,request_id=r.request_id,status="busy"});continue;}
                if(r.type=="reset"){RouteSearch.ResetState();Emit(new {protocol=2,request_id=r.request_id,status="ok"});continue;}
                if(r.type=="ping"){Emit(new {protocol=2,request_id=r.request_id,status="ok",version="1.3"});continue;}
                if(r.type!="choose"&&r.type!="analyze"){Emit(new {protocol=2,request_id=r.request_id,status="error",error="unknown request type"});continue;}
                activeId=r.request_id;NativeBudget.cancelled=false;
                worker=new Thread(()=>Run(r));worker.IsBackground=true;worker.Start();
            }
        }
        NativeBudget.cancelled=true;if(worker!=null)worker.Join(200);
    }
}
