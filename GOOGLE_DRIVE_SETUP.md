# Guia de Configuração do Google Drive

Este guia detalha como configurar a integração com o Google Drive para transcrição de vídeos.

## Pré-requisitos

- Conta Google com acesso ao Google Drive
- Python 3.7+ instalado
- Dependências do projeto instaladas (`pip install -r requirements.txt`)

## Passo a Passo

### 1. Criar Projeto no Google Cloud Console

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Clique em "Selecionar projeto" no topo da página
3. Clique em "Novo projeto"
4. Digite um nome para o projeto (ex: "Transcrição de Vídeos")
5. Clique em "Criar"

### 2. Ativar a API do Google Drive

1. No menu lateral, vá para "APIs e serviços" > "Biblioteca"
2. Procure por "Google Drive API"
3. Clique na API e depois em "Ativar"

### 3. Configurar Credenciais OAuth2

1. No menu lateral, vá para "APIs e serviços" > "Credenciais"
2. Clique em "Criar credenciais" > "ID do cliente OAuth 2.0"
3. Se solicitado, configure a tela de consentimento OAuth:
   - Tipo de usuário: Externo
   - Nome do aplicativo: "Transcrição de Vídeos"
   - Email de suporte: seu email
   - Domínios autorizados: deixe em branco
   - Clique em "Salvar e continuar"
   - Em escopos, adicione: 
     - `https://www.googleapis.com/auth/drive.readonly` (para ler arquivos)
     - `https://www.googleapis.com/auth/drive.file` (para salvar arquivos na mesma pasta)
   - Clique em "Salvar e continuar"
   - Em usuários de teste, adicione seu email
   - Clique em "Salvar e continuar"

4. Configure o tipo de aplicativo:
   - Tipo de aplicativo: "Aplicativo da área de trabalho"
   - Nome: "Transcrição de Vídeos"
   - Clique em "Criar"

5. Baixe o arquivo JSON das credenciais

### 4. Configurar o Projeto

1. Renomeie o arquivo baixado para `credentials.json`
2. Coloque o arquivo na raiz do projeto (mesmo nível do `transcrita_video.py`)
3. Execute o script de configuração:
   ```bash
   python setup_drive.py
   ```
4. Siga as instruções na tela
5. O navegador será aberto para você autorizar o aplicativo
6. Clique em "Permitir" para todas as permissões solicitadas

### 5. Testar a Configuração

1. Execute o aplicativo:
   ```bash
   streamlit run transcrita_video.py
   ```
2. Faça login no aplicativo
3. Selecione "Google Drive" como fonte do vídeo
4. Teste uma das opções de busca

## Funcionalidades Disponíveis

### Buscar por Nome
- Digite parte do nome do vídeo
- O sistema encontrará todos os vídeos que contenham esse texto no nome

### Buscar em Pasta Específica
- Cole a URL de uma pasta do Google Drive
- Exemplo: `https://drive.google.com/drive/folders/1ABC123DEF456`
- O sistema listará todos os vídeos na pasta

### Listar Todos os Vídeos
- Mostra todos os vídeos acessíveis na sua conta
- Útil para explorar o conteúdo disponível

### Salvar Transcrições no Google Drive
- **Nova funcionalidade**: Os arquivos de transcrição são automaticamente salvos na mesma pasta do vídeo original
- Arquivos gerados:
  - `{nome_do_video}_transcricao_completa.srt` - Transcrição completa com timestamps
  - `{nome_do_video}_resumo.pdf` - Resumo estruturado em PDF
  - `{nome_do_video}_transcricao_completa.pdf` - Transcrição completa em PDF
- Links diretos para abrir os arquivos no Google Drive
- Organização automática: tudo fica na mesma pasta do vídeo original

## Solução de Problemas

### Erro: "Arquivo 'credentials.json' não encontrado"
- Verifique se o arquivo está na raiz do projeto
- Verifique se o nome está correto (sem espaços ou caracteres especiais)

### Erro: "Não foi possível conectar ao Google Drive"
- Execute `python setup_drive.py` novamente
- Verifique se a API do Google Drive está ativada
- Verifique se as credenciais estão corretas

### Erro: "Token expirado"
- Execute `python setup_drive.py` para renovar o token
- Ou delete o arquivo `drive_token.pickle` e execute novamente

### Nenhum vídeo encontrado
- Verifique se você tem vídeos no Google Drive
- Verifique se os vídeos são acessíveis pela sua conta
- Tente usar "Listar todos os vídeos" primeiro

## Segurança

- O arquivo `credentials.json` contém informações sensíveis
- Nunca compartilhe este arquivo
- O arquivo está incluído no `.gitignore` para não ser versionado
- O token de acesso é salvo localmente em `drive_token.pickle`

## Permissões

O aplicativo solicita apenas permissão de leitura (`drive.readonly`):
- Pode listar arquivos e pastas
- Pode fazer download de vídeos
- **NÃO** pode modificar, deletar ou criar arquivos
- **NÃO** pode acessar outros dados da sua conta Google

## Suporte

Se encontrar problemas:
1. Verifique se seguiu todos os passos corretamente
2. Execute `python setup_drive.py` para reconfigurar
3. Verifique os logs do aplicativo para mensagens de erro
4. Entre em contato com o suporte se o problema persistir 