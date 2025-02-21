from flask import Flask, request, send_file, jsonify
import requests
import zipfile
import io
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote

app = Flask(__name__)

def descargar_imagenes_flipbook(url_pagina):
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url_pagina, headers=headers)
        if response.status_code != 200:
            return {"error": f"Error al obtener la página: {response.status_code}"}

        soup = BeautifulSoup(response.text, 'html.parser')

        file_name2 = soup.find("div", class_="heading-title heading-dotted")
        if not file_name2:
            return {"error": "No se encontró el título del archivo."}
        
        file_name = file_name2.find("span")
        
        flipbook_div = soup.find("div", class_="flipbook")
        if not flipbook_div:
            return {"error": "No se encontró la sección 'flipbook' con imágenes."}

        imagenes = flipbook_div.find_all("img")
        if not imagenes:
            return {"error": "No se encontraron imágenes en 'flipbook'."}

        imagenes_descargadas = []

        for idx, img in enumerate(imagenes, start=1):
            img_src = img.get("src")
            if not img_src:
                continue

            img_url = urljoin(url_pagina, img_src)
            img_url = unquote(img_url)

            img_response = requests.get(img_url, headers=headers)
            if img_response.status_code == 200:
                imagenes_descargadas.append((f"imagen_{idx}.jpg", img_response.content))
            else:
                print(f"No se pudo descargar {img_url}")

        if not imagenes_descargadas:
            return {"error": "No se pudo descargar ninguna imagen."}

        return {"mensaje": "Descarga completada", "imagenes_descargadas": imagenes_descargadas, "nombre_archivo": file_name.text.strip()}

    except Exception as e:
        return {"error": str(e)}

@app.route('/descargar-imagenes', methods=['GET'])
def descargar_imagenes():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "Falta el parámetro 'url'"}), 400

    resultado = descargar_imagenes_flipbook(url)

    if "error" in resultado:
        return jsonify(resultado), 400

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for nombre, contenido in resultado["imagenes_descargadas"]:
            zipf.writestr(nombre, contenido)

    zip_buffer.seek(0)
    
    return send_file(zip_buffer, as_attachment=True, download_name=resultado["nombre_archivo"]+".zip", mimetype="application/zip")

if __name__ == '__main__':
    app.run(debug=True, port=5004)
