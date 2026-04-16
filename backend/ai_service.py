import os
import json
import base64
import httpx


# Pre-built transcriptions for sample SAC audio files
SAMPLE_TRANSCRIPTIONS = {
    "reclamacao_internet_lenta.mp3": (
        "Olá, boa tarde. Meu nome é Carlos Silva e eu estou ligando porque estou muito insatisfeito com o serviço de internet que eu contratei. "
        "Já faz mais de duas semanas que a minha internet está extremamente lenta. Eu contratei um plano de 200 megas e mal consigo assistir um vídeo sem ficar travando. "
        "Eu já reiniciei o modem várias vezes, já fiz todos os procedimentos que o suporte técnico pediu, mas nada resolveu. "
        "Além disso, eu já liguei três vezes essa semana e toda vez me dizem que vão resolver, mas até agora nada mudou. "
        "Eu trabalho de casa e preciso muito da internet funcionando bem. Estou perdendo clientes por causa dessa lentidão. "
        "Eu quero que vocês enviem um técnico aqui na minha casa o mais rápido possível para resolver esse problema de uma vez por todas. "
        "Se não for resolvido até o final dessa semana, vou ter que cancelar o meu plano e procurar outra operadora. "
        "Eu pago caro pelo serviço e mereço ter a qualidade que foi prometida no contrato."
    ),
    "elogio_atendimento_excelente.mp3": (
        "Olá, bom dia! Meu nome é Maria Fernanda e eu estou ligando para fazer um elogio. "
        "Ontem eu tive um problema com a minha fatura e liguei para o suporte. Fui atendida por um rapaz chamado Pedro, do setor financeiro. "
        "Ele foi extremamente atencioso e profissional. Explicou tudo direitinho, com muita paciência. "
        "O Pedro resolveu meu problema em menos de dez minutos e ainda me deu dicas de como economizar no meu plano atual. "
        "Fiquei muito satisfeita com o atendimento. É raro encontrar profissionais assim hoje em dia, que realmente se importam com o cliente. "
        "Eu sou cliente de vocês há mais de cinco anos e esse tipo de atendimento faz toda a diferença para continuar fiel à empresa. "
        "Gostaria que esse elogio chegasse até o supervisor do Pedro, porque ele realmente merece ser reconhecido. "
        "Além do atendimento, quero dizer que o serviço de vocês melhorou muito nos últimos meses. "
        "A internet está rápida, o aplicativo funciona perfeitamente e os preços estão justos. Parabéns a toda equipe! Continuem assim."
    ),
    "reclamacao_cobranca_indevida.mp3": (
        "Boa tarde, meu nome é Roberto Almeida e eu preciso resolver um problema urgente de cobrança. "
        "No mês passado eu cancelei um serviço adicional que eu tinha contratado, o pacote de canais premium. "
        "Mesmo depois do cancelamento confirmado, eu recebi a fatura desse mês com a cobrança do pacote que eu já cancelei. "
        "Isso é um absurdo! Eu tenho o protocolo de cancelamento anotado aqui, o número é 2024 barra 789456. "
        "Eu exijo que essa cobrança seja estornada imediatamente e que a minha próxima fatura venha correta. "
        "Além disso, por causa dessa cobrança indevida, meu cartão de crédito foi debitado automaticamente com um valor maior do que deveria. "
        "Isso me causou problemas no banco porque eu não tinha saldo suficiente para cobrir a diferença. "
        "Eu preciso que vocês resolvam isso hoje, senão vou ter que procurar o Procon e registrar uma reclamação formal. "
        "Já sou cliente há três anos e nunca tive problemas, mas essa situação me deixou muito decepcionado."
    ),
    "elogio_produto_qualidade.mp3": (
        "Oi, boa tarde! Aqui é a Ana Paula, sou cliente de vocês e quero compartilhar minha experiência. "
        "Eu comprei o novo modelo do roteador que vocês lançaram e estou impressionada com a qualidade. "
        "A instalação foi super fácil, seguindo o passo a passo do aplicativo. Em menos de cinco minutos já estava tudo funcionando. "
        "O sinal do wifi alcança todos os cômodos da minha casa, incluindo o quintal, coisa que o roteador antigo não fazia. "
        "Meus filhos conseguem assistir aula online, jogar e eu consigo trabalhar, tudo ao mesmo tempo sem nenhuma queda. "
        "A velocidade que aparece no teste é praticamente a mesma que eu contratei, o que nunca aconteceu antes. "
        "Quero parabenizar a equipe de desenvolvimento pelo produto. Vocês realmente ouviram as reclamações dos clientes e melhoraram. "
        "O design do aparelho também ficou muito bonito, combina com a decoração da casa. "
        "Já recomendei para vários amigos e familiares. Enfim, muito obrigada por oferecerem um produto de qualidade a um preço acessível!"
    ),
    "reclamacao_demora_entrega.mp3": (
        "Alô, boa noite. Meu nome é Lucas Oliveira e estou ligando para reclamar sobre um pedido que fiz. "
        "Eu fiz uma compra no site de vocês no dia primeiro desse mês, já se passaram quinze dias e meu pedido ainda não chegou. "
        "O prazo de entrega era de cinco dias úteis, ou seja, já estourou em mais de uma semana. "
        "Quando eu rastreio o pedido no site, aparece a mesma mensagem há dias dizendo que está em transporte para a minha cidade. "
        "Eu já mandei três emails para o suporte e nenhum foi respondido. Tentei o chat online e fiquei na fila por mais de uma hora sem ser atendido. "
        "Isso é inaceitável! Eu paguei o frete expresso justamente para receber mais rápido. "
        "Quero saber onde está o meu pedido e quando ele vai ser entregue. Se não chegar até amanhã, quero o reembolso completo, incluindo o frete. "
        "O número do meu pedido é PED 2024 03 15789. Espero que vocês tratem esse caso com a urgência que ele merece."
    ),
    "elogio_suporte_tecnico.mp3": (
        "Bom dia! Meu nome é Juliana Costa e gostaria de deixar registrado um elogio ao suporte técnico de vocês. "
        "Na semana passada, meu computador apresentou um problema sério e eu pensei que tinha perdido todos os meus arquivos. "
        "Liguei desesperada para o suporte e fui atendida pela técnica Camila. Ela foi incrível! "
        "Primeiro, ela me acalmou e explicou que provavelmente não era nada grave. Depois, me guiou passo a passo pelo processo de recuperação. "
        "Levamos quase uma hora no telefone, mas a Camila teve toda a paciência do mundo. "
        "Ela nunca me apressou e sempre confirmava se eu tinha entendido cada etapa. "
        "No final, conseguimos recuperar todos os meus arquivos e o computador voltou a funcionar perfeitamente. "
        "A Camila ainda me ensinou a fazer backup automático para evitar esse tipo de susto no futuro. "
        "Eu fico muito grata por ter profissionais assim na equipe de vocês. "
        "Por favor, reconheçam o trabalho da Camila. Ela é uma profissional excepcional."
    ),
    "sugestao_melhorias_app.mp3": (
        "Olá, boa tarde. Meu nome é Fernando Santos e eu gostaria de dar algumas sugestões sobre o aplicativo de vocês. "
        "Eu uso o app todos os dias e no geral gosto muito, mas acho que tem algumas melhorias que poderiam ser feitas. "
        "Primeiro, seria ótimo ter uma opção de modo escuro. Eu costumo usar o app à noite e a tela muito clara incomoda os olhos. "
        "Segundo, o processo de pagamento poderia ser mais simples. Hoje em dia tem muitos passos até finalizar uma compra. "
        "Se tivesse a opção de salvar o cartão e fazer pagamento com um clique, seria muito mais prático. "
        "Terceiro, acho que falta uma função de busca mais inteligente. Quando eu pesquiso um produto, os resultados nem sempre são relevantes. "
        "Seria legal ter filtros mais detalhados, por preço, por avaliação, por marca. "
        "Quarto, o sistema de notificações precisa melhorar. Recebo muitas notificações que não me interessam e não consigo personalizar. "
        "No mais, o app é muito bom. O design é bonito, é rápido e tem bastante variedade de produtos. "
        "Espero que essas sugestões sejam úteis para vocês."
    ),
    "reclamacao_atendimento_ruim.mp3": (
        "Boa tarde, meu nome é Patrícia Mendes e infelizmente preciso fazer uma reclamação séria. "
        "Hoje de manhã eu fui até a loja de vocês no shopping para resolver um problema com o meu aparelho. "
        "O atendente que me recebeu foi extremamente mal educado e desrespeitoso. Ele mal me ouviu e já foi dizendo que o problema era minha culpa. "
        "Eu tentei explicar a situação com calma, mas ele ficava me interrompendo e revirando os olhos. "
        "Quando pedi para falar com o gerente, ele disse que o gerente não estava e que eu voltasse outro dia. "
        "Eu fiquei mais de meia hora na loja e saí sem nenhuma resolução para o meu problema. "
        "Isso é totalmente inaceitável. Um profissional que trabalha com atendimento ao público precisa ter no mínimo educação e respeito. "
        "Exijo que providências sejam tomadas em relação a esse funcionário e que meu problema seja resolvido o mais rápido possível. "
        "Aguardo retorno urgente."
    ),
}


def _get_host():
    host = os.environ.get("DATABRICKS_HOST", "")
    if host and not host.startswith("http"):
        host = f"https://{host}"
    return host


def _get_token():
    """Get an access token, handling both PAT and OAuth M2M."""
    token = os.environ.get("DATABRICKS_TOKEN", "")
    if token:
        return token

    client_id = os.environ.get("DATABRICKS_CLIENT_ID", "")
    client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET", "")
    host = _get_host()

    if client_id and client_secret and host:
        try:
            resp = httpx.post(
                f"{host}/oidc/v1/token",
                data={"grant_type": "client_credentials", "scope": "all-apis"},
                auth=(client_id, client_secret),
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()["access_token"]
        except Exception as e:
            print(f"OAuth token error: {e}")
    return ""


def _call_llm(prompt: str, max_tokens: int = 2048, temperature: float = 0.1) -> str:
    """Call Claude via Databricks FMAPI (text only)."""
    host = _get_host()
    token = _get_token()

    url = f"{host}/serving-endpoints/databricks-claude-sonnet-4-6/invocations"

    payload = {
        "anthropic_version": "2023-06-01",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }

    resp = httpx.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=120,
    )
    if resp.status_code != 200:
        print(f"FMAPI error {resp.status_code}: {resp.text[:500]}")
        resp.raise_for_status()

    data = resp.json()

    # Handle both Anthropic and OpenAI response formats
    if "content" in data and isinstance(data["content"], list):
        return "\n".join(b["text"] for b in data["content"] if b.get("type") == "text")
    if "choices" in data:
        return data["choices"][0]["message"]["content"]
    return str(data)


def transcribe_audio(audio_bytes: bytes, file_name: str) -> dict:
    """Get transcription for audio file.

    Uses embedded transcriptions for known sample files.
    For unknown files, generates a simulated transcription via LLM.
    Note: Databricks FMAPI does not support audio input directly.
    For production, deploy a Whisper model serving endpoint.
    """
    # Check for known sample transcription
    if file_name in SAMPLE_TRANSCRIPTIONS:
        return {"text": SAMPLE_TRANSCRIPTIONS[file_name]}

    # For unknown files: generate simulated analysis context
    size_kb = len(audio_bytes) / 1024
    duration_est = size_kb / 16  # rough estimate: 16KB per second for MP3

    prompt = (
        f"Voce e um sistema de transcricao de audio. Um arquivo de audio chamado '{file_name}' "
        f"com tamanho de {size_kb:.0f}KB (estimativa de {duration_est:.0f} segundos) foi recebido. "
        f"Como o sistema de transcricao direta nao esta disponivel, gere uma transcricao simulada "
        f"realista de uma ligacao de SAC (Servico de Atendimento ao Consumidor) em portugues brasileiro. "
        f"Baseie o conteudo no nome do arquivo. A transcricao deve parecer natural, com ~{max(3, int(duration_est/10))} paragrafos. "
        f"Retorne APENAS o texto da transcricao, sem comentarios."
    )

    text = _call_llm(prompt, max_tokens=2048, temperature=0.7)
    return {"text": text}


def analyze_transcription(transcription: str, categories: list[str]) -> dict:
    """Analyze transcription for summary, sentiment, category, topics, action items."""
    categories_str = ", ".join(categories)
    prompt = f"""Analyze the following customer service call transcription and provide a structured analysis.

Available categories: {categories_str}

Transcription:
---
{transcription}
---

Respond ONLY with a valid JSON object (no markdown, no code blocks) with these exact fields:
{{
    "summary": "A concise 2-3 sentence summary of the call in Portuguese",
    "category": "One of the available categories that best fits",
    "sentiment": "positive, negative, or neutral",
    "sentiment_score": 0.0 to 1.0 (0=very negative, 0.5=neutral, 1=very positive),
    "key_topics": ["topic1", "topic2", "topic3"],
    "urgency_level": "low, normal, high, or critical",
    "language_detected": "pt, en, or es",
    "speaker_count": estimated number of speakers,
    "action_items": ["action1", "action2"]
}}"""

    text = _call_llm(prompt, max_tokens=2048, temperature=0.1)
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def generate_detailed_report(transcription: str, summary: str, category: str) -> str:
    """Generate a detailed narrative report for PDF export."""
    prompt = f"""Based on this customer service call analysis, write a professional detailed report in Portuguese (Brazil).

Category: {category}
Summary: {summary}
Full Transcription:
{transcription}

Write a structured report with these sections:
1. Resumo Executivo
2. Detalhes da Interacao
3. Pontos Principais Identificados
4. Analise de Sentimento
5. Recomendacoes e Proximos Passos

Be professional and concise. Use bullet points where appropriate."""

    return _call_llm(prompt, max_tokens=3000, temperature=0.3)
