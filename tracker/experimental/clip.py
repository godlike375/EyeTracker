from transformers import CLIPSegProcessor, CLIPSegForImageSegmentation
import cv2
import numpy as np

processor = CLIPSegProcessor.from_pretrained("CIDAS/clipseg-rd64-refined")
model = CLIPSegForImageSegmentation.from_pretrained("CIDAS/clipseg-rd64-refined")

from PIL import Image
import requests

url = "https://media.istockphoto.com/id/93214254/ru/%D1%84%D0%BE%D1%82%D0%BE/vervet-%D0%BE%D0%B1%D0%B5%D0%B7%D1%8C%D1%8F%D0%BD%D0%B0-chlorocebus-pygerythrus.jpg?s=612x612&w=0&k=20&c=hYa92X1D2fHvwWH5aP1c8qMuGWBCKqp66PhM9huGqz8="
image = Image.open(requests.get(url, stream=True).raw)

prompts = ["pupil"]

import torch

inputs = processor(text=prompts, images=[image] * len(prompts), padding="max_length", return_tensors="pt")
# predict

with torch.no_grad():
  outputs = model(**inputs)
preds = outputs.logits.unsqueeze(1)

# Получаем метки классов
colored_preds = torch.sigmoid(preds[0][0]).cpu().numpy()
mx = colored_preds.max()
colored_preds = (colored_preds > mx - mx*0.3).astype(float)
colored_preds = cv2.resize(colored_preds, (image.width, image.height))



# Объединяем метки классов с оригинальным изображением
colored_image = np.array(image)
colored_image = cv2.cvtColor(colored_image, cv2.COLOR_RGB2BGR)
colored_image[:,:,0] = colored_image[:,:,0] * (1 - colored_preds)
colored_image[:,:,1] = colored_image[:,:,1] * (1 - colored_preds)
colored_image[:,:,2] = colored_image[:,:,2] * (1 - colored_preds) + colored_preds * 255



while cv2.waitKey(1) != ord('q'):
  cv2.imshow('Predicted', colored_image)


