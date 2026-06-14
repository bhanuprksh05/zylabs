import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Plus, Search, Trash2, Play, RefreshCw, AlertCircle, CheckCircle2,
  Clock, Sparkles, ExternalLink, Send, FileText, Layers, TrendingUp,
  Activity, AlertTriangle, Menu, X, MessageSquare, Building2, Calendar,
  ChevronRight, Globe, Zap, Info, ArrowLeft
} from 'lucide-react';
import { api } from './api';
import { HEALTH_CHECK_URL } from './config';

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────
const WORKFLOW_NODES = [
  { id: 'planner',             label: 'Research Planner',         desc: 'Analyses objective & builds research strategy' },
  { id: 'competitor_research', label: 'Competitor Intelligence',   desc: 'Identifies & profiles key market competitors' },
  { id: 'web_research',        label: 'Web Scraper & Search',      desc: 'Gathers Tavily results & scrapes website' },
  { id: 'summarize_content',   label: 'Content Synthesizer',       desc: 'Compresses raw web data into focused facts' },
  { id: 'structured_insights', label: 'Structured Fact Extractor', desc: 'Extracts leadership, tech stack & news' },
  { id: 'analyze',             label: 'Deep Business Analyzer',    desc: 'Synthesises pain points & discovery strategy' },
  { id: 'quality_check',       label: 'Quality Assurance Review',  desc: 'Validates completeness against threshold' },
  { id: 'generate_report',     label: 'Briefing Generator',        desc: 'Assembles the final structured report' },
];

const REPORT_TABS = [
  { id: 'overview',  label: 'Overview',  icon: FileText    },
  { id: 'products',  label: 'Products',  icon: Layers      },
  { id: 'signals',   label: 'Signals',   icon: TrendingUp  },
  { id: 'outreach',  label: 'Outreach',  icon: Zap         },
  { id: 'sources',   label: 'Gaps',      icon: Info        },
];

// ─────────────────────────────────────────────────────────────────────────────
// Small helper components
// ─────────────────────────────────────────────────────────────────────────────
function StatusPill({ status, className = '' }) {
  const MAP = {
    completed: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    running:   'bg-blue-500/10   text-blue-400   border-blue-500/30   animate-pulse',
    failed:    'bg-rose-500/10   text-rose-400   border-rose-500/30',
    pending:   'bg-amber-500/10  text-amber-400  border-amber-500/30',
  };
  return (
    <span className={`px-2 py-0.5 rounded-full border text-[10px] font-bold uppercase tracking-wider ${MAP[status] ?? 'bg-slate-800 text-slate-400 border-slate-700'} ${className}`}>
      {status}
    </span>
  );
}

function NodeBadge({ status }) {
  if (status === 'completed') return (
    <span className="flex items-center gap-1 text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
      <CheckCircle2 size={10} /> Done
    </span>
  );
  if (status === 'running') return (
    <span className="flex items-center gap-1 text-[10px] font-semibold text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-full border border-blue-500/20 animate-pulse">
      <Activity size={10} className="animate-spin" /> Running
    </span>
  );
  if (status === 'failed') return (
    <span className="flex items-center gap-1 text-[10px] font-semibold text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded-full border border-rose-500/20">
      <AlertCircle size={10} /> Failed
    </span>
  );
  return (
    <span className="flex items-center gap-1 text-[10px] font-semibold text-slate-500 bg-slate-800/60 px-2 py-0.5 rounded-full border border-slate-700">
      <Clock size={10} /> Pending
    </span>
  );
}

function Input({ icon: Icon, ...props }) {
  return (
    <div className="relative">
      {Icon && <Icon className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" size={14} />}
      <input
        {...props}
        className={`w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-indigo-500 rounded-xl ${Icon ? 'pl-9' : 'pl-4'} pr-4 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500/30 transition-all`}
      />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main App
// ─────────────────────────────────────────────────────────────────────────────
export default function App() {
  // ── Core data ──
  const [sessions, setSessions]           = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [activeSession, setActiveSession] = useState(null);
  const [searchQuery, setSearchQuery]     = useState('');

  // ── Form ──
  const [companyName, setCompanyName] = useState('');
  const [website, setWebsite]         = useState('');
  const [objective, setObjective]     = useState('');

  // ── Workflow ──
  const [nodeStatuses, setNodeStatuses]         = useState({});
  const [workflowError, setWorkflowError]       = useState(null);

  // ── Chat ──
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput]       = useState('');
  const [isChatSending, setIsChatSending] = useState(false);

  // ── UI ──
  const [sidebarOpen, setSidebarOpen]   = useState(false); // closed by default on mobile
  const [activeTab, setActiveTab]       = useState('overview');
  const [mobileView, setMobileView]     = useState('report'); // 'report' | 'chat'
  const [loading, setLoading]           = useState(false);
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [globalError, setGlobalError]   = useState(null);
  const [backendHealth, setBackendHealth] = useState(true);

  const pollingRef  = useRef(null);
  const chatBottom  = useRef(null);
  const tabBarRef   = useRef(null);

  // Close sidebar on desktop breakpoint change
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 768px)');
    const handler = (e) => { if (e.matches) setSidebarOpen(false); };
    mq.addEventListener('change', handler);
    // On desktop keep sidebar always visible via CSS, not state
    return () => mq.removeEventListener('change', handler);
  }, []);

  // ── Lifecycle ──
  useEffect(() => { checkHealth(); fetchSessions(); }, []);

  useEffect(() => {
    if (activeSession && ['running', 'pending'].includes(activeSession.status)) {
      startPolling(activeSession.id);
    } else {
      stopPolling();
    }
    return stopPolling;
  // eslint-disable-next-line
  }, [activeSession?.status, activeSession?.id]);

  useEffect(() => {
    chatBottom.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, isChatSending]);

  // ── API helpers ──
  const checkHealth = async () => {
    try {
      const r = await fetch(HEALTH_CHECK_URL);
      setBackendHealth(r.ok);
    } catch { setBackendHealth(false); }
  };

  const fetchSessions = async () => {
    setLoading(true);
    try {
      const d = await api.getSessions();
      setSessions(d.items || []);
      setGlobalError(null);
    } catch (e) {
      setGlobalError(`Could not load sessions: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const selectSession = async (id) => {
    setActiveSessionId(id);
    setLoading(true);
    stopPolling();
    setWorkflowError(null);
    setNodeStatuses({});
    setChatMessages([]);
    setSidebarOpen(false); // close drawer on mobile after selection
    setMobileView('report');

    try {
      const s = await api.getSession(id);
      setActiveSession(s);
      if (s.status === 'completed') {
        const h = await api.getChatHistory(id);
        setChatMessages(h.messages || []);
      }
      if (s.status === 'failed') {
        const st = await api.getWorkflowStatus(id);
        setNodeStatuses(st.node_statuses || {});
        setWorkflowError(s.error_message || st.error_message || 'Workflow failed.');
      }
    } catch (e) {
      setGlobalError(`Failed to load session: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  // ── Polling (ref-based to avoid circular useCallback deps) ──
  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  // pollingRef is a stable ref — no deps needed
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startPolling = useCallback((id) => {
    // Clear any existing poll first
    if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }

    const tick = async () => {
      try {
        const st = await api.getWorkflowStatus(id);
        setNodeStatuses(st.node_statuses || {});
        setWorkflowError(st.error_message || null);
        if (st.status === 'completed' || st.status === 'failed') {
          if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
          const s = await api.getSession(id);
          setActiveSession(s);
          if (st.status === 'completed') {
            const h = await api.getChatHistory(id);
            setChatMessages(h.messages || []);
          }
          const list = await api.getSessions();
          setSessions(list.items || []);
        }
      } catch (e) { console.error('Poll error', e); }
    };
    tick();
    pollingRef.current = setInterval(tick, 2500);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Actions ──
  const handleCreate = async (e) => {
    e.preventDefault();
    setFormSubmitting(true);
    setGlobalError(null);
    try {
      const s = await api.createSession(companyName, website, objective);
      await api.runWorkflow(s.id);
      setCompanyName(''); setWebsite(''); setObjective('');
      await fetchSessions();
      selectSession(s.id);
    } catch (e) {
      setGlobalError(`Failed to start session: ${e.message}`);
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleResume = async () => {
    if (!activeSession) return;
    setLoading(true);
    try {
      await api.resumeWorkflow(activeSession.id);
      setActiveSession(p => ({ ...p, status: 'running' }));
      fetchSessions();
    } catch (e) {
      setGlobalError(`Resume failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRerun = async () => {
    if (!activeSession) return;
    if (!window.confirm('Re-run research? Existing report & chat will be overwritten.')) return;
    setLoading(true);
    setChatMessages([]);
    try {
      await api.runWorkflow(activeSession.id, true);
      setActiveSession(p => ({ ...p, status: 'running' }));
      fetchSessions();
    } catch (e) {
      setGlobalError(`Rerun failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    if (!window.confirm('Delete this research session?')) return;
    try {
      await api.deleteSession(id);
      if (activeSessionId === id) { setActiveSessionId(null); setActiveSession(null); stopPolling(); }
      fetchSessions();
    } catch (e) {
      setGlobalError(`Delete failed: ${e.message}`);
    }
  };

  const handleChat = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || !activeSession || isChatSending) return;
    const text = chatInput.trim();
    setChatInput('');
    setIsChatSending(true);
    const temp = { id: '__temp__', role: 'user', content: text, created_at: new Date().toISOString() };
    setChatMessages(p => [...p, temp]);
    try {
      const d = await api.sendChatMessage(activeSession.id, text);
      setChatMessages(p => [...p.filter(m => m.id !== '__temp__'), d.user_message, d.assistant_message]);
    } catch (e) {
      setGlobalError(`Chat error: ${e.message}`);
      setChatMessages(p => p.filter(m => m.id !== '__temp__'));
    } finally {
      setIsChatSending(false);
    }
  };

  const handleClearChat = async () => {
    if (!window.confirm('Clear all chat messages?')) return;
    try {
      await api.clearChatHistory(activeSession.id);
      setChatMessages([]);
    } catch (e) {
      setGlobalError(`Clear failed: ${e.message}`);
    }
  };

  const filteredSessions = sessions.filter(s =>
    s.company_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.objective.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // ─────────────────────────────────────────────────────────────────────────
  // Render helpers
  // ─────────────────────────────────────────────────────────────────────────
  const report = activeSession?.report;

  const renderSidebarContent = () => (
    <>
      {/* Logo */}
      <div className="px-4 pt-5 pb-4 border-b border-slate-800/60 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
            <Sparkles size={16} className="animate-pulse" />
          </div>
          <div>
            <h1 className="font-extrabold text-sm tracking-tight bg-gradient-to-r from-slate-100 via-indigo-200 to-indigo-400 bg-clip-text text-transparent">
              Research Copilot
            </h1>
            <span className="text-[10px] font-semibold tracking-wider text-slate-500 uppercase">LangGraph Agent</span>
          </div>
        </div>
        {/* Mobile close */}
        <button onClick={() => setSidebarOpen(false)} className="md:hidden p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-all">
          <X size={16} />
        </button>
      </div>

      {/* New Research Button */}
      <div className="p-3 border-b border-slate-800/40">
        <button
          onClick={() => { setActiveSessionId(null); setActiveSession(null); stopPolling(); setSidebarOpen(false); }}
          className="w-full py-2.5 px-4 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 active:scale-[0.98] text-white rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-indigo-950/40 border border-indigo-500/20 transition-all text-xs"
        >
          <Plus size={15} /> New Research
        </button>
      </div>

      {/* Search */}
      <div className="px-3 py-2 border-b border-slate-800/40">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" size={13} />
          <input
            type="text"
            placeholder="Search companies..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950/80 border border-slate-800 hover:border-slate-700 focus:border-indigo-500/50 rounded-xl pl-8 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none transition-all"
          />
        </div>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
        <p className="px-2 py-1 text-[10px] font-bold text-slate-500 uppercase tracking-widest">History</p>

        {loading && sessions.length === 0 ? (
          <div className="space-y-2 p-2">
            {[1,2,3].map(i => <div key={i} className="h-14 bg-slate-800/50 rounded-xl animate-pulse" />)}
          </div>
        ) : filteredSessions.length === 0 ? (
          <p className="text-center text-xs text-slate-600 italic py-6">
            {searchQuery ? 'No matching sessions' : 'No sessions yet'}
          </p>
        ) : filteredSessions.map(s => {
          const active = activeSessionId === s.id;
          return (
            <div
              key={s.id}
              onClick={() => selectSession(s.id)}
              className={`group relative p-3 rounded-xl cursor-pointer border transition-all ${
                active ? 'bg-indigo-950/25 border-indigo-500/30' : 'border-transparent hover:bg-slate-800/40 hover:border-slate-800/60'
              }`}
            >
              <div className="pr-7">
                <p className={`font-semibold text-xs truncate ${active ? 'text-indigo-300' : 'text-slate-200 group-hover:text-indigo-300'} transition-colors`}>
                  {s.company_name}
                </p>
                <p className="text-[11px] text-slate-500 truncate mt-0.5">{s.objective}</p>
              </div>
              <div className="flex items-center justify-between mt-1.5">
                <span className="text-[10px] text-slate-600 flex items-center gap-1">
                  <Calendar size={9} />
                  {new Date(s.created_at).toLocaleDateString(undefined, { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' })}
                </span>
                <StatusPill status={s.status} />
              </div>
              {/* Delete */}
              <button
                onClick={e => handleDelete(e, s.id)}
                className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 p-1 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-slate-800 transition-all"
              >
                <Trash2 size={11} />
              </button>
            </div>
          );
        })}
      </div>
    </>
  );

  // ─────────────────────────────────────────────────────────────────────────
  // Report tab content
  // ─────────────────────────────────────────────────────────────────────────
  const renderReportTab = () => {
    if (!report) return null;
    switch (activeTab) {
      case 'overview': return (
        <div className="space-y-5">
          <div className="bg-slate-900/40 border border-slate-800/40 p-5 rounded-2xl">
            <p className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider mb-2">Executive Summary</p>
            <p className="text-slate-200 text-sm leading-relaxed">{report.company_overview?.description || 'Not available.'}</p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {[
              ['Industry', report.company_overview?.industry],
              ['Size', report.company_overview?.size],
              ['Founded', report.company_overview?.founded],
              ['HQ', report.company_overview?.headquarters],
              ['Model', report.company_overview?.business_model],
            ].map(([k, v]) => (
              <div key={k} className="bg-slate-900/40 border border-slate-800/40 p-3 rounded-xl">
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wide block">{k}</span>
                <span className="text-xs font-semibold text-slate-200 block mt-0.5 truncate">{v || '—'}</span>
              </div>
            ))}
          </div>
          {report.target_customers?.length > 0 && (
            <div className="bg-slate-900/40 border border-slate-800/40 p-5 rounded-2xl">
              <p className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider mb-3">Target Customers</p>
              <div className="flex flex-wrap gap-2">
                {report.target_customers.map((c, i) => (
                  <span key={i} className="px-3 py-1.5 bg-slate-950 border border-slate-800 text-slate-300 rounded-xl text-xs font-medium flex items-center gap-1.5">
                    <ChevronRight size={10} className="text-indigo-400 flex-shrink-0" />{c}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      );

      case 'products': return (
        <div className="space-y-4">
          <p className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider">Products & Services</p>
          {report.products_services?.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {report.products_services.map((p, i) => (
                <div key={i} className="bg-slate-900/40 border border-slate-800/40 p-4 rounded-2xl relative overflow-hidden">
                  <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-indigo-500 to-indigo-700" />
                  <h4 className="font-bold text-sm text-slate-200 pl-3">{p.name}</h4>
                  <p className="text-slate-400 text-xs leading-relaxed mt-1 pl-3">{p.description}</p>
                </div>
              ))}
            </div>
          ) : <p className="text-slate-500 text-sm italic">No products identified.</p>}
        </div>
      );

      case 'signals': return (
        <div className="space-y-5">
          <div className="space-y-3">
            <p className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider">Business Signals</p>
            {report.business_signals?.length > 0 ? report.business_signals.map((s, i) => (
              <div key={i} className="bg-slate-900/40 border border-slate-800/40 p-4 rounded-xl flex flex-col sm:flex-row sm:items-start gap-3">
                <span className="self-start px-2.5 py-0.5 rounded-full border border-indigo-500/20 text-indigo-400 text-[10px] bg-indigo-500/5 font-bold flex-shrink-0">
                  {s.category || 'Signal'}
                </span>
                <div>
                  <p className="font-semibold text-xs text-slate-200">{s.signal}</p>
                  <p className="text-[11px] text-slate-400 mt-1"><strong>Why it matters:</strong> {s.significance}</p>
                </div>
              </div>
            )) : <p className="text-slate-500 text-sm italic">No signals tracked.</p>}
          </div>
          {report.risks_challenges?.length > 0 && (
            <div className="bg-slate-900/40 border border-slate-800/40 p-5 rounded-2xl space-y-3">
              <p className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider">Risks & Challenges</p>
              <ul className="space-y-2">
                {report.risks_challenges.map((r, i) => (
                  <li key={i} className="flex items-start gap-3 text-slate-300 text-sm">
                    <span className="p-1 rounded bg-rose-500/10 border border-rose-500/20 text-rose-400 flex-shrink-0 mt-0.5">
                      <AlertTriangle size={9} />
                    </span>
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      );

      case 'outreach': return (
        <div className="space-y-5">
          <div className="space-y-3">
            <p className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider">Outreach Strategies</p>
            {report.suggested_outreach_strategy?.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {report.suggested_outreach_strategy.map((s, i) => (
                  <div key={i} className="bg-slate-900/40 border border-slate-800/40 p-4 rounded-xl flex items-start gap-3">
                    <span className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex-shrink-0">
                      <Zap size={10} className="animate-pulse" />
                    </span>
                    <p className="text-slate-300 text-xs leading-relaxed">{s}</p>
                  </div>
                ))}
              </div>
            ) : <p className="text-slate-500 text-sm italic">No strategies suggested.</p>}
          </div>
          {report.suggested_discovery_questions?.length > 0 && (
            <div className="bg-slate-900/40 border border-slate-800/40 p-5 rounded-2xl space-y-3">
              <p className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider">Discovery Questions</p>
              <ul className="space-y-2.5">
                {report.suggested_discovery_questions.map((q, i) => (
                  <li key={i} className="flex items-start gap-3 bg-slate-950/40 border border-slate-850/60 p-3.5 rounded-xl">
                    <span className="font-bold text-indigo-400 text-xs flex-shrink-0">Q{i+1}.</span>
                    <span className="text-slate-200 text-xs leading-relaxed">{q}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      );

      case 'sources': return (
        <div className="space-y-5">
          {report.unknowns?.length > 0 && (
            <div className="bg-slate-900/40 border border-slate-800/40 p-5 rounded-2xl space-y-2">
              <p className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider">Information Gaps</p>
              <ul className="space-y-1.5">
                {report.unknowns.map((g, i) => (
                  <li key={i} className="text-slate-400 text-xs flex items-start gap-2">
                    <span className="text-slate-600 mt-0.5">•</span>{g}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="space-y-3">
            <p className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider">Referenced Sources</p>
            {report.sources?.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {report.sources.map((src, i) => (
                  <div key={i} className="bg-slate-900/40 border border-slate-800/40 p-3.5 rounded-xl flex items-center justify-between gap-3 min-w-0">
                    <div className="min-w-0">
                      <p className="font-semibold text-xs text-slate-300 truncate">{src.title}</p>
                      {src.url && <p className="text-[10px] text-slate-500 truncate mt-0.5">{src.url}</p>}
                    </div>
                    {src.url && (
                      <a href={src.url} target="_blank" rel="noopener noreferrer"
                        className="p-2 bg-slate-950 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-indigo-400 rounded-lg transition-colors flex-shrink-0">
                        <ExternalLink size={11} />
                      </a>
                    )}
                  </div>
                ))}
              </div>
            ) : <p className="text-slate-500 text-sm italic">No sources listed.</p>}
          </div>
        </div>
      );

      default: return null;
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // JSX
  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-[100dvh] w-screen bg-slate-950 text-slate-100 text-sm overflow-hidden">

      {/* ── Backend offline banner ── */}
      {!backendHealth && (
        <div className="fixed inset-x-0 top-0 z-50 bg-rose-950/95 border-b border-rose-800 text-rose-200 px-4 py-2.5 flex items-center justify-between gap-3 text-xs backdrop-blur-sm">
          <span className="flex items-center gap-2 min-w-0">
            <AlertTriangle size={14} className="text-rose-400 animate-bounce flex-shrink-0" />
            <span className="truncate"><strong>Backend offline</strong> — make sure uvicorn is running on :8000</span>
          </span>
          <button onClick={checkHealth} className="shrink-0 bg-rose-900/60 hover:bg-rose-900 border border-rose-700 px-2.5 py-1 rounded-lg flex items-center gap-1 transition-all">
            <RefreshCw size={11} /> Retry
          </button>
        </div>
      )}

      {/* ── Toast error ── */}
      {globalError && (
        <div className={`fixed z-50 left-1/2 -translate-x-1/2 sm:left-auto sm:translate-x-0 sm:right-4 bottom-4 w-[calc(100vw-2rem)] sm:w-auto sm:max-w-sm bg-slate-900 border border-rose-500/30 shadow-2xl rounded-2xl p-4 flex items-start gap-3 ${!backendHealth ? 'mb-8' : ''}`}>
          <AlertCircle size={18} className="text-rose-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="font-bold text-[10px] text-rose-400 uppercase tracking-wider">Error</p>
            <p className="text-xs text-slate-300 mt-0.5 break-words">{globalError}</p>
          </div>
          <button onClick={() => setGlobalError(null)} className="text-slate-500 hover:text-slate-200 transition-colors flex-shrink-0">
            <X size={15} />
          </button>
        </div>
      )}

      {/* ── Mobile sidebar backdrop ── */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── SIDEBAR ── */}
      {/*
        Mobile: fixed slide-over drawer (z-40)
        Desktop (md+): static left column, always visible
      */}
      <aside className={`
        fixed md:static inset-y-0 left-0 z-40
        w-72 flex-shrink-0
        bg-slate-900/95 md:bg-slate-900/60 border-r border-slate-800/80
        flex flex-col h-full
        transition-transform duration-300 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        md:translate-x-0
        ${!backendHealth ? 'pt-9' : ''}
      `}>
        {renderSidebarContent()}
      </aside>

      {/* ── MAIN AREA ── */}
      <main className={`
        flex-1 flex flex-col h-full overflow-hidden bg-slate-950 min-w-0
        ${!backendHealth ? 'pt-9' : ''}
      `}>

        {/* ── Mobile top bar (hidden on desktop since sidebar is visible) ── */}
        <div className="md:hidden flex items-center gap-3 px-4 py-3 border-b border-slate-900 bg-slate-900/40 backdrop-blur-sm sticky top-0 z-20">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 rounded-xl bg-slate-800 border border-slate-700 text-slate-300 hover:text-slate-100 transition-all"
          >
            <Menu size={16} />
          </button>

          {activeSession ? (
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <button onClick={() => { setActiveSessionId(null); setActiveSession(null); stopPolling(); }} className="text-slate-500 hover:text-slate-200 transition-colors">
                  <ArrowLeft size={14} />
                </button>
                <h2 className="font-bold text-sm text-slate-100 truncate">{activeSession.company_name}</h2>
                <StatusPill status={activeSession.status} />
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                <Sparkles size={13} className="animate-pulse" />
              </div>
              <span className="font-extrabold text-sm bg-gradient-to-r from-slate-100 to-indigo-400 bg-clip-text text-transparent">
                Research Copilot
              </span>
            </div>
          )}

          {/* Mobile view toggle (report vs chat) when completed */}
          {activeSession?.status === 'completed' && (
            <button
              onClick={() => setMobileView(v => v === 'report' ? 'chat' : 'report')}
              className="p-2 rounded-xl bg-slate-800 border border-slate-700 text-slate-300 hover:text-indigo-400 transition-all flex-shrink-0"
            >
              {mobileView === 'report' ? <MessageSquare size={16} /> : <FileText size={16} />}
            </button>
          )}
        </div>

        {/* ── Create form (no active session) ── */}
        {!activeSessionId && (
          <div className="flex-1 overflow-y-auto flex items-start sm:items-center justify-center p-4 sm:p-8">
            <div className="w-full max-w-lg bg-slate-900/40 border border-slate-800/60 p-6 sm:p-8 rounded-2xl shadow-2xl backdrop-blur-md space-y-6">
              <div className="text-center space-y-2">
                <div className="inline-flex p-3 rounded-2xl bg-indigo-500/15 text-indigo-400 border border-indigo-500/20">
                  <Sparkles size={24} className="animate-pulse" />
                </div>
                <h2 className="text-lg sm:text-xl font-bold tracking-tight text-slate-100">
                  Start Company Intelligence Session
                </h2>
                <p className="text-slate-400 text-xs leading-relaxed max-w-sm mx-auto">
                  Provide a company name, website, and research target to launch the AI research crew.
                </p>
              </div>

              <form onSubmit={handleCreate} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Company Name</label>
                    <Input icon={Building2} type="text" placeholder="e.g. Stripe" value={companyName} onChange={e => setCompanyName(e.target.value)} required />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Website URL</label>
                    <Input icon={Globe} type="url" placeholder="https://stripe.com" value={website} onChange={e => setWebsite(e.target.value)} required />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Research Objective</label>
                  <textarea
                    placeholder="e.g. Preparing for a discovery meeting to pitch our security product to their CTO..."
                    rows={3}
                    value={objective}
                    onChange={e => setObjective(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-indigo-500 rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500/30 transition-all resize-none"
                    required
                  />
                </div>

                <button
                  type="submit"
                  disabled={formSubmitting || !backendHealth}
                  className="w-full py-3 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 active:scale-[0.99] disabled:opacity-40 disabled:pointer-events-none text-white rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-indigo-950/50 border border-indigo-500/20 transition-all"
                >
                  {formSubmitting ? (
                    <><Activity size={14} className="animate-spin" /> Starting AI Agents…</>
                  ) : (
                    <><Sparkles size={14} className="text-indigo-200 animate-pulse" /> Launch AI Research Crew</>
                  )}
                </button>
              </form>
            </div>
          </div>
        )}

        {/* ── Session detail view ── */}
        {activeSession && (
          <div className="flex-1 flex flex-col overflow-hidden">

            {/* Desktop header (md+) */}
            <div className="hidden md:flex px-6 py-3.5 border-b border-slate-900 bg-slate-900/20 items-center justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h2 className="font-extrabold text-base text-slate-100 truncate">{activeSession.company_name}</h2>
                  <a href={activeSession.website} target="_blank" rel="noopener noreferrer" className="text-slate-500 hover:text-indigo-400 transition-colors flex-shrink-0">
                    <ExternalLink size={12} />
                  </a>
                  <StatusPill status={activeSession.status} />
                </div>
                <p className="text-[11px] text-slate-400 truncate mt-0.5">
                  <strong>Objective:</strong> {activeSession.objective}
                </p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {activeSession.status === 'completed' && (
                  <button onClick={handleRerun} title="Rerun research" className="p-2 bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-400 hover:text-indigo-400 rounded-xl transition-all">
                    <RefreshCw size={13} />
                  </button>
                )}
              </div>
            </div>

            {/* ── Workflow progress view (not completed) ── */}
            {activeSession.status !== 'completed' && (
              <div className="flex-1 overflow-y-auto p-4 sm:p-8 flex flex-col items-center gap-6">
                {/* Status header */}
                <div className="w-full max-w-2xl text-center space-y-2 pt-2">
                  {activeSession.status === 'failed' ? (
                    <div className="inline-flex p-3 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400">
                      <AlertTriangle size={22} className="animate-bounce" />
                    </div>
                  ) : (
                    <div className="inline-flex p-3 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                      <Activity size={22} className="animate-spin" />
                    </div>
                  )}
                  <h3 className="text-base font-bold text-slate-100">
                    {activeSession.status === 'failed' ? 'Workflow Interrupted' : 'LangGraph Workflow in Progress'}
                  </h3>
                  <p className="text-slate-400 text-xs max-w-sm mx-auto">
                    {activeSession.status === 'failed'
                      ? 'Research failed. Resume from the last checkpoint or start fresh.'
                      : 'Running an 8-node LLM research graph. Progress updates every 2.5 s.'}
                  </p>

                  {workflowError && (
                    <div className="bg-rose-950/20 border border-rose-800/40 p-4 rounded-xl text-left text-xs text-rose-200 mt-2 overflow-x-auto">
                      <div className="font-bold flex items-center gap-1 text-rose-400 mb-1.5">
                        <AlertCircle size={13} /> Error Report
                      </div>
                      <pre className="font-mono text-[10px] whitespace-pre-wrap">{workflowError}</pre>
                    </div>
                  )}

                  {activeSession.status === 'failed' && (
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-3">
                      <button onClick={handleResume} className="w-full sm:w-auto py-2.5 px-5 bg-indigo-600 hover:bg-indigo-500 active:scale-[0.98] text-white font-bold rounded-xl text-xs flex items-center justify-center gap-2 shadow-lg shadow-indigo-950/30 transition-all border border-indigo-500/20">
                        <Play size={13} /> Resume from Checkpoint
                      </button>
                      <button onClick={handleRerun} className="w-full sm:w-auto py-2.5 px-5 bg-slate-900 border border-slate-800 hover:border-slate-700 active:scale-[0.98] text-slate-300 font-bold rounded-xl text-xs flex items-center justify-center gap-2 transition-all">
                        <RefreshCw size={13} /> Fresh Run
                      </button>
                    </div>
                  )}
                </div>

                {/* Node grid */}
                <div className="w-full max-w-2xl grid grid-cols-1 sm:grid-cols-2 gap-3 bg-slate-900/30 border border-slate-800/40 p-4 rounded-2xl">
                  {WORKFLOW_NODES.map((node, idx) => {
                    const st = nodeStatuses[node.id] || 'pending';
                    return (
                      <div key={node.id} className={`p-3 rounded-xl border flex items-center gap-3 transition-all ${
                        st === 'running'   ? 'bg-indigo-950/10 border-indigo-500/35 ring-1 ring-indigo-500/20' :
                        st === 'completed' ? 'bg-slate-900/30 border-slate-800/60' :
                        st === 'failed'    ? 'bg-rose-950/10 border-rose-500/30' :
                                             'bg-transparent border-slate-900'
                      }`}>
                        <div className={`h-6 w-6 rounded-lg text-xs font-extrabold flex items-center justify-center flex-shrink-0 border ${
                          st === 'completed' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                          st === 'running'   ? 'bg-blue-500/20 text-blue-400 border-blue-400/30 animate-pulse' :
                          st === 'failed'    ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' :
                                              'bg-slate-950 text-slate-600 border-slate-800'
                        }`}>
                          {idx + 1}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className={`font-semibold text-xs truncate ${
                            st === 'running' ? 'text-indigo-300' : st === 'completed' ? 'text-slate-300' : st === 'failed' ? 'text-rose-300' : 'text-slate-500'
                          }`}>{node.label}</p>
                          <p className="text-[10px] text-slate-500 mt-0.5 truncate">{node.desc}</p>
                        </div>
                        <div className="flex-shrink-0">
                          <NodeBadge status={st} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── Completed: report + chat ── */}
            {activeSession.status === 'completed' && report && (
              <div className="flex-1 flex overflow-hidden">

                {/* ── Report panel ── */}
                {/*
                  Mobile: full width, hidden when mobileView === 'chat'
                  Desktop: flex-1, always visible
                */}
                <div className={`
                  flex-col overflow-hidden border-r border-slate-900
                  ${mobileView === 'report' ? 'flex' : 'hidden'}
                  md:flex flex-1 min-w-0
                `}>
                  {/* Tab bar – horizontally scrollable */}
                  <div ref={tabBarRef} className="flex overflow-x-auto border-b border-slate-900 bg-slate-900/10 px-2 sm:px-4 shrink-0 scrollbar-none" style={{ scrollbarWidth: 'none' }}>
                    {REPORT_TABS.map(tab => {
                      const Icon = tab.icon;
                      return (
                        <button
                          key={tab.id}
                          onClick={() => setActiveTab(tab.id)}
                          className={`flex items-center gap-1.5 py-3 px-3 sm:px-4 border-b-2 whitespace-nowrap font-semibold text-xs transition-all flex-shrink-0 ${
                            activeTab === tab.id
                              ? 'border-indigo-500 text-indigo-400'
                              : 'border-transparent text-slate-500 hover:text-slate-200'
                          }`}
                        >
                          <Icon size={12} />{tab.label}
                        </button>
                      );
                    })}
                  </div>

                  {/* Tab content */}
                  <div className="flex-1 overflow-y-auto p-4 sm:p-6">
                    {renderReportTab()}
                  </div>
                </div>

                {/* ── Chat panel ── */}
                {/*
                  Mobile: full width, hidden when mobileView === 'report'
                  Desktop: fixed 340px sidebar
                */}
                <div className={`
                  flex-col bg-slate-900/35
                  ${mobileView === 'chat' ? 'flex' : 'hidden'}
                  md:flex w-full md:w-80 lg:w-96 flex-shrink-0
                `}>
                  {/* Chat header */}
                  <div className="px-4 py-3 border-b border-slate-900 flex items-center justify-between bg-slate-900/20 shrink-0">
                    <div className="flex items-center gap-2">
                      <MessageSquare size={13} className="text-indigo-400" />
                      <span className="font-bold text-xs text-slate-200">Follow-Up Chat</span>
                    </div>
                    {chatMessages.length > 0 && (
                      <button onClick={handleClearChat} title="Clear chat" className="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-slate-800 rounded-lg transition-all">
                        <Trash2 size={12} />
                      </button>
                    )}
                  </div>

                  {/* Messages */}
                  <div className="flex-1 overflow-y-auto p-4 space-y-3">
                    {chatMessages.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-center px-6 gap-3">
                        <div className="p-3 bg-indigo-500/5 rounded-full border border-indigo-500/10 text-indigo-400">
                          <MessageSquare size={18} className="animate-pulse" />
                        </div>
                        <p className="text-xs text-slate-500 leading-relaxed">
                          Ask follow-up questions about {activeSession.company_name}'s team, products, or strategy.
                        </p>
                      </div>
                    ) : chatMessages.map((msg, i) => {
                      const isUser = msg.role === 'user';
                      return (
                        <div key={msg.id || i} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                          <div className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed ${
                            isUser ? 'bg-indigo-600 text-white rounded-br-sm shadow-md shadow-indigo-950/20' : 'bg-slate-800/80 border border-slate-700/50 text-slate-200 rounded-bl-sm'
                          }`}>
                            <p className="whitespace-pre-wrap">{msg.content}</p>
                            <span className="text-[9px] text-slate-500/70 block text-right mt-1 select-none">
                              {new Date(msg.created_at).toLocaleTimeString(undefined, { hour:'2-digit', minute:'2-digit' })}
                            </span>
                          </div>
                        </div>
                      );
                    })}

                    {isChatSending && (
                      <div className="flex justify-start">
                        <div className="bg-slate-800/80 border border-slate-700/50 rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-1.5">
                          <div className="h-1.5 w-1.5 rounded-full bg-slate-400 dot-bounce-1" />
                          <div className="h-1.5 w-1.5 rounded-full bg-slate-400 dot-bounce-2" />
                          <div className="h-1.5 w-1.5 rounded-full bg-slate-400 dot-bounce-3" />
                        </div>
                      </div>
                    )}

                    <div ref={chatBottom} />
                  </div>

                  {/* Input */}
                  <form onSubmit={handleChat} className="p-3 border-t border-slate-900 bg-slate-900/10 flex items-center gap-2 shrink-0">
                    <input
                      type="text"
                      placeholder="Ask a question…"
                      value={chatInput}
                      onChange={e => setChatInput(e.target.value)}
                      disabled={isChatSending}
                      className="flex-1 bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-xs text-slate-200 placeholder-slate-600 focus:outline-none transition-all min-w-0"
                    />
                    <button
                      type="submit"
                      disabled={!chatInput.trim() || isChatSending}
                      className="p-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:pointer-events-none text-white rounded-xl transition-all flex-shrink-0"
                    >
                      <Send size={13} />
                    </button>
                  </form>
                </div>

              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
