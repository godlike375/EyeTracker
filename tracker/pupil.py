import cv2
cap = cv2.VideoCapture(1)
while True:
    # Захват кадра
    ret, image = cap.read()

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(blurred, 40, 255, cv2.THRESH_BINARY)

    min_area = 1
    min_circularity = 0.1
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    #contours = [c for c in contours if cv2.contourArea(c) > min_area and cv2.isContourConvex(c) and (cv2.contourArea(c) / (cv2.arcLength(c, True) * 2)) > min_circularity]
    if contours:
        max_contour = max(contours, key=cv2.contourArea)
        center = cv2.moments(max_contour)["m10"] / cv2.moments(max_contour)["m00"], cv2.moments(max_contour)["m01"] / cv2.moments(max_contour)["m00"]
        (x,y), radius = cv2.minEnclosingCircle(max_contour)
        radius = int(radius)
        cv2.circle(image, (int(center[0]), int(center[1])), radius, (0, 255, 0), 2)

    cv2.imshow("Detected Pupil", thresh)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Освобождение ресурсов
cap.release()
cv2.destroyAllWindows()