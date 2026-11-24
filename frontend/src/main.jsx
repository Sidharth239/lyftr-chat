import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

const BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const freshId = () => `s-${crypto.randomUUID()}`;
const suggestions = ['Explain response caching in two sentences.', 'What is the capital of France?', 'Give me a fun fact about space.'];
const modes = [ ['','Normal requests'], ['key_1=429','Key 1 — rate limit (429)'], ['key_1=500','Key 1 — server error (500)'], ['*=429','All keys — rate limit (429)'] ];
async function request(path, options) {
  const res = await fetch(BASE + path, options);
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data?.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(x => x.msg).join('; ') : `Request failed (${res.status})`);
  }
  if (!data) throw new Error('The server returned an invalid response.');
  return data;
}
function Metadata({m}) {
  if (!m) return null;
  return <div className="metadata">
    <div className="metric"><span>Source</span><strong className={'source '+(m.resolution_source==='LLM_CACHE'?'cache':'live')} data-testid="meta-source">{m.resolution_source}</strong></div>
    <div className="metric model"><span>Model</span><strong data-testid="meta-model">{m.model}</strong></div>
    <div className="metric"><span>Latency</span><strong data-testid="meta-latency">{m.latency_ms} ms</strong></div>
    <div className="metric"><span>Input tokens</span><strong data-testid="meta-input-tokens">{m.input_tokens}</strong></div>
    <div className="metric"><span>Output tokens</span><strong data-testid="meta-output-tokens">{m.output_tokens}</strong></div>
    <div className="metric"><span>Key / fallback attempts</span><strong>{m.key_id ?? 'None'} · {m.fallback_attempts}</strong></div>
  </div>;
}
function App(){
  const [session,setSession]=useState(freshId), [messages,setMessages]=useState([]), [input,setInput]=useState(''), [prompt,setPrompt]=useState(''), [simulation,setSimulation]=useState(''), [busy,setBusy]=useState(false), [health,setHealth]=useState(null), [history,setHistory]=useState(null), [copied,setCopied]=useState(false);
  const tail=useRef(null), field=useRef(null), inFlight=useRef(false);
  useEffect(()=>{let active=true; request('/health').then(x=>active&&setHealth(x)).catch(()=>active&&setHealth(false));return()=>{active=false}},[]);
  useEffect(()=>{tail.current?.scrollIntoView({behavior:'smooth',block:'end'})},[messages,busy]);
  const reset=()=>{setSession(freshId());setMessages([]);setInput('');setPrompt('');setSimulation('');setHistory(null);setCopied(false);field.current?.focus()};
  const send=async(e)=>{
    e.preventDefault(); const text=input.trim(); if(!text||inFlight.current) return;
    inFlight.current=true; setBusy(true); setInput('');setHistory(null);
    setMessages(old=>[...old,{role:'user',content:text}]);
    try {
      const headers={'Content-Type':'application/json'}; if(simulation)headers['X-Simulate-Failure']=simulation;
      const data=await request('/chat',{method:'POST',headers,body:JSON.stringify({session_id:session,message:text,...(prompt.trim()?{system_prompt:prompt.trim()}:{})})});
      setMessages(old=>[...old,{role:'assistant',content:data.reply,metadata:data.metadata}]);
    }catch(err){setMessages(old=>[...old,{role:'error',content:err.message==='all providers unavailable'?'All providers are unavailable. Try again or switch off failure simulation. This turn was not saved.':err.message}]);}
    finally{inFlight.current=false;setBusy(false);field.current?.focus()}
  };
  const showHistory=async()=>{try{setHistory(await request(`/sessions/${encodeURIComponent(session)}/messages`))}catch(err){setHistory({detail:err.message})}};
  const copyId=async()=>{try{await navigator.clipboard.writeText(session);setCopied(true)}catch{setCopied(false)}};
  return <div className="layout">
    <aside className="sidebar"><div className="brand"><div className="brand-mark">R<span>↗</span></div><div><b>Relay</b><small>RESILIENT AI CHAT</small></div></div>
      <button className="new" onClick={reset} disabled={busy}>＋ New chat</button>
      <div className="side-label">WORKSPACE</div><div className="current"><span>◉</span> Current conversation</div>
      <div className="side-label">SESSION SETTINGS</div>
      <label htmlFor="prompt">System prompt <small>optional</small></label><textarea id="prompt" data-testid="system-prompt-input" rows="3" disabled={busy} value={prompt} placeholder="You are a helpful assistant…" onChange={e=>setPrompt(e.target.value)}/>
      <label htmlFor="mode">Failure simulation</label><select id="mode" value={simulation} disabled={busy} onChange={e=>setSimulation(e.target.value)}>{modes.map(([v,t])=><option key={v} value={v}>{t}</option>)}</select><p className="hint">Sends X-Simulate-Failure on the next request while selected.</p>
      <div className="session"><div className="side-label">SESSION ID</div><code>{session}</code><button className="link" onClick={copyId}>{copied?'Copied':'Copy ID'}</button><button className="link" onClick={showHistory} disabled={busy}>View stored history ↗</button></div>
      <div className="side-foot"><span className={'dot '+(health?.status==='ok'?'green':'')}></span>{health?.status==='ok'?`${health.keys_configured} keys configured · cache on`:health===false?'Backend unavailable':'Checking backend…'}</div>
    </aside>
    <main><header><div><div className="eyebrow">LLM GATEWAY / CHAT</div><h1>Conversation</h1></div><a className="health" href={BASE+'/health'} target="_blank" rel="noreferrer"><span className={'dot '+(health?.status==='ok'?'green':'')}></span> API health ↗</a></header>
      <section className="thread" aria-label="Chat messages" aria-live="polite">
        {!messages.length&&<div className="welcome"><div className="hero-mark">✳</div><div className="eyebrow">A SMARTER ROUTE TO ANSWERS</div><h2>What can I help you with?</h2><p>Chat with an AI that remembers the conversation, switches keys when a provider fails, and reuses exact cached answers.</p><div className="suggestions">{suggestions.map(s=><button key={s} onClick={()=>{setInput(s);field.current?.focus()}}>{s}<span>↗</span></button>)}</div></div>}
        {messages.map((m,i)=>m.role==='assistant'?<article className="assistant" key={i} data-testid="assistant-message"><div className="msg-label"><span className="avatar">✳</span> Relay assistant</div><div className="reply">{m.content}</div><Metadata m={m.metadata}/></article>:m.role==='user'?<article className="user" key={i}><div className="user-bubble">{m.content}</div><small>You</small></article>:<div key={i} className="error" role="alert">⚠ {m.content}</div>)}
        {busy&&<div className="loading"><span className="spinner"/> Routing your request…</div>}<div ref={tail}/>
      </section>
      {history&&<section className="history"><div><b>SQLite session history</b><button className="link" onClick={()=>setHistory(null)}>Close ×</button></div><pre>{JSON.stringify(history,null,2)}</pre></section>}
      <footer><form className="composer" onSubmit={send}><textarea ref={field} data-testid="chat-input" aria-label="Message" value={input} maxLength={4000} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();send(e)}}} placeholder="Ask anything…" rows="2"/><button data-testid="send-button" aria-label="Send message" disabled={busy||!input.trim()} type="submit">↑</button></form><div className="footnote"><span>{simulation?'Simulation: '+simulation:'Enter to send · Shift+Enter for a new line'}</span><span>{input.length}/4000</span></div></footer>
    </main>
  </div>;
}
createRoot(document.getElementById('root')).render(<App/>);
