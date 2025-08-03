from datetime import datetime
import logging
from typing import Optional, Tuple

import cv2
import easyocr
import face_recognition
import numpy as np
from PIL import Image
import re
from django.apps import apps
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Verification


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("IdentityVerifier")


class IDExtraction:
    def __init__(self):
        self.first_name = "N/A"
        self.last_name = "N/A"
        self.gender = "N/A"
        self.expiration_date = "N/A"


def build_negative_response(message) -> Response:
    """
    Build a response where the identity verification process is considered as rejected.
    """
    now = datetime.now()
    timestamp_str = now.strftime("%d-%m-%Y %H:%M:%S")
    try:
        Verification(
            timestamp=now,
            passed=False,
            message=message
        ).save()
    except Exception as e:
        logger.warning(f"Failed to write verification info to database: {str(e)}")
    return Response(
        {
            "verification": {
                "timestamp": timestamp_str,
                "legit": False,
                "message": message,
            },
        },
        status=status.HTTP_200_OK,
    )


def build_positive_response(extraction: IDExtraction) -> Response:
    """
    Build a response where the identity verification process is considered as passing.
    """
    now = datetime.now()
    timestamp_str = now.strftime("%d-%m-%Y %H:%M:%S")
    try:
        Verification(
            timestamp=now,
            passed=True,
            first_name=extraction.first_name,
            last_name=extraction.last_name,
            gender=extraction.gender,
            document_expiration_date=extraction.expiration_date
        ).save()
    except Exception as e:
        logger.warning(f"Failed to write verification info to database: {str(e)}")
    return Response(
        {
            "verification": {
                "timestamp": timestamp_str,
                "legit": True,
            },
            "person": {
                "first_name": extraction.first_name,
                "last_name": extraction.last_name,
                "gender": extraction.gender,
            },
            "document": {"expiration_date": extraction.expiration_date},
        },
        status=status.HTTP_200_OK,
    )


def valid_request_parameters(id_doc_obj, portrait_obj) -> bool:
    logger.info(f"Valid request parameters: [{id_doc_obj}] [{portrait_obj}]")
    if not id_doc_obj or not portrait_obj:
        return False
    return True


def is_date_in_past(date_str):
    # Convert the string to a datetime object
    date_format = "%d.%m.%Y"  # Expected format: "DD.MM.YYYY"
    input_date = datetime.strptime(date_str, date_format)
    return input_date < datetime.now()


class IdentityVerifier(APIView):
    parser_classes = (
        MultiPartParser,
        FormParser,
    )   

    def post(self, request, *args, **kwargs):
        logger.info(f"Request data: [{request.data}]")
        logger.info(f"Request query parameters: [{request.query_params}]")
        id_doc_obj = request.FILES.get("id_document")
        portrait_obj = request.FILES.get("portrait")

        if not valid_request_parameters(id_doc_obj, portrait_obj):
            return Response(
                {"error": "Invalid request parameters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            is_id_document, is_valid, data = self.parse_id_document(id_doc_obj)
            if not is_id_document:
                return build_negative_response("The uploaded file is not an ID document")
            if not is_valid and data.expiration_date != "N/A":
                return build_negative_response("Expired ID document")
            if not is_valid:
                return build_negative_response("Invalid ID document")
            id_doc_np = face_recognition.load_image_file(id_doc_obj)

            doc_faces = face_recognition.face_encodings(id_doc_np)
            if len(doc_faces) == 0:
                return build_negative_response("Try uploading a clearer photo of your ID document")
            id_doc_encoding = doc_faces[0]
            
            portrait_np = face_recognition.load_image_file(portrait_obj)
            portrait_faces = face_recognition.face_encodings(portrait_np)
            # Validate portrait
            if len(portrait_faces) == 0:
                return build_negative_response("Try taking another portrait in better light")
            if len(portrait_faces) > 1:
                return build_negative_response("There is more than one person in the portrait")
            portrait_encoding = portrait_faces[0]

            if not face_recognition.compare_faces([portrait_encoding], id_doc_encoding)[
                0
            ]:
                return build_negative_response("Faces do not match")

            return build_positive_response(data)

        except Exception as e:
            logger.error(f"Error: {e}")
            return Response(
                {"error": "Server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def parse_id_document(self, image_file) -> Tuple[bool, Optional[bool], Optional[IDExtraction]]:
        """
        Parses the text of an image of an ID document.
        
        Returns: <is_id_document>, <is_valid>, <extraction_data>
        """
        img = cv2.imdecode(np.fromstring(image_file.read(), np.uint8), cv2.IMREAD_UNCHANGED)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        results = apps.get_app_config("identity_verifier_app").get_reader().readtext(blurred)
        text = " ".join([result[1] for result in results])
        text_lowered = text.lower()

        keywords = [
            "identity",
            "identitate",
            "carte",
            "name",
            "seria",
            "nr",
            "last name",
            "first name",
            "nationality",
            "cetatenie",
            "validity",
            "sex",
        ]
        cnt_found = 0
        for kw in keywords:
            if kw in text_lowered:
                cnt_found += 1
                logger.info(f"Keyword found in document: {kw}")
        ratio = cnt_found / len(keywords)
        if ratio < 0.1:
            return (False, None, None)

        extraction_data = IDExtraction()
        date = re.search(r"\d{2}\.\d{2}\.\d{2,4}-(\d{2}\.\d{2}\.\d{4})", text)
        if date:
            date = date.group(1)
            logger.info(f"Document expiry date: {date}")
            extraction_data.expiration_date = date

        names = re.search(r"idrou(\w+)<+(\w+)<+", text, re.IGNORECASE)
        if names:
            last_name = names.group(1)
            first_name = names.group(2)
            logger.info(f"Name: {first_name.upper()} {last_name.upper()}")
            extraction_data.last_name = last_name.upper()
            extraction_data.first_name = first_name.upper()

        gender = re.search(r"\s+([m|f])\s+", text, re.IGNORECASE)
        if gender:
            letter = gender.group(1)
            if letter.lower() == "m":
                gender = "MALE"
            elif letter.lower() == "f":
                gender = "FEMALE"
            logger.info(f"Gender: {gender}")
            extraction_data.gender = gender

        if extraction_data.expiration_date != "N/A" and is_date_in_past(extraction_data.expiration_date):
            return (True, False, extraction_data)
        return (True, True, extraction_data)