import streamlit as st
import re
import openai
from pathlib import Path
import tempfile
from moviepy.editor import VideoFileClip
import os
import base64
import logging
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import srt
import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurar cliente OpenAI
openai.api_key = st.secrets["OPENAI_API_KEY"]
client = openai.OpenAI()

# Configurar pastas temporárias
PASTA_TEMP = Path(tempfile.gettempdir())
ARQUIVO_AUDIO_TEMP = PASTA_TEMP / 'audio.mp3'
ARQUIVO_VIDEO_TEMP = PASTA_TEMP / 'video.mp4'

# Configurações OAuth
CLIENT_CONFIG = {
    "web": {
        "client_id": st.secrets["GOOGLE_CLIENT_ID"],
        "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [st.secrets["REDIRECT_URI"]],
    }
}

SCOPES = ['https://www.googleapis.com/auth/userinfo.email', 'openid']

def create_flow():
    return Flow.from_client_config(
        client_config=CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=CLIENT_CONFIG['web']['redirect_uris'][0]
    )

def google_login_button():
    flow = create_flow()
    auth_url, _ = flow.authorization_url(prompt="consent")
    
    # Google logo em base64
    google_logo = st.image('imagens/logo_google.jpg')
    button_html = f"""
    <style>
    .google-btn {{
        display: inline-flex;
        align-items: center;
        background-color: white;
        color: #757575;
        border: 1px solid #dadce0;
        border-radius: 4px;
        padding: 0 12px;
        font-size: 14px;
        font-weight: 500;
        font-family: 'Roboto', Arial, sans-serif;
        cursor: pointer;
        height: 40px;
        text-decoration: none;
    }}
    .google-btn:hover {{
        background-color: #f8f9fa;
        border-color: #d2e3fc;
    }}
    .google-btn img {{
        margin-right: 8px;
        width: 18px;
        height: 18px;
    }}
    .google-btn span {{
        padding: 10px 0;
    }}
    </style>
    <a href="{auth_url}" class="google-btn">
        <img src="{google_logo}" alt="Google logo">
        <span>Fazer login com o Google</span>
    </a>
    """
    st.markdown(button_html, unsafe_allow_html=True)

def transcreve_audio(caminho_audio, prompt=""):
    with open(caminho_audio, 'rb') as arquivo_audio:
        transcricao = client.audio.transcriptions.create(
            model='whisper-1',
            language='pt',
            response_format='srt',
            file=arquivo_audio,
            prompt=prompt,
        )
        return transcricao

def salva_audio_do_video(video_bytes):
    with open(ARQUIVO_VIDEO_TEMP, mode='wb') as video_f:
        video_f.write(video_bytes.read())
    moviepy_video = VideoFileClip(str(ARQUIVO_VIDEO_TEMP))
    moviepy_video.audio.write_audiofile(str(ARQUIVO_AUDIO_TEMP))

def gera_resumo_tldv(transcricao):
    resposta = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Você é um assistente especializado em criar resumos concisos e informativos no estilo do aplicativo tl;dv. Identifique e resuma as pautas mais importantes do vídeo, incluindo timestamps precisos."},
            {"role": "user", "content": f"Crie um resumo das pautas mais importantes desta transcrição, no formato do tl;dv. Inclua timestamps precisos (minutos:segundos) e tópicos chave. Formato desejado: '[MM:SS] - Tópico: Descrição breve':\n\n{transcricao}"}
        ]
    )
    return resposta.choices[0].message.content

def processa_srt(srt_content):
    subtitles = list(srt.parse(srt_content))
    transcript_text = ""
    for sub in subtitles:
        start_time = str(sub.start).split('.')[0]  # Remove microssegundos
        transcript_text += f"{start_time} - {sub.content}\n"
    return transcript_text

def create_download_link(file_path, link_text):
    with open(file_path, 'rb') as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    href = f'<a href="data:file/txt;base64,{b64}" download="{os.path.basename(file_path)}">{link_text}</a>'
    return href

def formata_resumo_com_links(resumo, video_path):
    linhas = resumo.split('\n')
    resumo_formatado = ""
    for linha in linhas:
        match = re.match(r'\[(\d{2}:\d{2})\] - (.+)', linha)
        if match:
            timestamp = match.group(1)
            conteudo = match.group(2)
            segundos = sum(int(x) * 60 ** i for i, x in enumerate(reversed(timestamp.split(':'))))
            link = f'<a href="#" onclick="seekVideo(\'{video_path}\', {segundos}); return false;">[{timestamp}]</a>'
            resumo_formatado += f"{link} - {conteudo}<br>"
        else:
            resumo_formatado += linha + "<br>"
    return resumo_formatado

def main():
    st.title("Resumo de Transcrição de Vídeo (Estilo tl;dv)")

    if 'credentials' not in st.session_state:
        st.session_state.credentials = None

    if st.session_state.credentials is None:
        st.write("Por favor, faça login com sua conta do Google para continuar.")
        google_login_button()
        
        if 'code' in st.query_params:
            code = st.query_params['code']
            flow = create_flow()
            flow.fetch_token(code=code)
            st.session_state.credentials = flow.credentials
            st.rerun()
    else:
        credentials = st.session_state.credentials
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        st.write(f"Logado como: {user_info['email']}")

        uploaded_video = st.file_uploader("Faça upload do vídeo", type=['mp4', 'avi', 'mov'])
        uploaded_transcript = st.file_uploader("Faça upload da transcrição (opcional)", type=['srt'])

        if uploaded_video:
            with st.spinner("Processando o vídeo..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_video.name.split('.')[-1]}") as temp_video:
                    temp_video.write(uploaded_video.getbuffer())
                    video_path = temp_video.name

                srt_content = None

                if uploaded_transcript:
                    srt_content = uploaded_transcript.getvalue().decode("utf-8")
                    st.success("Transcrição SRT fornecida carregada com sucesso!")
                else:
                    if st.button("Transcrever vídeo automaticamente"):
                        st.info("Transcrevendo o vídeo automaticamente... Isso pode levar alguns minutos.")
                        salva_audio_do_video(uploaded_video)
                        srt_content = transcreve_audio(ARQUIVO_AUDIO_TEMP)
                        if srt_content:
                            st.success("Transcrição automática concluída!")
                        else:
                            st.error("Não foi possível realizar a transcrição automática. Por favor, verifique as dependências do projeto.")
                    else:
                        st.warning("Nenhuma transcrição fornecida. Clique no botão acima para transcrever automaticamente.")

                if srt_content:
                    transcript_text = processa_srt(srt_content)
                    resumo_tldv = gera_resumo_tldv(transcript_text)

                    st.success("Processamento concluído!")

                    # Exibir resumo estilo tl;dv com links clicáveis
                    st.subheader("Resumo das Pautas Importantes:")
                    resumo_formatado = formata_resumo_com_links(resumo_tldv, video_path)
                    st.markdown(resumo_formatado, unsafe_allow_html=True)

                    # Adicionar JavaScript para controle do vídeo
                    st.markdown("""
                    <script>
                    function seekVideo(videoPath, seconds) {
                        const video = document.querySelector('video[src="' + videoPath + '"]');
                        if (video) {
                            video.currentTime = seconds;
                            video.play();
                        }
                    }
                    </script>
                    """, unsafe_allow_html=True)

                    # Salvar o resumo em um arquivo temporário
                    resumo_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt')
                    resumo_file.write(resumo_tldv)
                    resumo_file.close()

                    # Criar link de download para o resumo
                    st.markdown(create_download_link(resumo_file.name, "Baixar resumo"), unsafe_allow_html=True)

                    # Exibir transcrição completa
                    st.subheader("Transcrição Completa:")
                    st.text_area("Transcrição", transcript_text, height=300)

                    # Salvar a transcrição completa em um arquivo temporário
                    transcript_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt')
                    transcript_file.write(transcript_text)
                    transcript_file.close()

                    # Criar link de download para a transcrição completa
                    st.markdown(create_download_link(transcript_file.name, "Baixar transcrição completa"), unsafe_allow_html=True)

                    # Exibir vídeo
                    st.subheader("Vídeo Original:")
                    st.video(video_path)

                    # Limpar os arquivos temporários
                    os.unlink(video_path)
                    os.unlink(resumo_file.name)
                    os.unlink(transcript_file.name)
                    if os.path.exists(str(ARQUIVO_AUDIO_TEMP)):
                        os.unlink(str(ARQUIVO_AUDIO_TEMP))

if __name__ == "__main__":
    main()