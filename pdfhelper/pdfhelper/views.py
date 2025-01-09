from django.shortcuts import render
from django.http import HttpResponse
from django.db import IntegrityError
from django.shortcuts import render, get_object_or_404, redirect
from django.core.files.storage import FileSystemStorage, DefaultStorage
from .settings import UPLOAD_LOCATION
import uuid
import os
from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.config.enums import SupportedPdfParseMethod
from django.http import JsonResponse
import json
from mistralai import Mistral
import time
from .mistrelhelpyer import tools, names_to_functions
import cv2

api_key = os.environ.get("MISTREL_AI_API_KEY")
# model = "pixtral-12b-2409"
# model = "open-mistral-nemo"
model = "mistral-large-latest"

client = Mistral(api_key=api_key)

def index(request):
    knownLocations = [x for x in os.listdir(UPLOAD_LOCATION)]
    context = {
        "knownLocations": knownLocations
    }
    return render(request, 'index.html', context)


def pdf_info(request, pdf_id):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            user_message = body.get('data', [])
            auxiliary = []
            with open(os.path.join(UPLOAD_LOCATION, pdf_id, "original_content_list.json")) as f:
                content = f.read()
                dictionary = json.loads(content)
                systemMessage = "You will be provided with the text content of a PDF page. Answer any questions regard this."
                for entry in dictionary:
                    if entry["type"] == "text":
                        systemMessage += "\n"
                        systemMessage += entry["text"]
                messages = [
                    {
                        "role": "system",
                        "content": systemMessage
                    }
                ]
                for x in user_message:
                    messages.append(x)
                chat_response = client.chat.complete(
                    model= model,
                    messages = messages,
                    n = 1,
                    tool_choice="any",
                    tools=tools
                )
                time.sleep(1)
                print(chat_response)
                if chat_response.choices[0].message.tool_calls is not None and len(chat_response.choices[0].message.tool_calls) > 0:
                    print("will call tool")
                    time.sleep(2)
                    messages.append(chat_response.choices[0].message)
                    auxiliary.append({"role": "assistant", content: chat_response.choices[0].message.content})
                    tool_call = chat_response.choices[0].message.tool_calls[0]
                    function_name = tool_call.function.name
                    function_params = json.loads(tool_call.function.arguments)
                    print("will call tool2")
                    if function_name == "giveMeAllTheImages":
                        folderPath = os.path.join(UPLOAD_LOCATION, pdf_id, "output", "images")
                        returnValue = {}
                        try:
                            files = [f"http://{request.get_host()}/static/{pdf_id}/output/images/{f}" for f in os.listdir(folderPath) if os.path.isfile(os.path.join(folderPath, f))]
                            returnValue = {
                                "images": files
                            }
                        except:
                            pass
                        messages.append({"role":"tool", "name":function_name, "content":json.dumps(returnValue), "tool_call_id":tool_call.id})
                        auxiliary.append({"role":"tool", "name":function_name, "content":json.dumps(returnValue), "tool_call_id":tool_call.id})
                    elif function_name == "scanTheQrCode":
                        folderPath = os.path.join(UPLOAD_LOCATION, pdf_id, "output", "images")
                        function_result = {}
                        if os.path.exists(folderPath):
                            for f in os.listdir(folderPath):
                                filePath = os.path.join(folderPath, f)
                                if not os.path.isfile(filePath):
                                    continue
                                img = cv2.imread(filePath)
                                detector = cv2.QRCodeDetector()
                                data, bbox, straight_qrcode = detector.detectAndDecode(img)
                                if len(data) > 0:
                                    function_result = {
                                        "data": data
                                    }
                        messages.append({"role":"tool", "name":function_name, "content":json.dumps(function_result), "tool_call_id":tool_call.id})
                        auxiliary.append({"role":"tool", "name":function_name, "content":json.dumps(function_result), "tool_call_id":tool_call.id})
                        print(function_result)
                    elif function_name == "listEquations":
                        equations = []
                        for entry in dictionary:
                            if entry["type"] == "equation":
                                equations.append(entry["text"])
                        reply = {
                            "equations": equations
                        }
                        messages.append({"role":"tool", "name":function_name, "content":json.dumps(function_result), "tool_call_id":tool_call.id})
                        auxiliary.append({"role":"tool", "name":function_name, "content":json.dumps(function_result), "tool_call_id":tool_call.id})
                    else:
                        function_result = names_to_functions[function_name](**function_params)
                        messages.append({"role":"tool", "name":function_name, "content":function_result, "tool_call_id":tool_call.id})
                        auxiliary.append({"role":"tool", "name":function_name, "content":function_result, "tool_call_id":tool_call.id})
                    print(f"will call tool3 with {messages[-1]}")
                    response = client.chat.complete(
                        model = model, 
                        messages = messages,
                        n = 1,
                    )
                    print(f"will append new message {response}")
                    newMessage = response.choices[0].message.content
                else:
                    newMessage = chat_response.choices[0].message.content
                return JsonResponse({"reply": newMessage, "auxiliary": auxiliary}, json_dumps_params={"ensure_ascii": False})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    context = {
        "id": pdf_id
    }
    return render(request, 'pdf_info.html', context)


def upload(request):
    if request.method == 'POST':
        if request.FILES is None or len(request.FILES) != 1:
            return HttpResponse(status=418)
        id = list(request.FILES.keys())[0]
        file = request.FILES.get(id)
        (path, dirName) = generate_unique_path_name()
        FileSystemStorage(location=path).save("original.pdf", file)

        # args
        pdf_file_name = os.path.join(path, "original.pdf")
        name_without_suff = pdf_file_name.split(".")[0]

        # prepare env
        local_image_dir, local_md_dir = f"{path}/output/images", f"{path}/output"
        image_dir = str(os.path.basename(local_image_dir))

        os.makedirs(local_image_dir, exist_ok=True)

        image_writer, md_writer = FileBasedDataWriter(local_image_dir), FileBasedDataWriter(
            local_md_dir
        )
        image_dir = str(os.path.basename(local_image_dir))

        # read bytes
        reader1 = FileBasedDataReader("")
        pdf_bytes = reader1.read(pdf_file_name)  # read the pdf content

        # proc
        ## Create Dataset Instance
        ds = PymuDocDataset(pdf_bytes)

        ## inference
        if ds.classify() == SupportedPdfParseMethod.OCR:
            infer_result = ds.apply(doc_analyze, ocr=True)

            ## pipeline
            pipe_result = infer_result.pipe_ocr_mode(image_writer)

        else:
            infer_result = ds.apply(doc_analyze, ocr=False)

            ## pipeline
            pipe_result = infer_result.pipe_txt_mode(image_writer)

        ### draw model result on each page
        modelName = f"{name_without_suff}_model.pdf"
        infer_result.draw_model(os.path.join(local_md_dir, modelName))

        ### draw layout result on each page
        layoutName = f"{name_without_suff}_layout.pdf"
        pipe_result.draw_layout(os.path.join(local_md_dir, layoutName))

        ### draw spans result on each page
        spansName = f"{name_without_suff}_spans.pdf"
        pipe_result.draw_span(os.path.join(local_md_dir, spansName))

        ### dump markdown
        markdownName = f"{name_without_suff}.md"
        pipe_result.dump_md(md_writer, markdownName, image_dir)

        ### dump content list
        contentListName = f"{name_without_suff}_content_list.json"
        pipe_result.dump_content_list(md_writer, contentListName, image_dir)
        return JsonResponse({'allLocations': f"/{dirName}/"}, json_dumps_params={"ensure_ascii": False})
        
    return HttpResponse(status=418)


def generate_unique_path_name():
    while True:
        random = str(uuid.uuid4())
        path = os.path.join(UPLOAD_LOCATION, random)
        if os.path.isdir(path):
            continue
        os.makedirs(path, exist_ok=True)
        return (path, random)