# N8N Workflow (Chat normal, sem Webhook) - Chat Trigger v1.4

Este guia foi refeito para a sua versao do N8N (node **When chat message received**, v1.4).

Backend usado:
- API interna Docker: `http://api:8000`
- Endpoint: `POST /chat`
- API espera `multipart/form-data` com:
  - `question` (obrigatorio)
  - `session_id` (opcional)
  - `file` (opcional)

Observacao importante:
- Colocar uma URL dentro da mensagem de chat NAO chama automaticamente o endpoint `/scrape`.
- Se quiser ingerir conteudo web antes da resposta, adicione um passo dedicado para `POST /scrape` (fluxo opcional abaixo).

## Fluxo final

```text
When chat message received
  -> Code
  -> IF
      -> HTTP Request (com arquivo)
      -> HTTP Request (sem arquivo)
  -> Code
  -> Chat (Send a message)
```

## Fluxo opcional (chat + scrape por URL)

Use esse fluxo apenas se quiser que mensagens contendo link acionem ingestao web:

```text
When chat message received
  -> Code (normaliza)
  -> IF (mensagem contem http:// ou https://)
      True -> HTTP Request (POST /scrape)
           -> HTTP Request (POST /chat)
      False -> HTTP Request (POST /chat)
  -> Code (formata resposta)
  -> Chat (Send a message)
```

Expressao sugerida no IF de URL:

```text
{{ /https?:\/\//i.test($json.question || "") }}
```

No HTTP Request de scrape:
- Method: POST
- URL: `http://api:8000/scrape`
- Body Content Type: JSON
- Body:

```json
{
  "url": "={{ ($json.question.match(/https?:\/\/\S+/i) || [null])[0] }}"
}
```

Depois do scrape, siga para o HTTP Request de chat normal.

## 1) Node: When chat message received

Nome exato do node na UI:
- **When chat message received**

Aba **Parameters**:
- **Make Chat Publicly Available**: OFF
- **Make Available in n8n Chat Hub**: OFF
- Em **Options**:
  - **Allow File Uploads**: ON
  - **Allowed File Mime Types**: deixe vazio (teste) ou preencha se quiser restringir
  - **Response Mode**: **Using Response Nodes**

Aba **Settings**:
- Pode deixar padrao

## 2) Node: Code

Adicione um node **Code** logo depois do trigger.

Campos do node:
- **Language**: JavaScript
- **Mode**: Run Once for All Items

Codigo:

```javascript
// Normaliza campos vindos do Chat Trigger v1.4
const item = $input.all()[0];
const message = item.json.message ?? item.json.text ?? item.json.chatInput ?? "";
const sessionId = item.json.sessionId ?? item.json.session_id ?? $execution.id;
const binary = item.binary ?? {};
const firstBinaryKey = Object.keys(binary)[0];

// Padroniza o nome do campo binario para "file" para o HTTP Request
const normalizedBinary = firstBinaryKey ? { file: binary[firstBinaryKey] } : {};

return [{
  json: {
    question: String(message).trim(),
    session_id: String(sessionId),
  },
  binary: normalizedBinary,
}];
```

## 3) Node: IF

Adicione o node **IF** depois do node Code.

Configuracao exata na tela **Parameters -> Conditions**:
1. Clique em **Add condition**
2. Em **value1**, mude para **Expression** e use:

```text
{{ Object.keys($binary ?? {}).length > 0 }}
```

3. No seletor de tipo, escolha: **Boolean -> is true**

Como funciona:
- Saida **True Branch**: quando existe qualquer arquivo (independente do nome do campo)
- Saida **False Branch**: quando nao existe arquivo

## 4A) Node: HTTP Request (com arquivo)

Adicione node **HTTP Request** na trilha true.

Aba **Parameters**:
- **Method**: POST
- **URL**: `http://api:8000/chat`
- **Send Body**: ON
- **Body Content Type**: **Form-Data**

Em **Body Parameters** adicione exatamente:
1. **Name**: `question`
  - **Value** (Expression): `{{ $json.question }}`
2. **Name**: `session_id`
  - **Value** (Expression): `{{ $json.session_id }}`
3. **Name**: `file`
   - **Type**: Binary
   - **Input Data Field Name**: `file`

Observacao:
- Esse `file` precisa bater com o nome do campo binario do item de entrada.
- Como o node **Code** ja padroniza para `file`, aqui pode ficar sempre `file`.

## 4B) Node: HTTP Request (sem arquivo)

Adicione outro node **HTTP Request** na trilha false.

Aba **Parameters**:
- **Method**: POST
- **URL**: `http://api:8000/chat`
- **Send Body**: ON
- **Body Content Type**: **Form-Data**

Em **Body Parameters** adicione exatamente:
1. **Name**: `question`
  - **Value** (Expression): `{{ $json.question }}`
2. **Name**: `session_id`
  - **Value** (Expression): `{{ $json.session_id }}`

## 5) Node: Code

Junte as duas trilhas em um node **Code**.

Campos do node:
- **Language**: JavaScript
- **Mode**: Run Once for All Items

Codigo:

```javascript
const payload = $json;

const ok = !payload.error;
const reply = ok
  ? (payload.response || "Sem resposta")
  : `Erro: ${payload.error}${payload.detail ? ` - ${payload.detail}` : ""}`;

return [{
  reply,
  session_id: payload.session_id || null,
  success: ok,
}];
```

## 6) Node: Chat (Send a message)

Nome exato na UI: **Chat** → operacao **Send a message**

Aba **Parameters**:
- **Operation**: Send a message
- **Message** (Expression):

```text
{{ $json.reply }}
```

- **Response Type**: Free Text

## Conexoes exatas

- `When chat message received` -> `Code (1)`
- `Code (1)` -> `IF`
- `IF (True Branch)` -> `HTTP Request (com arquivo)`
- `IF (False Branch)` -> `HTTP Request (sem arquivo)`
- `HTTP Request (com arquivo)` -> `Code (2)`
- `HTTP Request (sem arquivo)` -> `Code (2)`
- `Code (2)` -> `Chat (Send a message)`

## Teste na sua UI

1. Salve o workflow
2. Clique em **Test chat** no node **When chat message received**
3. Envie texto simples
4. Envie texto + PDF
5. Confira resposta no painel de chat

## Se nao funcionar de primeira

1. No trigger, envie uma mensagem de teste
2. Abra o output do node **When chat message received**
3. Verifique os nomes reais dos campos (ex.: `message`, `text`, `chatInput`)
4. Se vier diferente, ajuste apenas no primeiro node **Code**

