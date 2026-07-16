import { useEffect, useRef, useState } from "react";
import { ChatInput } from "./ChatInput";
import { ChatMessage } from "./ChatMessage";
import {
  createConversation,
  listConversationMessages,
  sendConductorMessage,
} from "../../api/conductor";
import { ensureProject } from "../../api/client";
import { apiGet, type Envelope } from "../../api/client";
import { connectShareWs, type AgentEvent, type ShareWsHandle } from "../../api/shareWs";
import { useBoardStore } from "../../store/useBoardStore";
import type { Card } from "../../types/card";
import type { Conversation, Message as ConvMessage } from "../../types/conductor";

/**
 * ChatPanel — Orquestração Conversacional (F-023 Conductor).
 *
 * Cria uma conversa atrelada ao projeto padrão e conduz a ideia pelo pipeline
 * de agentes via mensagens. Após cada turno, sincroniza o Card afetado no
 * useBoardStore (para o Kanban refletir o avanço quando o usuário alterna de
 * view — Plano F-023 §5), buscando o card atualizado em GET /cards/{id}.
 */

async function fetchCard(cardId: string): Promise<Card | null> {
  try {
    const r = await apiGet<Envelope<Card>>(`/cards/${cardId}`);
    return r.data;
  } catch {
    return null;
  }
}

export function ChatPanel() {
  const [conv, setConv] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ConvMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [awaitingUser, setAwaitingUser] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  // Streaming em tempo real (abordagem híbrida): status dos agentes + narrative
  // acumulada em chunks via WebSocket, enquanto o POST síncrono processa.
  const [agentStatuses, setAgentStatuses] = useState<Record<string, "start" | "done">>({});
  const [liveNarrative, setLiveNarrative] = useState<string>("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const replaceCard = useBoardStore((s) => s.replaceCard);
  const setCards = useBoardStore((s) => s.setCards);
  const cards = useBoardStore((s) => s.cards);

  // Inicializa a conversa no projeto padrão. Reusa a conversa existente se já
  // houver uma para este projeto (evita duplicar a cada montagem do painel).
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const pid = await ensureProject();
        if (!active) return;
        setProjectId(pid);
        const conv = await createConversation({ project_id: pid });
        if (!active) return;
        setConv(conv);
        const hist = await listConversationMessages(conv.id);
        if (!active) return;
        setMessages(hist.messages);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "falha ao iniciar");
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  // Tempo real: abre a conexão WebSocket de compartilhamento para o projeto e
  // aplica as mudanças de card no store (o Kanban reflete o avanço disparado
  // pelo Conductor sem refresh manual — Plano F-023 §5). Também consome os
  // eventos agent.status/agent.chunk para exibir o progresso do turno em
  // tempo real (abordagem híbrida: POST síncrono + streaming de status).
  useEffect(() => {
    if (!projectId) return;
    const handle: ShareWsHandle = connectShareWs(projectId, {
      conversationId: conv?.id,
      onAgentEvent: (e: AgentEvent) => {
        if (e.type === "agent.status" && e.payload.agent) {
          const agent = e.payload.agent;
          const status = e.payload.status === "done" ? "done" : "start";
          setAgentStatuses((prev) => ({ ...prev, [agent]: status }));
        } else if (e.type === "agent.chunk" && e.payload.text) {
          setLiveNarrative((prev) => prev + e.payload.text);
        } else if (e.type === "agent.turn_done") {
          // O POST já devolveu o estado final; limpa o streaming ao concluir.
          setAgentStatuses({});
          setLiveNarrative("");
        }
      },
    });
    return () => handle.close();
  }, [projectId, conv?.id]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, busy]);

  const syncCard = async (cardId: string | null) => {
    if (!cardId) return;
    const card = await fetchCard(cardId);
    if (!card) return;
    const exists = cards.some((c) => c.id === card.id);
    if (exists) replaceCard(card);
    else setCards([...cards, card]);
  };

  const handleSend = async (text: string) => {
    if (!conv || busy) return;
    setBusy(true);
    setError(null);
    setAgentStatuses({});
    setLiveNarrative("");
    const userMsg: ConvMessage = {
      id: `local-${Date.now()}`,
      conversation_id: conv.id,
      role: "user",
      content: text,
      tool_name: null,
      tool_input: null,
      tool_output: null,
    };
    setMessages((m) => [...m, userMsg]);
    try {
      const turn = await sendConductorMessage(conv.id, text);
      // Reconstrói as mensagens do turno a partir da resposta do backend:
      // uma Message(role=tool) por tool_call + a Message(role=conductor).
      const newOnes: ConvMessage[] = [];
      for (const tc of turn.tool_calls) {
        newOnes.push({
          id: `tool-${tc.tool}-${Date.now()}-${Math.random()}`,
          conversation_id: conv.id,
          role: "tool",
          content: "",
          tool_name: tc.tool,
          tool_input: tc.input,
          tool_output: tc.output,
        });
      }
      newOnes.push({
        id: `conductor-${Date.now()}`,
        conversation_id: conv.id,
        role: "conductor",
        content: turn.conductor_reply,
        tool_name: null,
        tool_input: null,
        tool_output: null,
      });
      setMessages((m) => [...m, ...newOnes]);
      setAwaitingUser(turn.awaiting_user);
      if (turn.card_id) {
        setConv({ ...conv, card_id: turn.card_id });
        await syncCard(turn.card_id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "falha ao enviar");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
        <div>
          <h2 className="text-[15px] font-bold leading-tight">Conductor</h2>
          <p className="text-[12px] text-[var(--muted)]">
            Orquestração conversacional do pipeline de agentes
          </p>
        </div>
        {awaitingUser && (
          <span className="rounded-full border border-[var(--accent-soft)] bg-[var(--accent-soft)] px-2.5 py-1 text-[11.5px] font-medium text-[var(--accent-text)]">
            Aguardando você
          </span>
        )}
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && !busy && (
          <div className="mt-10 text-center text-[13px] text-[var(--muted)]">
            Converse com o Conductor para criar e evoluir sua ideia. Ex.:
            <br />
            <span className="text-[var(--text-2)]">
              “quero criar um app de caronas pra faculdade”
            </span>
          </div>
        )}
        {messages.map((m) => (
          <ChatMessage key={m.id} msg={m} />
        ))}
        {busy && (
          <div className="flex justify-start">
            <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-[var(--border)] bg-[var(--surface)] px-3.5 py-2.5 text-[13px]">
              <div className="mb-1.5 text-[12px] font-medium text-[var(--muted)]">
                Conductor está trabalhando…
              </div>
              {Object.keys(agentStatuses).length > 0 && (
                <ul className="mb-2 space-y-1">
                  {Object.entries(agentStatuses).map(([agent, status]) => (
                    <li
                      key={agent}
                      className="flex items-center gap-2 text-[12.5px]"
                    >
                      <span
                        className={
                          status === "done"
                            ? "text-[var(--accent-text)]"
                            : "text-[var(--muted)] animate-pulse"
                        }
                      >
                        {status === "done" ? "✓" : "•"}
                      </span>
                      <span className="capitalize">{agent.replace(/_/g, " ")}</span>
                      <span className="text-[11px] text-[var(--muted)]">
                        {status === "done" ? "concluído" : "em andamento…"}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {liveNarrative && (
                <div className="whitespace-pre-wrap text-[13px] text-[var(--text-2)]">
                  {liveNarrative}
                  <span className="ml-0.5 inline-block animate-pulse">▍</span>
                </div>
              )}
            </div>
          </div>
        )}
        {error && (
          <div
            role="alert"
            className="rounded-[10px] border border-red-300 bg-red-50 px-3 py-2 text-[12.5px] text-red-700"
          >
            Erro: {error}
          </div>
        )}
      </div>

      <ChatInput onSend={handleSend} disabled={busy || !conv} awaitingUser={awaitingUser} />
    </div>
  );
}
