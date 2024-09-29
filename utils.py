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

#CONFIGURAÇÕES GERAIS DE PASTAS
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

def process_video_chunk(chunk, chunk_number, total_chunks, session_id):
    chunk_dir = PASTA_TEMP / session_id
    chunk_dir.mkdir(exist_ok=True)
    chunk_file = chunk_dir / f"chunk_{chunk_number}.mp4"
    
    with open(chunk_file, "wb") as f:
        f.write(chunk)
    
    if chunk_number == total_chunks - 1:
        final_video = chunk_dir / "final_video.mp4"
        with open(final_video, "wb") as outfile:
            for i in range(total_chunks):
                chunk_file = chunk_dir / f"chunk_{i}.mp4"
                outfile.write(chunk_file.read_bytes())
                chunk_file.unlink()
        return str(final_video)
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

# def download_audio_from_vimeo(video_url, vimeo_client):
#     try:
#         video_id = extrair_video_id(video_url)
#         if not video_id:
#             return None

#         video_info = vimeo_client.get(f'/videos/{video_id}').json()
#         if not video_info:
#             return None

#         download_links = video_info.get('download', [])
#         if not download_links:
#             logger.error("Nenhum link de download disponível")
#             return None

#         # Tenta encontrar a menor versão do vídeo disponível para download
#         video_link = min(download_links, key=lambda x: x.get('size', float('inf'))).get('link')
#         if not video_link:
#             logger.error("Não foi possível encontrar um link de vídeo para download")
#             return None

#         with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_video_file:
#             response = requests.get(video_link, stream=True)
#             response.raise_for_status()
#             for chunk in response.iter_content(chunk_size=8192):
#                 temp_video_file.write(chunk)
#             temp_video_path = temp_video_file.name

#         # Extrair áudio do vídeo
#         video = VideoFileClip(temp_video_path)
#         audio_path = temp_video_path.replace('.mp4', '.mp3')
#         video.audio.write_audiofile(audio_path)
#         video.close()

#         # Remover o arquivo de vídeo temporário
#         os.remove(temp_video_path)

#         return audio_path

    except Exception as e:
        logger.exception(f"Erro ao processar o vídeo do Vimeo: {str(e)}")
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