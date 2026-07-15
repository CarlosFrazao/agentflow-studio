import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import {
  OnboardingTour,
  isOnboardingDone,
  markOnboardingDone,
  ONBOARDING_FLAG,
} from "./OnboardingTour";

describe("OnboardingTour (F-012)", () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("abre no passo 1 de 5 no primeiro acesso", () => {
    render(<OnboardingTour onDone={() => {}} />);
    expect(screen.getByText(/Passo 1 de 5/)).toBeTruthy();
    expect(screen.getByText(/Bem-vindo ao AgentFlow Studio/)).toBeTruthy();
  });

  it("'Concluir' grava a flag e dispara onDone", () => {
    const onDone = vi.fn();
    render(<OnboardingTour onDone={onDone} />);
    // Avança até o último passo e conclui.
    const next = screen.getByText(/Próximo/);
    fireEvent.click(next);
    fireEvent.click(next);
    fireEvent.click(next);
    fireEvent.click(next);
    const finish = screen.getByText(/Concluir/);
    fireEvent.click(finish);
    expect(localStorage.getItem(ONBOARDING_FLAG)).toBe("1");
    expect(onDone).toHaveBeenCalled();
  });

  it("'Pular' grava a flag e fecha o tour", () => {
    const onDone = vi.fn();
    render(<OnboardingTour onDone={onDone} />);
    fireEvent.click(screen.getByText(/Pular tour/));
    expect(localStorage.getItem(ONBOARDING_FLAG)).toBe("1");
    expect(onDone).toHaveBeenCalled();
  });

  it("não reaparece após concluído (isOnboardingDone=true)", () => {
    markOnboardingDone();
    expect(isOnboardingDone()).toBe(true);
  });

  it("Esc dispara pular (grava flag)", () => {
    render(<OnboardingTour onDone={() => {}} />);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(localStorage.getItem(ONBOARDING_FLAG)).toBe("1");
  });
});
