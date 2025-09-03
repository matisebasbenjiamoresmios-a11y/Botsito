from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"txt", "pdf", "docx"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    user_input = data.get("message", "")

    # Simulamos respuesta del bot
    respuesta = f"Hola! Soy un asistente digital diseñado para responderle a tus preguntas y ayudarte en lo que pueda. ¡Tengo la habilidad de resumir textos largos en español, así como de responder preguntas prácticas con claridad! Me complace atenderte. ¡Si tienes alguna pregunta, no dude en preguntarme!"
    return jsonify({"response": respuesta})

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"message": "No se envió ningún archivo"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"message": "Nombre de archivo vacío"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        # Simular un resumen como respuesta
        resumen = f"✅ Archivo '{filename}' recibido correctamente.\n(Resumen simulado aquí...)"
        return jsonify({"message": resumen})

    return jsonify({"message": "Tipo de archivo no permitido"}), 400

@app.route("/reset", methods=["POST"])
def reset():
    return jsonify({"message": "Contexto reiniciado"})

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    if path == "" or path == "index.html":
        return send_from_directory(".", "index.html")
    return send_from_directory(".", path)

if __name__ == "__main__":
    app.run(debug=True)
