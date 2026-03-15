from ultralytics import YOLO

model = YOLO("best.pt")

results = model.predict("leaf.JPG", conf=0.25, save=True)

print(results)