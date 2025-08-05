#!/usr/bin/env python3
"""
Script de configuração para Google Drive
Este script ajuda a configurar as credenciais do Google Drive
"""

import os
import json
import webbrowser
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

# Configurações do Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.readonly',
          'https://www.googleapis.com/auth/drive.file']


def setup_google_drive():
    """
    Configura as credenciais do Google Drive
    """
    print("=== Configuração do Google Drive ===")
    print()

    # Verificar se o arquivo de credenciais existe
    if not os.path.exists('credentials.json'):
        print("❌ Arquivo 'credentials.json' não encontrado!")
        print()
        print("Para configurar o Google Drive, siga estes passos:")
        print()
        print("1. Acesse https://console.cloud.google.com/")
        print("2. Crie um novo projeto ou selecione um existente")
        print("3. Ative a API do Google Drive")
        print("4. Vá para 'APIs & Services' > 'Credentials'")
        print("5. Clique em 'Create Credentials' > 'OAuth 2.0 Client IDs'")
        print("6. Configure o tipo como 'Desktop application'")
        print("7. Baixe o arquivo JSON e renomeie para 'credentials.json'")
        print("8. Coloque o arquivo na raiz deste projeto")
        print()
        return False

    print("✅ Arquivo 'credentials.json' encontrado!")
    print()

    # Tentar autenticar
    creds = None

    # Verificar se existe token salvo
    if os.path.exists('drive_token.pickle'):
        print("🔍 Verificando token existente...")
        with open('drive_token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # Se não há credenciais válidas, fazer autenticação
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Renovando token...")
            creds.refresh(Request())
        else:
            print("🔐 Iniciando autenticação...")
            print("O navegador será aberto para você autorizar o aplicativo.")
            print()

            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=8080)
                print("✅ Autenticação concluída!")
            except Exception as e:
                print(f"❌ Erro na autenticação: {str(e)}")
                return False

        # Salvar credenciais
        with open('drive_token.pickle', 'wb') as token:
            pickle.dump(creds, token)
        print("💾 Token salvo para uso futuro!")

    else:
        print("✅ Token válido encontrado!")

    print()
    print("🎉 Configuração do Google Drive concluída!")
    print("Agora você pode usar a funcionalidade do Google Drive no aplicativo.")
    print()

    return True


def test_connection():
    """
    Testa a conexão com o Google Drive
    """
    try:
        from googleapiclient.discovery import build

        # Carregar credenciais
        with open('drive_token.pickle', 'rb') as token:
            creds = pickle.load(token)

        # Criar serviço
        service = build('drive', 'v3', credentials=creds)

        # Testar listagem de arquivos
        results = service.files().list(
            pageSize=1,
            fields="nextPageToken, files(id, name)"
        ).execute()

        print("✅ Conexão com Google Drive testada com sucesso!")
        return True

    except Exception as e:
        print(f"❌ Erro ao testar conexão: {str(e)}")
        return False


if __name__ == "__main__":
    print("🚀 Iniciando configuração do Google Drive...")
    print()

    if setup_google_drive():
        print("🧪 Testando conexão...")
        if test_connection():
            print()
            print(
                "🎯 Tudo configurado! Execute 'streamlit run transcrita_video.py' para usar o aplicativo.")
        else:
            print()
            print("⚠️  Configuração concluída, mas houve erro no teste de conexão.")
            print("Tente executar o aplicativo mesmo assim.")
    else:
        print()
        print("❌ Configuração não concluída. Verifique as instruções acima.")
