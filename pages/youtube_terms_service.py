import streamlit as st

def main():
    st.title("Termos de Serviço - Uso da API do YouTube")

    st.write("""
    Bem-vindo à página de Termos de Serviço relacionada ao uso da API do YouTube em nosso projeto de transcrição de vídeos usando IA.
    
    Por favor, leia atentamente os seguintes termos e condições:
    """)

    st.header("1. Uso da API do YouTube")
    st.write("""
    - Nosso serviço utiliza a API do YouTube para acessar e processar vídeos para fins de transcrição.
    - Ao usar nosso serviço, você concorda em cumprir os Termos de Serviço da API do YouTube (https://developers.google.com/youtube/terms/api-services-terms-of-service).
    - Você é responsável por garantir que tem o direito de usar e transcrever os vídeos que submete através de nosso serviço.
    """)

    st.header("2. Limites e Restrições")
    st.write("""
    - O uso da API do YouTube está sujeito a limites de quota. Podemos restringir o uso do serviço para cumprir essas quotas.
    - Não é permitido usar nosso serviço para acessar ou transcrever conteúdo protegido por direitos autorais sem a devida autorização.
    - O uso abusivo ou excessivo do serviço pode resultar em restrições temporárias ou permanentes.
    """)

    st.header("3. Privacidade e Dados")
    st.write("""
    - Nós não armazenamos os vídeos processados ou suas transcrições além do tempo necessário para fornecer o serviço.
    - As informações de sua conta do Google usadas para autenticar na API do YouTube não são armazenadas por nós.
    - Consulte nossa Política de Privacidade para mais detalhes sobre como tratamos seus dados.
    """)

    st.header("4. Responsabilidade")
    st.write("""
    - Nosso serviço é fornecido "como está". Não garantimos a precisão das transcrições ou a disponibilidade contínua do serviço.
    - Não nos responsabilizamos por quaisquer danos ou perdas resultantes do uso de nosso serviço ou das transcrições geradas.
    """)

    st.header("5. Alterações nos Termos")
    st.write("""
    - Reservamo-nos o direito de modificar estes termos a qualquer momento. As mudanças entrarão em vigor assim que publicadas nesta página.
    - O uso continuado de nosso serviço após alterações nos termos constitui sua aceitação dos novos termos.
    """)

    st.header("6. Contato")
    st.write("""
    Para quaisquer dúvidas ou preocupações sobre estes termos, por favor, entre em contato conosco através do e-mail: suporte@transcricao-video.com
    """)

    st.write("Última atualização: 29/09/2024")

    # Checkbox para confirmar a leitura e aceitação dos termos
    terms_accepted = st.checkbox("Li e aceito os Termos de Serviço", key="youtube_terms_checkbox")

    if terms_accepted:
        st.session_state.youtube_terms_accepted = True
        st.success("Termos aceitos. Você pode agora usar a funcionalidade do YouTube.")
        if st.button("Voltar para a página principal"):
            st.switch_page("transcrita_video.py")
    else:
        st.session_state.youtube_terms_accepted = False
        if st.button("Voltar sem aceitar"):
            st.switch_page("transcrita_video.py")

if __name__ == "__main__":
    main()