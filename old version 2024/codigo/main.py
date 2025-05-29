from operator import itemgetter
from typing import List

import json
import requests

from google.cloud import storage
from io import StringIO

from elasticsearch import Elasticsearch
from langchain_openai import OpenAIEmbeddings

from langchain_openai.chat_models import ChatOpenAI

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
#from langchain_core.pydantic_v1 import BaseModel, Field
from pydantic import BaseModel, Field
from langchain_core.runnables import (
    RunnableLambda,
    ConfigurableFieldSpec,
    RunnablePassthrough,
)
from langchain_core.runnables.history import RunnableWithMessageHistory
import os


from langchain.chains import LLMChain
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import InMemoryChatMessageHistory
#from langchain.schema import HumanMessage, AIMessage
import pandas as pd
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_elasticsearch import ElasticsearchStore
from langchain.chains import create_history_aware_retriever, create_retrieval_chain

class InMemoryHistory(BaseChatMessageHistory, BaseModel):
    """In memory implementation of chat message history."""

    messages: List[BaseMessage] = Field(default_factory=list)

    def add_message(self, message: BaseMessage) -> None:
        """Add a self-created message to the store"""
        self.messages.append(message)

    def clear(self) -> None:
        self.messages = []
    class Config:
        arbitrary_types_allowed = True
        
def get_session_history(store, user_id: str, conversation_id: str) -> BaseChatMessageHistory:
    if (user_id, conversation_id) not in store:
        store[(user_id, conversation_id)] = InMemoryHistory()
    return store[(user_id, conversation_id)]

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)
#formato de texto de WP
def text_Message(number,text):
    data = json.dumps(
            {
                "messaging_product": "whatsapp",    
                "recipient_type": "individual",
                "to": number,
                "type": "text",
                "text": {
                    "body": text
                }
            }
    )
    return data


#Escritura
def convert_chat_history_to_json_string(history):
    """
    Convierte el historial de mensajes a un formato JSON serializable, incluyendo metadatos adicionales.
    """
    # Verificar si el objeto es una instancia de InMemoryChatMessageHistory
    if hasattr(history, 'messages'):  # Revisa si tiene atributo 'messages' para mayor flexibilidad
        serializable_data = [
            {
                'role': 'human' if isinstance(message, HumanMessage) else 'ai',
                'content': message.content,
                #'additional_kwargs': message.additional_kwargs,
                #'response_metadata': message.response_metadata if hasattr(message, 'response_metadata') else {},
                #'id': getattr(message, 'id', None),
                #'usage_metadata': getattr(message, 'usage_metadata', {})
            }
            for message in history.messages
        ]
        return json.dumps(serializable_data, indent=4)
    else:
        raise TypeError("El objeto pasado no tiene un formato de historial válido.")

def upload_to_gcs_directly(bucket_name, file_name, json_data_string):
    """
    Sube un archivo directamente desde una cadena JSON a un bucket de Google Cloud Storage.
    """
    # Crear cliente de almacenamiento
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)

    # Subir el archivo al bucket usando el contenido de la cadena JSON
    blob.upload_from_string(json_data_string, content_type='application/json')
    #print(f"Archivo guardado en GCS: gs://{bucket_name}/{file_name}")
    
#lectura
def download_from_gcs(bucket_name, file_name):
    """
    Descarga un archivo JSON desde Google Cloud Storage.
    """
    # Crear cliente de almacenamiento
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)

    # Descargar el contenido como cadena
    json_data_string = blob.download_as_text()
    return json_data_string

def reconstruct_chat_history_with_id(json_data_string, chat_id):
    """
    Reconstruye un diccionario con el ID original y el objeto InMemoryChatMessageHistory,
    incluyendo metadatos adicionales.
    """
    # Cargar la cadena JSON a una lista de diccionarios
    messages_list = json.loads(json_data_string)
    
    # Crear una lista de mensajes deserializados
    deserialized_messages = []
    for message in messages_list:
        if message['role'] == 'human':
            deserialized_messages.append(
                HumanMessage(
                    content=message['content'],
                    #additional_kwargs=message.get('additional_kwargs', {}),
                    #response_metadata=message.get('response_metadata', {})
                )
            )
        elif message['role'] == 'ai':
            deserialized_messages.append(
                AIMessage(
                    content=message['content'],
                    #additional_kwargs=message.get('additional_kwargs', {}),
                    #response_metadata=message.get('response_metadata', {}),
                    #id=message.get('id', None),
                    #usage_metadata=message.get('usage_metadata', {})
                )
            )
    
    # Crear un objeto InMemoryChatMessageHistory con los mensajes deserializados
    chat_history = InMemoryChatMessageHistory(messages=deserialized_messages)
    
    # Devolver el diccionario con el ID original
    return {chat_id: chat_history}
    
def recibir_mensajes(request):
    try:
        store = {}
        #variables generales 
        #api openAI        
        apikey="sk-************************************"
        #cloud storage
        cstorage = "nombre-cloud-storage"
        #token meta
        tokenmeta = "nombre-webhoot-token"
        whatsapp_token = "EA*************************************"
        #url api Meta whassapp
        whatsapp_url = "https://graph.facebook.com/v20.0/***************/messages"
        #credenciales Elasticsearch | Base de datos de productos usando RAG
        webip="http://**.**.**.**:9200"
        usuario="elastic"
        password="**********"
        indexname="*********"
        #openAI variable Global
        os.environ["OPENAI_API_KEY"] =apikey
        #limite de historial
        longitudtoken=10000
        
        request_args = request.args
        #captura GET para validar la primera vez los tokens
        if request.method == 'GET':
            token = request_args['hub.verify_token']
            challenge = request_args['hub.challenge']


            if token == tokenmeta and challenge != None:
                return challenge
        #Evento POST para los mensajes Whassapp
        else:
            body = request.get_json()
            if not body:
                return 'Invalid JSON body', 400

            # Extracción de los datos basados en la estructura proporcionada
            entry = body['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']
            
            if 'messages' in value and isinstance(value['messages'], list) and len(value['messages']) > 0:

                # Obtener los detalles del mensaje
                message = value['messages'][0]
                number = message['from']  # Tomamos el número directamente del campo 'from'
                messageId = message['id']
                filenumber = number+'.txt'
                # Obtener los detalles del contacto
                contacts = value['contacts'][0]
                name = contacts['profile']['name']

                # Obtener el cuerpo del mensaje de texto
                text = message['text']['body']
                
                #leer si existe historial
                client = storage.Client()
                bucket = client.get_bucket(cstorage)
                store ={}
                blob = bucket.get_blob(number+'.txt')
                
                if blob is not None:
                    json_data_string = download_from_gcs(cstorage, filenumber)
                    chat_history_with_id = reconstruct_chat_history_with_id(json_data_string, (number, number))
                    store = chat_history_with_id
                    downloaded_blob = blob.download_as_string()
                    downloaded_blob = downloaded_blob.decode("utf-8") 
                    lenstore = len(downloaded_blob)
                else:
                    store = {}
                    lenstore=0
                #conexion ElasticSearch    
                db_query= ElasticsearchStore(
                    es_url=webip,
                    es_user=usuario,
                    es_password=password,
                    index_name=indexname,
                    embedding=OpenAIEmbeddings())

                retriever = db_query.as_retriever()
                
                model = ChatOpenAI()
                
                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            """Eres un Asistente de {ability} de nombre "Digibot" y cuentas con acceso a historial de conversaciones, 
                              Usa la información previa en el chat para saber si ya te presentaste de lo contrario presentate con tu nombre y pidele su nombre al cliente,
                              Usa la información previa en el chat para responder siempre con el nombre del cliente, si aun no sabes su nombre preguntalo
                              Usa la información previa en el chat para proporcionar una respuesta que continúe de manera natural el hilo de la conversación. 
                              Si la pregunta no tiene contexto relevante en el historial, menciona que necesitas más información específica del usuario.
                              Aquí hay algo de {context}""",
                        ),
                        MessagesPlaceholder(variable_name="history"),
                        ("human", "{question}"),
                    ]
                )
                
                context = itemgetter("question") | retriever | format_docs
                first_step = RunnablePassthrough.assign(context=context)
                chain = first_step | prompt | model
                
                
                with_message_history = RunnableWithMessageHistory(
                    chain,
                    get_session_history=lambda user_id, conversation_id: get_session_history(store, user_id, conversation_id),
                    input_messages_key="question",
                    history_messages_key="history",
                    history_factory_config=[
                        ConfigurableFieldSpec(
                            id="user_id",
                            annotation=str,
                            name="User ID",
                            description="Unico identificador por usuario.",
                            default="",
                            is_shared=True,
                        ),
                        ConfigurableFieldSpec(
                            id="conversation_id",
                            annotation=str,
                            name="Conversation ID",
                            description="unico identificador por conversacion.",
                            default="",
                            is_shared=True,
                        ),
                    ],
                )
                
                sdata = (
                    with_message_history.invoke(
                        {"ability": "Ventas", "question": text},
                        config={
                            "configurable": {"user_id": number, "conversation_id": number}
                        },
                    )
                )
                dataResponse = sdata.content
                
                data =text_Message(number, dataResponse)
                print(data)
                headers = {'Content-Type': 'application/json',
                           'Authorization': 'Bearer ' + whatsapp_token}
                response = requests.post(whatsapp_url, 
                                         headers=headers, 
                                         data=data)
                print("Ancho de historia")
                print(str(lenstore))
                print(store)
                if (lenstore<longitudtoken):
                    chat_history = store[(number, number)]
                    print(chat_history)
                    json_data_string = convert_chat_history_to_json_string(chat_history)
                    upload_to_gcs_directly(cstorage, filenumber, json_data_string)
                if response.status_code == 200:
                    return 'mensaje enviado', 200
                else:
                    return 'error al enviar mensaje', response.status_code
            else:
                return 'estatus enviado', 200
    except Exception as e:
        print('no enviado ' + str(e))
        return 'no enviado ' + str(e)