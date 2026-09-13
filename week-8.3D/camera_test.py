import cv2

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    raise RuntimeError("Camera could not be opened")

success, frame = camera.read()
camera.release()

if not success:
    raise RuntimeError("Photo could not be captured")

cv2.imwrite("camera_test.jpg", frame)
print("Camera works. Saved camera_test.jpg")
