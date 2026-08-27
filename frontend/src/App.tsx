import { FormEvent, useState } from "react";
import { ask, ChatResponse } from "./api";
import "./styles.css";

export function App() {
  const [question,setQuestion]=useState("");
  const [result,setResult]=useState<ChatResponse|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  async function submit(event:FormEvent){event.preventDefault();if(!question.trim()||loading)return;setLoading(true);setError("");try{setResult(await ask(question.trim()));}catch(reason){setError(reason instanceof Error?reason.message:"Request failed");}finally{setLoading(false);}}
  return <main>
    <header><div className="mark" aria-hidden="true">A</div><div><p className="eyebrow">OPEN-SOURCE STARTER</p><h1>Build an answer agent from knowledge you control.</h1><p className="intro">Add Markdown documents, choose an OpenAI-compatible provider—or run the local extractive mode—and ship a transparent, grounded Q&amp;A experience.</p></div></header>
    <form onSubmit={submit}><label htmlFor="question">Ask the example knowledge base</label><div className="ask-row"><textarea id="question" value={question} onChange={event=>setQuestion(event.target.value)} placeholder="How does the example agent plan a project?" maxLength={8000} rows={4}/><button disabled={!question.trim()||loading} type="submit">{loading?"Searching…":"Ask"}</button></div></form>
    {error&&<p role="alert" className="error">{error}</p>}
    {result&&<section className="answer" aria-live="polite"><div className="answer-heading"><h2>Answer</h2><span>{result.mode}</span></div><p>{result.answer}</p><h3>Grounding sources</h3><ul>{result.sources.map(source=><li key={`${source.path}-${source.excerpt}`}><strong>{source.title}</strong> <code>{source.path}</code><p>{source.excerpt}</p></li>)}</ul></section>}
    <footer>Prompts are untrusted input. Review your documents before publishing and never commit secrets.</footer>
  </main>;
}
