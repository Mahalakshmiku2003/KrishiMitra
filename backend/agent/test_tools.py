# backend/agent/test_tools.py
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.tools import get_weather, get_mandi_price, get_treatment, get_govt_schemes

# Test each tool
print("Testing weather...")
print(get_weather.run("Pune"))
print()

print("Testing prices...")
print(get_mandi_price.run("Tomato"))
print()

print("Testing treatment...")
print(get_treatment.run("early blight"))
print()

print("Testing schemes...")
print(get_govt_schemes.run("Maharashtra"))
