import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
import os
import re
import logging
import tempfile
import requests
import hashlib
import datetime
from moviepy.editor import VideoFileClip
from utils import *

# Load environment variables
_ = load_dotenv(find_dotenv())

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


st.set_page_config(page_title="Resumo de Transcrição de Vídeo",
                   page_icon="🎥", layout="wide")


def get_openai_client():
    if "openai_client" not in st.session_state:
        api_key = st.session_state.get("openai_api_key")
        if api_key:
            st.session_state.openai_client = OpenAI(api_key=api_key)
        else:
            st.error(
                "Chave da API OpenAI não encontrada. Por favor, faça login novamente.")
            return None
    return st.session_state.openai_client


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
                        st.rerun()  # Força o recarregamento da página após o login bem-sucedido
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
        st.image("images/escola_nomade.jpg", width=200)
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

        st.markdown(
            "[Matheus Bernardes](https://www.linkedin.com/in/matheusbnas)")
        st.markdown("Desenvolvido por [Matech AI](https://matechai.com/)")

    return model, max_tokens, temperature


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

# Função para usar o modelo WhisperX
# def transcribe_with_whisperx(video_path):
#     model = load_model("base")
#     result = transcribe(model, video_path, task="transcribe", language="pt")
#     return result.text


@st.cache_data
def gera_resumo_tldv(transcricao, model, max_tokens, temperature):
    client = get_openai_client()
    if not client:
        return None

    try:
        # Dividir a transcrição em partes menores se necessário
        max_chars = 15000  # Ajuste este valor conforme necessário
        transcricao_parts = [transcricao[i:i+max_chars]
                             for i in range(0, len(transcricao), max_chars)]

        resumo_completo = ""
        for part in transcricao_parts:
            resposta = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Você é um assistente especializado em criar resumos concisos e informativos."},
                    {"role": "user", "content": f"""Crie um resumo desta parte da transcrição, seguindo estas diretrizes:
                    1. Identifique os pontos principais do conteúdo sem repetições.
                    2. Escreva uma breve descrição para cada ponto importante.
                    3. Mantenha cada ponto conciso, mas informativo.
                    4. Cubra todo o conteúdo desta parte, não apenas o início.
                    5. Apresente os pontos em ordem cronológica.
                    6. Não inclua timestamps no resumo.
                    7. Verificar se o tempo da transcrição srt está compatível com o áudio do vídeo

                    Transcrição:
                    {part}"""}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            resumo_completo += resposta.choices[0].message.content + "\n\n"

        return resumo_completo.strip()
    except Exception as e:
        st.error(f"Erro ao gerar resumo: {str(e)}")
        return None


def process_audio_for_transcription(audio_path, duration_seconds=None):
    """
    Processa um arquivo de áudio para transcrição
    """
    try:
        logger.info(f"Iniciando processamento do áudio: {audio_path}")

        # Verificar se o arquivo de áudio existe
        if not os.path.exists(audio_path):
            raise FileNotFoundError(
                f"O arquivo de áudio não foi encontrado: {audio_path}")

        # Verificar se o arquivo tem tamanho > 0
        if os.path.getsize(audio_path) == 0:
            raise ValueError("O arquivo de áudio está vazio")

        # Dividir o áudio em chunks
        audio_chunks = split_audio(
            audio_path, chunk_duration=1200)  # 20 minutos por chunk
        full_transcript = ""

        logger.info(
            f"Iniciando transcrição de {len(audio_chunks)} chunks de áudio")

        # Processar cada chunk de áudio
        for i, (chunk_path, start_time) in enumerate(audio_chunks):
            logger.info(f"Processando chunk {i+1}/{len(audio_chunks)}")

            # Verificar se o chunk existe e tem tamanho > 0
            if not os.path.exists(chunk_path) or os.path.getsize(chunk_path) == 0:
                logger.warning(
                    f"Chunk {i+1} não existe ou está vazio, pulando...")
                continue

            chunk_size = os.path.getsize(chunk_path)
            logger.info(
                f"Tamanho do chunk: {chunk_size / (1024 * 1024):.2f} MB")

            chunk_transcript = transcreve_audio_chunk(chunk_path)
            if chunk_transcript:
                adjusted_transcript = ajusta_tempo_srt(
                    chunk_transcript, start_time)
                full_transcript += adjusted_transcript + "\n\n"

            # Remove o chunk de áudio após a transcrição
            try:
                os.remove(chunk_path)
            except Exception as e:
                logger.warning(
                    f"Não foi possível remover o chunk {chunk_path}: {str(e)}")

        logger.info("Transcrição completa")
        return full_transcript

    except Exception as e:
        logger.exception(f"Erro ao processar o áudio: {str(e)}")
        raise


def process_video(video_path_or_url):
    """
    Processa um arquivo de vídeo, extraindo o áudio e retornando a transcrição
    """
    temp_audio_file = None
    try:
        # Criar um arquivo temporário para o áudio
        temp_audio_file = tempfile.NamedTemporaryFile(
            delete=False, suffix='.mp3')
        temp_audio_file.close()
        audio_path = temp_audio_file.name

        logger.info(f"Iniciando processamento do vídeo: {video_path_or_url}")
        logger.info(f"Arquivo de áudio temporário criado: {audio_path}")

        # Extrair áudio do vídeo com tratamento de erro mais robusto
        try:
            with VideoFileClip(video_path_or_url) as video:
                if video.audio is None:
                    raise ValueError("O vídeo não possui faixa de áudio")

                audio = video.audio
                # Configurações mais robustas para write_audiofile
                audio.write_audiofile(
                    audio_path,
                    verbose=False,
                    logger=None,
                    bitrate="64k"
                )
        except Exception as e:
            logger.error(f"Erro ao extrair áudio: {str(e)}")
            raise

        logger.info(f"Áudio extraído e salvo em: {audio_path}")

        # Verificar se o arquivo de áudio foi criado corretamente
        if not os.path.exists(audio_path):
            raise FileNotFoundError(
                f"O arquivo de áudio não foi criado: {audio_path}")

        # Verificar se o arquivo tem tamanho > 0
        if os.path.getsize(audio_path) == 0:
            raise ValueError("O arquivo de áudio foi criado mas está vazio")

        # Processar o áudio extraído
        return process_audio_for_transcription(audio_path)

    except Exception as e:
        logger.exception(f"Erro ao processar o vídeo: {str(e)}")
        raise

    finally:
        # Limpar arquivo temporário
        if temp_audio_file and os.path.exists(temp_audio_file.name):
            try:
                os.remove(temp_audio_file.name)
            except Exception as e:
                logger.warning(
                    f"Não foi possível remover o arquivo temporário {temp_audio_file.name}: {str(e)}")

########################################
# FUNÇÕES DE TRANSCRIÇÃO DE VIDEO DO YOUTUBE
########################################


def process_youtube_video_simple(youtube_url):
    """
    Função simplificada para processar vídeos do YouTube usando yt-dlp
    """
    try:
        import yt_dlp

        # Configurações do yt-dlp mais robustas
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': '%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }

        # Baixar o áudio do vídeo
        with tempfile.TemporaryDirectory() as temp_dir:
            ydl_opts['outtmpl'] = os.path.join(temp_dir, '%(title)s.%(ext)s')

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Primeiro, extrair informações sem baixar
                try:
                    info = ydl.extract_info(youtube_url, download=False)
                    video_title = info.get('title', 'video_youtube')
                    video_duration = info.get('duration', 0)
                except Exception as e:
                    logger.warning(
                        f"Erro ao extrair informações do vídeo: {str(e)}")
                    video_title = 'video_youtube'
                    video_duration = 0

                # Agora baixar o áudio
                try:
                    info = ydl.extract_info(youtube_url, download=True)
                except Exception as e:
                    logger.error(f"Erro ao baixar vídeo: {str(e)}")
                    raise Exception(
                        f"Não foi possível baixar o vídeo: {str(e)}")

                # Encontrar o arquivo de áudio baixado
                audio_files = [f for f in os.listdir(
                    temp_dir) if f.endswith('.mp3')]
                if not audio_files:
                    raise Exception("Não foi possível baixar o áudio do vídeo")

                audio_path = os.path.join(temp_dir, audio_files[0])

                # Verificar se o arquivo tem tamanho > 0
                if os.path.getsize(audio_path) == 0:
                    raise Exception(
                        "O arquivo de áudio foi baixado mas está vazio")

                # Processar o áudio usando a função específica para áudio
                srt_content = process_audio_for_transcription(audio_path)

                # Retornar tanto o conteúdo SRT quanto o título do vídeo e duração
                return srt_content, video_title, video_duration

    except ImportError:
        st.error("Biblioteca yt-dlp não encontrada. Instale com: pip install yt-dlp")
        return None, None
    except Exception as e:
        logger.exception(f"Erro ao processar vídeo do YouTube: {str(e)}")
        st.error(f"Erro ao processar vídeo do YouTube: {str(e)}")
        return None, None

########################################
# FUNÇÕES DE PROCESSO DE TRANSCRIÇÃO EM SRT E PDF
########################################


def generate_summarized_srt_from_full(srt_content, client, model):
    """
    Generate a summarized SRT that maintains timing but provides concise summaries
    of key points with topic and explanation format.
    """
    segments = []
    current_segment = {}
    current_text = []

    # Parse original SRT content
    for line in srt_content.strip().split('\n'):
        line = line.strip()
        if line.isdigit():  # Segment number
            if current_segment:
                current_segment['text'] = ' '.join(current_text)
                segments.append(current_segment)
                current_segment = {}
                current_text = []
        elif '-->' in line:  # Timestamp
            start, end = line.split(' --> ')
            current_segment['start_time'] = start.strip()
            current_segment['end_time'] = end.strip()
        elif line:  # Content
            current_text.append(line)

    # Add last segment if exists
    if current_segment and current_text:
        current_segment['text'] = ' '.join(current_text)
        segments.append(current_segment)

    # Group segments into meaningful chunks
    chunk_size = 3  # Adjust based on your needs
    chunks = [segments[i:i + chunk_size]
              for i in range(0, len(segments), chunk_size)]

    # Generate summaries for each chunk
    summarized_segments = []
    for chunk in chunks:
        # Combine text from segments in chunk
        chunk_text = " ".join(seg['text'] for seg in chunk)

        # Generate summary using OpenAI with specific format prompt
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system",
                 "content": """Você é um especialista em criar resumos estruturados em português do Brasil.
                Para cada segmento, forneça um resumo EXATAMENTE neste formato:

                Título do tópico: Explicação concisa e direta do conteúdo.

                O título deve ser curto e direto, seguido de dois pontos.
                A explicação deve ser uma única frase clara e informativa.
                Cada resumo deve ter exatamente uma linha com o título e a explicação.

                Exemplo exato do formato:
                Curso Intensivo sobre Nietzsche: O curso foca em uma das obras mais significativas de Nietzsche, considerada por alguns como uma das maiores contribuições da humanidade."""},
                {"role": "user",
                 "content": f"Resuma este segmento no formato especificado: {chunk_text}"}
            ],
            max_tokens=150,
            temperature=0.4
        )

        summary = response.choices[0].message.content.strip()

        # Create new segment with summary
        summarized_segments.append({
            'start_time': chunk[0]['start_time'],
            'end_time': chunk[-1]['end_time'],
            'text': summary
        })

    # Convert summarized segments back to SRT format
    srt_output = ""
    for i, segment in enumerate(summarized_segments, 1):
        srt_output += f"{i}\n"
        srt_output += f"{segment['start_time']} --> {segment['end_time']}\n"
        srt_output += f"{segment['text']}\n\n"

    # Para a versão sem timestamps, criar uma versão separada com linhas em branco entre os segmentos
    text_only_output = "\n\n".join(
        segment['text'] for segment in summarized_segments)

    return srt_output, text_only_output


def process_single_video(drive_service, video_id, video_name, model, max_tokens, temperature):
    """
    Processa um vídeo individual do Google Drive
    """
    try:
        # Download do vídeo
        temp_video_path = download_video_from_drive(
            drive_service, video_id, video_name)

        if temp_video_path:
            # Processar transcrição
            srt_content = process_video(temp_video_path)
            if srt_content:
                st.success("✅ Transcrição concluída!")
                # Processar e salvar no Drive
                process_transcription(srt_content, model, max_tokens, temperature,
                                      video_name, None, drive_service, video_id)
            else:
                st.error("❌ Não foi possível realizar a transcrição.")

            # Limpar arquivo temporário
            try:
                os.remove(temp_video_path)
            except:
                pass
        else:
            st.error("❌ Erro ao fazer download do vídeo.")

    except Exception as e:
        st.error(f"❌ Erro durante a transcrição: {str(e)}")
        logger.exception("Erro durante a transcrição do vídeo do Drive")


def process_transcription(srt_content, model, max_tokens, temperature, video_path_or_filename, duration_seconds=None, drive_service=None, video_file_id=None):
    client = get_openai_client()
    if not client:
        return

    # Extrair o nome do arquivo original
    # Se for um caminho completo, extrair o nome; se for apenas o nome, usar diretamente
    if '/' in video_path_or_filename or '\\' in video_path_or_filename or video_path_or_filename.startswith(('http://', 'https://')):
        original_filename = extract_filename_from_path(video_path_or_filename)
    else:
        # Se for apenas o nome do arquivo (caso do upload local)
        original_filename = os.path.splitext(video_path_or_filename)[0]
        # Limpar caracteres especiais
        original_filename = re.sub(r'[<>:"/\\|?*]', '_', original_filename)

    # Status placeholder para mensagens de progresso
    status_placeholder = st.empty()
    status_placeholder.success(
        "Transcrição automática concluída! Gerando documentos...")

    # Generate summarized SRT and text-only version
    status_placeholder.info("Gerando resumo da transcrição...")
    summarized_srt, text_only_summary = generate_summarized_srt_from_full(
        srt_content, client, model)

    # Get video duration (only if we have a valid video path and duration wasn't provided)
    duracao_total_segundos = duration_seconds or 0
    if not duration_seconds and ('/' in video_path_or_filename or '\\' in video_path_or_filename or video_path_or_filename.startswith(('http://', 'https://'))):
        try:
            with VideoFileClip(video_path_or_filename) as video:
                duracao_total_segundos = int(video.duration)
        except Exception as e:
            logger.warning(
                f"Não foi possível obter a duração do vídeo: {str(e)}")

    # Create PDFs and SRTs with original filename
    status_placeholder.info("Gerando arquivos PDF e SRT...")
    transcript_pdf = create_pdf(processa_srt_sem_timestamp(
        srt_content), f"{original_filename}_transcricao_completa.pdf")
    summarized_pdf = create_pdf(
        text_only_summary, f"{original_filename}_transcricao_resumida.pdf")

    # Save SRT files with original filename
    summarized_srt_filename = f"{original_filename}_transcricao_resumida.srt"
    transcript_srt_filename = f"{original_filename}_transcricao_completa.srt"

    # Create SRT files in temp directory with proper names
    temp_dir = tempfile.gettempdir()
    summarized_srt_file_path = os.path.join(temp_dir, summarized_srt_filename)
    transcript_srt_file_path = os.path.join(temp_dir, transcript_srt_filename)

    with open(summarized_srt_file_path, 'w', encoding='utf-8') as f:
        f.write(summarized_srt)

    with open(transcript_srt_file_path, 'w', encoding='utf-8') as f:
        f.write(srt_content)

    # Remover mensagem de status
    status_placeholder.empty()

    # Mostrar mensagem final de sucesso
    st.success("Processamento completo! Todos os arquivos foram gerados.")

    # Create tabs for display
    tab1, tab2 = st.tabs([
        "Transcrição Resumida",
        "Transcrição Completa"
    ])

    with tab1:
        st.text_area("Transcrição Resumida", text_only_summary, height=300)

    with tab2:
        st.text_area("Transcrição Completa",
                     processa_srt(srt_content), height=300)

    # Download section
    st.subheader("Download dos Arquivos")
    tab1, tab2 = st.tabs(["Transcrição Resumida", "Transcrição Completa"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(create_download_link_pdf(summarized_pdf, "Baixar Transcrição Resumida (PDF)",
                        f"{original_filename}_transcricao_resumida.pdf"), unsafe_allow_html=True)
        with col2:
            st.markdown(create_download_link(summarized_srt_file_path, "Baixar Transcrição Resumida (SRT)",
                        f"{original_filename}_transcricao_resumida.srt"), unsafe_allow_html=True)

    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(create_download_link_pdf(transcript_pdf, "Baixar Transcrição Completa (PDF)",
                        f"{original_filename}_transcricao_completa.pdf"), unsafe_allow_html=True)
        with col2:
            st.markdown(create_download_link(transcript_srt_file_path, "Baixar Transcrição Completa (SRT)",
                        f"{original_filename}_transcricao_completa.srt"), unsafe_allow_html=True)

    # Salvar no Google Drive se especificado
    if drive_service and video_file_id:
        st.info("Salvando arquivos no Google Drive...")
        try:
            # Salvar arquivos na mesma pasta do vídeo original
            uploaded_files = save_transcription_to_drive(
                drive_service,
                video_file_id,
                srt_content,
                text_only_summary,
                original_filename
            )

            if uploaded_files:
                st.success("✅ Arquivos salvos no Google Drive com sucesso!")
                st.subheader("📁 Arquivos salvos no Google Drive")

                for file_info in uploaded_files:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(
                            f"**{file_info['name']}** - {file_info['type']}")
                    with col2:
                        st.markdown(
                            f"[🔗 Abrir no Drive]({file_info['link']})", unsafe_allow_html=True)
            else:
                st.warning(
                    "⚠️ Não foi possível salvar os arquivos no Google Drive.")

        except Exception as e:
            st.error(f"❌ Erro ao salvar no Google Drive: {str(e)}")
            logger.exception("Erro ao salvar arquivos no Google Drive")

    # Cleanup temporary files
    for file in [summarized_srt_file_path, transcript_srt_file_path]:
        try:
            os.remove(file)
        except Exception as e:
            logger.warning(
                f"Não foi possível remover o arquivo temporário {file}: {str(e)}")


def page(model, max_tokens, temperature):
    st.title("Resumo de Transcrição de Vídeo")

    if 'session_id' not in st.session_state:
        st.session_state.session_id = hashlib.md5(
            str(datetime.datetime.now()).encode()).hexdigest()

    video_source = st.radio("Escolha a fonte do vídeo:", [
                            "Upload Local", "YouTube", "Google Cloud Storage", "Google Drive"])

    if video_source == "Upload Local":
        uploaded_video = st.file_uploader(
            "Faça upload do vídeo", type=['mp4', 'avi', 'mov'])
        if uploaded_video:
            file_size = uploaded_video.size
            st.write(f"Tamanho do arquivo: {file_size / (1024 * 1024):.2f} MB")

            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
                temp_file.write(uploaded_video.read())
                temp_file_path = temp_file.name

            if st.button("Transcrever vídeo automaticamente"):
                st.info(
                    "Transcrevendo o vídeo automaticamente... Isso pode levar alguns minutos.")
                try:
                    srt_content = process_video(temp_file_path)
                    if srt_content:
                        st.success("Transcrição automática concluída!")
                        # Passar o nome original do arquivo para process_transcription
                        original_filename = uploaded_video.name
                        process_transcription(
                            srt_content, model, max_tokens, temperature, original_filename, None)
                    else:
                        st.error(
                            "Não foi possível realizar a transcrição automática.")
                except Exception as e:
                    st.error(f"Erro durante a transcrição: {str(e)}")
                    logger.exception("Erro durante a transcrição do vídeo")
                finally:
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)

    elif video_source == "Google Cloud Storage":
        gcs_video_url = st.text_input(
            "Digite a URL pública do vídeo no Google Cloud Storage")
        if gcs_video_url:
            st.write(f"URL do vídeo: {gcs_video_url}")

            if st.button("Transcrever vídeo do GCS"):
                st.info(
                    "Transcrevendo o vídeo do GCS... Isso pode levar alguns minutos.")
                try:
                    with st.spinner("Realizando transcrição..."):
                        srt_content = process_video(gcs_video_url)

                    if srt_content:
                        st.success("Transcrição automática concluída!")
                        process_transcription(
                            srt_content, model, max_tokens, temperature, gcs_video_url, None)
                    else:
                        st.error(
                            "Não foi possível realizar a transcrição automática.")
                except Exception as e:
                    st.error(f"Erro durante a transcrição: {str(e)}")
                    logger.exception("Erro durante a transcrição do vídeo")

    elif video_source == "YouTube":
        youtube_url = st.text_input("Digite a URL do vídeo do YouTube")
        if youtube_url:
            st.write(f"URL do vídeo: {youtube_url}")

            if st.button("Transcrever vídeo do YouTube"):
                st.info(
                    "Transcrevendo o vídeo do YouTube... Isso pode levar alguns minutos.")
                try:
                    with st.spinner("Realizando transcrição..."):
                        srt_content, video_title, video_duration = process_youtube_video_simple(
                            youtube_url)

                    if srt_content:
                        st.success("Transcrição automática concluída!")
                        # Usar o título do vídeo para nomear os arquivos
                        if video_title:
                            # Limpar o título para usar como nome de arquivo
                            clean_title = re.sub(
                                r'[<>:"/\\|?*]', '_', video_title)
                            process_transcription(
                                srt_content, model, max_tokens, temperature, clean_title, video_duration)
                        else:
                            process_transcription(
                                srt_content, model, max_tokens, temperature, youtube_url, video_duration)
                    else:
                        st.error(
                            "Não foi possível realizar a transcrição automática.")
                except Exception as e:
                    st.error(f"Erro durante a transcrição: {str(e)}")
                    logger.exception(
                        "Erro durante a transcrição do vídeo do YouTube")

    elif video_source == "Google Drive":
        st.subheader("Transcrição de Vídeos do Google Drive")

        # Verificar se o serviço do Drive está disponível
        drive_service = get_drive_service()

        if not drive_service:
            st.error(
                "Não foi possível conectar ao Google Drive. Verifique as credenciais.")
        else:
            # Opções de busca
            search_option = st.radio("Como deseja buscar os vídeos?", [
                "Buscar por nome",
                "Buscar em pasta específica",
                "Listar todos os vídeos"
            ])

            if search_option == "Transcrever vídeo por URL do Drive":
                drive_url = st.text_input(
                    "Cole aqui o link do vídeo ou pasta do Google Drive:",
                    placeholder="https://drive.google.com/file/d/VIDEO_ID/view ou https://drive.google.com/drive/folders/FOLDER_ID"
                )

                if drive_url:
                    if st.button("🎬 Processar Drive"):
                        with st.spinner("Analisando conteúdo do Google Drive..."):
                            try:
                                # Verificar se é URL de arquivo ou pasta
                                if '/file/d/' in drive_url:
                                    # É um arquivo específico
                                    video_id = drive_url.split(
                                        '/file/d/')[1].split('/')[0]

                                    # Obter informações do vídeo
                                    try:
                                        video_metadata = drive_service.files().get(
                                            fileId=video_id,
                                            fields='id,name,size,parents'
                                        ).execute()

                                        video_name = video_metadata.get(
                                            'name', 'video_drive')
                                        st.info(
                                            f"📹 Processando arquivo: {video_name}")

                                        # Processar o vídeo
                                        process_single_video(
                                            drive_service, video_id, video_name, model, max_tokens, temperature)

                                    except Exception as e:
                                        st.error(
                                            f"❌ Erro ao acessar o arquivo: {str(e)}")
                                        return

                                elif '/drive/folders/' in drive_url or '/folders/' in drive_url:
                                    # É uma pasta
                                    folder_id = None
                                    if '/drive/folders/' in drive_url:
                                        folder_id = drive_url.split(
                                            '/drive/folders/')[1].split('/')[0]
                                    elif '/folders/' in drive_url:
                                        folder_id = drive_url.split(
                                            '/folders/')[1].split('/')[0]

                                    if not folder_id:
                                        st.error(
                                            "❌ Não foi possível extrair o ID da pasta da URL fornecida.")
                                        return

                                    # Buscar vídeos na pasta
                                    videos = search_videos_in_drive(
                                        drive_service, folder_id=folder_id)

                                    if videos:
                                        st.success(
                                            f"✅ Encontrados {len(videos)} vídeo(s) na pasta!")
                                        st.subheader(
                                            "📹 Vídeos disponíveis para transcrição:")

                                        for i, video in enumerate(videos):
                                            col1, col2, col3 = st.columns(
                                                [3, 1, 1])
                                            with col1:
                                                st.write(
                                                    f"**{video['name']}**")
                                                if 'size' in video:
                                                    size_mb = int(
                                                        video['size']) / (1024 * 1024)
                                                    st.write(
                                                        f"Tamanho: {size_mb:.2f} MB")
                                            with col2:
                                                if st.button(f"🎬 Transcrever", key=f"transcribe_folder_{video['id']}"):
                                                    with st.spinner(f"Processando {video['name']}..."):
                                                        process_single_video(
                                                            drive_service, video['id'], video['name'], model, max_tokens, temperature)
                                            with col3:
                                                st.write("")
                                    else:
                                        st.warning(
                                            "⚠️ Nenhum vídeo encontrado nesta pasta.")

                                else:
                                    st.error(
                                        "❌ URL não reconhecida. Use uma URL de arquivo ou pasta do Google Drive.")
                                    st.info("💡 Formatos aceitos:")
                                    st.info(
                                        "• Arquivo: https://drive.google.com/file/d/VIDEO_ID/view")
                                    st.info(
                                        "• Pasta: https://drive.google.com/drive/folders/FOLDER_ID")

                            except Exception as e:
                                st.error(
                                    f"❌ Erro durante o processamento: {str(e)}")
                                logger.exception(
                                    "Erro durante o processamento do Drive")

            elif search_option == "Buscar por nome":
                search_query = st.text_input(
                    "Digite o nome do vídeo para buscar:")
                if search_query:
                    videos = search_videos_in_drive(
                        drive_service, query=search_query)

                    if videos:
                        st.write(f"Encontrados {len(videos)} vídeo(s):")
                        for video in videos:
                            col1, col2, col3 = st.columns([3, 1, 1])
                            with col1:
                                st.write(f"**{video['name']}**")
                                if 'size' in video:
                                    size_mb = int(
                                        video['size']) / (1024 * 1024)
                                    st.write(f"Tamanho: {size_mb:.2f} MB")
                            with col2:
                                if st.button(f"Transcrever", key=f"transcribe_{video['id']}"):
                                    with st.spinner(f"Fazendo download e transcrevendo {video['name']}..."):
                                        try:
                                            # Download do vídeo
                                            temp_video_path = download_video_from_drive(
                                                drive_service, video['id'], video['name'])
                                            if temp_video_path:
                                                # Processar transcrição
                                                srt_content = process_video(
                                                    temp_video_path)
                                                if srt_content:
                                                    st.success(
                                                        "Transcrição concluída!")
                                                    process_transcription(
                                                        srt_content, model, max_tokens, temperature, video['name'], None, drive_service, video['id'])
                                                else:
                                                    st.error(
                                                        "Não foi possível realizar a transcrição.")

                                                # Limpar arquivo temporário
                                                try:
                                                    os.remove(temp_video_path)
                                                except:
                                                    pass
                                            else:
                                                st.error(
                                                    "Erro ao fazer download do vídeo.")
                                        except Exception as e:
                                            st.error(
                                                f"Erro durante a transcrição: {str(e)}")
                                            logger.exception(
                                                "Erro durante a transcrição do vídeo do Drive")
                            with col3:
                                st.write("")

            elif search_option == "Buscar em pasta específica":
                folder_url = st.text_input(
                    "Digite a URL da pasta do Google Drive:")
                if folder_url:
                    folder_id = get_folder_id_from_url(folder_url)
                    if folder_id:
                        videos = search_videos_in_drive(
                            drive_service, folder_id=folder_id)

                        if videos:
                            st.write(
                                f"Encontrados {len(videos)} vídeo(s) na pasta:")
                            for video in videos:
                                col1, col2, col3 = st.columns([3, 1, 1])
                                with col1:
                                    st.write(f"**{video['name']}**")
                                    if 'size' in video:
                                        size_mb = int(
                                            video['size']) / (1024 * 1024)
                                        st.write(f"Tamanho: {size_mb:.2f} MB")
                                with col2:
                                    if st.button(f"Transcrever", key=f"transcribe_{video['id']}"):
                                        with st.spinner(f"Fazendo download e transcrevendo {video['name']}..."):
                                            try:
                                                # Download do vídeo
                                                temp_video_path = download_video_from_drive(
                                                    drive_service, video['id'], video['name'])
                                                if temp_video_path:
                                                    # Processar transcrição
                                                    srt_content = process_video(
                                                        temp_video_path)
                                                    if srt_content:
                                                        st.success(
                                                            "Transcrição concluída!")
                                                        process_transcription(
                                                            srt_content, model, max_tokens, temperature, video['name'], None, drive_service, video['id'])
                                                    else:
                                                        st.error(
                                                            "Não foi possível realizar a transcrição.")

                                                    # Limpar arquivo temporário
                                                    try:
                                                        os.remove(
                                                            temp_video_path)
                                                    except:
                                                        pass
                                                else:
                                                    st.error(
                                                        "Erro ao fazer download do vídeo.")
                                            except Exception as e:
                                                st.error(
                                                    f"Erro durante a transcrição: {str(e)}")
                                                logger.exception(
                                                    "Erro durante a transcrição do vídeo do Drive")
                                with col3:
                                    st.write("")
                    else:
                        st.error(
                            "Não foi possível extrair o ID da pasta da URL fornecida.")

            elif search_option == "Listar todos os vídeos":
                if st.button("Listar todos os vídeos"):
                    videos = search_videos_in_drive(drive_service)

                    if videos:
                        st.write(f"Encontrados {len(videos)} vídeo(s):")
                        for video in videos:
                            col1, col2, col3 = st.columns([3, 1, 1])
                            with col1:
                                st.write(f"**{video['name']}**")
                                if 'size' in video:
                                    size_mb = int(
                                        video['size']) / (1024 * 1024)
                                    st.write(f"Tamanho: {size_mb:.2f} MB")
                            with col2:
                                if st.button(f"Transcrever", key=f"transcribe_{video['id']}"):
                                    with st.spinner(f"Fazendo download e transcrevendo {video['name']}..."):
                                        try:
                                            # Download do vídeo
                                            temp_video_path = download_video_from_drive(
                                                drive_service, video['id'], video['name'])
                                            if temp_video_path:
                                                # Processar transcrição
                                                srt_content = process_video(
                                                    temp_video_path)
                                                if srt_content:
                                                    st.success(
                                                        "Transcrição concluída!")
                                                    process_transcription(
                                                        srt_content, model, max_tokens, temperature, video['name'], None, drive_service, video['id'])
                                                else:
                                                    st.error(
                                                        "Não foi possível realizar a transcrição.")

                                                # Limpar arquivo temporário
                                                try:
                                                    os.remove(temp_video_path)
                                                except:
                                                    pass
                                            else:
                                                st.error(
                                                    "Erro ao fazer download do vídeo.")
                                        except Exception as e:
                                            st.error(
                                                f"Erro durante a transcrição: {str(e)}")
                                            logger.exception(
                                                "Erro durante a transcrição do vídeo do Drive")
                            with col3:
                                st.write("")

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
