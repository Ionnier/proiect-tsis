def giveMeSecretMesage():
    return "Hello World"

def giveMeListOfDocuments():
    return "Hello World"

tools = [
    {
        "type": "function",
        "function": {
            "name": "giveMeSecretMesage",
            "description": "Returns a secret message to give to the user",
            "parameters": {
                
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "giveMeAllTheImages",
            "description": "Returns the link of each of the images inside a document",
            "parameters": {
                
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scanTheQrCode",
            "description": "Returns the scan of a QR code inside the document. The returned result should be sent without any modifications",
            "parameters": {
                
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listEquations",
            "description": "Lists all equations on the PDF",
            "parameters": {
                
            },
        },
    }
]

import functools

names_to_functions = {
    'giveMeSecretMesage': functools.partial(giveMeSecretMesage),
    'giveMeAllTheImages': functools.partial(giveMeListOfDocuments),
    'scanTheQrCode': functools.partial(giveMeListOfDocuments),
}