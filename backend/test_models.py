import os
import sys
import json

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent.diagnose import diagnose_image
from config import CLASSIFIER_PATH, DETECTOR_PATH

def verify_diagnosis():
    # Use any image from the project or a dummy path just to test model loading
    # We'll check if it fails with 'Model not found' or actually tries to run
    print(f"Testing with Classifier: {CLASSIFIER_PATH}")
    print(f"Testing with Detector: {DETECTOR_PATH}")
    
    # Check file existence
    if not os.path.exists(CLASSIFIER_PATH):
        print(f"FAIL: Classifier not found at {CLASSIFIER_PATH}")
        return
    if not os.path.exists(DETECTOR_PATH):
        print(f"FAIL: Detector not found at {DETECTOR_PATH}")
        return
    
    print("SUCCESS: Models located.")
    
    # We can't easily run a real image diagnosis without an actual image, 
    # but the fact that the server started (and loaded the models in the print logs) is a good sign.
    # The models are loaded at the module level in diagnose.py or inside diagnose_image.
    
if __name__ == "__main__":
    verify_diagnosis()
