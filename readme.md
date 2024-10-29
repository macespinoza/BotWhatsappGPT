# BotWhatsappGPT

Este repositorio contiene una solución integral para crear un bot de WhatsApp utilizando LangChain, Google Cloud, y otras tecnologías clave. A continuación, se detallan los componentes del repositorio y las instrucciones para su correcta configuración.

## Estructura del Repositorio

### Código
- **`main.py`**: Código fuente completo de la solución integrada, diseñado para ejecutarse en **Google Cloud Function**.
- **`requirements.txt`**: Lista de librerías necesarias para la aplicación.

### JSON
- **`EjemplohistorialResumen.json`**: Ejemplo de cómo se está guardando actualmente el historial de conversaciones en **Google Cloud Storage**.
- **`EjemploHistoricoGPT.json`**: Ejemplo de datos completos del historial utilizado por el bot. Se han eliminado ciertos campos para reducir costos de tokens.
- **`notificacionWebhook.json`**: Ejemplo de la estructura JSON de retorno que **Meta** envía al Webhook configurado.

### Otros
- **`EjemploConversacion.jpg`**: Imagen que ejemplifica una conversación simple con el modelo GPT.
- **`productos.csv`**: Lista de productos cargados a **ElasticSearch** para la búsqueda y consulta.

## Nivel de Conocimiento Requerido

Para implementar y comprender completamente esta solución, se recomienda tener un nivel de conocimiento intermedio en las siguientes tecnologías:

- **Python**: Intermedio
- **LangChain**: Intermedio
- **ElasticSearch**: Básico
- **Google Cloud**: Intermedio
- **Meta (Plataforma WhatsApp)**: Básico

## Configuración de Variables

En el archivo **`main.py`**, es necesario reemplazar las siguientes variables con sus propios valores para garantizar el correcto funcionamiento de la aplicación:

- **API de OpenAI para GPT**:  
  `apikey = "sk-************************************"`
  
- **Nombre del Cloud Storage para almacenar el historial**:  
  `cstorage = "nombre-cloud-storage"`

- **Datos de token de la plataforma Meta**:  
  `tokenmeta = "nombre-webhook-token"`  
  `whatsapp_token = "EA*************************************"`

- **URL de la API de Meta WhatsApp para envío de mensajes**:  
  `whatsapp_url = "https://graph.facebook.com/v20.0/***************/messages"`

- **Credenciales de ElasticSearch para almacenar productos vía pipeline**:  
  `webip = "http://**.**.**.**:9200"`  
  `usuario = "elastic"`  
  `password = "**********"`  
  `indexname = "*********"`

- **Tamaño máximo del historial**:  
  `longitudtoken = 10000`  
  > El tamaño máximo que puede tener el historial; si crece más de este límite, no se guardará más historial.

## Configuración de Cloud Storage

Es recomendable establecer un ciclo de vida en **Google Cloud Storage** para que los archivos se almacenen solo por un tiempo determinado. Esto permite que, si un usuario regresa después de un año, no se mantenga innecesariamente su información almacenada, lo cual es una decisión relativa al negocio.

## Cálculo de Costos

### Costo de GPT-5 Usado para esta Solución

- **$0.003000** por cada **1K tokens de entrada**
- **$0.001500** por cada **1K tokens de salida**

### Ejemplo de Consumo de Tokens

Cada interacción acumula el historial de las interacciones previas, lo que incrementa el número de tokens utilizados:

1. **Primera Interacción**: 189 tokens  
2. **Segunda Interacción**: 189 + 339 = 528 tokens  
3. **Tercera Interacción**: 189 + 339 + 454 = 982 tokens  
4. **Cuarta Interacción**: 189 + 339 + 454 + 432 = 1,414 tokens  
5. **Quinta Interacción**: 189 + 339 + 454 + 432 + 533 = 1,947 tokens  
6. **Sexta Interacción**: 189 + 339 + 454 + 432 + 533 + 305 = 2,252 tokens  
7. **Séptima Interacción**: 189 + 339 + 454 + 432 + 533 + 305 + 331 = 2,583 tokens  
8. **Octava Interacción**: 189 + 339 + 454 + 432 + 533 + 305 + 331 + 449 = 3,032 tokens  

**Total de Tokens Gastados**: 12,927  
**Costo Aproximado**: $0.036 dólares

## Desarrollado por

**MAC**: Miguel Angel Cotrina
**Linkedin**: https://www.linkedin.com/in/mcotrina/
