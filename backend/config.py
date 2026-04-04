from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL     = os.getenv("REDIS_URL")
MODEL_PATH    = os.getenv("MODEL_PATH", "weights/best.pt")
UPLOAD_DIR    = "uploads"

# ONNX Models for Specialized Diagnosis
STITCH_DIR = r"c:\Users\Lohitha\krishimitra\KrishiMitra\stitch"
CLASSIFIER_PATH = os.path.join(STITCH_DIR, "classifier.onnx")
DETECTOR_PATH   = os.path.join(STITCH_DIR, "detector.onnx")