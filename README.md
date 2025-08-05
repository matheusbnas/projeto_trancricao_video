# Projeto de Transcrição e Resumo de Vídeo

Este projeto é uma aplicação Streamlit que permite aos usuários fazer upload de vídeos, transcrevê-los automaticamente ou usar uma transcrição fornecida, e gerar resumos no estilo tl;dv. A aplicação também oferece funcionalidades de sincronização entre o resumo e o vídeo.

## Funcionalidades

- Upload de vídeo local (formatos suportados: mp4, avi, mov)
- Transcrição de vídeos do YouTube via URL
- Transcrição de vídeos do Google Cloud Storage via URL
- **Transcrição de vídeos do Google Drive** - Busca e transcrição de vídeos armazenados no Google Drive
- Transcrição automática de vídeo usando OpenAI Whisper
- Geração de resumo estruturado no estilo tl;dv
- Download de resumo e transcrição completa em formato PDF e SRT
- Nomes de arquivo personalizados baseados no arquivo original
- Autenticação via sistema de usuários

## Requisitos

- Python 3.7+
- Bibliotecas Python (ver `requirements.txt`)
- Chave de API do OpenAI
- FFmpeg (para processamento de áudio/vídeo)
- yt-dlp (para download de vídeos do YouTube)
- Credenciais do Google Drive API (para acesso aos vídeos do Drive)

## Instalação

1. Clone o repositório:
   ```
   git clone https://github.com/matheusbnas/projeto_trancricao_video.git
   cd projeto_trancricao_video
   ```

2. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```

3. Configure as variáveis de ambiente:
   Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:
   ```
   OPENAI_API_KEY=sua_chave_api_do_openai
   ```

4. **Configuração do Google Drive (Opcional):**
   Para usar a funcionalidade de transcrição de vídeos do Google Drive:
   
   a) Crie um projeto no Google Cloud Console
   b) Ative a Google Drive API
   c) Configure as credenciais OAuth2
   d) Execute o script de configuração:
   ```bash
   python setup_drive.py
   ```
   
   Para instruções detalhadas, consulte o arquivo `GOOGLE_DRIVE_SETUP.md`.

## Uso

1. Execute a aplicação Streamlit:
   ```
   streamlit run transcrita_video.py
   ```

2. Acesse a aplicação através do navegador (geralmente em `http://localhost:8501`).

3. Faça login com suas credenciais.

4. Escolha a fonte do vídeo:
   - **Upload Local**: Faça upload de um arquivo de vídeo
   - **YouTube**: Cole a URL do vídeo do YouTube
   - **Google Cloud Storage**: Cole a URL pública do vídeo
   - **Google Drive**: Busque e selecione vídeos do seu Google Drive

5. Clique em "Transcrever vídeo automaticamente".

6. Aguarde o processamento (pode levar alguns minutos).

7. Visualize o resumo gerado e a transcrição completa.

8. Faça o download dos arquivos PDF e SRT gerados.

## Estrutura do Projeto

- `transcrita_video.py`: Arquivo principal contendo o código da aplicação Streamlit.
- `utils.py`: Funções auxiliares para processamento de arquivos e geração de PDFs.
- `requirements.txt`: Lista de dependências do projeto.
- `images/`: Diretório contendo imagens usadas na aplicação.
- `README_MODIFICACOES.md`: Documentação detalhada das modificações implementadas.
- `.env`: Arquivo para armazenar variáveis de ambiente (não incluído no repositório).
- `setup_drive.py`: Script de configuração automática do Google Drive API.
- `credentials_example.json`: Exemplo de estrutura para arquivo de credenciais do Google Drive.
- `GOOGLE_DRIVE_SETUP.md`: Guia detalhado para configuração do Google Drive API.

## Funcionalidades do Google Drive

A aplicação oferece três opções para trabalhar com vídeos do Google Drive:

1. **Buscar por nome**: Digite o nome do vídeo para encontrar arquivos específicos
2. **Buscar em pasta específica**: Cole a URL de uma pasta do Google Drive para listar todos os vídeos nela
3. **Listar todos os vídeos**: Visualize todos os vídeos acessíveis na sua conta do Google Drive

### Arquivos Gerados

- **Transcrição completa**: Arquivo SRT com timestamps precisos
- **Resumo estruturado**: PDF com pontos-chave no estilo tl;dv
- **Transcrição completa em PDF**: Documento PDF com a transcrição completa

### Salvamento Automático no Google Drive

- **Nova funcionalidade**: Os arquivos de transcrição são automaticamente salvos na mesma pasta do vídeo original
- **Organização**: Mantém todos os arquivos relacionados organizados no local correto
- **Links diretos**: Acesso rápido aos arquivos salvos no Google Drive
- **Nomenclatura consistente**: Arquivos nomeados com o mesmo padrão do vídeo original

### Suporte

Para problemas relacionados ao Google Drive:
- Verifique se as credenciais estão configuradas corretamente
- Certifique-se de que a Google Drive API está ativada
- Consulte o arquivo `GOOGLE_DRIVE_SETUP.md` para instruções detalhadas

## Contribuindo

Contribuições são bem-vindas! Por favor, sinta-se à vontade para submeter pull requests ou abrir issues para reportar bugs ou sugerir melhorias. Note que, devido à natureza da licença, todas as contribuições estarão sujeitas aos mesmos termos de licenciamento.

## Licença

Este projeto está licenciado sob a Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License (CC BY-NC-ND 4.0).

Isso significa que você é livre para:
- Compartilhar — copiar e redistribuir o material em qualquer suporte ou formato

Sob as seguintes condições:
- Atribuição — Você deve dar o crédito apropriado, fornecer um link para a licença e indicar se mudanças foram feitas. Você deve fazê-lo em qualquer circunstância razoável, mas de maneira alguma que sugira ao licenciante a apoiar você ou o seu uso.
- Não Comercial — Você não pode usar o material para fins comerciais.
- Sem Derivações — Se você remixar, transformar ou criar a partir do material, você não pode distribuir o material modificado.
- Sem restrições adicionais — Você não pode aplicar termos jurídicos ou medidas de caráter tecnológico que restrinjam legalmente outros de fazerem algo que a licença permita.

Para ver uma cópia desta licença, visite:
[http://creativecommons.org/licenses/by-nc-nd/4.0/](http://creativecommons.org/licenses/by-nc-nd/4.0/)

Para qualquer uso comercial ou modificações no projeto, entre em contato com o autor para obter permissão.

© 2024-2025 Matheus Bernardes Costa do Nascimento. Todos os direitos reservados.

**Última atualização: Agosto de 2025**

## Contato

Matheus Bernardes Costa do Nascimento - [E-mail](mailto:matheusbnas@gmail.com)

Link do projeto: [https://github.com/matheusbnas/projeto_trancricao_video](https://github.com/matheusbnas/projeto_trancricao_video)
