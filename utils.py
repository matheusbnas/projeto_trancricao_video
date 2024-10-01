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
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
import googleapiclient.errors
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
from google_auth_oauthlib.flow import Flow
import webbrowser
from google.cloud import storage

# CONFIGURAÇÕES GERAIS DE PASTAS
# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurar pastas temporárias
PASTA_TEMP = Path(tempfile.gettempdir())
ARQUIVO_AUDIO_TEMP = PASTA_TEMP / 'audio.mp3'
ARQUIVO_VIDEO_TEMP = PASTA_TEMP / 'video.mp4'

MAX_CHUNK_SIZE = 25 * 1024 * 1024  # 25 MB em bytes

########################################
#FUNÇÃO DE PROCESSAMENTO DE AUDIO E VÍDEO
########################################
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
    
def upload_to_gcs(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name)

    print(f"File {source_file_name} uploaded to {destination_blob_name}.")
    return f"gs://{bucket_name}/{destination_blob_name}"

def process_video_chunk(chunk, chunk_number, total_chunks, session_id, bucket_name):
    chunk_dir = PASTA_TEMP / session_id
    chunk_dir.mkdir(exist_ok=True)
    chunk_file = chunk_dir / f"chunk_{chunk_number}.mp4"
    
    with open(chunk_file, "wb") as f:
        f.write(chunk)
    
    # Upload do chunk para o GCS
    destination_blob_name = f"{session_id}/chunk_{chunk_number}.mp4"
    gcs_path = upload_to_gcs(bucket_name, str(chunk_file), destination_blob_name)
    
    if chunk_number == total_chunks - 1:
        # Todos os chunks foram enviados, agora podemos combinar no GCS
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        # Combinar todos os chunks em um único arquivo
        combined_blob = bucket.blob(f"{session_id}/final_video.mp4")
        combined_blob.compose([bucket.blob(f"{session_id}/chunk_{i}.mp4") for i in range(total_chunks)])
        
        # Deletar os chunks individuais
        for i in range(total_chunks):
            bucket.blob(f"{session_id}/chunk_{i}.mp4").delete()
        
        return f"gs://{bucket_name}/{session_id}/final_video.mp4"
    return None

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
        video_link = min(files, key=lambda x: x.get('height', float('inf'))).get('link')

        if video_link:
            return video_link
        else:
            logger.error("Não foi possível encontrar um link de vídeo")
            return None

    except Exception as e:
        logger.exception(f"Erro ao obter link do vídeo do Vimeo: {str(e)}")
        return None

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
            
            print(f"Por favor, acesse esta URL para autorizar o aplicativo: {auth_url}")
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
        logger.error(f"Erro ao obter URL de download do vídeo do YouTube: {str(e)}")
        return None
    
########################################
#FUNÇÃO DE PROCESSAMENTO E DOWNLOAD DO ARQUIVO SRT
########################################
def ajusta_tempo_srt(srt_content, offset):
    subtitles = list(srt.parse(srt_content))
    for sub in subtitles:
        sub.start += datetime.timedelta(seconds=offset)
        sub.end += datetime.timedelta(seconds=offset)
    return srt.compose(subtitles)

def processa_srt(srt_content):
    subtitles = list(srt.parse(srt_content))
    transcript_text = ""
    for sub in subtitles:
        start_time = str(sub.start).split('.')[0]  # Remove microssegundos
        transcript_text += f"{start_time} - {sub.content}\n"
    return transcript_text

def txt_to_srt(txt_content):
    lines = txt_content.split('\n')
    subtitles = []
    for i, line in enumerate(lines, start=1):
        if line.strip():
            start_time = datetime.timedelta(seconds=i*5)
            end_time = start_time + datetime.timedelta(seconds=5)
            subtitle = srt.Subtitle(index=i, start=start_time, end=end_time, content=line)
            subtitles.append(subtitle)
    return srt.compose(subtitles)

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
        segundos_totais = int(sub.start.total_seconds())
        minutos, segundos = divmod(segundos_totais, 60)
        timestamp = f"{minutos:02d}:{segundos:02d}"
        link = f'<a href="#" onclick="seekVideo(\'{video_path}\', {segundos_totais}); return false;">[{timestamp}]</a>'
        resumo_formatado += f"{link} - {sub.content}<br>"
    return resumo_formatado

########################################
#FUNÇÃO DE CRIAÇÃO E DOWNLOAD DE ARQUIVO PDF
########################################
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