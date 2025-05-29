from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
import psycopg
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_elasticsearch import ElasticsearchStore
from langgraph.prebuilt import create_react_agent
import json
from flask import Flask, jsonify, request
import os
import requests

os.environ["OPENAI_API_KEY"] ="sk...."

app = Flask(__name__)

@app.route('/webhook', methods=['GET', 'POST'])
def main():
    request_args = request.args
    whatsapp_token = "EAA"
    whatsapp_url = "https://graph.facebook.com/v22.0/xxxxxxx/messages"
    tokenmeta = "xxxxxxxxxx"

    # captura GET para validar la primera vez los tokens
    if request.method == 'GET':
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if token == tokenmeta and challenge != None:
            return challenge
    # Evento POST para los mensajes Whassapp
    else:
        body = request.get_json()
        if not body:
            return 'Invalid JSON body', 400
        # Extracción de los datos basados en la estructura proporcionada
        entry = body['entry'][0]
        changes = entry['changes'][0]
        if not changes:
            return "No changes", 200
        value = changes['value']
        if 'messages' in value and isinstance(value['messages'], list) and len(value['messages']) > 0:
            # Obtener los detalles del mensaje
            message = value['messages'][0]
            number = message['from']  # Tomamos el número directamente del campo 'from'
            messageId = message['id']
            # Obtener los detalles del contacto
            contacts = value['contacts'][0]
            name = contacts['profile']['name']
            # Obtener el cuerpo del mensaje de texto
            text = message['text']['body']
            # Enviamos por la funcion creada
            data = agent_message(number, text)
            headers = {'Content-Type': 'application/json',
                       'Authorization': 'Bearer ' + whatsapp_token}
            response = requests.post(whatsapp_url, headers=headers, data=data)
            return "EVENT_RECEIVED", 200
        else:
            # Solo logueas que hubo un evento sin mensaje
            print("Evento recibido sin mensaje: ", body)
            return "No message content", 200

def agent_message(number, msg):
    # Variables de memoria
    uribd = "postgresql://user:password@0.0.0.0:5432/postgres?sslmode=disable"
    elasticw = "j67jdedrzUivAfkhrkI7"
    connection_kwargs = {
        "autocommit": True,
        "prepare_threshold": 0,
    }
    # Base de datos vectorial
    db_query = ElasticsearchStore(
        es_url="http://0.0.0.0:9200",
        es_user="elastic",
        es_password=elasticw,
        index_name="lg-productos",
        embedding=OpenAIEmbeddings())

    retriever = db_query.as_retriever()

    tool_rag = retriever.as_tool(
        name="busqueda_productos",
        description="Consulta en la informacion de computadoras, y articulos de computo",
    )

    # Inicializamos la memoria
    with ConnectionPool(
            # Example configuration
            conninfo=uribd,
            max_size=20,
            kwargs=connection_kwargs,
    ) as pool:
        checkpointer = PostgresSaver(pool)

        # Inicializamos el modelo
        model = ChatOpenAI(model="gpt-4.1-2025-04-14")

        # Agrupamos las herramientas
        tolkit = [tool_rag]

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system",
                 """
                 Eres un asistente gentil de ventas de computadoras especializado.
                 Utiliza únicamente las herramientas disponibles para responder y brindar infromacion.
                 Si no cuentas con una herramienta específica para resolver una pregunta, infórmalo claramente e indica como pueded ayudar.
 
                 Tu objetivo es guiar al cliente de forma amigable, breve y conversacional, como si fueras un amigo experto en tecnología. Sigue estos pasos:
 
                 1. Saluda y pregunta: Da un saludo cálido, pregunta qué busca el cliente y si tiene una idea clara de lo que necesita (ej. laptop para gaming, PC de oficina, accesorios). Si no sabe, sugiere 2-3 opciones populares, priorizando productos con más stock.
                 2. Consulta productos: Usa la información de productos segun su necesidad para responder con detalles de productos relevantes (nombre, descripción, precio, stock). Destaca los que tienen mayor disponibilidad.
                 3. Envío o tienda: Pregunta si prefiere recoger en tienda o entrega a domicilio (costo adicional de S/20 para compras menores a S/500; gratis si supera S/500). Si no alcanza los S/50, sugiere añadir algo  para obtener envío gratis o confirma si ya lo logró.
                 4. Confirmar pedido: Resume el pedido y pregunta si quiere añadir algo más.
                 5. Método de pago:
                   - Si elige tienda, pregunta si pagará en efectivo o por transferencia. Solicita su nombre y apellido para generar un código de pedido (formato: AAAAMMDD_HHMMSS_NombreApellido, ej. 20250414_153022_JuanPerez).
                   - Si elige domicilio, pide una dirección completa y confirma que el pago será por transferencia.
                 6. Cierre de compra:
                   - Para transferencias, proporciona el número de cuenta 12730317292820 en BankaNet y pide confirmar el pago.
                   - Para pago en tienda, entrega el código de pedido.
                 7. Estilo: Sé breve, usa un tono entusiasta y natural. Evita tecnicismos a menos que el cliente los mencione. Responde solo lo necesario para avanzar la conversación.
 
                 """),
                ("human", "{messages}"),
            ]
        )
        # inicializamos el agente
        agent_executor = create_react_agent(model, tolkit, checkpointer=checkpointer, prompt=prompt)

        config = {"configurable": {"thread_id": number}}
        response = agent_executor.invoke({"messages": [HumanMessage(content=msg)]}, config=config)
        return format_message(number, response['messages'][-1].content)


def format_message(number, text):
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

if __name__ == '__main__':
    # La aplicación escucha en el puerto 8080, requerido por Cloud Run
    app.run(host='0.0.0.0', port=8080)