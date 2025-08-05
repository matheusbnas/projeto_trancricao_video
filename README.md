# Projeto de Transcrição e Resumo de Vídeo

Este projeto é uma aplicação Streamlit que permite aos usuários fazer upload de vídeos, transcrevê-los automaticamente ou usar uma transcrição fornecida, e gerar resumos no estilo tl;dv. A aplicação também oferece funcionalidades de sincronização entre o resumo e o vídeo.

## Funcionalidades

- Upload de vídeo local (formatos suportados: mp4, avi, mov)
- Transcrição de vídeos do YouTube via URL
- Transcrição de vídeos do Google Cloud Storage via URL
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

© 2024 Matheus Bernardes Costa do Nascimento. Todos os direitos reservados.

## Contato

Matheus Bernardes Costa do Nascimento - [E-mail](mailto:matheusbnas@gmail.com)

Link do projeto: [https://github.com/matheusbnas/projeto_trancricao_video](https://github.com/matheusbnas/projeto_trancricao_video)
