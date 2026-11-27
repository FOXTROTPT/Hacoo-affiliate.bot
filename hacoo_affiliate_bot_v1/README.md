# Hacoo Affiliate Bot — V1

Bot de Telegram que recebe um link público de produto, tenta recolher título, descrição, preço e imagem da página e prepara uma publicação em português.

## O que inclui

- Comandos `/start` e `/help`.
- Leitura de metadados Open Graph, Twitter Cards e alguns campos de preço estruturado.
- Texto de publicação com preço, link de compra e hashtags.
- Tentativa de enviar a imagem principal do produto.
- Limites de tempo e tamanho e bloqueio básico de endereços locais/privados ao abrir links.

Os resultados dependem dos metadados públicos do site. Algumas lojas carregam os dados com JavaScript ou bloqueiam pedidos automáticos, pelo que o bot pode não conseguir extrair o produto.

## Requisitos

- Python 3.10 ou superior.
- Um bot criado através de `@BotFather` no Telegram.

## Instalação local

1. Descomprime o ZIP e abre a pasta `hacoo-bot` num terminal.
2. Cria e ativa um ambiente virtual:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   No Windows, ativa-o com `.venv\Scripts\activate`.

3. Instala as dependências:

   ```bash
   pip install -r requirements.txt
   ```

4. Copia `.env.example` para `.env` e substitui o valor de `TELEGRAM_BOT_TOKEN` pelo token recebido do BotFather.
5. Inicia o bot:

   ```bash
   python bot.py
   ```

6. Abre o teu bot no Telegram, carrega em **Start** e envia um link de produto.

## Alojamento na cloud

Usa um serviço que permita executar um processo Python continuamente. Define `TELEGRAM_BOT_TOKEN` nas variáveis privadas do serviço e usa `python bot.py` como comando de arranque. Não carregues o ficheiro `.env` nem o token para o GitHub.

## Links de afiliado e utilização

O bot usa exatamente o link que receber como link de compra. Para atribuição de afiliado, envia ao bot o teu link de afiliado já criado pela plataforma. O bot não cria nem acrescenta parâmetros de afiliado, porque o formato oficial da Hacoo não foi fornecido.

Confirma título, preço, descrição, imagem e condições do programa antes de publicares. Não uses nomes de marcas, alegações de autenticidade ou outras informações que não estejam confirmadas pelo vendedor. Segue os termos do programa de afiliados e identifica claramente conteúdos publicitários quando aplicável.

## Privacidade e segurança

- O token é lido da variável de ambiente e não está incluído neste projeto.
- Os links são descarregados para tentar ler dados públicos; não devem conter palavras-passe, tokens ou informação privada.
- A extração pode falhar para páginas que exijam sessão, JavaScript ou que bloqueiem automação.
