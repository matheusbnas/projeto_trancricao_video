import streamlit as st
import os
import base64
import logging
import tempfile
import datetime
import hashlib
from io import BytesIO
from pathlib import Path
import requests
from moviepy.editor import VideoFileClip, AudioFileClip
from pydub import AudioSegment
import srt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_JUSTIFY
import googleapiclient.errors
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import pickle
from google_auth_oauthlib.flow import Flow
import webbrowser
import re
import urllib.parse

# CONFIGURAÇÕES GERAIS DE PASTAS
# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurar pastas temporárias
PASTA_TEMP = Path(tempfile.gettempdir())
ARQUIVO_AUDIO_TEMP = PASTA_TEMP / 'audio.mp3'
ARQUIVO_VIDEO_TEMP = PASTA_TEMP / 'video.mp4'

MAX_CHUNK_SIZE = 25 * 1024 * 1024  # 25 MB em bytes

# Configurações do Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/drive.file']

########################################
# FUNÇÕES DE AUTENTICAÇÃO E BUSCA NO GOOGLE DRIVE
########################################

def get_drive_service():
    """
    Obtém o serviço autenticado do Google Drive
    """
    creds = None
    
    # Verifica se existe arquivo de token
    if os.path.exists('drive_token.pickle'):
        with open('drive_token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # Se não há credenciais válidas, faz a autenticação
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Verifica se existe arquivo de credenciais
            if not os.path.exists('credentials.json'):
                st.error("Arquivo 'credentials.json' não encontrado. Por favor, configure as credenciais do Google Drive.")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Salva as credenciais para próxima execução
        with open('drive_token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        logger.error(f"Erro ao criar serviço do Drive: {str(e)}")
        return None

def search_videos_in_drive(service, query=None, folder_id=None):
    """
    Busca vídeos no Google Drive
    """
    try:
        # Construir a query de busca
        search_query = "mimeType contains 'video/'"
        
        if query:
            search_query += f" and name contains '{query}'"
        
        if folder_id:
            search_query += f" and '{folder_id}' in parents"
        
        # Buscar arquivos
        results = service.files().list(
            q=search_query,
            spaces='drive',
            fields='nextPageToken, files(id, name, mimeType, size, createdTime)',
            orderBy='createdTime desc'
        ).execute()
        
        files = results.get('files', [])
        
        if not files:
            st.info("Nenhum vídeo encontrado no Google Drive.")
            return []
        
        return files
        
    except Exception as e:
        logger.error(f"Erro ao buscar vídeos no Drive: {str(e)}")
        st.error(f"Erro ao buscar vídeos no Drive: {str(e)}")
        return []

def download_video_from_drive(service, file_id, filename):
    """
    Faz download de um vídeo do Google Drive
    """
    try:
        # Criar arquivo temporário
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_path = temp_file.name
        temp_file.close()
        
        # Fazer download do arquivo
        request = service.files().get_media(fileId=file_id)
        fh = open(temp_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                st.progress(progress / 100)
        
        fh.close()
        
        return temp_path
        
    except Exception as e:
        logger.error(f"Erro ao fazer download do vídeo: {str(e)}")
        st.error(f"Erro ao fazer download do vídeo: {str(e)}")
        return None

def get_video_parent_folder(service, file_id):
    """
    Obtém o ID da pasta pai de um arquivo no Google Drive
    """
    try:
        file_metadata = service.files().get(
            fileId=file_id,
            fields='parents,name'
        ).execute()
        
        parents = file_metadata.get('parents', [])
        file_name = file_metadata.get('name', 'Unknown')
        
        logger.info(f"Arquivo '{file_name}' (ID: {file_id}) - Pais encontrados: {parents}")
        
        if parents:
            parent_id = parents[0]  # Retorna o primeiro parent (pasta pai)
            logger.info(f"Pasta pai do arquivo '{file_name}': {parent_id}")
            return parent_id
        else:
            logger.warning(f"Arquivo '{file_name}' não tem pasta pai (está na raiz do Drive)")
            return None  # Arquivo está na raiz do Drive
            
    except Exception as e:
        logger.error(f"Erro ao obter pasta pai do vídeo {file_id}: {str(e)}")
        return None

def upload_file_to_drive(service, file_path, filename, parent_folder_id=None, mime_type=None):
    """
    Faz upload de um arquivo para o Google Drive
    """
    try:
        logger.info(f"Iniciando upload do arquivo '{filename}' para pasta: {parent_folder_id}")
        
        # Determinar o MIME type baseado na extensão do arquivo
        if not mime_type:
            if filename.endswith('.pdf'):
                mime_type = 'application/pdf'
            elif filename.endswith('.srt'):
                mime_type = 'application/x-subrip'
            elif filename.endswith('.txt'):
                mime_type = 'text/plain'
            else:
                mime_type = 'application/octet-stream'
        
        # Preparar os metadados do arquivo
        file_metadata = {
            'name': filename,
            'parents': [parent_folder_id] if parent_folder_id else []
        }
        
        logger.info(f"Metadados do arquivo: {file_metadata}")
        
        # Criar o media upload
        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
        
        # Fazer o upload
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,name,webViewLink'
        ).execute()
        
        logger.info(f"Arquivo '{filename}' enviado para o Google Drive com sucesso! ID: {file.get('id')}")
        return file
        
    except Exception as e:
        logger.error(f"Erro ao fazer upload do arquivo '{filename}': {str(e)}")
        st.error(f"Erro ao fazer upload do arquivo '{filename}': {str(e)}")
        return None

def save_transcription_to_drive(service, video_file_id, transcription_content, summary_content, video_name):
    """
    Salva os arquivos de transcrição na mesma pasta do vídeo original no Google Drive
    """
    try:
        logger.info(f"Iniciando salvamento de transcrição para vídeo '{video_name}' (ID: {video_file_id})")
        
        # Obter a pasta pai do vídeo
        parent_folder_id = get_video_parent_folder(service, video_file_id)
        
        logger.info(f"Pasta pai determinada: {parent_folder_id}")
        
        if not parent_folder_id:
            st.warning("Não foi possível determinar a pasta do vídeo. Os arquivos serão salvos na raiz do Drive.")
            logger.warning(f"Vídeo '{video_name}' não tem pasta pai - salvando na raiz do Drive")
        
        # Criar arquivos temporários
        temp_files = []
        uploaded_files = []
        
        # 1. Arquivo SRT da transcrição completa
        srt_filename = f"{video_name}_transcricao_completa.srt"
        srt_temp_path = tempfile.NamedTemporaryFile(delete=False, suffix='.srt', mode='w', encoding='utf-8')
        srt_temp_path.write(transcription_content)
        srt_temp_path.close()
        temp_files.append(srt_temp_path.name)
        
        # Upload do SRT
        srt_file = upload_file_to_drive(service, srt_temp_path.name, srt_filename, parent_folder_id)
        if srt_file:
            uploaded_files.append({
                'name': srt_filename,
                'link': srt_file.get('webViewLink'),
                'type': 'Transcrição Completa (SRT)'
            })
        
        # 2. Arquivo PDF do resumo
        pdf_filename = f"{video_name}_resumo.pdf"
        pdf_buffer = create_pdf(summary_content, pdf_filename)
        pdf_temp_path = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf_temp_path.write(pdf_buffer.getvalue())
        pdf_temp_path.close()
        temp_files.append(pdf_temp_path.name)
        
        # Upload do PDF
        pdf_file = upload_file_to_drive(service, pdf_temp_path.name, pdf_filename, parent_folder_id)
        if pdf_file:
            uploaded_files.append({
                'name': pdf_filename,
                'link': pdf_file.get('webViewLink'),
                'type': 'Resumo (PDF)'
            })
        
        # 3. Arquivo PDF da transcrição completa
        pdf_full_filename = f"{video_name}_transcricao_completa.pdf"
        pdf_full_buffer = create_pdf(transcription_content, pdf_full_filename)
        pdf_full_temp_path = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf_full_temp_path.write(pdf_full_buffer.getvalue())
        pdf_full_temp_path.close()
        temp_files.append(pdf_full_temp_path.name)
        
        # Upload do PDF completo
        pdf_full_file = upload_file_to_drive(service, pdf_full_temp_path.name, pdf_full_filename, parent_folder_id)
        if pdf_full_file:
            uploaded_files.append({
                'name': pdf_full_filename,
                'link': pdf_full_file.get('webViewLink'),
                'type': 'Transcrição Completa (PDF)'
            })
        
        # Limpar arquivos temporários
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except:
                pass
        
        # Verificar se os arquivos foram salvos corretamente
        for file_info in uploaded_files:
            try:
                file_id = file_info.get('link', '').split('/')[-1]
                if file_id:
                    file_metadata = service.files().get(
                        fileId=file_id,
                        fields='parents,name'
                    ).execute()
                    actual_parents = file_metadata.get('parents', [])
                    logger.info(f"Arquivo '{file_metadata.get('name')}' salvo na pasta: {actual_parents}")
            except Exception as e:
                logger.warning(f"Erro ao verificar localização do arquivo: {str(e)}")
        
        return uploaded_files
        
    except Exception as e:
        logger.error(f"Erro ao salvar transcrição no Drive: {str(e)}")
        st.error(f"Erro ao salvar transcrição no Drive: {str(e)}")
        return []

def get_folder_id_from_url(url):
    """
    Extrai o ID da pasta do Google Drive a partir da URL
    """
    try:
        # Padrões comuns de URLs do Google Drive
        patterns = [
            r'drive\.google\.com/drive/folders/([a-zA-Z0-9_-]+)',
            r'drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)',
            r'drive\.google\.com/drive/u/\d+/folders/([a-zA-Z0-9_-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
        
    except Exception as e:
        logger.error(f"Erro ao extrair ID da pasta: {str(e)}")
        return None

def list_drive_folders(service):
    """
    Lista as pastas do Google Drive
    """
    try:
        results = service.files().list(
            q="mimeType='application/vnd.google-apps.folder'",
            spaces='drive',
            fields='nextPageToken, files(id, name)',
            orderBy='name'
        ).execute()
        
        folders = results.get('files', [])
        return folders
        
    except Exception as e:
        logger.error(f"Erro ao listar pastas: {str(e)}")
        return []

def debug_folder_access(service, folder_id):
    """
    Função de debug para verificar acesso a uma pasta específica
    """
    try:
        logger.info(f"Testando acesso à pasta: {folder_id}")
        
        # Tentar obter informações da pasta
        folder_metadata = service.files().get(
            fileId=folder_id,
            fields='id,name,parents'
        ).execute()
        
        logger.info(f"Pasta encontrada: {folder_metadata.get('name')} (ID: {folder_metadata.get('id')})")
        logger.info(f"Pais da pasta: {folder_metadata.get('parents', [])}")
        
        # Listar arquivos na pasta
        files_in_folder = service.files().list(
            q=f"'{folder_id}' in parents",
            fields='files(id, name, mimeType)',
            pageSize=10
        ).execute()
        
        files = files_in_folder.get('files', [])
        logger.info(f"Arquivos encontrados na pasta: {len(files)}")
        for file in files:
            logger.info(f"  - {file.get('name')} ({file.get('mimeType')})")
        
        return True
        
    except Exception as e:
        logger.error(f"Erro ao acessar pasta {folder_id}: {str(e)}")
        return False

########################################
# FUNÇÃO DE EXTRAÇÃO DO NOME DO ARQUIVO
########################################


def extract_filename_from_path(file_path):
    """
    Extrai o nome do arquivo original de diferentes tipos de caminhos:
    - Arquivos locais: /path/to/video.mp4 -> video
    - URLs: https://example.com/video.mp4 -> video
    - URLs com parâmetros: https://example.com/video.mp4?param=value -> video
    """
    try:
        # Se for uma URL
        if file_path.startswith(('http://', 'https://')):
            # Parse da URL
            parsed_url = urllib.parse.urlparse(file_path)
            # Extrair o nome do arquivo do path
            filename = os.path.basename(parsed_url.path)
        else:
            # Se for um caminho local
            filename = os.path.basename(file_path)

        # Remover a extensão do arquivo
        name_without_extension = os.path.splitext(filename)[0]

        # Limpar caracteres especiais que podem causar problemas em nomes de arquivo
        clean_name = re.sub(r'[<>:"/\\|?*]', '_', name_without_extension)

        return clean_name if clean_name else "transcricao"

    except Exception as e:
        logger.warning(f"Erro ao extrair nome do arquivo: {str(e)}")
        return "transcricao"

########################################
# FUNÇÃO DE PROCESSAMENTO DE AUDIO E VÍDEO
########################################


def split_audio(audio_path, chunk_duration=1200):  # 20 minutos por chunk
    try:
        audio = AudioFileClip(audio_path)
        duration = audio.duration
        chunks = []

        for start in range(0, int(duration), chunk_duration):
            end = min(start + chunk_duration, duration)
            chunk = audio.subclip(start, end)
            chunk_path = f"{audio_path}_{start}_{end}.mp3"

            # Configurações mais robustas para write_audiofile
            chunk.write_audiofile(
                chunk_path,
                bitrate="64k",
                verbose=False,
                logger=None
            )

            # Verificar o tamanho do arquivo
            file_size = os.path.getsize(chunk_path)
            if file_size > 25 * 1024 * 1024:  # Se o arquivo for maior que 25 MB
                os.remove(chunk_path)  # Remove o arquivo grande
                # Divide este chunk em dois menores
                mid = (start + end) // 2
                chunk1 = audio.subclip(start, mid)
                chunk2 = audio.subclip(mid, end)
                chunk_path1 = f"{audio_path}_{start}_{mid}.mp3"
                chunk_path2 = f"{audio_path}_{mid}_{end}.mp3"
                chunk1.write_audiofile(
                    chunk_path1, bitrate="64k", verbose=False, logger=None)
                chunk2.write_audiofile(
                    chunk_path2, bitrate="64k", verbose=False, logger=None)
                chunks.append((chunk_path1, start))
                chunks.append((chunk_path2, mid))
            else:
                chunks.append((chunk_path, start))

        audio.close()
        return chunks

    except Exception as e:
        logger.error(f"Erro ao dividir áudio: {str(e)}")
        # Fallback: retornar o arquivo original como único chunk
        return [(audio_path, 0)]

###############################################
# FUNÇÃO DE EXTRAÇÃO DE VÍDEO NO VIMEO E YOUTUBE
###############################################

###### VIMEO #####


def extrair_video_id(url):
    import re
    match = re.search(r'vimeo.com/(\d+)', url)
    if match:
        return match.group(1)
    else:
        return None


def get_vimeo_video_link(video_url, vimeo_client):
    try:
        video_id = extrair_video_id(video_url)
        if not video_id:
            return None

        video_info = vimeo_client.get(f'/videos/{video_id}').json()
        if not video_info:
            return None

        # Tentar obter o link do vídeo com a menor qualidade disponível
        files = video_info.get('files', [])
        video_link = min(files, key=lambda x: x.get(
            'height', float('inf'))).get('link')

        if video_link:
            return video_link
        else:
            logger.error("Não foi possível encontrar um link de vídeo")
            return None

    except Exception as e:
        logger.exception(f"Erro ao obter link do vídeo do Vimeo: {str(e)}")
        return None


#### YOUTUBE ####
def get_authenticated_service():
    scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
    credentials = None

    # Tenta carregar as credenciais do arquivo token.pickle
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            credentials = pickle.load(token)

    # Se não há credenciais válidas disponíveis, faça o login
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            client_config = {
                "installed": {
                    "client_id": os.getenv("YOUTUBE_CLIENT_ID"),
                    "client_secret": os.getenv("YOUTUBE_CLIENT_SECRET"),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": ["http://localhost:8501/"]
                }
            }

            flow = Flow.from_client_config(
                client_config,
                scopes=scopes,
                redirect_uri="http://localhost:8501/"
            )

            auth_url, _ = flow.authorization_url(prompt='consent')

            print(
                f"Por favor, acesse esta URL para autorizar o aplicativo: {auth_url}")
            webbrowser.open(auth_url)  # Abre o navegador automaticamente

            # Aguarda o usuário inserir o código de autorização
            auth_code = input("Cole o código de autorização aqui: ")

            flow.fetch_token(code=auth_code)
            credentials = flow.credentials

        # Salva as credenciais para a próxima execução
        with open('token.pickle', 'wb') as token:
            pickle.dump(credentials, token)

    return build("youtube", "v3", credentials=credentials)


def get_video_details(youtube, video_id):
    try:
        request = youtube.videos().list(
            part="snippet,contentDetails",
            id=video_id
        )
        response = request.execute()

        if 'items' in response:
            return response['items'][0]
        else:
            return None
    except Exception as e:
        logger.error(f"Erro ao obter detalhes do vídeo do YouTube: {str(e)}")
        return None


def get_video_download_url(youtube, video_id):
    try:
        request = youtube.videos().list(
            part="player",
            id=video_id
        )
        response = request.execute()

        if 'items' in response and response['items']:
            embed_html = response['items'][0]['player']['embedHtml']
            # Extrair a URL do vídeo do HTML de incorporação
            # Nota: Este é um método simplificado e pode precisar de ajustes
            video_url = embed_html.split('src="')[1].split('"')[0]
            return video_url
        else:
            return None
    except Exception as e:
        logger.error(
            f"Erro ao obter URL de download do vídeo do YouTube: {str(e)}")
        return None

########################################
# FUNÇÃO DE PROCESSAMENTO E DOWNLOAD DO ARQUIVO SRT
########################################


def processa_srt(srt_content):
    subtitles = list(srt.parse(srt_content))
    transcript_text = ""
    for sub in subtitles:
        # Limpa os asteriscos do conteúdo
        sub.content = sub.content.replace('*', '')
        start_time = str(sub.start).split('.')[0]  # Remove microssegundos
        transcript_text += f"{start_time} - {sub.content}\n"
    return transcript_text


def create_download_link(file_path, link_text, custom_filename=None):
    """
    Cria um link de download para um arquivo com nome personalizado.
    """
    with open(file_path, 'rb') as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()

    # Usar o nome personalizado se fornecido, senão usar o nome original do arquivo
    download_filename = custom_filename if custom_filename else os.path.basename(
        file_path)

    href = f'<a href="data:file/txt;base64,{b64}" download="{download_filename}">{link_text}</a>'
    return href


def processa_srt_sem_timestamp(srt_content):
    subtitles = list(srt.parse(srt_content))
    transcript_text = ""
    for sub in subtitles:
        # Limpa os asteriscos do conteúdo
        sub.content = sub.content.replace('*', '')
        transcript_text += f"{sub.content}\n"
    return transcript_text


def gera_srt_do_resumo(resumo, duracao_total_segundos):
    linhas = resumo.split('\n')
    subtitles = []
    tempo_por_linha = duracao_total_segundos / len(linhas)

    for i, linha in enumerate(linhas, start=1):
        if linha.strip():
            start_time = datetime.timedelta(
                seconds=int((i-1) * tempo_por_linha))
            end_time = datetime.timedelta(seconds=int(i * tempo_por_linha))

            # Extrair o timestamp do início da linha (se existir)
            match = re.match(r'\[(\d{2}:\d{2})\] - (.+)', linha)
            if match:
                timestamp, content = match.groups()
                minutos, segundos = map(int, timestamp.split(':'))
                start_time = datetime.timedelta(
                    minutes=minutos, seconds=segundos)
                end_time = start_time + \
                    datetime.timedelta(seconds=int(tempo_por_linha))
            else:
                content = linha

            # Limpa os asteriscos do conteúdo
            content = content.strip().replace('*', '')

            subtitle = srt.Subtitle(
                index=i,
                start=start_time,
                end=end_time,
                content=content
            )
            subtitles.append(subtitle)

    # Gera o conteúdo SRT limpo
    return srt.compose(subtitles)


def ajusta_tempo_srt(srt_content, offset):
    subtitles = list(srt.parse(srt_content))
    for sub in subtitles:
        # Limpa os asteriscos do conteúdo
        sub.content = sub.content.replace('*', '')
        sub.start += datetime.timedelta(seconds=offset)
        sub.end += datetime.timedelta(seconds=offset)
    return srt.compose(subtitles)

########################################
# FUNÇÃO DE CRIAÇÃO E DOWNLOAD DE ARQUIVO PDF
########################################


def create_pdf(content, filename):
    """
    Cria um PDF com o conteúdo fornecido e retorna um buffer.
    O filename é usado apenas para referência, não afeta o conteúdo do PDF.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72,
                            leftMargin=72, topMargin=72, bottomMargin=18)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY))
    flowables = []

    # Dividir o conteúdo em parágrafos
    # Assume que parágrafos são separados por linha em branco
    paragraphs = content.split('\n\n')

    for paragraph in paragraphs:
        if paragraph.strip():
            # Remove qualquer numeração ou formatação especial
            clean_paragraph = re.sub(r'^\d+\.\s*', '', paragraph.strip())
            clean_paragraph = re.sub(
                r'\*\*(.*?)\*\*', r'\1', clean_paragraph)  # Remove negrito (**)

            p = Paragraph(clean_paragraph, styles['Justify'])
            flowables.append(p)
            flowables.append(Spacer(1, 12))  # Espaçamento entre parágrafos

    doc.build(flowables)
    buffer.seek(0)
    return buffer


def create_download_link_pdf(pdf_buffer, link_text, filename):
    """
    Cria um link de download para um PDF com nome de arquivo personalizado.
    """
    b64 = base64.b64encode(pdf_buffer.getvalue()).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">{link_text}</a>'
    return href
