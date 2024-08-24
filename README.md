# Projeto de Transcrição e Resumo de Vídeo

Este projeto é uma aplicação Streamlit que permite aos usuários fazer upload de vídeos, transcrevê-los automaticamente ou usar uma transcrição fornecida, e gerar resumos no estilo tl;dv. A aplicação também oferece funcionalidades de sincronização entre o resumo e o vídeo.

## Funcionalidades

- Upload de vídeo (formatos suportados: mp4, avi, mov)
- Upload opcional de arquivo de transcrição em formato txt
- Transcrição automática de vídeo usando OpenAI Whisper
- Geração de resumo no estilo tl;dv
- Sincronização entre resumo e vídeo
- Download de resumo e transcrição completa em formato SRT
- Autenticação via Google OAuth

## Requisitos

- Python 3.7+
- Bibliotecas Python (ver `requirements.txt`)
- Conta Google Cloud para autenticação OAuth
- Chave de API do OpenAI

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
   GOOGLE_CLIENT_ID=seu_client_id_do_google
   GOOGLE_CLIENT_SECRET=seu_client_secret_do_google
   REDIRECT_URI=http://localhost:8501/
   ```

## Uso

1. Execute a aplicação Streamlit:
   ```
   streamlit run transcrita_video.py
   ```

2. Acesse a aplicação através do navegador (geralmente em `http://localhost:8501`).

3. Faça login com sua conta Google.

4. Faça upload de um vídeo e, opcionalmente, de um arquivo de transcrição em formato txt.

5. Se não fornecer uma transcrição, use a opção de transcrição automática.

6. Visualize o resumo gerado e a transcrição completa.

7. Use os links de timestamp para navegar no vídeo.

8. Faça o download do resumo e da transcrição completa em formato SRT.

## Estrutura do Projeto

- `transcrita_video.py`: Arquivo principal contendo o código da aplicação Streamlit.
- `requirements.txt`: Lista de dependências do projeto.
- `imagens/`: Diretório contendo imagens usadas na aplicação (como o logo do Google).
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
