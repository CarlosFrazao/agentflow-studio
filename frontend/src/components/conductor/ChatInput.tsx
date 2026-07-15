import { useState, type KeyboardEvent } from "react";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
  awaitingUser?: boolean;
}

const SUGGESTIONS = [
  "quero criar um app de caronas pra faculdade",
  "seguir com a pesquisa",
  "fazer o plano",
  "revisar",
  "gerar o código",
];

export function ChatInput({ onSend, disabled, awaitingUser }: ChatInputProps) {
  const [text, setText] = useState("");

  const submit = () => {
    const value = text.trim();
    if (!value || disabled) return;
    onSend(value);
    setText("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="flex flex-col gap-2 border-t border-[var(--border)] bg-[var(--surface)] px-3 py-3">
      {awaitingUser && (
        <div className="rounded-[10px] border border-[var(--accent-soft)] bg-[var(--accent-soft)] px-3 py-2 text-[12.5px] text-[var(--accent-text)]">
          ⚠️ O Reviewer apontou um alerta crítico. Decida como prosseguir para
          que o Conductor continue.
        </div>
      )}
      <div className="flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            disabled={disabled}
            onClick={() => onSend(s)}
            className="rounded-full border border-[var(--border)] bg-[var(--surface-2)] px-2.5 py-1 text-[11.5px] text-[var(--text-2)] outline-none transition-colors hover:border-[var(--border-strong)] hover:text-[var(--text)] disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>
      <div className="flex items-end gap-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          placeholder="Descreva sua ideia ou peça o próximo passo…"
          className="max-h-32 min-h-[40px] flex-1 resize-none rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-[13.5px] text-[var(--text)] outline-none transition-colors focus:border-[var(--accent)]"
        />
        <button
          type="button"
          onClick={submit}
          disabled={disabled || !text.trim()}
          className="rounded-[12px] bg-[var(--accent)] px-4 py-2 text-[13.5px] font-semibold text-white outline-none transition-[opacity,transform] hover:opacity-90 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40"
        >
          Enviar
        </button>
      </div>
    </div>
  );
}
