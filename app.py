from flask import Flask, request, send_file, jsonify
import requests
import io
import os
import concurrent.futures
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image

app = Flask(__name__)

def descargar_imagen(img_url):
    """ Descarga una imagen y la convierte en un objeto PIL """
    try:
        response = requests.get(img_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if response.status_code == 200:
            imagen_bytes = io.BytesIO(response.content)
            img_obj = Image.open(imagen_bytes).convert("RGB")
            return img_obj
    except Exception as e:
        print(f"Error descargando {img_url}: {e}")
    return None

def descargar_imagenes_flipbook(url_pagina):
    """ Obtiene la lista de imágenes de flipbook y las descarga en paralelo """
    try:
        response = requests.get(url_pagina, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if response.status_code != 200:
            return {"error": f"Error al obtener la página: {response.status_code}"}

        soup = BeautifulSoup(response.text, 'html.parser')
        file_name2 = soup.find("div", class_="heading-title heading-dotted")
        if not file_name2:
            return {"error": "No se encontró el título del archivo."}
        
        file_name = file_name2.find("span").text.strip()
        flipbook_div = soup.find("div", class_="flipbook")
        if not flipbook_div:
            return {"error": "No se encontró la sección 'flipbook' con imágenes."}

        imagenes = flipbook_div.find_all("img")
        if not imagenes:
            return {"error": "No se encontraron imágenes en 'flipbook'."}

        # Obtener URLs de las imágenes
        imagen_urls = [urljoin(url_pagina, unquote(img.get("src"))) for img in imagenes if img.get("src")]

        # Descargar imágenes en paralelo
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            imagenes_descargadas = list(executor.map(descargar_imagen, imagen_urls))

        # Filtrar imágenes no descargadas correctamente
        imagenes_descargadas = [img for img in imagenes_descargadas if img]

        if not imagenes_descargadas:
            return {"error": "No se pudo descargar ninguna imagen."}

        return {"mensaje": "Descarga completada", "imagenes_descargadas": imagenes_descargadas, "nombre_archivo": file_name}

    except Exception as e:
        return {"error": str(e)}

@app.route('/descargar-imagenes', methods=['GET'])
def descargar_pdf():
    """ Genera y devuelve un PDF con las imágenes descargadas """
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "Falta el parámetro 'url'"}), 400

    resultado = descargar_imagenes_flipbook(url)

    if "error" in resultado:
        return jsonify(resultado), 400

    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    width, height = letter

    imagen_temp_paths = []  # Lista para eliminar imágenes después

    for i, img_obj in enumerate(resultado["imagenes_descargadas"]):
        try:
            # Redimensionar imagen sin perder calidad
            img_obj.thumbnail((width, height), Image.LANCZOS)
            img_width, img_height = img_obj.size

            x_position = (width - img_width) / 2
            y_position = (height - img_height) / 2

            # Guardar imagen en disco temporalmente (Render usa `/tmp/`)
            temp_filename = f"/tmp/temp_image_{i}.png"
            img_obj.save(temp_filename, "PNG")
            imagen_temp_paths.append(temp_filename)

            # Dibujar la imagen en el PDF usando la ruta
            c.drawImage(temp_filename, x_position, y_position, img_width, img_height, preserveAspectRatio=True, mask='auto')
            c.showPage()

        except Exception as e:
            print(f"Error procesando imagen {i} en PDF: {e}")

    c.save()
    pdf_buffer.seek(0)

    # Eliminar imágenes temporales después de crear el PDF
    for path in imagen_temp_paths:
        try:
            os.remove(path)
        except Exception as e:
            print(f"Error eliminando imagen temporal {path}: {e}")

    return send_file(pdf_buffer, as_attachment=True, download_name=resultado["nombre_archivo"]+".pdf", mimetype="application/pdf")



if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(debug=False, host="0.0.0.0", port=port)
