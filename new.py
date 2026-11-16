import static_ffmpeg
static_ffmpeg.add_paths()

import asyncio
import os
import re
import json
import wave
import math
import struct
import audioop  # لو بايثون 3.13+: pip install audioop-lts
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pyrogram import Client
from pytgcalls import PyTgCalls, filters as fl
from pytgcalls.types import MediaStream, RecordStream, AudioQuality, StreamFrames, Direction
import edge_tts
from groq import Groq
from mutagen.mp3 import MP3  # pip install mutagen

try:
    from ddgs import DDGS  # pip install ddgs
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

# ================= الإعدادات =================
# المفاتيح مكتوبة هنا مؤقتاً لحد ما نخلص الاختبار (ولو متغير بيئة موجود بياخد الأولوية)
API_ID = int(os.getenv("TG_API_ID", "39154761"))
API_HASH = os.getenv("TG_API_HASH", "6d9a4d05676699954be3a2baf7fcbd8d")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "sk_ae707d2f2ac9c2b95d2294cbc3cd6fa46457c99dd88788de")
ELEVENLABS_VOICE_ID = "pFZP5JQG7iQjIQuC4Bku"

# بحث الويب المدمج في Groq (موديلات compound) بنفس مفتاح Groq من غير كريدتس إضافية
GROQ_SEARCH_MODELS = ["groq/compound-mini", "groq/compound"]

OWNER_NAME = "هدى"            # صاحبة المساعدة (مش اللي بتكلمها سلمى)
ASSISTANT_NAME = "سلمى"
SISTER_PHONE = ""
CALL_TIME = ""               # فاضي = فوراً، أو "2026-11-12 19:00:00"
ENABLE_WEB_SEARCH = True

# إعدادات الاستماع
VOICE_RMS_MIN = 400           # أقل حد للكلام (الحد الفعلي بيتظبط تلقائياً حسب ضوضاء المكالمة)
NOISE_MULTIPLIER = 3.0
SILENCE_SECONDS = 1.7
MIN_SPEECH_SECONDS = 0.25
PRE_ROLL_SECONDS = 0.5
MAX_TURN_SECONDS = 25.0

# إعدادات الثقة في التفريغ
NO_SPEECH_MAX = 0.6           # فوق الرقم ده المقطع يعتبر ضوضاء
MIN_AVG_LOGPROB = -0.9        # تحت الرقم ده التفريغ مش مضمون، فنطلب إعادة
MAX_UNCLEAR_IN_ROW = 2        # بعد كده نقبل الكلام زي ما هو بدل ما نلف في دايرة

UNCLEAR_PHRASE = "معلش مسمعتش كويس، ممكن تعيدي تاني؟"

SMART_AI_PROMPT = f"""
أنتِ "{ASSISTANT_NAME}"، مساعدة ذكاء اصطناعي شخصية تابعة لـ "{OWNER_NAME}". بتتكلمي بالعامية المصرية القاهرية الطبيعية.
أنتِ بتكلمي دلوقتي شخص على التليفون (قريبة لـ {OWNER_NAME})، والشخص ده مش {OWNER_NAME}.

قواعد الهوية (مهمة جداً):
- أنتِ مساعدة {OWNER_NAME}، مش {OWNER_NAME} نفسها. {OWNER_NAME} مش على المكالمة.
- ممنوع تنادي اللي بتكلميها باسم {OWNER_NAME}، وممنوع تفترضي إنها {OWNER_NAME}.
- ممنوع تسألي عن {OWNER_NAME} أو عن أخبارها أو حالها (زي "{OWNER_NAME} عاملة إيه").
- متعرفيش اسم اللي بتكلميها. متنادييهاش بأي اسم ومتخمّنيش اسم.
- في أول رد بس: قولي ألو وعرّفي نفسك بسرعة إنك {ASSISTANT_NAME} المساعدة الذكية بتاعة {OWNER_NAME}، واسألي "أقدر أساعدك في إيه؟".

الفهم:
- الكلام جاي من تفريغ صوتي، فممكن فيه كلمة غلط. لو جملة مش منطقية أو ناقصة، اطلبي منها تعيد بلطف بدل ما تخمّني المقصود.
- افهمي العامية المصرية والكلمات الإنجليزي المعرّبة (تاسك، ميتينج، أوكي، ديدلاين، أبديت، إيميل) من غير ما تغيّري أو تصحّحي كلامها.

الدقة (أهم حاجة):
- جاوبي على اللي اتسألتيه بالظبط، من غير ما تضيفي حاجة محدش سأل عنها.
- متقوليش أي معلومة أو رقم أو تاريخ أو اسم إلا لو متأكدة منه 100%. لو مش متأكدة قولي "مش متأكدة" بصراحة.
- الحسابات: احسبي بالراحة وجاوبي بالنتيجة الصحيحة بس.
- لو اتبعتلك "نتائج بحث من الإنترنت" مع السؤال، اعتمدي عليها وحدها في المعلومات المتغيرة (أسعار، أخبار، طقس، نتايج)، وقوليها بأسلوبك مختصرة. لو النتايج مفيهاش الإجابة أو متضاربة، قولي إنك مش لاقية معلومة مؤكدة. متألفيش.
- لو سألتك عن تفاصيل شخصية عن {OWNER_NAME} أو مواعيدها، قولي إنك مش عارفة وهتوصّلي رسالتها لـ {OWNER_NAME}.

الردود:
- جملة أو جملتين قصيرين (حوالي 8 إلى 30 كلمة) عشان المكالمة تفضل طبيعية.
- ممنوع الإيموجي والرموز والنجوم والترقيم بالأرقام. اكتبي الأرقام بالحروف لأنها هتتنطق.
- لو بتقفل المكالمة (قالت سلام، باي، هقفل، مع السلامة)، ردي بوداع لطيف واكتبي في الآخر [END_CALL].

تاريخ النهاردة: {datetime.now().strftime("%Y-%m-%d")}.
"""
# =============================================

groq_client = Groq(api_key=GROQ_API_KEY)
http_session = requests.Session()

recorded_audio_buffer = bytearray()
pre_roll_buffer = bytearray()
is_recording = False
last_voice_time = 0.0
voiced_bytes = 0
has_spoken = False
detected_sample_rate = 48000
detected_channels = 2
noise_floor = 150.0

HALLUCINATIONS = [
    "اشتركوا في القناة", "اشترك في القناة", "ترجمة نانسي", "شكرا على المشاهدة",
    "شكراً على المشاهدة", "subscribe", "thank you for watching", "اشتركوا", "لا تنسوا الاشتراك",
    "ترجمة", "امارا", "نهاية الحلقة",
]

SEARCH_HINTS = re.compile(
    r"(سعر|أسعار|اسعار|النهاردة|النهارده|دلوقتي|دلوقت|طقس|الجو|أخبار|اخبار|"
    r"دولار|يورو|ذهب|دهب|نتيجة|ماتش|مين هو|مين هي|فين|امتى|إمتى|كام)"
)

# ---------------- اختيار الموديل تلقائياً ----------------
PREFERRED_KEYWORDS = [
    "llama-3.3-70b", "gpt-oss-120b", "llama-3.1-70b", "llama-4",
    "qwen", "gpt-oss-20b", "llama-3.1-8b", "llama",
]
EXCLUDE_KEYWORDS = ["whisper", "guard", "tts", "playai", "orpheus", "distil", "embed", "compound", "safeguard"]


def get_model_candidates():
    try:
        ids = [m.id for m in groq_client.models.list().data]
    except Exception as e:
        print("تعذر جلب قائمة الموديلات:", e)
        ids = []

    chat_ids = [i for i in ids if not any(x in i.lower() for x in EXCLUDE_KEYWORDS)]
    print("الموديلات المتاحة:", chat_ids)

    ordered = []
    for kw in PREFERRED_KEYWORDS:
        for i in chat_ids:
            if kw in i.lower() and i not in ordered:
                ordered.append(i)
    for i in chat_ids:
        if i not in ordered:
            ordered.append(i)

    for fallback in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "openai/gpt-oss-20b"]:
        if fallback not in ordered:
            ordered.append(fallback)
    return ordered


MODEL_CANDIDATES = get_model_candidates()
ACTIVE_MODEL = MODEL_CANDIDATES[0]
print("الموديل المبدئي:", ACTIVE_MODEL)

WHISPER_MODELS = ["whisper-large-v3", "whisper-large-v3-turbo"]


# ---------------- الصوت ----------------
def calculate_rms(pcm_bytes):
    count = len(pcm_bytes) // 2
    if count == 0:
        return 0
    shorts = struct.unpack(f"<{count}h", pcm_bytes[:count * 2])
    return math.sqrt(sum(s * s for s in shorts) / count)


def bytes_per_second():
    return detected_sample_rate * detected_channels * 2


def voice_threshold():
    """حد الكلام بيتظبط تلقائياً حسب ضوضاء المكالمة."""
    return max(VOICE_RMS_MIN, noise_floor * NOISE_MULTIPLIER)


async def listen_for_turn():
    """يسجل لحد ما الكلام يخلص فعلاً (صمت كفاية بعد كلام حقيقي)."""
    global is_recording, recorded_audio_buffer, last_voice_time, has_spoken, voiced_bytes
    loop = asyncio.get_event_loop()
    recorded_audio_buffer = bytearray(pre_roll_buffer)
    voiced_bytes = 0
    has_spoken = False
    start = loop.time()
    last_voice_time = start
    is_recording = True

    while True:
        await asyncio.sleep(0.05)
        now = loop.time()
        if has_spoken and (now - last_voice_time) >= SILENCE_SECONDS:
            break
        if (now - start) >= MAX_TURN_SECONDS:
            break
        if not has_spoken and (now - start) >= 12.0:
            break

    is_recording = False
    return has_spoken


def generate_tts_sync(text, filename):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream?optimize_streaming_latency=3"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY,
    }
    data = {
        "text": text,
        "model_id": "eleven_flash_v2_5",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.85},
    }
    try:
        r = http_session.post(url, json=data, headers=headers, timeout=10)
        if r.status_code == 200 and r.content:
            with open(filename, "wb") as f:
                f.write(r.content)
            return True
    except Exception:
        pass
    return False


async def text_to_speech(text, filename):
    clean = text.replace("[END_CALL]", "").strip()
    loop = asyncio.get_running_loop()
    ok = await loop.run_in_executor(None, generate_tts_sync, clean, filename)
    if not ok:
        await edge_tts.Communicate(clean, "ar-EG-SalmaNeural").save(filename)
    return filename, clean


def audio_duration(filename, fallback_text=""):
    try:
        return MP3(filename).info.length
    except Exception:
        return max(2.5, len(fallback_text) * 0.075)


# ---------------- الذكاء + البحث ----------------
def _is_model_missing(e):
    msg = str(e).lower()
    return any(k in msg for k in ("model_not_found", "404", "decommission", "does not exist"))


def ask_groq_sync(messages, search_context=None):
    global ACTIVE_MODEL
    trimmed = [dict(m) for m in ([messages[0]] + messages[1:][-20:])]

    # نتائج البحث بتتضاف للرسالة الأخيرة بس (ومش بتتحفظ في التاريخ)
    if search_context and trimmed[-1]["role"] == "user":
        trimmed[-1]["content"] += (
            "\n\n[نتائج بحث من الإنترنت - اعتمدي عليها وحدها في المعلومات المتغيرة، "
            "ولو مفيهاش الإجابة قولي إنك مش لاقية معلومة مؤكدة]\n" + search_context
        )

    candidates = [ACTIVE_MODEL] + [m for m in MODEL_CANDIDATES if m != ACTIVE_MODEL]
    last_error = None

    for model in candidates:
        try:
            res = groq_client.chat.completions.create(
                messages=trimmed,
                model=model,
                temperature=0.2,
                max_tokens=300,
            )
            text = res.choices[0].message.content or ""
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            if not text:
                continue
            if model != ACTIVE_MODEL:
                print("اتحوّلت للموديل:", model)
                ACTIVE_MODEL = model
            return text
        except Exception as e:
            last_error = e
            if _is_model_missing(e):
                print(f"الموديل {model} مش متاح، بجرّب اللي بعده...")
                continue
            raise
    raise last_error


SEARCH_PLANNER_PROMPT = f"""أنت مصنّف داخلي. اقرأ آخر جملة قالها الشخص في مكالمة تليفون وقرر هل الرد الصحيح محتاج بحث في الإنترنت.
محتاج بحث: أخبار، أسعار، عملات، طقس، رياضة ونتايج، مواعيد، معلومات عن شخص أو شركة أو مكان أو منتج، معنى كلمة أو تعريف، أحداث حديثة، أي حقيقة محددة ممكن تكون اتغيرت.
مش محتاج بحث: تحية، سلام، شكر، دردشة، رأي شخصي، حسابات بسيطة، ترجمة، نصايح عامة، رد على كلام سابق.
نوع البحث (type):
- weather: درجة الحرارة أو الطقس. حط في place اسم المدينة بالإنجليزي (لو مقالتش مدينة اكتب Cairo).
- currency: سعر عملة قصاد عملة. حط في from و to كود العملة (USD, EUR, SAR, EGP...). لو مقالتش العملة التانية اكتب EGP.
- news: أخبار أو أحداث حديثة أو نتايج.
- general: أي حاجة تانية (معلومة، تعريف، معنى كلمة، شخص، مكان، منتج، سعر دهب...).
في query اكتب عبارة بحث كاملة وواضحة بالعربي، وفي query_en نفس العبارة بالإنجليزي.
- الكلام جاي من تفريغ صوتي، فالأسماء ممكن تتهجّى غلط بحرف أو اتنين. لو معاكي نتايج بحث فيها الاسم الصح، اعتمدي عليه وجاوبي مباشرة. اطلبي منها تعيد بس لو الجملة ناقصة فعلاً ومفيش نتايج.
تاريخ النهاردة: {datetime.now().strftime("%Y-%m-%d")}.
رجّع JSON فقط بدون أي كلام تاني:
{{"search": true, "type": "general", "query": "...", "query_en": "...", "place": "", "from": "", "to": ""}}  أو  {{"search": false}}"""


def plan_search_sync(user_text, history):
    """بيقرر هل نبحث، وبيرجّع خطة البحث (dict) أو None."""
    recent = [m for m in history[1:][-4:] if m["role"] in ("user", "assistant")]
    context = "\n".join(f'{m["role"]}: {m["content"]}' for m in recent)
    try:
        res = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": SEARCH_PLANNER_PROMPT},
                {"role": "user", "content": f"آخر المحادثة:\n{context}\n\nآخر جملة: {user_text}"},
            ],
            model=ACTIVE_MODEL,
            temperature=0,
            max_tokens=250,
        )
        raw = res.choices[0].message.content or ""
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            if data.get("search"):
                data.setdefault("type", "general")
                if not str(data.get("query", "")).strip():
                    data["query"] = user_text
                return data
            return None
    except Exception as e:
        print("تعذر قرار البحث:", e)
    # احتياطي: لو المصنّف فشل ولقينا كلمات بتدل على معلومة متغيرة، نبحث بالنص نفسه
    if SEARCH_HINTS.search(user_text):
        return {"search": True, "type": "general", "query": user_text, "query_en": ""}
    return None


# ---------- مصادر البحث ----------
def _get_json(url, params=None, timeout=8):
    r = http_session.get(url, params=params, timeout=timeout, headers={"User-Agent": "SalmaCallBot/1.0"})
    r.raise_for_status()
    return r.json()


WEATHER_CODES = {
    0: "سما صافية", 1: "صافية غالباً", 2: "غيوم متفرقة", 3: "غائم", 45: "شبورة", 48: "شبورة",
    51: "رذاذ خفيف", 53: "رذاذ", 55: "رذاذ كثيف", 61: "مطر خفيف", 63: "مطر", 65: "مطر غزير",
    71: "ثلج خفيف", 73: "ثلج", 75: "ثلج كثيف", 80: "زخات مطر", 81: "زخات مطر", 82: "زخات مطر قوية",
    95: "عاصفة رعدية", 96: "عاصفة رعدية", 99: "عاصفة رعدية",
}


def weather_sync(place):
    """طقس فعلي ودقيق من Open-Meteo (مجاني من غير مفتاح)."""
    place = (place or "").strip() or "Cairo"
    try:
        g = _get_json("https://geocoding-api.open-meteo.com/v1/search",
                      {"name": place, "count": 1, "language": "en"})
        if not g.get("results"):
            return None
        loc = g["results"][0]
        w = _get_json("https://api.open-meteo.com/v1/forecast", {
            "latitude": loc["latitude"], "longitude": loc["longitude"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto", "forecast_days": 2,
        })
        c, d = w["current"], w["daily"]
        desc = WEATHER_CODES.get(c.get("weather_code"), "")
        name = loc.get("name", place)
        return (
            f"- (بيانات طقس فعلية لمدينة {name}) الحرارة دلوقتي {round(c['temperature_2m'])} درجة مئوية"
            f" (المحسوسة {round(c['apparent_temperature'])})، {desc}، الرطوبة {round(c['relative_humidity_2m'])} في المية،"
            f" الرياح {round(c['wind_speed_10m'])} كيلومتر في الساعة. "
            f"النهاردة العظمى {round(d['temperature_2m_max'][0])} والصغرى {round(d['temperature_2m_min'][0])}، "
            f"واحتمال المطر {round(d['precipitation_probability_max'][0] or 0)} في المية. "
            f"بكرة العظمى {round(d['temperature_2m_max'][1])} والصغرى {round(d['temperature_2m_min'][1])}."
        )
    except Exception as e:
        print("تعذر جلب الطقس:", e)
        return None


def currency_sync(frm, to):
    """سعر صرف رسمي مباشر (مجاني من غير مفتاح)."""
    frm = (frm or "").strip().upper()
    to = (to or "").strip().upper() or "EGP"
    if not frm or frm == to:
        return None
    try:
        data = _get_json(f"https://open.er-api.com/v6/latest/{frm}")
        rate = data["rates"][to]
        return (f"- (سعر صرف رسمي مباشر) كل 1 {frm} = {rate:.2f} {to}. "
                f"ده السعر الرسمي العالمي، وممكن يختلف شوية عن سعر البنوك أو السوق في مصر.")
    except Exception as e:
        print("تعذر جلب سعر العملة:", e)
        return None


def wikipedia_sync(query, lang="ar"):
    """ملخص ويكيبيديا للتعاريف والمعلومات الثابتة."""
    if not query:
        return None
    try:
        r = _get_json(f"https://{lang}.wikipedia.org/w/api.php",
                      {"action": "query", "list": "search", "srsearch": query, "srlimit": 1, "format": "json"})
        hits = r.get("query", {}).get("search", [])
        if not hits:
            return None
        title = hits[0]["title"]
        s = _get_json(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
                      + requests.utils.quote(title.replace(" ", "_")))
        extract = (s.get("extract") or "").strip()
        return f"- (ويكيبيديا - {title}): {extract[:500]}" if extract else None
    except Exception as e:
        print("تعذر ويكيبيديا:", e)
        return None


def groq_search_sync(query):
    """بحث ويب مدمج في Groq (compound) بنفس مفتاح Groq. بيرجّع ملخص حقائق قصير أو None لو فشل."""
    for model in GROQ_SEARCH_MODELS:
        try:
            res = groq_client.chat.completions.create(
                model=model,
                temperature=0,
                max_tokens=400,
                messages=[
                    {"role": "system", "content": (
                        "ابحث في الإنترنت وجاوب بحقائق مؤكدة ومختصرة (جملتين أو تلاتة) باللغة العربية. "
                        "اذكر الأرقام والتواريخ والوحدات بدقة زي ما هي في المصادر، واذكر المكان أو الوقت لو مهم. "
                        "لو مالقيتش معلومة مؤكدة قول كده بصراحة ومتخمّنش. بدون روابط وبدون تنسيق.")},
                    {"role": "user", "content": query},
                ],
            )
            text = (res.choices[0].message.content or "").strip()
            if text:
                return f"- (ملخص بحث): {text}"
        except Exception as e:
            print(f"بحث Groq ({model}) فشل:", str(e)[:200])
    return None


def web_search_sync(query, kind="text", max_results=6):
    if DDGS is None:
        print("مكتبة البحث مش متسطبة: pip install ddgs")
        return None
    if not query:
        return None
    try:
        with DDGS() as d:
            if kind == "news":
                results = list(d.news(query, region="wt-wt", max_results=max_results))
            else:
                results = list(d.text(query, region="wt-wt", max_results=max_results))
        lines = []
        for r in results:
            title = (r.get("title") or "").strip()
            body = (r.get("body") or "").strip()
            date = (r.get("date") or "").strip()
            if body:
                lines.append(f"- {title}{' (' + date[:10] + ')' if date else ''}: {body[:400]}")
        return "\n".join(lines) if lines else None
    except Exception as e:
        print("تعذر البحث:", e)
        return None


def gather_context(plan):
    """بيجمّع المعلومات من أكتر من مصدر في نفس الوقت، والبيانات المباشرة ليها الأولوية."""
    t = plan.get("type", "general")
    q = str(plan.get("query", "")).strip()
    qe = str(plan.get("query_en", "")).strip()

    if t == "weather":
        r = weather_sync(plan.get("place"))
        if r:
            return r
    if t == "currency":
        r = currency_sync(plan.get("from"), plan.get("to"))
        if r:
            return r

    kind = "news" if t == "news" else "text"
    ex = ThreadPoolExecutor(max_workers=5)
    futs = [ex.submit(groq_search_sync, q or qe), ex.submit(web_search_sync, q, kind)]
    if qe and qe != q:
        futs.append(ex.submit(web_search_sync, qe, kind))
    if t == "general":
        futs.append(ex.submit(wikipedia_sync, q, "ar"))
        if qe:
            futs.append(ex.submit(wikipedia_sync, qe, "en"))

    parts = []
    for f in futs:
        try:
            r = f.result(timeout=14)
            if r:
                parts.append(r)
        except Exception:
            pass
    ex.shutdown(wait=False)
    return "\n".join(parts)[:3500] if parts else None


def answer_with_search_sync(user_text, history):
    """يقرر + يبحث (لو لزم) + يرد."""
    context = None
    if ENABLE_WEB_SEARCH:
        plan = plan_search_sync(user_text, history)
        if plan:
            print(f"🔎 بحث ({plan.get('type')}): {plan.get('query')}")
            context = gather_context(plan)
            if context:
                print("نتايج البحث:\n" + context)
            else:
                print("مفيش نتايج بحث.")
    return ask_groq_sync(history, search_context=context)


# ---------------- التفريغ ----------------
def save_wav_16k(pcm_data, filename):
    raw = bytes(pcm_data)
    if detected_channels == 2:
        raw = audioop.tomono(raw, 2, 0.5, 0.5)
    if detected_sample_rate != 16000:
        raw, _ = audioop.ratecv(raw, 2, 1, detected_sample_rate, 16000, None)

    # رفع الصوت الواطي (Whisper بيفهم أحسن لما الصوت واضح)
    peak = audioop.max(raw, 2)
    if peak > 0:
        gain = min(8.0, 20000.0 / peak)
        if gain > 1.1:
            raw = audioop.mul(raw, 2, gain)

    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(raw)
    return filename


def _g(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def transcribe_sync(audio_path, last_ai_text=""):
    """بيرجّع (النص، واثق_فيه؟). النص الفاضي = ضوضاء/مفيش كلام."""
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    prompt = "مكالمة تليفون بالعامية المصرية. كلمات إنجليزي متعرّبة زي: ميتينج، تاسك، أوكي، ديدلاين، أبديت، إيميل."
    if last_ai_text:
        prompt += " آخر كلام اتقال: " + last_ai_text[:120]

    last_error = None
    for model in WHISPER_MODELS:
        try:
            result = groq_client.audio.transcriptions.create(
                file=(audio_path, audio_bytes),
                model=model,
                language="ar",
                temperature=0,
                response_format="verbose_json",
                prompt=prompt,
            )
            text = (_g(result, "text", "") or "").strip()
            segs = _g(result, "segments", None) or []
            if not segs:
                return text, True

            speech = [s for s in segs if (_g(s, "no_speech_prob", 0) or 0) < NO_SPEECH_MAX]
            if not speech:
                return "", True  # ضوضاء بس
            text = " ".join((_g(s, "text", "") or "").strip() for s in speech).strip()
            logs = [_g(s, "avg_logprob", 0) or 0 for s in speech]
            avg_lp = sum(logs) / len(logs)
            print(f"ثقة التفريغ: {avg_lp:.2f}")
            return text, avg_lp >= MIN_AVG_LOGPROB
        except Exception as e:
            last_error = e
            if _is_model_missing(e):
                print(f"موديل التفريغ {model} مش متاح، بجرّب اللي بعده...")
                continue
            raise
    raise last_error


def is_hallucination(text):
    low = text.lower().strip(" .!؟?،,")
    if any(h in low for h in HALLUCINATIONS) and len(low) < 40:
        return True
    words = low.split()
    # تكرار نفس الكلمة كتير = هلوسة
    if len(words) >= 6 and len(set(words)) <= 2:
        return True
    return False


async def play_and_wait(call_py, chat_id, audio_file, clean):
    """يشغل الملف ويستنى مدته الفعلية، وبعدين يفضّي الـ pre-roll عشان صدى الـ AI ميدخلش التسجيل."""
    global is_recording
    is_recording = False
    await call_py.play(chat_id, MediaStream(audio_file))
    await asyncio.sleep(audio_duration(audio_file, clean) + 0.35)
    pre_roll_buffer.clear()


def last_ai_text(history):
    for m in reversed(history):
        if m["role"] == "assistant":
            return m["content"].replace("[END_CALL]", "").strip()
    return ""


# ---------------- ملخص المكالمة ----------------
def summarize_call_sync(history):
    """يعمل ملخص مكتوب + نص المكالمة ويحفظهم في call_summary.txt."""
    lines = []
    for m in history[2:]:  # بنتخطى رسالة التعليمات الأولى
        who = "سلمى" if m["role"] == "assistant" else "المتصلة"
        lines.append(f'{who}: {m["content"].replace("[END_CALL]", "").strip()}')
    transcript = "\n".join(lines)

    summary = "تعذر عمل الملخص."
    if transcript:
        try:
            res = groq_client.chat.completions.create(
                model=ACTIVE_MODEL,
                temperature=0.2,
                max_tokens=500,
                messages=[
                    {"role": "system", "content": (
                        "لخّص المكالمة دي بالعربي في نقاط قصيرة: إيه اللي المتصلة طلبته أو سألت عنه، "
                        "وإيه الردود المهمة، وأي حاجة محتاجة متابعة. اعتمد على النص بس ومتضيفش حاجة من عندك.")},
                    {"role": "user", "content": transcript},
                ],
            )
            summary = (res.choices[0].message.content or "").strip() or summary
        except Exception as e:
            print("تعذر عمل الملخص:", e)

    with open("call_summary.txt", "w", encoding="utf-8") as f:
        f.write("ملخص المكالمة\n=============\n" + summary + "\n\nنص المكالمة\n===========\n" + transcript + "\n")

    print("\n===== ملخص المكالمة =====\n" + summary + "\n\n===== نص المكالمة =====\n" + transcript + "\n")
    return summary, transcript


async def send_call_summary(app, history):
    """يعمل الملخص ويبعته على تليجرام (Saved Messages)."""
    try:
        loop = asyncio.get_running_loop()
        summary, _ = await loop.run_in_executor(None, summarize_call_sync, history)
        await app.send_message("me", ("📞 ملخص المكالمة\n\n" + summary)[:4000])
        await app.send_document("me", "call_summary.txt", caption="نص المكالمة كامل")
        print("✅ الملخص اتبعت على تليجرام.")
    except Exception as e:
        print("تعذر إرسال الملخص:", e)


# ---------------- المكالمة ----------------
async def start_smart_call(app, call_py):
    print(f"جاري الاتصال بـ {SISTER_PHONE}...")
    history = [{"role": "system", "content": SMART_AI_PROMPT}]
    loop = asyncio.get_running_loop()

    try:
        user = await app.get_users(SISTER_PHONE)
        chat_id = user.id

        try:
            await call_py.leave_call(chat_id)
        except Exception:
            pass

        history.append({"role": "user", "content":
            f"المكالمة اتفتحت. قولي ألو، وعرّفي نفسك إنك {ASSISTANT_NAME} المساعدة الذكية بتاعة {OWNER_NAME}، "
            f"واسأليها أقدر أساعدك في إيه. متسأليش عن {OWNER_NAME} ومتناديهاش باسم."})
        raw = await loop.run_in_executor(None, ask_groq_sync, history)
        history.append({"role": "assistant", "content": raw})

        welcome_file, clean = await text_to_speech(raw, "welcome.mp3")
        unclear_file, unclear_clean = await text_to_speech(UNCLEAR_PHRASE, "unclear.mp3")
        print(f"الـ AI: {clean}")

        await call_py.play(chat_id, MediaStream(welcome_file))
        print("✅ بدأ الاتصال!")
        await call_py.record(chat_id, RecordStream(True, AudioQuality.HIGH))
        await asyncio.sleep(audio_duration(welcome_file, clean) + 0.35)
        pre_roll_buffer.clear()

        unclear_streak = 0
        silent_streak = 0

        for turn in range(30):
            print("🎤 تفضلي بالكلام...")
            got_audio = await listen_for_turn()
            if not got_audio:
                silent_streak += 1
                print("صمت...")
                if silent_streak >= 6:
                    print("صمت طويل، هقفل المكالمة.")
                    break
                continue
            silent_streak = 0

            t0 = asyncio.get_event_loop().time()
            wav = save_wav_16k(recorded_audio_buffer, f"sister_{turn}.wav")
            text, confident = await loop.run_in_executor(
                None, transcribe_sync, wav, last_ai_text(history)
            )
            print(f"هي قالت: {text}")

            if not text or len(text) < 2 or is_hallucination(text):
                continue

            # لو مش واثقين من السمع، نطلب إعادة بدل ما نرد على كلام غلط
            if not confident and unclear_streak < MAX_UNCLEAR_IN_ROW:
                unclear_streak += 1
                print("⚠️ تفريغ مش مضمون، بطلب إعادة.")
                await play_and_wait(call_py, chat_id, unclear_file, unclear_clean)
                continue
            unclear_streak = 0

            history.append({"role": "user", "content": text})  # النص زي ما هو من غير تعديل
            raw = await loop.run_in_executor(None, answer_with_search_sync, text, history)
            history.append({"role": "assistant", "content": raw})
            should_end = "[END_CALL]" in raw

            reply_file, clean = await text_to_speech(raw, f"reply_{turn}.mp3")
            print(f"⚡ رد في {asyncio.get_event_loop().time() - t0:.1f} ثانية: {clean}")
            await play_and_wait(call_py, chat_id, reply_file, clean)

            if should_end:
                print("تم إنهاء المكالمة بوداع لطيف.")
                break

        await call_py.leave_call(chat_id)
        print("تم إغلاق المكالمة.")

    except Exception as e:
        print(f"حدث خطأ: {e}")

    finally:
        # الملخص بيتبعت في كل الحالات (حتى لو المكالمة اتقفلت فجأة أو حصل خطأ)
        spoke = any(m["role"] == "user" for m in history[2:])
        if spoke:
            await send_call_summary(app, history)
        else:
            try:
                await app.send_message("me", "📞 المكالمة خلصت من غير ما حد يتكلم (أو فشل الاتصال).")
            except Exception as e:
                print("تعذر إرسال الإشعار:", e)


async def main():
    app = Client("my_account", api_id=API_ID, api_hash=API_HASH)
    call_py = PyTgCalls(app)

    @call_py.on_update(fl.stream_frame(Direction.INCOMING))
    async def on_audio_frame(_, update: StreamFrames):
        global recorded_audio_buffer, last_voice_time, has_spoken, voiced_bytes
        global detected_sample_rate, detected_channels, noise_floor
        if hasattr(update, "format") and update.format:
            detected_sample_rate = getattr(update.format, "rate", 48000)
            detected_channels = getattr(update.format, "channels", 2)

        now = asyncio.get_event_loop().time()
        cap = int(bytes_per_second() * PRE_ROLL_SECONDS)

        for frame in update.frames:
            data = frame.frame
            level = calculate_rms(data)
            thr = voice_threshold()

            # تتبّع مستوى الضوضاء الخلفية عشان حد الكلام يتظبط لوحده
            if level <= thr:
                noise_floor = 0.98 * noise_floor + 0.02 * level

            if is_recording:
                recorded_audio_buffer.extend(data)
                if level > thr:
                    voiced_bytes += len(data)
                    last_voice_time = now
                    if voiced_bytes >= bytes_per_second() * MIN_SPEECH_SECONDS:
                        has_spoken = True
            else:
                pre_roll_buffer.extend(data)
                if len(pre_roll_buffer) > cap:
                    del pre_roll_buffer[: len(pre_roll_buffer) - cap]

    await app.start()
    await call_py.start()

    if CALL_TIME:
        target = datetime.strptime(CALL_TIME, "%Y-%m-%d %H:%M:%S")
        wait = (target - datetime.now()).total_seconds()
        if wait > 0:
            print(f"تمت جدولة المكالمة: {CALL_TIME}")
            await asyncio.sleep(wait)

    await start_smart_call(app, call_py)
    await app.stop()

if __name__ == "__main__":
  asyncio.run(main())
