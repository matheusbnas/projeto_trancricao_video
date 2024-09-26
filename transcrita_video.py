import streamlit as st
import re
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
from pathlib import Path
import tempfile
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip
import os
import base64
import logging
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import srt
import datetime
import shutil
import hashlib
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from io import BytesIO

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurar cliente OpenAI
# openai.api_key = st.secrets["OPENAI_API_KEY"]
#client = OpenAI()

# Load environment variables
_ = load_dotenv(find_dotenv())

# Configurar pastas temporárias
PASTA_TEMP = Path(tempfile.gettempdir())
ARQUIVO_AUDIO_TEMP = PASTA_TEMP / 'audio.mp3'
ARQUIVO_VIDEO_TEMP = PASTA_TEMP / 'video.mp4'

MAX_CHUNK_SIZE = 25 * 1024 * 1024  # 25 MB em bytes

st.set_page_config(page_title="Resumo de Transcrição de Vídeo", page_icon="🎥", layout="wide")

# Remova ou comente esta linha
# client = OpenAI()

# Adicione esta função para obter o cliente OpenAI
def get_openai_client():
    if "openai_client" not in st.session_state:
        api_key = st.session_state.get("openai_api_key")
        if api_key:
            st.session_state.openai_client = OpenAI(api_key=api_key)
        else:
            st.error("Chave da API OpenAI não encontrada. Por favor, faça login novamente.")
            return None
    return st.session_state.openai_client

def get_openai_api_key():
    return st.session_state.get("openai_api_key")

def validate_openai_api_key(api_key):
    try:
        test_client = OpenAI(api_key=api_key)
        test_client.models.list()
        return True
    except Exception as e:
        st.error(f"Erro ao validar a chave API do OpenAI: {str(e)}")
        return False

def check_password():
    if "authentication_status" not in st.session_state:
        st.session_state["authentication_status"] = False

    if not st.session_state["authentication_status"]:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        openai_api_key = st.text_input("OpenAI API Key", type="password")

        if st.button("Login"):
            if username in st.secrets["users"]:
                if st.secrets["users"][username]["password"] == password:
                    if validate_openai_api_key(openai_api_key):
                        st.session_state["authentication_status"] = True
                        st.session_state["username"] = username
                        st.session_state["user_role"] = st.secrets["users"][username]["role"]
                        st.session_state["openai_api_key"] = openai_api_key
                        st.success("Login com sucesso")
                        return True
                    else:
                        st.error("Chave da OpenAI API inválida")
                else:
                    st.error("Senha inválida")
            else:
                st.error("Usuário não encontrado")
        return False
    return True

# Função para configurar o slidebar
def sidebar():
    with st.sidebar:
        st.image("images/logo_google.jpg", width=200)
        st.title("Assistente de Transcrição de Vídeo")
        st.header("SEJA BEM VINDO!")
        st.write(f"Olá, {st.session_state.get('username', 'Usuário')}!")

        # Configurações do modelo OpenAI
        st.write("**Ajuste de parâmetros do modelo da OpenAI**")
        model = st.selectbox(
            "Modelo OpenAI",
            ["gpt-4o-mini", "gpt-4o-mini-2024-07-18"],
            key="model_selectbox"
        )
        max_tokens = st.slider(
            "Máximo de Tokens", 
            4000, 10000, 
            16000,
            key="max_tokens_slider"
        )
        temperature = st.slider(
            "Temperatura", 
            0.0, 1.0, 
            0.7,
            key="temperature_slider"
        )

        if st.button("Logout"):
            st.session_state["authentication_status"] = False
            st.session_state["openai_api_key"] = None
            st.session_state["username"] = None
            st.session_state["user_role"] = None
            st.rerun()

        st.markdown("[Matheus Bernardes](https://www.linkedin.com/in/matheusbnas)")
        st.markdown("Desenvolvido por [Matech 3D](https://matech3d.com.br/)")

    return model, max_tokens, temperature

def split_audio(audio_path, chunk_duration=300):  # 5 minutos por chunk
    audio = AudioFileClip(audio_path)
    duration = audio.duration
    chunks = []
    
    for start in range(0, int(duration), chunk_duration):
        end = min(start + chunk_duration, duration)
        chunk = audio.subclip(start, end)
        chunk_path = f"{audio_path}_{start}_{end}.mp3"
        chunk.write_audiofile(chunk_path)
        chunks.append((chunk_path, start))
    
    audio.close()
    return chunks

@st.cache_data
def transcreve_audio_chunk(chunk_path, prompt=""):
    client = get_openai_client()
    if not client:
        return None

    with open(chunk_path, 'rb') as arquivo_audio:
        transcricao = client.audio.transcriptions.create(
            model='whisper-1',
            language='pt',
            response_format='srt',
            file=arquivo_audio,
            prompt=prompt,
        )
        return transcricao

def ajusta_tempo_srt(srt_content, offset):
    subtitles = list(srt.parse(srt_content))
    for sub in subtitles:
        sub.start += datetime.timedelta(seconds=offset)
        sub.end += datetime.timedelta(seconds=offset)
    return srt.compose(subtitles)

@st.cache_data
def gera_resumo_tldv(transcricao, model, max_tokens, temperature):
    client = get_openai_client()
    if not client:
        return None

    # Preparar a transcrição com timestamps originais
    linhas = transcricao.split('\n')
    transcricao_com_timestamps = []
    for i in range(0, len(linhas), 4):
        if i+3 < len(linhas):
            numero = linhas[i]
            tempos = linhas[i+1]
            conteudo = linhas[i+2]
            transcricao_com_timestamps.append(f"{numero}\n{tempos}\n{conteudo}")

    transcricao_formatada = "\n\n".join(transcricao_com_timestamps)

    try:
        resposta = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Você é um assistente especializado em criar resumos concisos e informativos no estilo do aplicativo tl;dv. Identifique e resuma as pautas mais importantes do vídeo, mantendo o formato SRT original."},
                {"role": "user", "content": f"Crie um resumo das pautas mais importantes desta transcrição, mantendo o formato SRT. Use os timestamps originais e tópicos chave. Mantenha o formato exato do SRT, incluindo números de sequência, timestamps e linhas em branco entre as entradas. Utilize apenas os timestamps fornecidos, não crie novos. Comece diretamente com o número 1 e o primeiro timestamp:\n\n{transcricao_formatada}"}
            ],
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        resumo = resposta.choices[0].message.content
        
        # Verificar se o resumo está no formato SRT
        if not re.match(r'^\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n', resumo):
            # Se não estiver no formato SRT, forçar a formatação
            linhas_resumo = resumo.split('\n')
            resumo_formatado = []
            for i, linha in enumerate(linhas_resumo):
                if linha.strip():
                    tempo_inicio = f"00:{i:02d}:00,000"
                    tempo_fim = f"00:{i+1:02d}:00,000"
                    resumo_formatado.extend([
                        str(i+1),
                        f"{tempo_inicio} --> {tempo_fim}",
                        linha,
                        ""
                    ])
            resumo = "\n".join(resumo_formatado).strip()
        
        return resumo
    except Exception as e:
        st.error(f"Erro ao gerar resumo: {str(e)}")
        return None

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

def formata_resumo_com_links(resumo_srt, video_path):
    subtitles = list(srt.parse(resumo_srt))
    resumo_formatado = ""
    for sub in subtitles:
        # Converter timedelta para segundos
        segundos_totais = int(sub.start.total_seconds())
        # Formatar o timestamp manualmente
        minutos, segundos = divmod(segundos_totais, 60)
        timestamp = f"{minutos:02d}:{segundos:02d}"
        link = f'<a href="#" onclick="seekVideo(\'{video_path}\', {segundos_totais}); return false;">[{timestamp}]</a>'
        resumo_formatado += f"{link} - {sub.content}<br>"
    return resumo_formatado

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

def gera_resumo_e_transcricao(srt_content, model, max_tokens, temperature):
    resumo_srt = gera_resumo_tldv(srt_content, model, max_tokens, temperature)
    
    if resumo_srt is None:
        st.error("Não foi possível gerar o resumo. Por favor, tente novamente.")
        return None, srt_content
    
    return resumo_srt, srt_content  # Retornando resumo em SRT e transcrição completa em SRT

def process_video(video_path):
    try:
        audio_path = video_path.replace(".mp4", ".mp3")
        with VideoFileClip(video_path) as video:
            video.audio.write_audiofile(audio_path)
        
        audio_chunks = split_audio(audio_path)
        full_transcript = ""
        
        for chunk_path, start_time in audio_chunks:
            chunk_transcript = transcreve_audio_chunk(chunk_path)
            adjusted_transcript = ajusta_tempo_srt(chunk_transcript, start_time)
            full_transcript += adjusted_transcript + "\n\n"
            os.remove(chunk_path)  # Remove o chunk de áudio após a transcrição
        
        return full_transcript
    finally:
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except PermissionError:
                logger.warning(f"Não foi possível remover o arquivo de áudio temporário: {audio_path}")

def process_video_chunk(chunk, chunk_number, total_chunks, session_id):
    chunk_dir = PASTA_TEMP / session_id
    chunk_dir.mkdir(exist_ok=True)
    chunk_file = chunk_dir / f"chunk_{chunk_number}.mp4"
    
    with open(chunk_file, "wb") as f:
        f.write(chunk)
    
    if chunk_number == total_chunks - 1:
        # Combinar todos os chunks
        final_video = chunk_dir / "final_video.mp4"
        with open(final_video, "wb") as outfile:
            for i in range(total_chunks):
                chunk_file = chunk_dir / f"chunk_{i}.mp4"
                outfile.write(chunk_file.read_bytes())
                chunk_file.unlink()  # Remove o chunk após combinar
        
        return str(final_video)
    return None

def create_pdf(content, filename):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    flowables = []

    for line in content.split('\n'):
        p = Paragraph(line, styles['Normal'])
        flowables.append(p)
        flowables.append(Spacer(1, 12))

    doc.build(flowables)
    buffer.seek(0)
    return buffer

def create_download_link_pdf(pdf_buffer, link_text, filename):
    b64 = base64.b64encode(pdf_buffer.getvalue()).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">{link_text}</a>'
    return href

def page(model, max_tokens, temperature):
    st.title("Resumo de Transcrição de Vídeo (Estilo tl;dv)")

    if 'session_id' not in st.session_state:
        st.session_state.session_id = hashlib.md5(str(datetime.datetime.now()).encode()).hexdigest()

    uploaded_video = st.file_uploader("Faça upload do vídeo", type=['mp4', 'avi', 'mov'])
    uploaded_transcript = st.file_uploader("Faça upload da transcrição (opcional, .txt)", type=['txt'])
    
    if uploaded_video:
        file_size = uploaded_video.size
        st.write(f"Tamanho do arquivo: {file_size / (1024 * 1024):.2f} MB")

        chunk_size = 200 * 1024 * 1024  # 200MB chunks
        total_chunks = -(-file_size // chunk_size)  # Ceil division

        progress_bar = st.progress(0)
        status_text = st.empty()

        final_video_path = None
        for i in range(total_chunks):
            status_text.text(f"Fazendo upload do chunk {i+1}/{total_chunks}")
            start = i * chunk_size
            end = min((i + 1) * chunk_size, file_size)
            chunk = uploaded_video.read(end - start)
            result = process_video_chunk(chunk, i, total_chunks, st.session_state.session_id)
            if result:
                final_video_path = result
            progress_bar.progress((i + 1) / total_chunks)

        if final_video_path:
            status_text.text("Processando o vídeo...")
            try:
                srt_content = None

                if uploaded_transcript:
                    txt_content = uploaded_transcript.getvalue().decode("utf-8")
                    srt_content = txt_to_srt(txt_content)
                    st.success("Arquivo TXT convertido para SRT com sucesso!")
                else:
                    if st.button("Transcrever vídeo automaticamente"):
                        st.info("Transcrevendo o vídeo automaticamente... Isso pode levar alguns minutos.")
                        try:
                            transcript = process_video(final_video_path)
                            srt_content = transcript
                            
                            if srt_content:
                                st.success("Transcrição automática concluída!")
                            else:
                                st.error("Não foi possível realizar a transcrição automática. Por favor, verifique as dependências do projeto.")
                        except Exception as e:
                            st.error(f"Erro durante a transcrição: {str(e)}")
                            logger.exception("Erro durante a transcrição do vídeo")
                    else:
                        st.warning("Nenhuma transcrição fornecida. Clique no botão acima para transcrever automaticamente.")

                if srt_content:
                    resumo_srt, transcript_srt = gera_resumo_e_transcricao(srt_content, model, max_tokens, temperature)

                    st.success("Processamento concluído!")

                    # Exibir resumo estilo tl;dv com links clicáveis
                    st.subheader("Resumo das Pautas Importantes:")
                    resumo_formatado = formata_resumo_com_links(resumo_srt, final_video_path)
                    st.markdown(resumo_formatado, unsafe_allow_html=True)

                    # Exibir transcrição completa
                    st.subheader("Transcrição Completa:")
                    st.text_area("Transcrição", processa_srt(transcript_srt), height=300)

                    # Exibir vídeo
                    st.subheader("Vídeo Original:")
                    st.video(final_video_path)

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

                    # Criar PDFs e SRTs
                    resumo_pdf = create_pdf(processa_srt(resumo_srt), "resumo.pdf")
                    transcript_pdf = create_pdf(processa_srt(transcript_srt), "transcricao_completa.pdf")
                    
                    resumo_srt_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.srt')
                    resumo_srt_file.write(resumo_srt)
                    resumo_srt_file.close()
                    
                    transcript_srt_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.srt')
                    transcript_srt_file.write(transcript_srt)
                    transcript_srt_file.close()

                    # Criar abas para download
                    st.subheader("Download dos Arquivos")
                    tab1, tab2 = st.tabs(["Resumo", "Transcrição Completa"])
                    
                    with tab1:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(create_download_link_pdf(resumo_pdf, "Baixar Resumo (PDF)", "resumo.pdf"), unsafe_allow_html=True)
                        with col2:
                            st.markdown(create_download_link(resumo_srt_file.name, "Baixar Resumo (SRT)"), unsafe_allow_html=True)

                    with tab2:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(create_download_link_pdf(transcript_pdf, "Baixar Transcrição Completa (PDF)", "transcricao_completa.pdf"), unsafe_allow_html=True)
                        with col2:
                            st.markdown(create_download_link(transcript_srt_file.name, "Baixar Transcrição Completa (SRT)"), unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Ocorreu um erro durante o processamento: {str(e)}")
                logger.exception("Erro durante o processamento do vídeo")
            
            finally:
                # Limpar os arquivos temporários
                try:
                    for item in os.listdir(PASTA_TEMP / st.session_state.session_id):
                        if item != "final_video.mp4":
                            os.remove(PASTA_TEMP / st.session_state.session_id / item)
                except Exception as e:
                    logger.warning(f"Não foi possível remover todos os arquivos temporários: {str(e)}")

                for file in ['resumo_srt_file', 'transcript_srt_file']:
                    if file in locals() and os.path.exists(locals()[file].name):
                        try:
                            os.remove(locals()[file].name)
                        except Exception as e:
                            logger.warning(f"Não foi possível remover o arquivo temporário {file}: {str(e)}")

    else:
        st.warning("Por favor, faça upload de um vídeo para continuar.")

def main():
    if check_password():
        # Sempre renderizar a sidebar
        model, max_tokens, temperature = sidebar()
        
        # Atualizar o estado da sessão com as configurações mais recentes
        st.session_state.sidebar_config = (model, max_tokens, temperature)
        
        # Chamar a página principal com as configurações atualizadas
        page(model, max_tokens, temperature)
    else:
        st.warning("Você não tem permissão para acessar essa página.")

if __name__ == "__main__":
    main()