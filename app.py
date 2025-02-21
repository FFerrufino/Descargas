from flask import Flask, request, send_file, jsonify
import requests
import io
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image

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
                imagen_bytes = io.BytesIO(img_response.content)
                try:
                    img_obj = Image.open(imagen_bytes).convert("RGB")
                    imagenes_descargadas.append((f"imagen_{idx}.png", img_obj))
                except Exception as e:
                    print(f"Error procesando la imagen {img_url}: {e}")
            else:
                print(f"No se pudo descargar {img_url}")

        if not imagenes_descargadas:
            return {"error": "No se pudo descargar ninguna imagen."}

        return {"mensaje": "Descarga completada", "imagenes_descargadas": imagenes_descargadas, "nombre_archivo": file_name.text.strip()}

    except Exception as e:
        return {"error": str(e)}

@app.route('/descargar-imagenes', methods=['GET'])
def descargar_pdf():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "Falta el parámetro 'url'"}), 400

    resultado = descargar_imagenes_flipbook(url)

    if "error" in resultado:
        return jsonify(resultado), 400

    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    width, height = letter

    for nombre, img_obj in resultado["imagenes_descargadas"]:
        try:
            img_width, img_height = img_obj.size

            scale_factor = min(width / img_width, height / img_height)
            new_width = img_width * scale_factor
            new_height = img_height * scale_factor

            x_position = (width - new_width) / 2
            y_position = (height - new_height) / 2

            temp_img_buffer = io.BytesIO()
            img_obj.save(temp_img_buffer, format="PNG")
            temp_img_buffer.seek(0)

            temp_filename = f"temp_{nombre}.png"
            img_obj.save(temp_filename, "PNG")

            c.drawImage(temp_filename, x_position, y_position, new_width, new_height, preserveAspectRatio=True, mask='auto')
            c.showPage()

        except Exception as e:
            print(f"Error procesando la imagen {nombre}: {e}")

    c.save()
    pdf_buffer.seek(0)

    return send_file(pdf_buffer, as_attachment=True, download_name=resultado["nombre_archivo"]+".pdf", mimetype="application/pdf")


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(debug=False, host="0.0.0.0", port=port)
