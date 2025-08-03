import React, { useEffect, useRef, useState } from "react";
import "./App.css";
import "./index.css";
import { UploadDropzone } from "@bytescale/upload-widget-react";
import { Camera, CircleX, Info, CheckCircle, XCircle } from "lucide-react";
import { GridLoader } from "react-spinners";

const options = {
  apiKey: "free",
  editor: {
    images: {
      allowResizeOnMove: false,
      crop: false,
      cropFilePath: Function,
      cropRatio: 1,
      cropShape: "circ",
      preview: false,
    },
  },
  maxFileCount: 1,
  showRemoveButton: false,
  styles: {
    colors: {
      primary: "#000",
    },
  },
};

function App() {
  const docRef = useRef(null);
  const videoRef = useRef();
  const canvasRef = useRef();
  const peerConnectionRef = useRef();
  const dataChannelRef = useRef();
  const ICE_GATHERING_TIMEOUT = 1000;

  const [isStreaming, setIsStreaming] = useState(false);
  const [faceDetected, setFaceDetected] = useState(false);
  const [verificationResult, setVerificationResult] = useState(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const [stream, setStream] = useState(null);
  const [isDocumentUploaded, setIsDocumentUploaded] = useState(false);
  const [error, setError] = useState(null);

  const UploadWidget = () => (
    <UploadDropzone
      options={options}
      onUpdate={({ uploadedFiles }) => {
        docRef.current = uploadedFiles[0];
        console.log("Document file uploaded:", uploadedFiles[0]);
        setIsDocumentUploaded(true);
      }}
      width="100%"
    />
  );

  useEffect(() => {
    return () => {
      if (peerConnectionRef.current) {
        peerConnectionRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    if (faceDetected && stream) {
      stopStreaming();
    }
  }, [faceDetected]);

  useEffect(() => {
    if (isDocumentUploaded) {
      startStreaming();
    }
  }, [isDocumentUploaded]);

  const setupDataChannel = (peerConnection) => {
    const dataChannel = peerConnection.createDataChannel("faceDetection");
    dataChannelRef.current = dataChannel;

    dataChannel.onopen = () => {
      console.log("Data channel is open");
      dataChannel.send("start");
    };

    dataChannel.onmessage = async (event) => {
      if (event.data === "face_detected") {
        console.log("Data channel: Face detected");
        setFaceDetected(true);
        setIsStreaming(false);
      } else {
        console.log("Data channel: Frame with detection received");
        const img = new Image();
        img.onload = () => {
          const canvas = canvasRef.current;
          if (canvas) {
            canvas.width = img.width;
            canvas.height = img.height;
            const ctx = canvas.getContext("2d");
            ctx.drawImage(img, 0, 0);
          }
        };
        img.src = "data:image/jpeg;base64," + event.data;
        console.log("Sending data for identity verification");
        const result = await verifyIdentity();
        console.log(result);
      }
    };

    dataChannel.onclose = () => {
      console.log("Data channel is closed");
    };
  };

  const fetchBlob = async (url) => {
    const response = await fetch(url);
    return response.blob();
  };

  function canvasToBlob(canvas, mimeType = "image/jpeg", quality = 0.95) {
    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob) => {
          if (blob) {
            resolve(blob);
          } else {
            reject(new Error("Canvas to Blob conversion failed"));
          }
        },
        mimeType,
        quality
      );
    });
  }

  const verifyIdentity = async () => {
    setIsVerifying(true);
    const doc = await fetchBlob(docRef.current.fileUrl);
    const face = await canvasToBlob(canvasRef.current);
    console.log("Sending document file:", doc);
    console.log("Sending face image file:", face);
    const formData = new FormData();
    formData.append("id_document", doc, docRef.current.originalFileName);
    formData.append("portrait", face, "portrait.jpg");
    for (const [key, value] of formData) {
      const output = `${key}: ${value}\n`;
      console.log(output);
    }
    const response = await fetch("http://localhost:8000/api/verify-identity/", {
      method: "POST",
      body: formData,
    });
    const result = await response.json();
    setVerificationResult(result);
    setIsVerifying(false);
    return result;
  };

  const startStreaming = async () => {
    try {
      if (peerConnectionRef.current) {
        console.log("Peer connection already exists");
        return;
      }

      setError(null);
      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: false,
      });
      setStream(stream);

      const videoTrack = stream.getVideoTracks()[0];
      const constraints = { frameRate: { ideal: 5, max: 5 } };
      await videoTrack.applyConstraints(constraints);

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }

      const peerConnection = new RTCPeerConnection({
        iceServers: [
          { urls: "stun:stun.l.google.com:19302" },
          // { urls: 'stun:stun1.l.google.com:19302' },
        ],
        iceTransportPolicy: "all",
      });
      peerConnectionRef.current = peerConnection;

      const iceCandidates = [];

      const iceGatheringComplete = new Promise((resolve) => {
        if (peerConnection) {
          peerConnection.onicegatheringstatechange = (event) => {
            console.log(
              "ICE gathering state:",
              peerConnection?.iceGatheringState
            );

            if (peerConnection.iceGatheringState === "complete") {
              console.log("ICE candidates:", iceCandidates);
              resolve();
            }
          };
        }
      });

      setupDataChannel(peerConnection);

      stream.getTracks().forEach((track) => {
        peerConnection.addTrack(track, stream);
      });

      peerConnection.oniceconnectionstatechange = () => {
        console.log("ICE connection state:", peerConnection.iceConnectionState);
      };

      peerConnection.onsignalingstatechange = (event) => {
        console.log("Signaling state:", peerConnection.signalingState);
      };

      peerConnection.onicecandidateerror = (event) => {
        console.error("ICE candidate error:", event);
      };

      peerConnection.onicecandidate = async (event) => {
        const c = event.candidate;
        if (c) {
          try {
            // console.log("ICE candidate:", c)
            iceCandidates.push(c.toJSON());
            await fetch("http://localhost:8080/ice_candidate", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                component: c.component,
                foundation: c.foundation,
                ip: c.address,
                port: c.port,
                priority: c.priority,
                protocol: c.protocol,
                type: c.type,
                relatedAddress: c.relatedAddress,
                relatedPort: c.relatedPort,
                sdpMid: c.sdpMid,
                sdpMLineIndex: c.sdpMLineIndex,
                tcpType: c.tcpType,
              }),
            });
          } catch (error) {
            console.error("Error sending ICE candidate:", error);
          }
        }
      };

      const offer = await peerConnection.createOffer();
      await peerConnection.setLocalDescription(offer);

      const timeoutPromise = new Promise((resolve) => {
        setTimeout(() => {
          console.log("ICE gathering timed out");
          resolve();
        }, ICE_GATHERING_TIMEOUT);
      });

      // Wait for either ICE gathering to complete or timeout
      await Promise.race([iceGatheringComplete, timeoutPromise]);

      // Force ICE gathering to complete if it hasn't already
      if (peerConnection.iceGatheringState !== "complete") {
        peerConnection.onicegatheringstatechange = null;
        console.log("Forcing ICE gathering to complete");
        peerConnection.dispatchEvent(new Event("icegatheringstatechange"));
      }

      const response = await fetch("http://localhost:8080/offer", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          sdp: peerConnection.localDescription.sdp,
          type: peerConnection.localDescription.type,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const answer = await response.json();
      await peerConnection.setRemoteDescription(
        new RTCSessionDescription(answer)
      );

      setIsStreaming(true);
    } catch (error) {
      console.error("Error starting stream:", error);
      setError(`Failed to start streaming: ${error.message}`);
      setIsStreaming(false);
    }
  };

  const stopStreaming = () => {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      setStream(null);
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsStreaming(false);
  };

  const renderVerificationFeedback = () => {
    if (!verificationResult) return null;

    const { verification, person, document } = verificationResult;

    if (verification.legit) {
      return (
        <div className="mt-6 p-4 bg-green-100 rounded-lg">
          <div className="flex items-center space-x-2 text-green-700 mb-2">
            <CheckCircle size={24} />
            <p className="text-lg font-medium">Passed</p>
          </div>
          <p>Timestamp: {verification.timestamp}</p>
          {person.first_name !== "N/A" && (
            <p>
              Name: {person.first_name} {person.last_name}
            </p>
          )}
          {person.gender !== "N/A" && <p>Gender: {person.gender}</p>}
          {document.expiration_date !== "N/A" && (
            <p>Document Expiration: {document.expiration_date}</p>
          )}
        </div>
      );
    } else {
      return (
        <div className="mt-6 p-4 bg-red-100 rounded-lg">
          <div className="flex items-center space-x-2 text-red-700">
            <XCircle size={24} />
            <p className="text-lg font-medium">Rejected</p>
          </div>
          <p>{verification.message}</p>
        </div>
      );
    }
  };

  return (
    <div className="min-h-screen bg-gray-200 flex flex-col items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl p-10 w-full max-w-screen-lg">
        <h1 className="text-2xl font-thin text-gray-500 mb-6">
          Identity Verifier
        </h1>

        <div className="mb-6 relative">
          {!faceDetected && (
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`w-full h-full object-cover rounded-lg ${
                isStreaming ? "block" : "hidden"
              }`}
            />
          )}
          <div className="relative">
            <canvas
              ref={canvasRef}
              className={`w-full h-full object-cover rounded-lg ${
                faceDetected && isVerifying ? "block" : "hidden"
              }`}
            />
            {isVerifying && (
              <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-50 rounded-lg">
                <GridLoader color="#ffffff" margin={5} size={15} />
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          {!isDocumentUploaded ? (
            <UploadWidget />
          ) : isStreaming && !faceDetected ? (
            <div className="flex items-center justify-center space-x-2 text-black-600">
              <Camera size={24} />
              <p className="text-lg font-medium">Look into the camera</p>
            </div>
          ) : isVerifying ? (
            <div className="flex items-center justify-center space-x-2 text-black-600">
              <Info size={24} />
              <p className="text-lg font-medium">Verifying your identity</p>
            </div>
          ) : null}
        </div>

        {renderVerificationFeedback()}

        {error && (
          <div className="flex items-center justify-center space-x-2 text-red-600">
            <CircleX size={24} />
            <p className="text-lg font-medium">{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
