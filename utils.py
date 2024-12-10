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
import pickle
from google_auth_oauthlib.flow import Flow
import webbrowser
import re

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
def split_audio(audio_path, chunk_duration=1200):  # 20 minutos por chunk
    audio = AudioFileClip(audio_path)
    duration = audio.duration
    chunks = []
    
    for start in range(0, int(duration), chunk_duration):
        end = min(start + chunk_duration, duration)
        chunk = audio.subclip(start, end)
        chunk_path = f"{audio_path}_{start}_{end}.mp3"
        chunk.write_audiofile(chunk_path, bitrate="64k")  # Reduzindo a qualidade para manter o tamanho sob controle
        
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
            chunk1.write_audiofile(chunk_path1, bitrate="64k")
            chunk2.write_audiofile(chunk_path2, bitrate="64k")
            chunks.append((chunk_path1, start))
            chunks.append((chunk_path2, mid))
        else:
            chunks.append((chunk_path, start))
    
    audio.close()
    return chunks
 
###############################################
#FUNÇÃO DE EXTRAÇÃO DE VÍDEO NO VIMEO E YOUTUBE
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
        video_link = min(files, key=lambda x: x.get('height', float('inf'))).get('link')

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

def processa_srt(srt_content):
    subtitles = list(srt.parse(srt_content))
    transcript_text = ""
    for sub in subtitles:
        # Limpa os asteriscos do conteúdo
        sub.content = sub.content.replace('*', '')
        start_time = str(sub.start).split('.')[0]  # Remove microssegundos
        transcript_text += f"{start_time} - {sub.content}\n"
    return transcript_text


def create_download_link(file_path, link_text):
    with open(file_path, 'rb') as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    href = f'<a href="data:file/txt;base64,{b64}" download="{os.path.basename(file_path)}">{link_text}</a>'
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
            start_time = datetime.timedelta(seconds=int((i-1) * tempo_por_linha))
            end_time = datetime.timedelta(seconds=int(i * tempo_por_linha))
            
            # Extrair o timestamp do início da linha (se existir)
            match = re.match(r'\[(\d{2}:\d{2})\] - (.+)', linha)
            if match:
                timestamp, content = match.groups()
                minutos, segundos = map(int, timestamp.split(':'))
                start_time = datetime.timedelta(minutes=minutos, seconds=segundos)
                end_time = start_time + datetime.timedelta(seconds=int(tempo_por_linha))
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
#FUNÇÃO DE CRIAÇÃO E DOWNLOAD DE ARQUIVO PDF
########################################
def create_pdf(content, filename):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY))
    flowables = []

    # Dividir o conteúdo em parágrafos
    paragraphs = content.split('\n\n')  # Assume que parágrafos são separados por linha em branco

    for paragraph in paragraphs:
        if paragraph.strip():
            # Remove qualquer numeração ou formatação especial
            clean_paragraph = re.sub(r'^\d+\.\s*', '', paragraph.strip())
            clean_paragraph = re.sub(r'\*\*(.*?)\*\*', r'\1', clean_paragraph)  # Remove negrito (**)
            
            p = Paragraph(clean_paragraph, styles['Justify'])
            flowables.append(p)
            flowables.append(Spacer(1, 12))  # Espaçamento entre parágrafos

    doc.build(flowables)
    buffer.seek(0)
    return buffer

def create_download_link_pdf(pdf_buffer, link_text, filename):
    b64 = base64.b64encode(pdf_buffer.getvalue()).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">{link_text}</a>'
    return href