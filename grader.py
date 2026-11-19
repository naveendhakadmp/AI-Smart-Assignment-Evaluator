import re
from pathlib import Path

def extract_text(path):
    """Extract selectable PDF text; optionally use local Tesseract OCR for scans/photos."""
    suffix = Path(path).suffix.lower()
    try:
        if suffix == ".pdf":
            import pymupdf as fitz
            doc = fitz.open(path)
            text = "\n".join(page.get_text("text") for page in doc).strip()
            if text:
                return text, ""
            try:
                import pytesseract, io
                from PIL import Image
                chunks = []
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    chunks.append(pytesseract.image_to_string(
                        Image.open(io.BytesIO(pix.tobytes("png"))), lang="eng+hin"))
                scanned = "\n".join(chunks).strip()
                if scanned:
                    return scanned, ""
            except Exception:
                pass
            return "", "इस PDF से टेक्स्ट नहीं निकला। यह scanned PDF हो सकती है; OCR सेटअप जाँचें।"
        try:
            import pytesseract
            from PIL import Image
            text = pytesseract.image_to_string(Image.open(path), lang="eng+hin").strip()
            if text:
                return text, ""
        except Exception:
            pass
        return "", "फोटो OCR उपलब्ध नहीं हुआ। Tesseract OCR और भाषा पैक इंस्टॉल करें।"
    except Exception as exc:
        return "", f"फाइल पढ़ने में समस्या: {exc}"

def words(text):
    return re.findall(r"[A-Za-z0-9]+|[\u0900-\u097F]+", (text or "").lower())

def evaluate_answer(answer, topics, total):
    """Free offline heuristic prototype; it is not a trained semantic AI model."""
    tokens = words(answer)
    topic_list = [x.strip() for x in re.split(r"[,;\n]+", topics) if x.strip()]
    if not tokens:
        return {"score": 0.0, "feedback":
            "पढ़ने योग्य टेक्स्ट नहीं मिला। OCR ठीक करें या selectable-text PDF दें।"}
    normalized = " ".join(tokens)
    covered = []
    for topic in topic_list:
        tw = words(topic)
        if tw and (" ".join(tw) in normalized or any(w in tokens for w in tw)):
            covered.append(topic)
    coverage = len(covered) / max(1, len(topic_list))
    length_ratio = min(len(tokens) / max(80, len(topic_list) * 55), 1.0)
    structure = min((answer.count("\n") + 1) / max(2, len(topic_list)), 1.0)
    ratio = 0.68 * coverage + 0.24 * length_ratio + 0.08 * structure
    score = round(max(0, min(total, total * ratio)), 1)
    missing = [t for t in topic_list if t not in covered]
    feedback = (f"शब्द: {len(tokens)} | टॉपिक कवरेज: {len(covered)}/{len(topic_list)}"
        f" | लंबाई संकेतक: {int(length_ratio*100)}%")
    if covered:
        feedback += " | मिले टॉपिक्स: " + ", ".join(covered[:8])
    if missing:
        feedback += " | कम मिले/जाँचें: " + ", ".join(missing[:8])
    feedback += " | यह शुरुआती नियम-आधारित सुझाव है। तथ्य, अर्थ और प्रासंगिकता शिक्षक जाँचें।"
    return {"score": score, "feedback": feedback}
