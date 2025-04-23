import io

from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder, Quality
from picamera2.outputs import FileOutput

from fastapi import FastAPI
from fastapi import Request
from starlette.background import BackgroundTask
from fastapi.responses import Response
from fastapi.responses import StreamingResponse
from threading import Condition
import logging
from ultralytics import YOLO
import cv2
import numpy as np

app = FastAPI()


@app.get("/image")
def get_image():
    picam2 = Picamera2()
    capture_config = picam2.create_still_configuration(main={"size": (1920, 1080)})
    picam2.configure(capture_config)
    data = io.BytesIO()
    picam2.start()
    picam2.capture_file(data, format="jpeg")
    picam2.stop()
    picam2.close()
    return Response(content=data.getvalue(), media_type="image/jpeg")


class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()

    def read(self):
        with self.condition:
            self.condition.wait()
            return self.frame


async def generate_frames(output, request):
    model = YOLO("yolov8n_ncnn_model")
    while True:
        try:

            if await request.is_disconnected():
                print("Client disconnected, stopping frame generation.")
                break

            jpeg_data = output.read()

            # Convert JPEG data to OpenCV format
            np_arr = np.frombuffer(jpeg_data, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            # # Perform object detection
            results = model(img)
            annotated_frame = results[0].plot()
                
            # Encode image back to JPEG
            _, annotated_frame_jpeg = cv2.imencode('.jpg', annotated_frame)

            yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + annotated_frame_jpeg.tobytes() + b"\r\n")
        except Exception as e:
            logging.error(f"Error in generate_frames: {str(e)}")
            break

    print("done")


@app.get("/mjpeg")
async def mjpeg(request: Request):
    picam2 = Picamera2()
    video_config = picam2.create_video_configuration(main={"size": (1920, 1080)})
    picam2.configure(video_config)
    output = StreamingOutput()
    picam2.start_recording(MJPEGEncoder(), FileOutput(output), Quality.VERY_HIGH)
    def stop():
        print("Stopping recording")
        picam2.stop_recording()
        picam2.close()
    return StreamingResponse(
        generate_frames(output, request),
        media_type="multipart/x-mixed-replace; boundary=frame",
        background=BackgroundTask(stop),
    )