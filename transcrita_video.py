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
import shutil

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
    
    # Carregando o logo do Google
    google_logo_path = "imagens/logo_google.jpg"
    
    # Verificando se o arquivo existe
    if os.path.exists(google_logo_path):
        with open(google_logo_path, "rb") as f:
            google_logo_base64 = base64.b64encode(f.read()).decode()
    else:
        st.error(f"Arquivo de logo não encontrado: {google_logo_path}")
        return

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
        <img src="data:image/jpeg;base64,{google_logo_base64}" alt="Google logo">
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

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def txt_to_srt(txt_content):
    lines = txt_content.split('\n')
    subtitles = []
    for i, line in enumerate(lines, start=1):
        if line.strip():  # ignora linhas vazias
            start_time = datetime.timedelta(seconds=i*5)  # cada linha dura 5 segundos
            end_time = start_time + datetime.timedelta(seconds=5)
            subtitle = srt.Subtitle(index=i, start=start_time, end=end_time, content=line)
            subtitles.append(subtitle)
    return srt.compose(subtitles)

def gera_resumo_e_transcricao(srt_content):
    transcript_text = processa_srt(srt_content)
    resumo_tldv = gera_resumo_tldv(transcript_text)
    
    # Convertendo o resumo para formato SRT
    resumo_srt = txt_to_srt(resumo_tldv)
    
    return resumo_srt, srt_content  # Retornando resumo em SRT e transcrição completa em SRT

def process_video(video_path):
    try:
        audio_path = video_path.replace(".mp4", ".mp3")
        with VideoFileClip(video_path) as video:
            video.audio.write_audiofile(audio_path)
        transcript = transcreve_audio(audio_path)
        return transcript
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)

def handle_video_upload(uploaded_file):
    temp_dir = tempfile.mkdtemp()
    temp_video_path = os.path.join(temp_dir, "temp_video.mp4")
    
    with open(temp_video_path, "wb") as f:
        f.write(uploaded_file.getvalue())
    
    return temp_video_path, temp_dir

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
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"Logado como: {user_info['email']}")
        with col2:
            if st.button("Logout"):
                logout()

    uploaded_video = st.file_uploader("Faça upload do vídeo", type=['mp4', 'avi', 'mov'])
    uploaded_transcript = st.file_uploader("Faça upload da transcrição (opcional, .txt)", type=['txt'])

    if uploaded_video:
        file_size = uploaded_video.size
        st.write(f"Tamanho do arquivo: {file_size / (1024 * 1024):.2f} MB")

        with st.spinner("Processando o vídeo..."):
            try:
                temp_video_path, temp_dir = handle_video_upload(uploaded_video)

                srt_content = None

                if uploaded_transcript:
                    txt_content = uploaded_transcript.getvalue().decode("utf-8")
                    srt_content = txt_to_srt(txt_content)
                    st.success("Arquivo TXT convertido para SRT com sucesso!")
                else:
                    if st.button("Transcrever vídeo automaticamente"):
                        st.info("Transcrevendo o vídeo automaticamente... Isso pode levar alguns minutos.")
                        
                        full_transcript = process_video(temp_video_path)
                        
                        srt_content = txt_to_srt(full_transcript)
                        
                        if srt_content:
                            st.success("Transcrição automática concluída!")
                        else:
                            st.error("Não foi possível realizar a transcrição automática. Por favor, verifique as dependências do projeto.")
                    else:
                        st.warning("Nenhuma transcrição fornecida. Clique no botão acima para transcrever automaticamente.")

                if srt_content:
                    resumo_srt, transcript_srt = gera_resumo_e_transcricao(srt_content)

                    st.success("Processamento concluído!")

                    # Exibir resumo estilo tl;dv com links clicáveis
                    st.subheader("Resumo das Pautas Importantes:")
                    resumo_formatado = formata_resumo_com_links(resumo_srt, temp_video_path)
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

                    # Salvar o resumo em um arquivo temporário SRT
                    resumo_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.srt')
                    resumo_file.write(resumo_srt)
                    resumo_file.close()

                    # Criar link de download para o resumo SRT
                    st.markdown(create_download_link(resumo_file.name, "Baixar resumo (SRT)"), unsafe_allow_html=True)

                    # Exibir transcrição completa
                    st.subheader("Transcrição Completa:")
                    st.text_area("Transcrição", processa_srt(transcript_srt), height=300)

                    # Salvar a transcrição completa em um arquivo temporário SRT
                    transcript_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.srt')
                    transcript_file.write(transcript_srt)
                    transcript_file.close()

                    # Criar link de download para a transcrição completa SRT
                    st.markdown(create_download_link(transcript_file.name, "Baixar transcrição completa (SRT)"), unsafe_allow_html=True)

                    # Exibir vídeo
                    st.subheader("Vídeo Original:")
                    st.video(temp_video_path)

            except Exception as e:
                st.error(f"Ocorreu um erro durante o processamento: {str(e)}")
                logger.exception("Erro durante o processamento do vídeo")
            
            finally:
                # Limpar os arquivos temporários
                if 'temp_dir' in locals():
                    shutil.rmtree(temp_dir, ignore_errors=True)
                if 'resumo_file' in locals() and os.path.exists(resumo_file.name):
                    os.remove(resumo_file.name)
                if 'transcript_file' in locals() and os.path.exists(transcript_file.name):
                    os.remove(transcript_file.name)

    else:
        st.warning("Por favor, faça upload de um vídeo para continuar.")

if __name__ == "__main__":
    main()