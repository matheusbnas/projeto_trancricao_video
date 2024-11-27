import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
import os
import vimeo
import re
import logging
from utils import *
import math

# Load environment variables
_ = load_dotenv(find_dotenv())

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações do Vimeo
VIMEO_ACCESS_TOKEN = st.secrets["VIMEO_ACCESS_TOKEN"]
VIMEO_CLIENT_ID = st.secrets["VIMEO_CLIENT_ID"]
VIMEO_CLIENT_SECRET = st.secrets["VIMEO_CLIENT_SECRET"]

# Inicializar cliente Vimeo
vimeo_client = vimeo.VimeoClient(
    token=VIMEO_ACCESS_TOKEN,
    key=VIMEO_CLIENT_ID,
    secret=VIMEO_CLIENT_SECRET
)

st.set_page_config(page_title="Resumo de Transcrição de Vídeo", page_icon="🎥", layout="wide")


def get_openai_client():
    if "openai_client" not in st.session_state:
        api_key = st.session_state.get("openai_api_key")
        if api_key:
            st.session_state.openai_client = OpenAI(api_key=api_key)
        else:
            st.error("Chave da API OpenAI não encontrada. Por favor, faça login novamente.")
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

        st.markdown("[Matheus Bernardes](https://www.linkedin.com/in/matheusbnas)")
        st.markdown("Desenvolvido por [Matech 3D](https://matech3d.com.br/)")

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
        transcricao_parts = [transcricao[i:i+max_chars] for i in range(0, len(transcricao), max_chars)]
        
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

def process_video(video_path_or_url):
    temp_audio_file = None
    try:
        # Criar um arquivo temporário para o áudio
        temp_audio_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_audio_file.close()
        audio_path = temp_audio_file.name
        
        logger.info(f"Iniciando processamento do vídeo: {video_path_or_url}")
        logger.info(f"Arquivo de áudio temporário criado: {audio_path}")
        
        # Extrair áudio do vídeo
        with VideoFileClip(video_path_or_url) as video:
            audio = video.audio
            audio.write_audiofile(audio_path)
        
        logger.info(f"Áudio extraído e salvo em: {audio_path}")
        
        # Verificar se o arquivo de áudio foi criado corretamente
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"O arquivo de áudio não foi criado: {audio_path}")
        
        # Dividir o áudio em chunks
        audio_chunks = split_audio(audio_path, chunk_duration=1200)  # 20 minutos por chunk
        full_transcript = ""
        
        logger.info(f"Iniciando transcrição de {len(audio_chunks)} chunks de áudio")
        
        # Processar cada chunk de áudio
        for i, (chunk_path, start_time) in enumerate(audio_chunks):
            logger.info(f"Processando chunk {i+1}/{len(audio_chunks)}")
            chunk_size = os.path.getsize(chunk_path)
            logger.info(f"Tamanho do chunk: {chunk_size / (1024 * 1024):.2f} MB")
            
            chunk_transcript = transcreve_audio_chunk(chunk_path)
            adjusted_transcript = ajusta_tempo_srt(chunk_transcript, start_time)
            full_transcript += adjusted_transcript + "\n\n"
            os.remove(chunk_path)  # Remove o chunk de áudio após a transcrição
        
        logger.info("Transcrição completa")
        return full_transcript
    
    except Exception as e:
        logger.exception(f"Erro ao processar o vídeo: {str(e)}")
        raise
    
    finally:
        logger.info("Iniciando limpeza de recursos")
        # Limpeza dos arquivos temporários
        if temp_audio_file and os.path.exists(temp_audio_file.name):
            try:
                os.remove(temp_audio_file.name)
                logger.info(f"Arquivo de áudio temporário removido: {temp_audio_file.name}")
            except Exception as e:
                logger.warning(f"Não foi possível remover o arquivo de áudio temporário: {str(e)}")

########################################
#FUNÇÕES DE TRANSCRIÇÃO DE VIDEO DO VIMEO
########################################
def transcribe_vimeo_video(video_link):
    client = get_openai_client()
    if not client:
        return None

    try:
        # Baixar o vídeo em um arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
            response = requests.get(video_link, stream=True)
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_file_path = temp_file.name

        # Transcrever o vídeo
        with open(temp_file_path, 'rb') as video_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=video_file,
                response_format="srt",
                language="pt"
            )

        # Remover o arquivo temporário
        os.remove(temp_file_path)

        return transcription
    except Exception as e:
        logger.exception(f"Erro ao transcrever vídeo do Vimeo: {str(e)}")
        st.error(f"Erro ao transcrever vídeo: {str(e)}")
        return None

def process_vimeo_video(vimeo_url, model, max_tokens, temperature):
    try:
        with st.spinner("Obtendo informações do vídeo do Vimeo..."):
            video_link = get_vimeo_video_link(vimeo_url, vimeo_client)
            if not video_link:
                st.error("Não foi possível obter o link do vídeo do Vimeo.")
                return

        with st.spinner("Transcrevendo vídeo..."):
            srt_content = transcribe_vimeo_video(video_link)
            if not srt_content:
                st.error("Não foi possível gerar a transcrição do vídeo do Vimeo.")
                return

        st.success("Transcrição automática concluída!")
        process_transcription(srt_content, model, max_tokens, temperature, vimeo_url)

    except Exception as e:
        logger.exception(f"Ocorreu um erro ao processar o vídeo do Vimeo: {str(e)}")
        st.error(f"Ocorreu um erro ao processar o vídeo do Vimeo: {str(e)}")

########################################
#FUNÇÕES DE TRANSCRIÇÃO DE VIDEO DO YOUTUBE
########################################
def extract_youtube_video_id(url):
    # Função para extrair o ID do vídeo do YouTube da URL
    pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?(.+)'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def process_youtube_video(video_id, model, max_tokens, temperature):
    try:
        youtube = get_authenticated_service()
        
        with st.spinner("Obtendo informações do vídeo do YouTube..."):
            video_details = get_video_details(youtube, video_id)
            if not video_details:
                st.error("Não foi possível obter informações do vídeo do YouTube.")
                return

            video_url = get_video_download_url(youtube, video_id)
            if not video_url:
                st.error("Não foi possível obter o link do vídeo do YouTube.")
                return

        with st.spinner("Transcrevendo vídeo..."):
            srt_content = transcribe_youtube_video(video_url)
            if not srt_content:
                st.error("Não foi possível gerar a transcrição do vídeo do YouTube.")
                return

        st.success("Transcrição automática concluída!")
        process_transcription(srt_content, model, max_tokens, temperature, video_url)

    except Exception as e:
        logger.exception(f"Ocorreu um erro ao processar o vídeo do YouTube: {str(e)}")
        st.error(f"Ocorreu um erro ao processar o vídeo do YouTube: {str(e)}")

def transcribe_youtube_video(video_url):
    client = get_openai_client()
    if not client:
        return None

    try:
        # Baixar o vídeo em um arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
            response = requests.get(video_url, stream=True)
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_file_path = temp_file.name

        # Transcrever o vídeo
        with open(temp_file_path, 'rb') as video_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=video_file,
                response_format="srt",
                language="pt"
            )

        # Remover o arquivo temporário
        os.remove(temp_file_path)

        return transcription
    except Exception as e:
        logger.exception(f"Erro ao transcrever vídeo do YouTube: {str(e)}")
        st.error(f"Erro ao transcrever vídeo: {str(e)}")
        return None
    
########################################
#FUNÇÕES DE PROCESSO DE TRANSCRIÇÃO EM SRT E PDF
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
    text_only_output = "\n\n".join(segment['text'] for segment in summarized_segments)
    
    return srt_output, text_only_output

def process_transcription(srt_content, model, max_tokens, temperature, video_path):
    client = get_openai_client()
    if not client:
        return

    # Status placeholder para mensagens de progresso
    status_placeholder = st.empty()
    status_placeholder.success("Transcrição automática concluída! Gerando documentos...")

    # Generate summarized SRT and text-only version
    status_placeholder.info("Gerando resumo da transcrição...")
    summarized_srt, text_only_summary = generate_summarized_srt_from_full(srt_content, client, model)
    
    # Get video duration
    with VideoFileClip(video_path) as video:
        duracao_total_segundos = int(video.duration)

    # Create PDFs and SRTs
    status_placeholder.info("Gerando arquivos PDF e SRT...")
    transcript_pdf = create_pdf(processa_srt_sem_timestamp(srt_content), "transcricao_completa.pdf")
    summarized_pdf = create_pdf(text_only_summary, "transcricao_resumida.pdf")
    
    # Save SRT files
    summarized_srt_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.srt', encoding='utf-8')
    summarized_srt_file.write(summarized_srt)
    summarized_srt_file.close()
    
    transcript_srt_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.srt', encoding='utf-8')
    transcript_srt_file.write(srt_content)
    transcript_srt_file.close()

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
        st.text_area("Transcrição Completa", processa_srt(srt_content), height=300)

    # Download section
    st.subheader("Download dos Arquivos")
    tab1, tab2 = st.tabs(["Transcrição Resumida", "Transcrição Completa"])
    
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(create_download_link_pdf(summarized_pdf, "Baixar Transcrição Resumida (PDF)", "transcricao_resumida.pdf"), unsafe_allow_html=True)
        with col2:
            st.markdown(create_download_link(summarized_srt_file.name, "Baixar Transcrição Resumida (SRT)"), unsafe_allow_html=True)
            
    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(create_download_link_pdf(transcript_pdf, "Baixar Transcrição Completa (PDF)", "transcricao_completa.pdf"), unsafe_allow_html=True)
        with col2:
            st.markdown(create_download_link(transcript_srt_file.name, "Baixar Transcrição Completa (SRT)"), unsafe_allow_html=True)

    # Cleanup temporary files
    for file in [summarized_srt_file.name, transcript_srt_file.name]:
        try:
            os.remove(file)
        except Exception as e:
            logger.warning(f"Não foi possível remover o arquivo temporário {file}: {str(e)}")

def page(model, max_tokens, temperature):
    st.title("Resumo de Transcrição de Vídeo")

    if 'session_id' not in st.session_state:
        st.session_state.session_id = hashlib.md5(str(datetime.datetime.now()).encode()).hexdigest()

    video_source = st.radio("Escolha a fonte do vídeo:", ["Upload Local", "Google Cloud Storage", "Amazon S3"])

    if video_source == "Upload Local":
        uploaded_video = st.file_uploader("Faça upload do vídeo", type=['mp4', 'avi', 'mov'])
        if uploaded_video:
            file_size = uploaded_video.size
            st.write(f"Tamanho do arquivo: {file_size / (1024 * 1024):.2f} MB")

            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
                temp_file.write(uploaded_video.read())
                temp_file_path = temp_file.name

            if st.button("Transcrever vídeo automaticamente"):
                st.info("Transcrevendo o vídeo automaticamente... Isso pode levar alguns minutos.")
                try:
                    srt_content = process_video(temp_file_path)
                    if srt_content:
                        st.success("Transcrição automática concluída!")
                        process_transcription(srt_content, model, max_tokens, temperature, temp_file_path)
                    else:
                        st.error("Não foi possível realizar a transcrição automática.")
                except Exception as e:
                    st.error(f"Erro durante a transcrição: {str(e)}")
                    logger.exception("Erro durante a transcrição do vídeo")
                finally:
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)

    elif video_source == "Google Cloud Storage":
        gcs_video_url = st.text_input("Digite a URL pública do vídeo no Google Cloud Storage")
        if gcs_video_url:
            st.write(f"URL do vídeo: {gcs_video_url}")
            
            if st.button("Transcrever vídeo do GCS"):
                st.info("Transcrevendo o vídeo do GCS... Isso pode levar alguns minutos.")
                try:
                    with st.spinner("Realizando transcrição..."):
                        srt_content = process_video(gcs_video_url)
                    
                    if srt_content:
                        st.success("Transcrição automática concluída!")
                        process_transcription(srt_content, model, max_tokens, temperature, gcs_video_url)
                    else:
                        st.error("Não foi possível realizar a transcrição automática.")
                except Exception as e:
                    st.error(f"Erro durante a transcrição: {str(e)}")
                    logger.exception("Erro durante a transcrição do vídeo")

    elif video_source == "Amazon S3":
        s3_video_url = st.text_input("Digite a URL pública do vídeo no Amazon S3")
        if s3_video_url:
            st.write(f"URL do vídeo: {s3_video_url}")
            
            if st.button("Transcrever vídeo do S3"):
                st.info("Transcrevendo o vídeo do S3... Isso pode levar alguns minutos.")
                try:
                    with st.spinner("Realizando transcrição..."):
                        srt_content = process_video(s3_video_url)
                    
                    if srt_content:
                        st.success("Transcrição automática concluída!")
                        process_transcription(srt_content, model, max_tokens, temperature, s3_video_url)
                    else:
                        st.error("Não foi possível realizar a transcrição automática.")
                except Exception as e:
                    st.error(f"Erro durante a transcrição: {str(e)}")
                    logger.exception("Erro durante a transcrição do vídeo")

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

# def show_youtube_terms():
#     youtube_terms_service.main()
    
#     # Verificar se o checkbox foi marcado
#     if st.session_state.get('youtube_terms_checkbox', False):
#         st.session_state.youtube_terms_accepted = True
#         st.success("Termos aceitos. Você pode agora usar a funcionalidade do YouTube.")
#     else:
#         st.session_state.youtube_terms_accepted = False
        
def main():
    if check_password():
        # Sempre renderizar a sidebar
        model, max_tokens, temperature = sidebar()

        # Atualizar o estado da sessão com as configurações mais recentes
        st.session_state.sidebar_config = (model, max_tokens, temperature)

        # Adicionar link para Termos de Serviço na sidebar
        # if st.sidebar.button("Termos de Serviço do YouTube"):
        #     st.switch_page("pages/youtube_terms_service.py")

        # Chamar a página principal com as configurações atualizadas
        page(model, max_tokens, temperature)
    else:
        st.warning("Você não tem permissão para acessar essa página.")

if __name__ == "__main__":
    main()