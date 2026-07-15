# Fase A1 — Gerador de Habilidades Dinâmicas (Skill Factory)

**Tipo de tarefa:** criação de sistema que gera skills automaticamente a partir de documentos de requisitos.
**Modelo sugerido:** Sonnet (raciocínio médio, precisa ler 2 docs e mapear para templates).
**Tempo estimado:** ~14h.

---

## 1. Objetivo

Criar `backend/app/services/skill_factory.py` que analisa
`Cria\PRD_AgentFlow_Studio_v1_1.md` e `Cria\Spec_Tecnica_Integracao_v1_0.md`,
extrai "necessidades" (integrações SRA/Firecrawl/GitHub, modos de pesquisa,
checagem de licença, circuit breakers) e **gera skills customizadas** em
`.claude/skills/auto-skill-generator/<nome>/SKILL.md`.

O sistema também deve criar a própria skill "meta" que instrui o Claude a
regerar skills quando o PRD/Spec mudar.

## 2. Origem no Hermes (copiar a lógica, remover imports)

- `Hermes\hermes-agent\agent\skill_utils.py` → funções `parse_frontmatter`,
  `SKILL_SUPPORT_DIRS`, `is_excluded_skill_path` (validação de frontmatter YAML).
- `Hermes\hermes-agent\agent\skill_bundles.py` → lógica de empacotar uma skill
  (SKILL.md + references + templates) num pacote coerente.
- `Hermes\hermes-agent\agent\skill_preprocessing.py` → normalização de nomes
  (lowercase, hífens, ≤64 chars; description ≤1024).
- `Hermes\hermes-agent\skills\software-development\hermes-agent-skill-authoring\SKILL.md`
  → formato exato do frontmatter esperado (name, description, version, author,
  license, metadata com tags/related_skills).

**Obrigatório:** remover todo `import` de `hermes_constants`, `agent.*`,
`get_hermes_home`, etc. Substituir por leitura de paths locais do AgentFlow.

## 3. O que criar (sem nome hermes)

### 3.1 `backend/app/services/skill_factory.py`
```python
"""Skill Factory — gera skills do projeto a partir de PRD + Spec de integração.

Lógica adaptada de Hermes (skill_bundles/skill_preprocessing/skill_utils),
sem nenhuma dependência de hermes_*.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List

SKILLS_ROOT = Path(__file__).resolve().parents[2] / ".claude" / "skills" / "auto-skill-generator"

@dataclass
class SkillSpec:
    name: str            # lowercase, hyphens, <=64
    description: str     # <=1024
    triggers: str        # quando usar
    body: str            # corpo markdown da skill
    references: dict     # arquivos auxiliares opcionais

# TODO (modelo executor): implementar
def analyze_requirements(prd_path: Path, spec_path: Path) -> List[SkillSpec]: ...
def generate_skill(spec: SkillSpec) -> Path: ...
def _assert_no_hermes(text: str) -> None:  # levanta se 'hermes' aparecer
    assert "hermes" not in text.lower()
```

Regras de geração:
- `analyze_requirements` varre os docs por keywords (SRA, Firecrawl, `/v2/scrape`,
  `--mode cirurgia`, `confidence_score >= 0.85`, `license`, `circuit breaker`,
  `timeout 90s`) e produz ≥4 `SkillSpec`:
  - `firecrawl-debugger` (usa `/v2/scrape` da Spec)
  - `sra-cirurgia-mode` (documenta `--mode cirurgia` vs `guerrilha`)
  - `auto-approve-validator` (repete regra ADR-007: confidence ≥0.85 E zero alertas)
  - `github-license-checker` (campo `license` do PRD F-009)
- `generate_skill` monta `<SKILLS_ROOT>/<name>/SKILL.md` com frontmatter
  validado por `parse_frontmatter` (copiado do hermes, sem o import).

### 3.2 `backend/app/services/skill_factory_templates.py`
Templates reais de corpo para cada skill acima.

### 3.3 `.claude/skills/auto-skill-generator/SKILL.md`
Skill meta: instrui o Claude a rodar `skill_factory.analyze_requirements` quando
PRD/Spec mudarem. Nome da skill: `auto-skill-generator`.

## 4. Critérios de Aceitação (testáveis)
- [ ] `analyze_requirements()` sobre PRD+Spec produz ≥4 SkillSpecs.
- [ ] Cada skill gerada passa `parse_frontmatter` (YAML válido).
- [ ] Nenhuma skill gerada contém "hermes" em nome/corpo/metadata.
- [ ] `pytest` cobre `analyze_requirements` e `generate_skill` (mock dos docs).

## 5. Verificação
```bash
cd F:\Criando sites pelo pc\Site AgentFlow Studio\backend
python -m pytest tests/ -q
python -c "from app.services.skill_factory import analyze_requirements, SKILLS_ROOT; print(len(analyze_requirements(Path('../Cria/PRD_AgentFlow_Studio_v1_1.md'), Path('../Cria/Spec_Tecnica_Integracao_v1_0.md'))))"
```
Esperado: imprime ≥4 e nenhum erro de assert.

## 6. Arquivos a ler antes de codar
- `Cria\PRD_AgentFlow_Studio_v1_1.md` (seções 2.3, 2.8, 2.9, 4.4)
- `Cria\Spec_Tecnica_Integracao_v1_0.md` (seções 1.3, 1.5, 2.2, 3)
- `Hermes\hermes-agent\agent\skill_utils.py`, `skill_bundles.py`
- `backend\app\core\config.py` (para paths base, se necessário)
