import os
import google.generativeai as genai
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

CLINICS_LIST = """
"الباطنة-العامة", "غدد-صماء-وسكر", "جهاز-هضمي-ومناظير", "باطنة-وقلب", "الجراحة-العامة",
"مناعة-وروماتيزم", "نساء-وتوليد", "أنف-وأذن-وحنجرة", "الصدر", "أمراض-الذكورة", "الجلدية",
"العظام", "المخ-والأعصاب-باطنة", "جراحة-المخ-والأعصاب", "المسالك-البولية", "الأوعية-الدموية",
"الأطفال", "الرمد", "تغذية-الأطفال", "مناعة-وحساسية-الأطفال", "القلب", "رسم-قلب-بالمجهود-وإيكو",
"جراحة-التجميل", "علاج-البواسير-والشرخ-بالليزر", "الأسنان", "السمعيات", "أمراض-الدم"
"""

# تهيئة النموذج خارج الدالة لتجنب إعادة التهيئة في كل طلب
# global_model سيكون متاحًا بعد التهيئة الأولية
global_model = None

@app.before_request
def initialize_gemini_model():
    global global_model
    if global_model is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("CRITICAL ERROR: GEMINI_API_KEY is not set in environment variables.")
            # يمكنك رفع استثناء هنا أو التعامل مع الخطأ
            return jsonify({"error": "Server configuration error: API Key missing."}), 500

        genai.configure(api_key=api_key)
        
        try:
            # حاول تحديد نقطة النهاية لمنطقتك إذا كانت مختلفة عن us-central1
            # "us-central1" هي الافتراضية
            # إذا كنت تعمل في europe-west1، قد تحتاج إلى شيء مثل
            # client_options = {"api_endpoint": "europe-west1-aiplatform.googleapis.com"}
            # ولكن google.generativeai عادة ما يستخدم نقطة نهاية عالمية.
            # قد يكون أفضل هو الانتقال إلى Vertex AI SDK
            
            global_model = genai.GenerativeModel('gemini-1.5-flash')
            print("Gemini model 'gemini-1.5-flash' initialized successfully.")
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to initialize Gemini model: {str(e)}")
            # Handle the error appropriately, maybe re-raise or set global_model to None
            return jsonify({"error": f"Server configuration error: AI model failed to load. Details: {str(e)}"}), 500


@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route("/api/recommend", methods=["POST"])
def recommend_clinic():
    global global_model
    if global_model is None:
        # يجب أن تكون قد تمت التهيئة في before_request
        return jsonify({"error": "AI model not initialized."}), 500

    try:
        data = request.get_json()
        symptoms = data.get('symptoms')
        if not symptoms:
            return jsonify({"error": "Missing symptoms"}), 400
        
        prompt = f"""
        أنت مساعد طبي خبير ومحترف في مستشفى كبير. مهمتك هي تحليل شكوى المريض بدقة واقتراح أفضل عيادتين بحد أقصى من قائمة العيادات المتاحة.
        قائمة معرفات (IDs) العيادات المتاحة هي: [{CLINICS_LIST}]
        شكوى المريض: "{symptoms}"
        ردك **يجب** أن يكون بصيغة JSON فقط، بدون أي نصوص أو علامات قبله أو بعده، ويحتوي على قائمة اسمها "recommendations" بداخلها عناصر تحتوي على "id" و "reason".
        """
        
        # تحديد response_mime_type عند استدعاء generate_content
        response = global_model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )

        # التحقق من أن response.text ليس فارغًا قبل محاولة تحليله
        if not response.text:
            print("ERROR: Gemini API returned an empty response.")
            return jsonify({"error": "Gemini API returned an empty response."}), 500

        # لا داعي لـ replace("```json", "").replace("```", "") إذا كان response_mime_type يعمل
        # ولكن تركه كـ fall-back لا يضر
        try:
            json_response = json.loads(response.text.strip())
        except json.JSONDecodeError:
            print(f"ERROR: Failed to decode JSON from Gemini response. Raw response: {response.text}")
            # حاول التنظيف مرة أخرى كـ fall-back إذا كانت الاستجابة غير متوقعة
            cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
            json_response = json.loads(cleaned_text)

        return jsonify(json_response)
        
    except Exception as e:
        print(f"ERROR in /api/recommend: {str(e)}")
        # أضف تفاصيل الخطأ في الاستجابة لمساعدتك في Debugging
        return jsonify({"error": f"An internal server error occurred: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

