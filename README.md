# Monitor de Preços de Medicamentos

Este projeto monitora automaticamente o preço de medicamentos nos sites:
- Pague Menos
- Drogasil
- Drogaria São Paulo

Ele considera kits ("leve mais por menos") e custos de frete, salvando o histórico em um banco SQLite e enviando alertas por e-mail.

## Configuração

1. **Ambiente Virtual e Dependências**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Produtos e Alvos**:
   Edite o arquivo `config.json` para adicionar seus medicamentos, termos de busca e o preço unitário alvo.
   - O sistema evita enviar notificações duplicadas se o preço e a farmácia da melhor oferta forem os mesmos do último alerta.
   - Você pode pausar notificações de um produto adicionando o campo `"snooze_until": "AAAA-MM-DD"`. O sistema não enviará alertas até essa data.
   
3. **Variáveis de Ambiente**:
   Crie um arquivo `monitor.env` baseado no `.env.example` com suas credenciais de e-mail (Ex: Senha de aplicativo do Gmail). O projeto usa `monitor.env` para evitar conflitos de permissão em alguns ambientes macOS.

4. **GitHub Actions**:
    O projeto está configurado para rodar automaticamente via GitHub Actions:
    - **CI**: Valida o código em cada push/pull request.
    - **Run Scraper**: Executa o monitoramento diariamente (09:00 UTC) e pode ser disparado manualmente.

    Para configurar a automação:
    1. Vá em `Settings > Secrets and variables > Actions`.
    2. Adicione os seguintes Secrets:
       - `SMTP_SERVER`: Servidor SMTP (ex: `smtp.gmail.com`).
       - `SMTP_PORT`: Porta SMTP (ex: `587`).
       - `EMAIL_USER`: Seu e-mail de envio.
       - `EMAIL_PASS`: Senha de aplicativo (App Password).
       - `EMAIL_TO`: E-mail que receberá os alertas.

## Estrutura do Projeto

- `main.py`: Orquestrador principal.
- `app/scraper.py`: Lógica de extração de dados dos sites.
- `app/database.py`: Gerenciamento do histórico (SQLite).
- `app/notifier.py`: Envio de e-mails.
- `app/config.py`: Carregamento de configurações.
- `.github/workflows/ci.yml`: Workflow de Integração Contínua.
- `.github/workflows/run_scraper.yml`: Workflow de execução agendada.
