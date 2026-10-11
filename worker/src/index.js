// On-demand recruitment scanner gateway. Deploy with Cloudflare Workers.
// Secrets: GITHUB_TOKEN (fine-grained token: Actions write, Contents read).
// Required KV binding: REFRESH_LIMIT (shared cooldown across requests).
const REPO="lmy930/lmy_qiuzhao";
const ORIGIN="https://lmy930.github.io";
const RESPONSE_HEADERS={"Access-Control-Allow-Origin":ORIGIN,"Access-Control-Allow-Methods":"GET,POST,OPTIONS","Access-Control-Allow-Headers":"Content-Type","Cache-Control":"no-store","Content-Type":"application/json; charset=utf-8"};
function reply(x,status=200){return new Response(JSON.stringify(x),{status,headers:RESPONSE_HEADERS})}
export default {
 async fetch(request,env){
  const url=new URL(request.url);
  if(request.method==="OPTIONS")return new Response(null,{status:204,headers:RESPONSE_HEADERS});
  if(url.pathname==="/health"&&request.method==="GET")return reply({ok:true,service:"qiuzhao-refresh",mode:"on-demand",cooldown_minutes:30});
  if(url.pathname!=="/refresh"||request.method!=="POST")return reply({error:"not_found"},404);
  if(request.headers.get("Origin")!==ORIGIN)return reply({error:"origin_not_allowed"},403);
  if(!env.GITHUB_TOKEN||!env.REFRESH_LIMIT)return reply({error:"backend_not_configured"},503);
  // KV puts are eventually consistent; this is a best-effort public-button throttle,
  // not strong per-user authentication. GitHub concurrency adds a second safeguard.
  const recent=await env.REFRESH_LIMIT.get("last");
  if(recent&&Date.now()-Number(recent)<30*60*1000)return reply({accepted:false,reason:"recent_scan",last_triggered_at:new Date(Number(recent)).toISOString()});
  const response=await fetch("https://api.github.com/repos/"+REPO+"/actions/workflows/daily-discovery.yml/dispatches",{
   method:"POST",headers:{"Authorization":"Bearer "+env.GITHUB_TOKEN,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"Qiuzhao-Refresh-Worker","Content-Type":"application/json"},
   body:JSON.stringify({ref:"main"})
  });
  if(!response.ok)return reply({accepted:false,error:"dispatch_failed",upstream_status:response.status},502);
  await env.REFRESH_LIMIT.put("last",String(Date.now()),{expirationTtl:1900});
  return reply({accepted:true,state:"queued",message:"正在后台重新检查657家企业，结果将陆续写回GitHub。"});
 }
};
