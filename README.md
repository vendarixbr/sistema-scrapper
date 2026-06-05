# Health Lead Extractor

Ferramenta de extração automatizada de leads de **profissionais de saúde individuais** (médicos, dentistas, psicólogos, etc.) do Doctoralia Brasil.

Filtra automaticamente clínicas, hospitais e empresas, calcula um score de qualidade comercial e exporta os dados em CSV e/ou Excel prontos para prospecção.

---

## Pré-requisitos

- Python **3.10** ou superior
- pip
- Conexão com a internet

---

## Instalação

```bash
# 1. Clone ou baixe o projeto
cd health-lead-extractor

# 2. Crie e ative o ambiente virtual
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Instale o navegador Chromium para o Playwright
playwright install chromium
```

---

## Como usar

### Modo interativo (sem argumentos)

```bash
python main.py
```

O sistema pedirá especialidade e cidade via prompt.

### Modo CLI

```bash
# Busca básica — exporta CSV + Excel
python main.py -e ginecologista -c "Nova Serrana"

# Especificar estado
python main.py -e cardiologista -c "Belo Horizonte" -s MG

# Limitar páginas e exportar apenas CSV
python main.py -e dentista -c Contagem --max-paginas 5 --formato csv

# Exportar apenas leads com score >= 60
python main.py -e psicologo -c "São Paulo" --min-score 60

# Modo debug (browser visível, logs detalhados)
python main.py -e nutricionista -c Uberlândia --debug

# Nome personalizado para os arquivos de saída
python main.py -e fisioterapeuta -c Juiz de Fora --output fisio_juizdefora
```

### Exemplos prontos

```bash
python run_example.py
```

---

## Argumentos disponíveis

| Argumento | Curto | Padrão | Descrição |
|-----------|-------|--------|-----------|
| `--especialidade` | `-e` | — | Especialidade médica |
| `--cidade` | `-c` | — | Cidade alvo |
| `--estado` | `-s` | MG | Sigla do estado |
| `--max-paginas` | — | 10 | Limite de páginas por busca |
| `--headless` | — | ativado | Browser invisível (produção) |
| `--debug` | — | — | Browser visível + logs extras |
| `--output` | — | leads | Nome base dos arquivos |
| `--formato` | — | ambos | `csv`, `excel` ou `ambos` |
| `--min-score` | — | 0 | Filtro mínimo de score |

---

## Especialidades suportadas

`ginecologista` · `cardiologista` · `dermatologista` · `ortopedista` · `neurologista` ·
`psiquiatra` · `urologista` · `oftalmologista` · `pediatra` · `endocrinologista` ·
`otorrinolaringologista` · `gastroenterologista` · `reumatologista` · `dentista` ·
`psicologo` · `nutricionista` · `fisioterapeuta`

---

## Campos do CSV / Excel

| Campo | Descrição |
|-------|-----------|
| Nome | Nome completo do profissional |
| Título | Dr. / Dra. / Prof. etc. |
| Especialidade | Área de atuação |
| Cidade / Estado | Localização |
| Endereço / Bairro | Endereço do consultório |
| Telefone 1 / 2 | Números de contato |
| WhatsApp | Número WhatsApp, se disponível |
| E-mail | E-mail de contato |
| CRM / RQE | Registro profissional |
| Nota / Qtd. Avaliações | Reputação no Doctoralia |
| Planos de Saúde | Convênios aceitos |
| Serviços | Procedimentos realizados |
| Tem Site | `Sim` = não tem site próprio (oportunidade de venda) |
| Instagram / Facebook | Redes sociais |
| URL Doctoralia | Link para o perfil |
| Score | Pontuação de qualidade (0–100) |
| Classificação | 🔥 Quente / ⭐ Qualificado / 👀 Morno / ❄️ Frio |

### Abas do Excel

| Aba | Conteúdo |
|-----|----------|
| Todos os Leads | Dataset completo |
| Leads Quentes | Score ≥ 60, ordenados por score (desc) |
| Descartados | Clínicas filtradas + motivo |

---

## Sistema de Score (0–100)

| Critério | Pontos |
|----------|--------|
| Tem telefone cadastrado | +20 |
| Avaliação ≥ 4.5 com > 10 reviews | +20 |
| Avaliação ≥ 4.0 com > 5 reviews | +10 |
| CRM verificado | +15 |
| **Não** tem site próprio (oportunidade!) | +15 |
| WhatsApp disponível | +10 |
| Tem Instagram | +5 |
| Aceita > 3 planos de saúde | +5 |
| Tem > 5 serviços listados | +5 |
| Endereço completo com bairro | +5 |

**Classificações:**
- `🔥 Lead Quente` — 80 a 100 pontos
- `⭐ Lead Qualificado` — 60 a 79 pontos
- `👀 Lead Morno` — 40 a 59 pontos
- `❄️ Lead Frio` — 0 a 39 pontos

---

## FAQ — Erros comuns

**`playwright install chromium` falha**  
Execute `python -m playwright install --with-deps chromium` (instala dependências do sistema).

**Nenhum resultado encontrado**  
Confirme que a especialidade e cidade existem no Doctoralia. Tente grafias alternativas.

**Timeout / página não carrega**  
O scraper reencaminha automaticamente até 3 vezes. Se persistir, aumente `REQUEST_DELAY_MIN` no `.env`.

**IP bloqueado temporariamente**  
O scraper pausa 60s automaticamente. Após 3 bloqueios seguidos, pausa 5 minutos.

**Caracteres especiais corrompidos no CSV**  
Abra o arquivo no Excel via "Dados → Importar de texto" selecionando UTF-8. Os arquivos já usam UTF-8 BOM para evitar esse problema.

**`fake-useragent` falha ao baixar banco de dados**  
O `BrowserManager` inclui um User-Agent de fallback. A extração continua normalmente.

---

## Configuração avançada (.env)

Copie `.env.example` para `.env` e ajuste:

```env
HEADLESS=true
MAX_PAGES=10
REQUEST_DELAY_MIN=2.0
REQUEST_DELAY_MAX=5.0
LOG_LEVEL=INFO
```

---

## Estrutura do projeto

```
health-lead-extractor/
├── main.py                  # CLI principal
├── config.py                # Configurações centrais
├── run_example.py           # Exemplos de uso
├── requirements.txt
├── scraper/
│   ├── browser_manager.py   # Playwright com anti-detecção
│   ├── doctoralia_scraper.py # Lógica principal de extração
│   └── pagination_handler.py
├── filters/
│   ├── professional_filter.py # Descarta clínicas/empresas
│   └── quality_scorer.py      # Calcula score 0-100
├── exporters/
│   ├── csv_exporter.py
│   └── excel_exporter.py
├── models/
│   └── lead.py              # Modelo Pydantic do lead
├── utils/
│   ├── logger.py            # Rich logger + progress bar
│   ├── rate_limiter.py      # Delays anti-bloqueio
│   └── retry_handler.py     # Tenacity retry
└── output/                  # Arquivos gerados aqui
```

---

## Aviso legal

Esta ferramenta acessa dados **publicamente disponíveis** no Doctoralia.
Use de forma responsável:

- Respeite os [Termos de Serviço](https://www.doctoralia.com.br) do site.
- Não faça requisições em volume excessivo.
- Use os dados apenas para fins legítimos de prospecção comercial B2B.
- Os dados de contato devem ser tratados conforme a **LGPD** (Lei 13.709/2018).
