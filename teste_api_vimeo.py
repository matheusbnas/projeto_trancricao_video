import streamlit as st
import vimeo
import re

# Autenticação no Vimeo
client = vimeo.VimeoClient(
    token="d6e255d7324222f61798f72964272bf3",  # Substitua pelo seu Access Token
    key="34472837b3776e1a777ee06555d7a6cbe0de0328",       # Substitua pelo seu Client ID
    secret="v6JSnuyBk3Tda4/JAJ6oxdrqslb7E8PRVd08szvRh8nM+qAN3Rj/wyh9jig4i+eZjqiGbgu2e/wjCSknFL4KkPLb/i3d+j4Hkd1axJunFPRTTASIou3MQZsePJyGl4kP" # Substitua pelo seu Client Secret
)

# Título do app no Streamlit
st.title("Integração com Vimeo API no Streamlit")

# Função para buscar vídeos por ID
def buscar_video_por_id(video_id):
    response = client.get(f"/videos/{video_id}")
    if response.status_code == 200:
        return response.json()
    else:
        st.error("Erro ao buscar o vídeo")
        return None

# Função para extrair o ID do vídeo da URL
def extrair_video_id(url):
    match = re.search(r'vimeo.com/(\d+)', url)
    if match:
        return match.group(1)
    else:
        st.error("URL inválida")
        return None

# Formulário para buscar vídeo no Vimeo pela URL
url = st.text_input("Cole a URL do vídeo do Vimeo")
if st.button("Buscar por URL"):
    if url:
        video_id = extrair_video_id(url)
        if video_id:
            dados_video = buscar_video_por_id(video_id)
            if dados_video:
                titulo = dados_video['name']
                embed_url = dados_video['embed']['html']
                st.write(f"**{titulo}**")
                st.markdown(embed_url, unsafe_allow_html=True)
    else:
        st.warning("Por favor, insira uma URL válida.")

# Linha divisória
st.markdown("---")

# Seção para exibir o seu vídeo diretamente no Streamlit
st.header("Meu Vídeo no Vimeo")

# URL do seu vídeo específico
vimeo_url = "https://vimeo.com/1013314536"

# Código embed do vídeo do Vimeo
embed_code = """
<iframe src="https://player.vimeo.com/video/1013314536" width="640" height="360" frameborder="0" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe>
"""

# Exibir o vídeo diretamente no Streamlit
st.markdown(embed_code, unsafe_allow_html=True)

# Exibir link para o vídeo diretamente no Vimeo
st.write(f"[Assista ao vídeo diretamente no Vimeo]({vimeo_url})")