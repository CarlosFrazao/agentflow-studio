import { render, screen } from "@testing-library/react";
import { ErrorBoundary } from "./ErrorBoundary";

// Componente que lança erro ao ser renderizado
function BadComponent(): never {
  throw new Error("Render error!");
}

describe("ErrorBoundary", () => {
  test("exibe fallback UI quando há erro", () => {
    render(
      <ErrorBoundary>
        <BadComponent />
      </ErrorBoundary>
    );

    // Verifica se o texto de fallback aparece
    expect(screen.getByText(/Algo deu errado/i)).toBeTruthy();
    expect(screen.getByText(/Render error!/i)).toBeTruthy();
    // Verifica se botão de reiniciar está presente
    expect(screen.getByRole("button", { name: /Entrar novamente/i })).toBeTruthy();
  });
});
