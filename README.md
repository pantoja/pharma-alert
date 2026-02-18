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
   
3. **Variáveis de Ambiente**:
   Crie um arquivo `monitor.env` baseado no `.env.example` com suas credenciais de e-mail (Ex: Senha de aplicativo do Gmail). O projeto usa `monitor.env` para evitar conflitos de permissão em alguns ambientes macOS.

4. **GitHub Actions**:
   Para rodar automaticamente no GitHub:
   - Vá em `Settings > Secrets and variables > Actions` no seu repositório.
   - Adicione os secrets: `SMTP_SERVER`, `SMTP_PORT`, `EMAIL_USER`, `EMAIL_PASS`, `EMAIL_TO`.

## Estrutura do Projeto

- `main.py`: Orquestrador principal.
- `app/scraper.py`: Lógica de extração de dados dos sites.
- `app/database.py`: Gerenciamento do histórico (SQLite).
- `app/notifier.py`: Envio de e-mails.
- `app/config.py`: Carregamento de configurações.
- `.github/workflows/main.yml`: Automação 2x ao dia.
