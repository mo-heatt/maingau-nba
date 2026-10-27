// Local contract fixture; never a production AI fallback.
const http = require('http');
http.createServer(async (req, res) => {
  if(req.method==='GET'&&req.url.endsWith('/v1/models')){const denied=req.headers.authorization==='Bearer rejected-key'?401:req.headers.authorization==='Bearer forbidden-key'?403:0;res.writeHead(denied||200,{'Content-Type':'application/json'});res.end(JSON.stringify(denied?{error:'unauthorized'}:{data:[{id:'fixture'}]}));return;}

  if (req.method !== 'POST' || !req.url.endsWith('/v1/chat/completions')) {
    res.writeHead(501, {'Content-Type':'application/json'}); res.end('{}'); return;
  }
  let raw='';for await (const chunk of req) raw+=chunk;
  const body=typeof req.body==='object'&&req.body?req.body:JSON.parse(raw||'{}');
  if(body.model==='http-error'){res.writeHead(503,{'Content-Type':'text/html'});res.end('<h1>Unavailable</h1>');return}
  if(body.model==='timeout'){await new Promise(r=>setTimeout(r,1000))}
  const source=JSON.parse(body.messages[1].content), packet=source.context||source;
  const facts=packet.facts||source.facts||[];
  const evidence=facts.slice(0,2).map(f=>({fact_id:f.id,quote:f.quote}));
  if(body.model==='bad-evidence')evidence[0]={fact_id:'F999999',quote:'invented'};
  let result;
  if(body.messages[0].content.includes('Write a finished German MAINGAU newsletter')){
    const quote=source.quote; const quoted=quote?.target?.name?(' Vorschlag: '+quote.target.name+(quote.target.monthly_eur!==undefined?(' für '+quote.target.monthly_eur+' EUR im Monat.') :'.')):'';
    result={headline:'Ein nützlicher Hinweis',subject:'Ein Update von MAINGAU',body:'Hallo! Hier ist ein hilfreicher Hinweis aus unserem Ratgeber.'+quoted,benefit_points:['Mehr im Originalbeitrag lesen'],evidence:facts.filter(f=>f.id==='N1').map(f=>({fact_id:f.id,quote:f.quote}))};
  } else if(body.messages[0].content.includes('Create MAINGAU outreach material')){
    const call=['outbound_call','agent_callback'].includes(source.channel);
    result={headline:'Ein passender nächster Schritt',subject:['email','newsletter_email'].includes(source.channel)?'Ein konkretes Angebot':null,
      body:body.model==='bad-price'?'Das kostet 99,99 €.':'Ein passendes Angebot auf Basis der vorhandenen Daten.',benefit_points:['Passendes Datenvolumen'],
      opening:call?'Passt es gerade?':null,discovery_questions:call?['Wie passt der aktuelle Tarif?']:[],offer_pitch:call?'Der vorgeschlagene Tarif passt zum Bedarf.':null,
      objections:call?[{concern:'Ich möchte überlegen.',response:'Natürlich, gerne in Ruhe prüfen.'}]:[],closing:call?'Wie möchten wir weiter vorgehen?':null,evidence};
    if(source.proposal?.action==='service'){
      const formal=source.tone==='sie';
      result={...result,headline:'Gemeinsam das Anliegen klären',subject:result.subject?(formal?'Hilfe zu Ihrem Anliegen':'Hilfe zu deinem Anliegen'):null,body:formal?'Wir helfen Ihnen gern, Ihr offenes Anliegen zu klären.':'Wir helfen dir gern, dein offenes Anliegen zu klären.',benefit_points:['Unterstützung beim offenen Anliegen'],discovery_questions:call?[formal?'Was ist Ihnen bei der Klärung wichtig?':'Was ist dir bei der Klärung wichtig?']:[],offer_pitch:call?(formal?'Wir klären gemeinsam Ihr Anliegen.':'Wir klären gemeinsam dein Anliegen.'):null};
      if(call)result.body='Offenes Serviceanliegen; nächster Schritt ist die gemeinsame Klärung.';
    }
  } else if(body.messages[0].content.includes('German MAINGAU email')){
    result={subject:'Ein passender nächster Schritt',body:'Guten Tag, wir möchten gemeinsam eine passende Option prüfen.',evidence};
  } else {
    const policy=packet.policy;
    let action=policy.forced_action||'offer';
    let p=(packet.catalogue||[]).find(p=>!p.blocked.length&&p.action_type!=='service'&&p.economics&&p.economics.per_channel.some(c=>c.dclv>policy.min_expected_gain_eur));
    if(action==='service')p=packet.catalogue.find(p=>p.action_type==='service'&&!p.blocked.length&&p.economics?.expected_gain_eur>policy.min_expected_gain_eur);
    if(!p&&['offer','service'].includes(action))action='none';
    const channel=action==='offer'?p.economics.per_channel.find(c=>c.dclv>policy.min_expected_gain_eur).channel:action==='service'?'agent_callback':null;
    result={action,product_id:['offer','service'].includes(action)?p.product_id:null,channel,need:'Contract fixture need',rationale:'Contract fixture rationale',customer_benefit:'Review suitability before offering.',why_now:'Snapshot analysis',evidence,alternatives:['No contact'],missing_data:['Tariff eligibility']};
    if(body.model==='invalid-product')result={...result,action:'offer',product_id:'P-INVENTED',channel:'email'};
  }
  res.writeHead(200,{'Content-Type':'application/json'});
  res.end(JSON.stringify({choices:[{finish_reason:'stop',message:{role:'assistant',content:body.model==='malformed'?'not-json':JSON.stringify(result)}}],usage:{prompt_tokens:10,completion_tokens:10,total_tokens:20}}));
}).listen(process.env.PORT||4901);
