import asyncio
import base64
import logging
import json

import cv2
from aiohttp import web
from aiohttp_cors import ResourceOptions
from aiohttp_cors import setup as cors_setup
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription, RTCIceCandidate, RTCConfiguration, RTCIceServer
from av import VideoFrame

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PortraitCapturer")

pcs = set()


class FaceDetectorTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self, track):
        super().__init__()
        self.track = track
        self.data_channel = None
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.eye_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_eye.xml"
        )
        self.mouth_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_smile.xml"
        )
        self.frame_count = 0
        self.detecting = asyncio.Event()

    def set_data_channel(self, data_channel):
        self.data_channel = data_channel
        logger.info("Data channel set for FaceDetectorTrack")

    def _is_entire_face_visible(self, img):
        # Convert the frame to grayscale and apply histogram equalization for better detection
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        # Detect faces in the frame
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        if len(faces) == 0:
            logger.info("No faces found")
            return False

        if len(faces) > 1:
            logger.warning(f"More than one face found: {len(faces)}")
            return False
        logger.info("Face: OK")

        face = faces[0]
        x, y, w, h = face

        # Define the region of interest for the face
        face_roi = gray[y : y + h, x : x + w]

        # Detect eyes within the face region
        eyes = self.eye_cascade.detectMultiScale(face_roi, scaleFactor=1.1, minNeighbors=10, minSize=(15, 15), flags=cv2.CASCADE_SCALE_IMAGE)
        # Allow multiple detected eyes
        if len(eyes) < 1:
            logger.warning(f"No eyes found")
            return False
        logger.info("Eyes: OK")

        # Detect mouth within the face region (we adjust mouth region because it's typically lower on the face)
        # mouth_roi = face_roi[h//2:, :]
        mouth = self.mouth_cascade.detectMultiScale(face_roi, scaleFactor=1.1, minNeighbors=10, minSize=(15, 15), flags=cv2.CASCADE_SCALE_IMAGE)
        # Allow multiple detected mouths
        if len(mouth) < 1:
            logger.warning(f"No mouth found")
            return False
        logger.info("Mouth: OK")

        # TODO integrate visualization with front-end
        # Draw a rectangle around the face
        # cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 0), 2)
        # Draw rectangles around eyes and mouth
        # roi_color = img[y:y + h, x:x + w]
        # for (ex, ey, ew, eh) in eyes:
        #     cv2.rectangle(roi_color, (ex, ey), (ex + ew, ey + eh), (0, 255, 0), 2)
        # for (mx, my, mw, mh) in mouth:
        # Ensure the mouth is detected lower on the face to avoid false positives around the nose
        # if my > h // 2:
        #     cv2.rectangle(roi_color, (mx, my), (mx + mw, my + mh), (0, 0, 255), 2)

        return True

    async def recv(self):
        if not self.detecting.is_set():
            return await self.track.recv()

        self.frame_count += 1
        frame = await self.track.recv()
        img = frame.to_ndarray(format="bgr24")

        # logger.info(f"Searching for faces in frame {self.frame_count}")

        if self._is_entire_face_visible(img):
            logger.info(f"Full face detected in frame {self.frame_count}")

            _, buffer = cv2.imencode(".jpg", img)
            jpg_as_text = base64.b64encode(buffer).decode("utf-8")

            if self.data_channel and self.data_channel.readyState == "open":
                try:
                    self.data_channel.send("face_detected")
                    self.data_channel.send(jpg_as_text)
                    logger.info("Face detection message and image sent successfully")
                    self.detecting.clear()
                except Exception as e:
                    logger.error(
                        f"Failed to send face detection message or image: {str(e)}"
                    )
            else:
                logger.warning(
                    "Data channel not ready, skipping face detection message and image send"
                )

        new_frame = VideoFrame.from_ndarray(img, format="bgr24")
        new_frame.pts = frame.pts
        new_frame.time_base = frame.time_base
        return new_frame


async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection(configuration=RTCConfiguration([
            RTCIceServer("stun:stun.l.google.com:19302"),
            # RTCIceServer("stun:stun1.l.google.com:19302"),
        ])
    )
    face_detector_track = None

    @pc.on("datachannel")
    def on_datachannel(channel):
        logger.info(f"Data channel '{channel.label}' created by remote party")

        if face_detector_track:
            face_detector_track.set_data_channel(channel)

        @channel.on("message")
        def on_message(message):
            if message == "start":
                logger.info("Received start signal, beginning face detection")
                if face_detector_track:
                    face_detector_track.detecting.set()
            elif message == "stop":
                logger.info("Received stop signal, stopping face detection")
                if face_detector_track:
                    face_detector_track.detecting.clear()

    @pc.on("track")
    def on_track(track):
        logger.info(f"Track received: {track.kind}")
        if track.kind == "video":
            nonlocal face_detector_track
            face_detector_track = FaceDetectorTrack(track)
            pc.addTrack(face_detector_track)

    @pc.on("signalingstatechange")
    async def on_signalingstatechange():
        print('Signaling state change:', pc.signalingState)
        if pc.signalingState == 'stable':
            print('ICE gathering complete')
            # Log all gathered candidates
            # for candidate in ice_candidates:
            #     print('Gathered candidate:', candidate)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info(f"Connection state is: {pc.connectionState}")
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        logger.info(f"ICE connection state is {pc.iceConnectionState}")
        if pc.iceConnectionState == "failed":
            logger.error("ICE connection failed")
            await pc.close()
            pcs.discard(pc)

    @pc.on('icegatheringstatechange')
    async def on_icegatheringstatechange():
        print('ICE gathering state changed to', pc.iceGatheringState)
        if pc.iceGatheringState == 'complete':
            print('All ICE candidates have been gathered.')
            # Log all gathered candidates
            # for candidate in self.ice_candidates:
            #     print('Gathered candidate:', candidate)

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    pcs.add(pc)

    return web.json_response(
        {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    )


async def handle_ice_candidate(request):
    params = await request.json()
    print("params:", params)
    candidate = RTCIceCandidate(
        component=params.get("component"),
        foundation=params.get("foundation"),
        ip=params.get("ip"),
        port=params.get("port"),
        priority=params.get("priority"),
        protocol=params.get("protocol"),
        type=params.get("type"),
        relatedAddress=params.get("relatedAddress"),
        relatedPort=params.get("relatedPort"),
        sdpMid=params.get("sdpMid"),
        sdpMLineIndex=params.get("sdpMLineIndex"),
        tcpType=params.get("tcpType"),
    )
    print("candidate:", candidate)
    for pc in pcs:
        await pc.addIceCandidate(candidate)
    return web.Response(status=204)


async def on_shutdown(app):
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


async def app():
    app = web.Application()
    app.on_shutdown.append(on_shutdown)

    cors = cors_setup(
        app,
        defaults={
            "*": ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
        },
    )

    app.router.add_post("/offer", offer)
    app.router.add_post("/ice_candidate", handle_ice_candidate)

    for route in list(app.router.routes()):
        cors.add(route)

    logger.info("Starting server")

    return app
