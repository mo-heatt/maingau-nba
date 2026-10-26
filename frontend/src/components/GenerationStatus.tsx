type Result={status:string;errors:string[];error?:string|null;attempts?:{number:number;status:string;errors:string[]}[];max_attempts?:number;failure_reasons?:{title:string;message:string}[]};
function fallback(error:string){
 if(/tone/.test(error))return 'The draft mixes Du and Sie. Every spoken part must use the customer’s chosen form of address.';
 if(/Evidence|cite/.test(error))return 'A statement or reference could not be verified against the supplied source.';
 if(/call brief|Call script/.test(error))return 'The customer brief and spoken script are mixed, or a required call section is missing.';
 if(/numeric|Savings|price|Date|contact time/.test(error))return 'A price, quantity, saving or timing is not supported by the supplied data.';
 return error;
}
export default function GenerationStatus({result,busy,onRetry}:{result:Result;busy:boolean;onRetry:()=>void}){
 const failed=result.status==='failed',count=result.attempts?.length;
 const reasons=result.failure_reasons?.length?result.failure_reasons.map(r=>r.message):[...new Set(result.errors.map(fallback))];
 return <div className="generation-status" role="status"><span className="eyebrow">{failed?'Generation interrupted':'Quality check stopped this draft'}</span><h3>{failed?'The AI could not finish this draft.':'The draft still needs correction.'}</h3>
 <p>{count?`Stopped after ${count} of at most ${result.max_attempts||3} attempts.`:'The saved draft did not pass its content checks.'} Automatic retries have stopped.</p>
 {reasons.length>0&&<ul>{reasons.map(reason=><li key={reason}>{reason}</li>)}</ul>}
 {failed&&<p>The AI service did not return a usable response. You can try again manually.</p>}
 <p className="small-text muted">The NBA decision is kept. No message was sent. A new run allows one draft and up to two automatic repairs.</p>
 <button className="button primary" disabled={busy} onClick={onRetry}>Try generating the text again</button>
 <details><summary>Check details</summary><ul>{result.errors.map((error,i)=><li key={i}>{error}</li>)}</ul>{result.error&&<p>{result.error}</p>}{result.attempts?.map(a=><p key={a.number}>Attempt {a.number}: {a.status}{a.errors.length?' · '+a.errors.join('; '):''}</p>)}</details>
 </div>
}
